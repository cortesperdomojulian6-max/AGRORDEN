"""Genera el reporte de revisión de cuarentena para Robin (SPEC-003).

Salida: docs/revision_robin_cuarentena_<fecha>.xlsx
Hojas: RESUMEN, R1_sin_fecha, R4_CC_imposible, R3_pesos_litros, OTRO_pesajes_fichas.
Excluye R5 (sub-encabezados estructurales: no son rescatables).
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from etl.config import get_connection


def extraer_contenido(payload) -> str:
    if payload is None:
        return ""
    if "observaciones" in payload:
        return str(payload["observaciones"])
    if "peso" in payload:
        return f"peso={payload['peso']}"
    return str(payload)


def main() -> int:
    conn = get_connection()
    try:
        df = pd.read_sql(
            """
            SELECT origen_archivo AS archivo, hoja, numero_fila AS fila_excel,
                   regla, motivo, payload
            FROM etl_cuarentena
            ORDER BY hoja, numero_fila
            """,
            conn,
        )
    finally:
        conn.close()

    df["contenido"] = df["payload"].apply(extraer_contenido)
    df = df.drop(columns=["payload"])

    revisables = df[df["regla"] != "R5"].copy()
    print(f"Total cuarentena: {len(df)} | Revisables por Robin: {len(revisables)}")
    print(revisables["regla"].value_counts().to_string())

    ruta = Path("docs") / f"revision_robin_cuarentena_{date.today():%Y-%m-%d}.xlsx"
    with pd.ExcelWriter(ruta, engine="openpyxl") as xl:
        resumen = (
            revisables.groupby(["archivo", "regla"]).size().reset_index(name="filas")
        )
        resumen.to_excel(xl, sheet_name="RESUMEN", index=False)
        for regla, hoja_nombre in [
            ("R1", "R1_sin_fecha"),
            ("R4", "R4_CC_imposible"),
            ("R3", "R3_pesos_litros"),
            ("OTRO", "OTRO_pesajes_fichas"),
        ]:
            parte = revisables[revisables["regla"] == regla]
            parte.to_excel(xl, sheet_name=hoja_nombre, index=False)

    print(f"Reporte generado: {ruta}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
