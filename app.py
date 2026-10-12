"""Predicción mensual de residuos sólidos domiciliarios en Bogotá.

Ejecutar con: streamlit run app.py
"""

import io
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, root_mean_squared_error

DATOS_OFICIALES = Path(__file__).parent / "data" / "residuos_domiciliarios_ase.csv"
COLUMNAS = ["fecha", "zona", "toneladas"]
HORIZONTE_MAX = 12  # meses hacia adelante que se pueden predecir
MESES_PRUEBA = 12  # últimos meses reservados para evaluar
VARIABLES = ["horizonte", "mes", "ultimo_rel", "anio_anterior_rel"]
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

# Alcaldía de Bogotá, 7 de febrero de 2026:
# https://bogota.gov.co/mi-ciudad/habitat/como-esta-dividido-el-esquema-de-aseo-en-las-localidades-de-bogota
LOCALIDADES_POR_ASE = {
    "ASE 1": "Usaquén, Chapinero, Santa Fe, San Cristóbal, Usme, La Candelaria y Sumapaz (Promoambiental Distrito)",
    "ASE 2": "Tunjuelito, Teusaquillo, Bosa, Los Mártires, Antonio Nariño, Puente Aranda, Rafael Uribe Uribe "
    "y Ciudad Bolívar (LIME)",
    "ASE 3": "Kennedy y Fontibón (Ciudad Limpia)",
    "ASE 4": "Engativá y Barrios Unidos (Bogotá Limpia)",
    "ASE 5": "Suba (Área Limpia)",
}

FORMATO_CSV = """
**Columnas requeridas**
- `fecha`: mes en formato AAAA-MM (p. ej. `2024-01`)
- `zona`: localidad o zona (también se acepta `localidad`)
- `toneladas`: toneladas recolectadas en el mes (número ≥ 0)

Separador `,` con punto decimal, o `;` con coma decimal.
Un único total por zona y mes.
"""


def formato_mes(periodo):
    return f"{MESES[periodo.month - 1]} {periodo.year}"


def formato_toneladas(valor):
    return f"{valor:,.0f} t".replace(",", ".")


def formato_meses(n):
    return f"{n} {'mes' if n == 1 else 'meses'}"


def leer_csv(contenido):
    """Lee un CSV en UTF-8 o Latin-1, separado por ',' (punto decimal) o ';' (coma decimal)."""
    try:
        texto = contenido.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = contenido.decode("latin-1")
    encabezado = texto.lstrip().split("\n", 1)[0]
    opciones = {"sep": ";", "decimal": ","} if encabezado.count(";") > encabezado.count(",") else {}
    try:
        return pd.read_csv(io.StringIO(texto), **opciones)
    except pd.errors.EmptyDataError:
        raise ValueError("el archivo está vacío.") from None
    except pd.errors.ParserError as error:
        raise ValueError(f"el archivo no tiene un formato CSV válido ({error}).") from None


def validar(crudo):
    """Devuelve (datos limpios, avisos). Lanza ValueError si los datos no se pueden usar."""
    crudo = crudo.rename(columns=lambda c: str(c).strip().lower())
    if "zona" not in crudo.columns and "localidad" in crudo.columns:
        crudo = crudo.rename(columns={"localidad": "zona"})
    faltantes = [c for c in COLUMNAS if c not in crudo.columns]
    if faltantes:
        raise ValueError(
            f"faltan las columnas {', '.join(faltantes)}. Columnas encontradas: {', '.join(crudo.columns)}."
        )

    fechas = crudo["fecha"].astype(str).str.strip().str[:7]
    datos = pd.DataFrame({
        "fecha": pd.to_datetime(fechas, format="%Y-%m", errors="coerce").dt.to_period("M"),
        "zona": crudo["zona"].fillna("").astype(str).str.strip(),
        "toneladas": pd.to_numeric(crudo["toneladas"], errors="coerce"),
    })

    avisos = []
    invalidas = datos["fecha"].isna() | (datos["zona"] == "") | datos["toneladas"].isna() | (datos["toneladas"] < 0)
    if invalidas.all():
        raise ValueError("ninguna fila tiene una fecha (AAAA-MM), una zona y unas toneladas válidas.")
    if invalidas.any():
        lineas = ", ".join(str(i + 2) for i in datos.index[invalidas][:5])
        avisos.append(
            f"Se descartaron {invalidas.sum()} filas con fecha, zona o toneladas inválidas "
            f"(líneas del archivo: {lineas}{', …' if invalidas.sum() > 5 else ''})."
        )
        datos = datos[~invalidas]

    repetidas = datos.duplicated(["fecha", "zona"], keep=False)
    if repetidas.any():
        ejemplo = datos[repetidas].iloc[0]
        raise ValueError(
            f"hay {repetidas.sum()} filas con la misma zona y mes (p. ej. {ejemplo['zona']}, "
            f"{formato_mes(ejemplo['fecha'])}). Debe haber un único total mensual por zona."
        )

    for zona, grupo in datos.groupby("zona"):
        esperados = (grupo["fecha"].max() - grupo["fecha"].min()).n + 1
        if len(grupo) < esperados:
            avisos.append(
                f"{zona}: faltan {formato_meses(esperados - len(grupo))} entre {formato_mes(grupo['fecha'].min())} y "
                f"{formato_mes(grupo['fecha'].max())}. Las predicciones que dependen de esos meses se omiten."
            )
    return datos.sort_values(["zona", "fecha"]).reset_index(drop=True), avisos


def construir_filas(datos):
    """Una fila por (zona, mes objetivo, horizonte) con variables conocidas en el mes de origen.

    Para predecir el mes t con h meses de anticipación, el último mes conocido es t - h.
    Variables: h, mes del año de t, toneladas de t - h y de t - 12 (conocido porque h <= 12),
    ambas divididas por el promedio de los 12 meses que terminan en t - h. Nunca se usa el valor de t.
    """
    partes = []
    for zona, grupo in datos.groupby("zona"):
        serie = grupo.set_index("fecha")["toneladas"]
        indice = pd.period_range(serie.index.min(), serie.index.max() + HORIZONTE_MAX, freq="M")
        serie = serie.reindex(indice)  # meses faltantes y futuros quedan en NaN
        media12 = serie.rolling(12).mean()
        for h in range(1, HORIZONTE_MAX + 1):
            partes.append(pd.DataFrame({
                "zona": zona,
                "fecha": indice,
                "origen": indice - h,
                "horizonte": h,
                "mes": indice.month,
                "ultimo": serie.shift(h).to_numpy(),
                "media12": media12.shift(h).to_numpy(),
                "anio_anterior": serie.shift(12).to_numpy(),
                "toneladas": serie.to_numpy(),
            }))
    filas = pd.concat(partes, ignore_index=True).dropna(subset=["ultimo", "media12", "anio_anterior"])
    filas["ultimo_rel"] = filas["ultimo"] / filas["media12"]
    filas["anio_anterior_rel"] = filas["anio_anterior"] / filas["media12"]
    return filas


def nuevo_modelo():
    return RandomForestRegressor(n_estimators=300, min_samples_leaf=3, random_state=0, n_jobs=-1)


@st.cache_data(show_spinner="Entrenando el modelo…")
def entrenar_y_evaluar(datos):
    """Evalúa en los últimos MESES_PRUEBA meses con un modelo entrenado solo con meses anteriores;
    luego reentrena con toda la historia para predecir los meses futuros."""
    filas = construir_filas(datos)
    historicas = filas.dropna(subset=["toneladas"])
    inicio_prueba = datos["fecha"].max() - (MESES_PRUEBA - 1)
    entrenamiento = historicas[historicas["fecha"] < inicio_prueba]
    prueba = historicas[historicas["fecha"] >= inicio_prueba].copy()

    horizontes = set(range(1, HORIZONTE_MAX + 1))
    if not horizontes <= set(entrenamiento["horizonte"]) or not horizontes <= set(prueba["horizonte"]):
        raise ValueError(
            "Datos insuficientes para entrenar y evaluar el modelo. Se necesitan al menos 36 meses seguidos "
            "en alguna zona: 12 de historial para calcular las variables, 12 para entrenar todos los "
            "horizontes de predicción y 12 para la prueba."
        )

    # El modelo predice la proporción respecto al promedio de 12 meses, para compartir patrones entre zonas.
    modelo = nuevo_modelo().fit(entrenamiento[VARIABLES], entrenamiento["toneladas"] / entrenamiento["media12"])
    prueba["modelo"] = modelo.predict(prueba[VARIABLES]) * prueba["media12"]
    prueba["referencia"] = prueba["anio_anterior"]

    final = nuevo_modelo().fit(historicas[VARIABLES], historicas["toneladas"] / historicas["media12"])
    ultimo_mes = datos.groupby("zona")["fecha"].max()
    futuro = filas[filas["toneladas"].isna() & (filas["origen"] == filas["zona"].map(ultimo_mes))].copy()
    if not futuro.empty:
        futuro["modelo"] = final.predict(futuro[VARIABLES]) * futuro["media12"]
        futuro["referencia"] = futuro["anio_anterior"]
    return prueba, futuro, inicio_prueba, len(entrenamiento)


def tabla_metricas(prueba):
    metodos = [("Random Forest", "modelo"), ("Referencia: mismo mes del año anterior", "referencia")]
    return pd.DataFrame([
        {
            "Método": nombre,
            "MAE (t)": mean_absolute_error(prueba["toneladas"], prueba[columna]),
            "RMSE (t)": root_mean_squared_error(prueba["toneladas"], prueba[columna]),
        }
        for nombre, columna in metodos
    ])


def mae_por_horizonte(prueba):
    errores = pd.DataFrame({
        "horizonte": prueba["horizonte"],
        "Random Forest": (prueba["modelo"] - prueba["toneladas"]).abs(),
        "Referencia": (prueba["referencia"] - prueba["toneladas"]).abs(),
    })
    return errores.groupby("horizonte").mean()


# ---------------------------------------------------------------- Interfaz

st.set_page_config(page_title="Residuos Bogotá", page_icon="♻️", layout="wide")
st.title("Predicción mensual de residuos domiciliarios en Bogotá")

with st.sidebar:
    st.header("Fuente de datos")
    fuente = st.radio("Conjunto de datos", ["Oficial UAESP (incluido)", "Cargar CSV propio"])
    archivo = None
    if fuente == "Cargar CSV propio":
        archivo = st.file_uploader("Archivo CSV", type=["csv"])
        st.markdown(FORMATO_CSV)
oficial = fuente == "Oficial UAESP (incluido)"

# 1. Carga y validación
st.header("1. Datos")
try:
    if oficial:
        crudo = pd.read_csv(DATOS_OFICIALES)
    elif archivo is None:
        st.info("Cargue un archivo CSV en la barra lateral.")
        st.stop()
    else:
        crudo = leer_csv(archivo.getvalue())
    datos, avisos = validar(crudo)
except FileNotFoundError:
    st.error(f"No se encontró {DATOS_OFICIALES}. Genérelo con: python preparar_datos.py")
    st.stop()
except ValueError as error:  # incluye CSV vacío o mal formado
    st.error(f"No se pudieron usar los datos: {error}")
    st.stop()

if oficial:
    st.info(
        "Fuente: UAESP, Datos Abiertos Bogotá, «Residuos dispuestos de recolección por ASEs en PIDJ» (CC0 1.0). "
        "Variable: recolección domiciliaria (t/mes). Los datos públicos están desagregados por "
        "**Área de Servicio Exclusivo (ASE)**, no por localidad: cada ASE agrupa una o varias localidades."
    )
    with st.expander("Localidades de cada ASE"):
        st.table(pd.DataFrame(LOCALIDADES_POR_ASE.items(), columns=["ASE", "Localidades (operador)"]))
for aviso in avisos:
    st.warning(aviso)

c1, c2, c3 = st.columns(3)
c1.metric("Zonas", datos["zona"].nunique())
c2.metric("Periodo", f"{formato_mes(datos['fecha'].min())} – {formato_mes(datos['fecha'].max())}")
c3.metric("Registros mensuales", len(datos))

# 2. Historia
st.header("2. Evolución histórica")
historia = datos.assign(fecha=datos["fecha"].dt.to_timestamp())
figura = px.line(historia, x="fecha", y="toneladas", color="zona",
                 labels={"fecha": "Mes", "toneladas": "Toneladas / mes", "zona": "Zona"})
st.plotly_chart(figura)

# 3. Modelo y evaluación
st.header("3. Modelo y evaluación")
try:
    prueba, futuro, inicio_prueba, n_entrenamiento = entrenar_y_evaluar(datos)
except ValueError as error:
    st.error(str(error))
    st.stop()

st.markdown(
    f"**Random Forest** que predice un mes con 1 a {HORIZONTE_MAX} meses de anticipación usando solo información "
    "disponible al momento de predecir: mes del año, meses de anticipación, último mes conocido y mismo mes "
    "del año anterior (estos dos, divididos por el promedio de los 12 meses previos, para que el modelo aprenda "
    "de todas las zonas a la vez). "
    "**Referencia**: repetir el valor del mismo mes del año anterior.\n\n"
    f"Separación cronológica: el modelo de evaluación se entrena con {n_entrenamiento} ejemplos cuyo mes objetivo es "
    f"anterior a {formato_mes(inicio_prueba)}, y se prueba en {formato_mes(inicio_prueba)} – "
    f"{formato_mes(datos['fecha'].max())} ({len(prueba)} predicciones, todos los horizontes)."
)
metricas = tabla_metricas(prueba)
st.dataframe(metricas, hide_index=True,
             column_config={c: st.column_config.NumberColumn(format="%.0f") for c in ["MAE (t)", "RMSE (t)"]})
mae_modelo, mae_referencia = metricas["MAE (t)"]
if mae_modelo < mae_referencia:
    st.success(f"En la prueba, el Random Forest reduce el MAE un {(1 - mae_modelo / mae_referencia) * 100:.0f} % "
               "frente a la referencia.")
else:
    st.warning(f"En la prueba, el Random Forest no supera a la referencia (MAE {formato_toneladas(mae_modelo)} "
               f"frente a {formato_toneladas(mae_referencia)}). Revise abajo en qué horizontes es útil.")

por_horizonte = mae_por_horizonte(prueba)
figura = px.line(por_horizonte.reset_index().melt("horizonte", var_name="Método", value_name="MAE"),
                 x="horizonte", y="MAE", color="Método", markers=True,
                 labels={"horizonte": "Meses de anticipación", "MAE": "MAE en prueba (t)"})
st.plotly_chart(figura)

# 4. Predicción
st.header("4. Predicción")
if futuro.empty:
    st.error("No es posible predecir: ninguna zona tiene completos sus últimos 12 meses.")
    st.stop()
sin_prediccion = sorted(set(datos["zona"]) - set(futuro["zona"]))
if sin_prediccion:
    st.warning("Sin predicción por faltar datos en sus últimos 12 meses: " + ", ".join(sin_prediccion))

c1, c2 = st.columns(2)
zona = c1.selectbox("Zona", sorted(futuro["zona"].unique()))
serie = datos[datos["zona"] == zona]
ultimo = serie["fecha"].max()
opciones = futuro[futuro["zona"] == zona].set_index("horizonte").sort_index()
h = c2.selectbox("Mes a predecir", opciones.index.tolist(),
                 format_func=lambda k: f"{formato_mes(ultimo + k)} ({formato_meses(k)} después "
                                       f"del último dato, {formato_mes(ultimo)})")
if oficial and zona in LOCALIDADES_POR_ASE:
    st.caption(f"{zona}: {LOCALIDADES_POR_ASE[zona]}")

fila = opciones.loc[h]
error_modelo, error_referencia = por_horizonte.loc[h, "Random Forest"], por_horizonte.loc[h, "Referencia"]
c1, c2 = st.columns(2)
c1.metric("Random Forest", formato_toneladas(fila["modelo"]),
          help=f"Error absoluto medio en la prueba a {formato_meses(h)}: {formato_toneladas(error_modelo)}")
c2.metric("Referencia (mismo mes del año anterior)", formato_toneladas(fila["referencia"]),
          help=f"Error absoluto medio en la prueba a {formato_meses(h)}: {formato_toneladas(error_referencia)}")
if error_modelo < error_referencia:
    st.success(f"Con {formato_meses(h)} de anticipación, el Random Forest tuvo menos error en la prueba "
               f"(MAE {formato_toneladas(error_modelo)} frente a {formato_toneladas(error_referencia)}).")
else:
    st.warning(f"Con {formato_meses(h)} de anticipación, la referencia tuvo menos error en la prueba "
               f"(MAE {formato_toneladas(error_referencia)} frente a {formato_toneladas(error_modelo)} del "
               "Random Forest). Para este periodo, la referencia es la estimación más confiable.")

prediccion = opciones.reset_index()
prediccion["fecha"] = prediccion["fecha"].dt.to_timestamp()
x_continuo = [ultimo.to_timestamp(), *prediccion["fecha"]]
y_ultimo = serie["toneladas"].iloc[-1]
figura = go.Figure()
figura.add_scatter(x=serie["fecha"].dt.to_timestamp(), y=serie["toneladas"], name="Histórico", mode="lines")
figura.add_scatter(x=x_continuo, y=[y_ultimo, *prediccion["modelo"]], name="Random Forest",
                   mode="lines+markers", line={"dash": "dash"})
figura.add_scatter(x=x_continuo, y=[y_ultimo, *prediccion["referencia"]], name="Referencia",
                   mode="lines+markers", line={"dash": "dot"})
figura.add_scatter(x=[(ultimo + h).to_timestamp()], y=[fila["modelo"]], name="Mes seleccionado",
                   mode="markers", marker={"size": 14, "symbol": "star"})
figura.update_layout(xaxis_title="Mes", yaxis_title="Toneladas / mes", title=zona)
st.plotly_chart(figura)
