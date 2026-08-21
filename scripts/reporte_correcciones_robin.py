"""Hoja de correcciones para Robin v2 — con contexto visual de su propio Excel.

Mejoras sobre v1 (feedback: Robin no ubicaba las filas):
    - Muestra las filas de ALREDEDOR tal como él las ve, para reconocerlas.
    - Excluye las filas casi vacías (basura estructural): se descartan solas.
    - Preguntas en lenguaje natural, una sola columna para responder.
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from etl.config import RAW_DIR, get_connection
from etl.extract import load_sheet, resolve_source_files

MAX_ANCHO = 60


def fila_resumen(row, cols) -> str:
    """Una fila del Excel de Robin como texto corto y legible."""
    partes = []
    for nombre, col in cols.items():
        if col and col in row.index and pd.notna(row[col]):
            valor = row[col]
            if hasattr(valor, "strftime"):
                valor = valor.strftime("%d/%m/%Y")
            texto = str(valor).strip()
            if texto:
                partes.append(f"{nombre}: {texto[:MAX_ANCHO]}")
    return " · ".join(partes) if partes else "(vacía)"


def contexto_de_hoja(path, hoja, idx_fila) -> str:
    """Reconstruye la vecindad de la fila problemática como la ve Robin."""
    try:
        df = load_sheet(path, hoja)
    except Exception as exc:  # noqa: BLE001
        return f"(no se pudo leer la hoja: {exc})"
    if idx_fila >= len(df):
        return "(fila fuera de rango)"
    cols = {}
    for c in df.columns:
        clave = str(c).upper()
        if "FECHA" in clave:
            cols["fecha"] = c
        elif "OBSERVAC" in clave:
            cols["obs"] = c
        elif "PESO" in clave:
            cols["peso"] = c
        elif "PELVICA" in clave or "C.PELVICA" in clave:
            cols["pelvica"] = c
        elif "CONDICION" in clave:
            cols["cc"] = c

    lineas = []
    for i in range(max(0, idx_fila - 2), min(len(df), idx_fila + 3)):
        marca = ">>> ESTA >>>" if i == idx_fila else "             "
        lineas.append(f"{marca} {fila_resumen(df.iloc[i], cols)}")
    return "\n".join(lineas)


def main() -> int:
    conn = get_connection()
    try:
        df = pd.read_sql(
            """
            SELECT origen_archivo AS archivo, hoja AS animal,
                   numero_fila AS idx, regla, motivo, payload
            FROM etl_cuarentena
            WHERE regla <> 'R5'
            ORDER BY animal, idx
            """,
            conn,
        )
    finally:
        conn.close()

    # R1 casi vacías: basura, se descartan sin molestar a Robin.
    def obs(p):
        return (p or {}).get("observaciones") or ""

    df["texto"] = df["payload"].apply(obs)
    r1_vacias = df[(df.regla == "R1") & (df.texto.str.strip() == "")]
    revisar = df[~((df.regla == "R1") & (df.texto.str.strip() == ""))].copy()
    print(f"Descartadas automáticamente (casi vacías): {len(r1_vacias)}")
    print(f"Filas que sí necesita revisar Robin: {len(revisar)}")

    files = resolve_source_files(RAW_DIR)
    paths = {p.name: p for p in files.values()}

    def contexto(row) -> str:
        if row.archivo in paths and row.regla in ("R1", "R4", "OTRO"):
            return contexto_de_hoja(paths[row.archivo], row.animal, int(row.idx))
        return f"{row.motivo}"  # CURVA/R3: el motivo ya dice mes y dato

    revisar["LO QUE VES EN TU EXCEL (alrededor)"] = revisar.apply(contexto, axis=1)
    revisar["ANIMAL"] = revisar["animal"]
    revisar["QUÉ DICEN LOS DATOS"] = revisar.apply(
        lambda r: r.texto if r.texto else str(r.payload or ""), axis=1)
    revisar["TU RESPUESTA"] = ""

    leeme = pd.DataFrame({
        "PARA ROBIN": [
            "Este archivo muestra los pocos datos de tus Excel que el sistema",
            "no pudo cargar porque algo no cuadraba (sin fecha, número imposible...).",
            "",
            "CÓMO LEER CADA CASO:",
            "  • La caja 'LO QUE VES EN TU EXCEL' reproduce las filas de alrededor,",
            "    igual que en tu archivo. La línea marcada con >>> ESTA >>> es el problema.",
            "  • 'QUÉ DICEN LOS DATOS' repite el contenido exacto de esa línea.",
            "",
            "QUÉ HACER: escribe UNA respuesta en 'TU RESPUESTA':",
            "  • Si falta la fecha: escríbela (ejemplo: 15/03/2026)",
            "  • Si el número está mal: escribe el correcto (ejemplo: 480)",
            "  • Si es basura y se ignora: escribe BORRAR",
            "  • Si no recuerdas: deja la casilla vacía y sigue.",
            "",
            "Cuando termines, entrégale el archivo a Julián. Él hace el resto.",
        ]
    })

    salida = Path.home() / "Desktop" / f"CORRECCIONES_DE_ROBIN_v2_{date.today():%Y-%m-%d}.xlsx"
    with pd.ExcelWriter(salida, engine="openpyxl") as xl:
        leeme.to_excel(xl, sheet_name="LEEME PRIMERO", index=False)
        for regla, nombre in [
            ("R1", "1_SIN_FECHA"),
            ("R4", "2_CONDICION_IMPOSIBLE"),
            ("R3", "3_PESO_O_LITRO_MALO"),
            ("OTRO", "4_PESOS_SIN_LUGAR"),
        ]:
            parte = revisar[revisar.regla == regla][
                ["ANIMAL", "LO QUE VES EN TU EXCEL (alrededor)",
                 "QUÉ DICEN LOS DATOS", "TU RESPUESTA"]
            ]
            parte.to_excel(xl, sheet_name=nombre, index=False)
        for ws in xl.book.worksheets:
            ws.column_dimensions["A"].width = 12
            ws.column_dimensions["B"].width = 70
            ws.column_dimensions["C"].width = 40
            ws.column_dimensions["D"].width = 25

    print(f"Hoja generada: {salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
