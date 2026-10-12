/* ============================================================
   app.js — Lógica del prototipo
   Flujo: entrada de variables -> modelo -> predicción -> gráfica
   ============================================================ */

/* ---------- 1. Utilidades ---------- */

/* Generador pseudoaleatorio determinista: la misma entrada
   produce siempre la misma salida, para que el prototipo sea
   reproducible durante la demostración. */
function ruido(semilla) {
  const x = Math.sin(semilla * 12.9898) * 43758.5453;
  return x - Math.floor(x);
}

function formatoTon(valor) {
  return valor.toLocaleString("es-CO", { maximumFractionDigits: 0 });
}

function buscarLocalidad(id) {
  return LOCALIDADES.find(l => l.id === id);
}

function buscarModelo(id) {
  return MODELOS.find(m => m.id === id);
}

/* ---------- 2. Modelo sustituto ---------- */
/* Estimación base: población x generación per cápita x factor
   estacional, ajustada por estrato, festivos y clima. Sustituye
   temporalmente al modelo entrenado (SVR / Random Forest). */
function estimarBase(loc, mesIndex, anio, festivos, lluvia) {
  const kg = loc.poblacion * loc.percapita;      // kg/mes
  let ton = kg / 1000;                            // toneladas/mes
  ton *= FACTOR_MES[mesIndex];                    // estacionalidad
  ton *= 1 + (anio - 2024) * 0.018;               // tendencia anual
  ton *= 1 + festivos * 0.012;                    // festivos del mes
  ton *= lluvia ? 1.035 : 1.0;                    // temporada de lluvia
  return ton;
}

function predecir(entrada) {
  const loc = buscarLocalidad(entrada.localidad);
  const modelo = buscarModelo(entrada.modelo);
  const base = estimarBase(loc, entrada.mes, entrada.anio, entrada.festivos, entrada.lluvia);

  /* Cada modelo introduce su propio sesgo y dispersión, de modo
     que la comparación entre modelos sea visible en la interfaz. */
  const semilla = entrada.mes + entrada.anio + loc.poblacion / 1000;
  const desvio = (ruido(semilla) - 0.5) * 2 * modelo.dispersion;
  const prediccion = base * modelo.sesgo * (1 + desvio);

  return {
    localidad: loc,
    modelo: modelo,
    prediccion: prediccion,
    inferior: prediccion - modelo.mae,
    superior: prediccion + modelo.mae
  };
}

/* Serie histórica de los 12 meses previos al periodo consultado. */
function historico(entrada) {
  const loc = buscarLocalidad(entrada.localidad);
  const serie = [];
  for (let k = 12; k >= 1; k--) {
    let mes = entrada.mes - k;
    let anio = entrada.anio;
    while (mes < 0) { mes += 12; anio -= 1; }
    const base = estimarBase(loc, mes, anio, 1, mes >= 2 && mes <= 4);
    const variacion = (ruido(mes + anio + loc.percapita) - 0.5) * 0.06;
    serie.push({
      etiqueta: MESES[mes].slice(0, 3),
      anio: anio,
      valor: base * (1 + variacion)
    });
  }
  return serie;
}

/* ---------- 3. Gráfica (SVG dibujado a mano) ---------- */
function dibujarGrafica(serie, prediccion, etiquetaPred) {
  const ancho = 720, alto = 260;
  const margen = { arriba: 20, derecha: 16, abajo: 34, izquierda: 56 };
  const areaAncho = ancho - margen.izquierda - margen.derecha;
  const areaAlto = alto - margen.arriba - margen.abajo;

  const puntos = serie.map(p => p.valor).concat([prediccion]);
  const max = Math.max(...puntos) * 1.12;
  const min = Math.min(...puntos) * 0.88;

  const x = i => margen.izquierda + (areaAncho * i) / puntos.length + areaAncho / (puntos.length * 2);
  const y = v => margen.arriba + areaAlto - ((v - min) / (max - min)) * areaAlto;

  let svg = `<svg viewBox="0 0 ${ancho} ${alto}" role="img" aria-label="Histórico y predicción de toneladas mensuales">`;

  /* Líneas guía horizontales con su valor */
  for (let i = 0; i <= 3; i++) {
    const valor = min + ((max - min) * i) / 3;
    const py = y(valor);
    svg += `<line class="guia" x1="${margen.izquierda}" y1="${py}" x2="${ancho - margen.derecha}" y2="${py}" />`;
    svg += `<text class="eje" x="${margen.izquierda - 8}" y="${py + 4}" text-anchor="end">${formatoTon(valor)}</text>`;
  }

  /* Línea del histórico */
  const camino = serie.map((p, i) => `${i === 0 ? "M" : "L"} ${x(i)} ${y(p.valor)}`).join(" ");
  svg += `<path class="linea" d="${camino}" />`;

  /* Tramo punteado que conecta el último dato real con la predicción */
  const ultimo = serie.length - 1;
  svg += `<path class="linea-pred" d="M ${x(ultimo)} ${y(serie[ultimo].valor)} L ${x(puntos.length - 1)} ${y(prediccion)}" />`;

  /* Puntos del histórico y etiquetas del eje X */
  serie.forEach((p, i) => {
    svg += `<circle class="punto" cx="${x(i)}" cy="${y(p.valor)}" r="3.5" />`;
    if (i % 2 === 0) {
      svg += `<text class="eje" x="${x(i)}" y="${alto - 12}" text-anchor="middle">${p.etiqueta}</text>`;
    }
  });

  /* Punto de la predicción, destacado */
  const px = x(puntos.length - 1), py = y(prediccion);
  svg += `<circle class="punto-pred" cx="${px}" cy="${py}" r="6" />`;
  svg += `<text class="eje destacado" x="${px}" y="${alto - 12}" text-anchor="middle">${etiquetaPred}</text>`;

  svg += `</svg>`;
  document.getElementById("grafica").innerHTML = svg;
}

/* ---------- 4. Render de resultados ---------- */
function mostrarResultado(res, serie) {
  /* serie[0] es el mismo mes del año anterior: la comparación
     estacional correcta para una serie mensual. */
  const mismoMesAnterior = serie[0].valor;
  const variacion = ((res.prediccion - mismoMesAnterior) / mismoMesAnterior) * 100;
  const signo = variacion >= 0 ? "+" : "";
  const clase = variacion >= 0 ? "sube" : "baja";

  document.getElementById("valor-prediccion").textContent = formatoTon(res.prediccion);
  document.getElementById("rango").textContent =
    `Rango esperado: ${formatoTon(res.inferior)} – ${formatoTon(res.superior)} t (± MAE del modelo)`;
  document.getElementById("variacion").innerHTML =
    `<span class="${clase}">${signo}${variacion.toFixed(1)}%</span> frente al mismo mes del año anterior`;
  document.getElementById("detalle-modelo").textContent =
    `${res.modelo.nombre} · MAE ${res.modelo.mae} t · RMSE ${res.modelo.rmse} t · R² ${res.modelo.r2}`;

  /* Interpretación operativa: cuántos viajes de camión implica. */
  const capacidadCamion = 8; // toneladas por viaje
  const viajes = Math.ceil(res.prediccion / capacidadCamion);
  document.getElementById("operativo").textContent =
    `≈ ${formatoTon(viajes)} viajes de camión (capacidad estimada ${capacidadCamion} t) durante el mes.`;

  document.getElementById("resultado").hidden = false;
}

function pintarTablaModelos(idActivo) {
  const cuerpo = document.getElementById("tabla-modelos");
  cuerpo.innerHTML = MODELOS.map(m => `
    <tr class="${m.id === idActivo ? "activo" : ""}">
      <td>${m.nombre}</td>
      <td>${m.mae}</td>
      <td>${m.rmse}</td>
      <td>${m.r2}</td>
    </tr>`).join("");
}

/* ---------- 5. Inicialización ---------- */
function llenarFormulario() {
  const selLoc = document.getElementById("localidad");
  selLoc.innerHTML = LOCALIDADES
    .map(l => `<option value="${l.id}">${l.nombre}</option>`).join("");

  const selMes = document.getElementById("mes");
  selMes.innerHTML = MESES
    .map((m, i) => `<option value="${i}">${m}</option>`).join("");

  const selModelo = document.getElementById("modelo");
  selModelo.innerHTML = MODELOS
    .map(m => `<option value="${m.id}">${m.nombre}</option>`).join("");

  selLoc.value = "kennedy";
  selMes.value = "11";
}

function actualizarDatosLocalidad() {
  const loc = buscarLocalidad(document.getElementById("localidad").value);
  document.getElementById("info-localidad").textContent =
    `Población ${loc.poblacion.toLocaleString("es-CO")} hab · estrato predominante ${loc.estrato}`;
}

function ejecutar(evento) {
  evento.preventDefault();
  const entrada = {
    localidad: document.getElementById("localidad").value,
    mes: parseInt(document.getElementById("mes").value, 10),
    anio: parseInt(document.getElementById("anio").value, 10),
    festivos: parseInt(document.getElementById("festivos").value, 10),
    lluvia: document.getElementById("lluvia").checked,
    modelo: document.getElementById("modelo").value
  };

  const res = predecir(entrada);
  const serie = historico(entrada);

  mostrarResultado(res, serie);
  dibujarGrafica(serie, res.prediccion, MESES[entrada.mes].slice(0, 3));
  pintarTablaModelos(entrada.modelo);
}

document.addEventListener("DOMContentLoaded", () => {
  llenarFormulario();
  actualizarDatosLocalidad();
  pintarTablaModelos(null);
  document.getElementById("localidad").addEventListener("change", actualizarDatosLocalidad);
  document.getElementById("formulario").addEventListener("submit", ejecutar);
});
