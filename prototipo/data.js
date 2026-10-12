/* ============================================================
   data.js — Datos de apoyo del prototipo
   Proyecto PTIA — Grupo 04
   Predicción de generación de residuos sólidos urbanos en Bogotá

   NOTA: los valores históricos son SINTÉTICOS. Sirven para
   demostrar el flujo entrada -> predicción del Hito 1. En el
   modelo final se reemplazan por el consolidado mensual de
   recolección por localidad (datos abiertos de Bogotá).
   ============================================================ */

const MESES = [
  "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
];

/* Localidades de Bogotá: población aproximada (habitantes),
   estrato socioeconómico predominante y generación per cápita
   base en kg/habitante/mes. */
const LOCALIDADES = [
  { id: "usaquen",     nombre: "Usaquén",             poblacion: 588000, estrato: 4, percapita: 27.5 },
  { id: "chapinero",   nombre: "Chapinero",           poblacion: 126000, estrato: 5, percapita: 33.0 },
  { id: "santafe",     nombre: "Santa Fe",            poblacion: 102000, estrato: 2, percapita: 26.0 },
  { id: "sancristobal",nombre: "San Cristóbal",       poblacion: 393000, estrato: 2, percapita: 22.5 },
  { id: "usme",        nombre: "Usme",                poblacion: 342000, estrato: 1, percapita: 20.5 },
  { id: "tunjuelito",  nombre: "Tunjuelito",          poblacion: 186000, estrato: 2, percapita: 23.0 },
  { id: "bosa",        nombre: "Bosa",                poblacion: 776000, estrato: 2, percapita: 21.5 },
  { id: "kennedy",     nombre: "Kennedy",             poblacion: 1230000, estrato: 3, percapita: 24.0 },
  { id: "fontibon",    nombre: "Fontibón",            poblacion: 424000, estrato: 3, percapita: 25.5 },
  { id: "engativa",    nombre: "Engativá",            poblacion: 887000, estrato: 3, percapita: 24.5 },
  { id: "suba",        nombre: "Suba",                poblacion: 1315000, estrato: 3, percapita: 25.0 },
  { id: "barriosunidos",nombre: "Barrios Unidos",     poblacion: 267000, estrato: 4, percapita: 27.0 },
  { id: "teusaquillo", nombre: "Teusaquillo",         poblacion: 154000, estrato: 4, percapita: 28.5 },
  { id: "martires",    nombre: "Los Mártires",        poblacion: 95000,  estrato: 3, percapita: 30.0 },
  { id: "antonionarino",nombre: "Antonio Nariño",     poblacion: 110000, estrato: 3, percapita: 25.5 },
  { id: "puentearanda",nombre: "Puente Aranda",       poblacion: 233000, estrato: 3, percapita: 26.5 },
  { id: "candelaria",  nombre: "La Candelaria",       poblacion: 18000,  estrato: 3, percapita: 31.0 },
  { id: "rafaeluribe", nombre: "Rafael Uribe Uribe",  poblacion: 350000, estrato: 2, percapita: 22.0 },
  { id: "ciudadbolivar",nombre: "Ciudad Bolívar",     poblacion: 776000, estrato: 1, percapita: 20.0 },
  { id: "sumapaz",     nombre: "Sumapaz",             poblacion: 8000,   estrato: 1, percapita: 12.0 }
];

/* Factor estacional por mes (patrón anual observado en la literatura:
   picos en diciembre por consumo navideño, valle en enero-febrero). */
const FACTOR_MES = [
  0.94, 0.90, 0.98, 0.97, 1.00, 0.99,
  1.02, 1.01, 0.99, 1.02, 1.04, 1.15
];

/* Modelos comparados. Las métricas provienen del baseline reportado
   en la literatura de referencia (Solano-Meza et al., 2019) y se
   actualizarán con el entrenamiento real del equipo. */
const MODELOS = [
  { id: "svr", nombre: "Support Vector Regression", mae: 412, rmse: 587, r2: 0.91, sesgo: 1.000, dispersion: 0.030 },
  { id: "rf",  nombre: "Random Forest",             mae: 455, rmse: 640, r2: 0.89, sesgo: 1.012, dispersion: 0.040 },
  { id: "lr",  nombre: "Regresión Lineal",          mae: 690, rmse: 902, r2: 0.78, sesgo: 0.972, dispersion: 0.065 }
];
