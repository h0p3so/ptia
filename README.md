# Predicción mensual de residuos domiciliarios en Bogotá

Aplicación en Streamlit que carga datos históricos mensuales de residuos y los valida. Muestra su evolución, entrena un
Random Forest, lo compara con una predicción de referencia (MAE y RMSE) y predice de 1 a 12 meses hacia adelante
para la zona que se elija.

## Instalación y ejecución

Requiere Python 3.11 o superior.

```bash
python3 -m venv .venv
source .venv/bin/activate          # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

La aplicación se abre en http://localhost:8501.

## Archivos

| Archivo | Contenido |
|---|---|
| `app.py` | Interfaz, validación, entrenamiento, evaluación y predicción |
| `preparar_datos.py` | Descarga los archivos oficiales de la UAESP y genera el CSV de `data/` |
| `data/residuos_domiciliarios_ase.csv` | Datos oficiales ya procesados (500 filas) |
| `requirements.txt` | Dependencias |

## Datos incluidos

- **Fuente**: UAESP, Datos Abiertos Bogotá, [«Residuos dispuestos de recolección por ASEs en PIDJ»](https://datosabiertos.bogota.gov.co/dataset/residuos-dispuestos-de-recoleccion-por-ases-en-pidj). Licencia CC0 1.0.
- **Variable**: «Recolección Domiciliaria (t/mes)», es decir, las toneladas de residuos domiciliarios recogidas en cada zona y dispuestas en el relleno Doña Juana.
- **Periodo**: marzo de 2018 a junio de 2026. Enero y febrero de 2018 se excluyen porque el esquema de ASE empezó el 12 de febrero de 2018 y esos meses están incompletos.
- **Verificación**: se cruzaron valores de muestra con otro conjunto de la UAESP, «Datos Residuos Recogidos RBL». ASE 1 coincide exactamente en abril de 2023 (30.950,56 t) y mayo de 2026 (33.693,51 t), y difiere 0,29 t en enero de 2021.

Para regenerar el CSV desde la fuente: `python preparar_datos.py`. El script verifica que los meses repetidos entre
archivos tengan el mismo valor.

### Limitación importante: los datos son por ASE, no por localidad

No encontré datos públicos mensuales de residuos por localidad. La UAESP los publica por **Área de Servicio Exclusivo
(ASE)**, y cada ASE agrupa varias localidades
([Alcaldía de Bogotá, 7 de febrero de 2026](https://bogota.gov.co/mi-ciudad/habitat/como-esta-dividido-el-esquema-de-aseo-en-las-localidades-de-bogota)):

| ASE | Operador | Localidades |
|---|---|---|
| ASE 1 | Promoambiental Distrito | Usaquén, Chapinero, Santa Fe, San Cristóbal, Usme, La Candelaria, Sumapaz |
| ASE 2 | LIME | Tunjuelito, Teusaquillo, Bosa, Los Mártires, Antonio Nariño, Puente Aranda, Rafael Uribe Uribe, Ciudad Bolívar |
| ASE 3 | Ciudad Limpia | Kennedy, Fontibón |
| ASE 4 | Bogotá Limpia | Engativá, Barrios Unidos |
| ASE 5 | Área Limpia | Suba |

Solo Suba (ASE 5) corresponde a una única localidad. Si consiguen datos por localidad, pueden cargarlos como CSV propio.

## Formato del CSV propio

| Columna | Contenido |
|---|---|
| `fecha` | Mes en formato `AAAA-MM`. También se acepta `AAAA-MM-DD`, y en ese caso se usa el mes. |
| `zona` (o `localidad`) | Nombre de la zona o localidad |
| `toneladas` | Toneladas del mes, un número mayor o igual a 0 |

Se aceptan dos formatos: separador `,` con punto decimal, o separador `;` con coma decimal (formato de Excel en español).
Debe haber un único valor por zona y mes.

- **Filas inválidas**: las filas con fecha, zona o toneladas inválidas se descartan y se avisa cuáles son.
- **Errores que detienen la carga**: columnas faltantes, filas repetidas y archivos vacíos o mal formados.
- **Mínimo para entrenar**: 36 meses seguidos en al menos una zona.
- **Mínimo para predecir**: los últimos 12 meses de la zona deben estar completos.

## Modelo

**Qué se predice.** Las toneladas del mes *t*, con *h* = 1 a 12 meses de anticipación. Por eso el último mes conocido
es *t − h*.

**Variables.** Solo se usa lo que ya se conoce en *t − h*:
- los meses de anticipación *h*;
- el mes del año de *t*;
- las toneladas de *t − h*;
- las toneladas de *t − 12*, que se conocen porque *h* ≤ 12.

Las dos últimas se dividen por el promedio de los 12 meses que terminan en *t − h*. El modelo nunca usa el valor del
mes objetivo.

**Qué predice el Random Forest.** La proporción respecto a ese promedio. Así las zonas, que tienen tamaños distintos,
comparten un mismo modelo.

**Referencia.** Repetir el valor del mismo mes del año anterior.

**Evaluación cronológica.**
- **Prueba**: los últimos 12 meses de datos, con todos los horizontes.
- **Entrenamiento**: solo los meses objetivo anteriores al periodo de prueba.
- **Predicciones futuras**: se reentrena con toda la historia.

### Resultados con los datos incluidos (prueba: julio 2025 – junio 2026)

| Método | MAE (t) | RMSE (t) |
|---|---|---|
| Random Forest | 1.239 | 1.678 |
| Referencia: mismo mes del año anterior | 1.191 | 1.540 |

En conjunto, **el Random Forest no supera a la referencia**. Por horizonte:
- **De 1 a 5 meses**: tiene menos error, por ejemplo MAE de 921 t frente a 1.191 t a un mes.
- **A 7 meses**: prácticamente empata (1.189 t frente a 1.191 t).
- **A 6 meses y de 8 a 12 meses**: tiene más error.

La aplicación muestra esta comparación y advierte cuando, para el mes elegido, la referencia es más confiable.

### Limitaciones

- **Sin variables externas**: no se usan población, clima, festivos ni otras variables externas.
- **Una sola ventana de prueba**: la evaluación usa una sola ventana de 12 meses (720 predicciones de 5 zonas).
- **Diseño elegido con la misma prueba**: probé tres variantes del Random Forest y me quedé con la de proporciones
  respecto al promedio de 12 meses porque tuvo el menor error. Las métricas de arriba pueden ser algo optimistas.
- **Datos por ASE**: la predicción es por ASE y no se puede repartir entre localidades sin datos adicionales.
