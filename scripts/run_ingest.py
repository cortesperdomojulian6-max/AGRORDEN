"""Orquestador del ETL de ingesta v1 del ERP Ganadero AGRORDEN.

Alcance v1 (según spec y validaciones Robin 2026-08-20):
    animales             <- hojas-animal de FICHAS, CURVA y PESAJE
    hitos_reproductivos  <- C.PELVICA de FICHAS normalizada
    eventos_sanitarios   <- OBSERVACIONES con palabras clave sanitarias
    etl_cuarentena       <- rechazos R1/R4/R5 y pesajes sin tabla destino

Uso:
    python scripts/run_ingest.py
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from etl.config import RAW_DIR, get_connection  # noqa: E402
from etl.extract import iter_animal_sheets, load_sheet, resolve_source_files  # noqa: E402
from etl.load import (  # noqa: E402
    load_animales,
    load_catalogs,
    load_cuarentena,
    load_eventos,
    load_hitos,
    reset_operational_tables,
)
from etl.transform import TransformResult, build_registry, transform_fichas_sheet  # noqa: E402


def main() -> int:
    files = resolve_source_files(RAW_DIR)
    print(f"Fuentes: {', '.join(p.name for p in files.values())}")

    sheets_by_file = {
        key: list(iter_animal_sheets(path)) for key, path in files.items()
    }
    total_sheets = sum(len(v) for v in sheets_by_file.values())
    print(f"Hojas de animal detectadas: {total_sheets}")

    result = TransformResult(
        animales=build_registry(sheets_by_file),
        hitos=[],
        eventos=[],
        cuarentena=[],
    )

    fichas = files["fichas"]
    for ref in sheets_by_file["fichas"]:
        df = load_sheet(fichas, ref.sheet)
        transform_fichas_sheet(df, ref.numero_base, fichas.name, ref.sheet, result)

    reglas = Counter(q.regla for q in result.cuarentena)
    print(f"Transformación: {len(result.hitos)} hitos, {len(result.eventos)} eventos, "
          f"cuarentena {dict(reglas)}")

    conn = get_connection()
    try:
        reset_operational_tables(conn)
        lotes, tipos = load_catalogs(conn)
        ids = load_animales(conn, result.animales)
        n_hitos = load_hitos(conn, result.hitos, ids)
        n_eventos = load_eventos(conn, result.eventos, ids, tipos)
        n_cuar = load_cuarentena(conn, result.cuarentena)
        conn.commit()
        print(f"Carga OK: {len(ids)} animales, {n_hitos} hitos, {n_eventos} eventos, "
              f"{n_cuar} filas en cuarentena.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
