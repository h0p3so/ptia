"""Construye data/residuos_domiciliarios_ase.csv a partir de los archivos oficiales de la UAESP.

Fuente: Datos Abiertos Bogotá — "Residuos dispuestos de recolección por ASEs en PIDJ. UAESP. Bogotá D.C."
https://datosabiertos.bogota.gov.co/dataset/residuos-dispuestos-de-recoleccion-por-ases-en-pidj
Licencia: CC0 1.0.

De cada archivo se toma la columna "Recolección Domiciliaria (t/mes)" de cada Área de Servicio
Exclusivo (ASE). Uso: python preparar_datos.py
"""

import io
import re
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

import openpyxl
import pandas as pd

BASE = "https://datosabiertos.bogota.gov.co/dataset/73ade8e2-498a-406e-b37c-46443bea10f1/resource/"
RECURSOS = [
    "48b139ec-88e9-4aab-aaa8-4525223312fd/download/residuos-dispuestos-de-recoleccion-por-ases-en-pidj-ano-2018.xlsx",
    "fb184288-2d7c-4822-bb15-4690dd001e91/download/residuos-dispuestos-de-recoleccion-por-ases-en-pidj-ano-2019.xlsx",
    "65ce74dc-3fc1-4576-9ac1-688b59876372/download/residuos-dispuestos-de-recoleccion-por-ases-en-pidj-ano-2020.xlsx",
    "eacf74e4-63ca-4a97-be4c-5c6c4ff37132/download/residuos-dispuestos-de-recoleccion-por-ases-en-pidj-ano-2021.xlsx",
    "056de1e6-7080-41f6-b7ab-17bd0b7bc4d5/download/residuos-dispuestos-de-recoleccion-por-ases-en-pidj-2022.zip",
    "0a118551-f471-442a-86bb-0b3739a4487a/download/residuos-dispuestos-de-recoleccion-por-ases-en-pidj-2023.zip",
    "2cc5df34-9e37-4381-bba9-25f2c22211f2/download/residuos-dispuestos-de-recoleccion-por-ases-en-pidj-2024.zip",
    "dd52384f-4af4-4755-a73a-b130a8139a45/download/residuos-dispuestos-de-recoleccion-por-ases-en-pidj-2025.zip",
    "2528176c-f325-4005-99f2-10a4c2962281/download/residuos-dispuestos-de-recoleccion-porases-en-pidj-i-sem-2026.xlsx",
]
SALIDA = Path(__file__).parent / "data" / "residuos_domiciliarios_ase.csv"


def descargar(url):
    """Devuelve una lista de (nombre, bytes) con los .xlsx del recurso (descomprime los .zip)."""
    with urllib.request.urlopen(url, timeout=120) as respuesta:
        contenido = respuesta.read()
    if url.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(contenido)) as z:
            return [(n, z.read(n)) for n in z.namelist() if n.lower().endswith(".xlsx")]
    return [(url.rsplit("/", 1)[-1], contenido)]


def leer_libro(nombre, contenido):
    """Extrae (fecha, zona, toneladas, archivo) de cada hoja: fila 2 = nombres de ASE, fila 3 = encabezados."""
    registros = []
    libro = openpyxl.load_workbook(io.BytesIO(contenido), data_only=True, read_only=True)
    for hoja in libro.worksheets:
        filas = list(hoja.iter_rows(values_only=True))
        columnas = {}
        for j, celda in enumerate(filas[1]):
            ase = re.match(r"\s*ASE\s*(\d)", str(celda or ""))
            if ase and re.search(r"domiciliaria", str(filas[2][j]), re.I):
                columnas[f"ASE {ase.group(1)}"] = j
        for fila in filas[3:]:
            if not isinstance(fila[0], datetime):
                continue
            for zona, j in columnas.items():
                registros.append((fila[0].strftime("%Y-%m"), zona, fila[j], f"{nombre}:{hoja.title}"))
    return registros


def main():
    registros = []
    for recurso in RECURSOS:
        for nombre, contenido in descargar(BASE + recurso):
            registros += leer_libro(nombre, contenido)
    datos = pd.DataFrame(registros, columns=["fecha", "zona", "toneladas", "archivo"])
    datos["toneladas"] = pd.to_numeric(datos["toneladas"], errors="coerce")

    # Algunos meses aparecen en dos archivos (p. ej. 2023-07 a 2023-12): se exige que coincidan.
    diferencias = datos.groupby(["fecha", "zona"])["toneladas"].agg(lambda s: s.max() - s.min())
    if (diferencias > 0.01).any():
        raise SystemExit(f"Valores distintos para un mismo mes y ASE:\n{diferencias[diferencias > 0.01]}")
    datos = datos.drop_duplicates(["fecha", "zona"]).sort_values(["zona", "fecha"])

    # El esquema de ASE empezó el 12 de febrero de 2018: enero (en ceros) y febrero (parcial) no son comparables.
    datos = datos[datos["fecha"] >= "2018-03"]

    SALIDA.parent.mkdir(exist_ok=True)
    datos[["fecha", "zona", "toneladas"]].to_csv(SALIDA, index=False, float_format="%.2f")
    print(f"{len(datos)} filas, {datos['fecha'].min()} a {datos['fecha'].max()} -> {SALIDA}")


if __name__ == "__main__":
    main()
