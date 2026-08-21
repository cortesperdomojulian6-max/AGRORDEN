"""Orquestador del ETL de ingesta del ERP Ganadero AGRORDEN.

Alcance (según specs y validaciones Robin):
    SPEC-001:
        animales             <- hojas-animal de FICHAS, CURVA y PESAJE
        hitos_reproductivos  <- C.PELVICA de FICHAS normalizada
        eventos_sanitarios   <- OBSERVACIONES con palabras clave sanitarias
    SPEC-002:
        pesajes              <- FECHA/PESO de PESAJE GENERAL (solo lo medido)
        produccion_lechera   <- bloques mensuales Días/Litros de CURVA
        eventos_reproductivos<- etiquetas reproductivas de CURVA
    etl_cuarentena           <- rechazos R1/R3/R4/R5/OTRO trazables

Uso:
    python scripts/run_ingest.py
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from etl.config import RAW_DIR, get_connection  # noqa: E402
from etl.extract import (  # noqa: E402
    iter_animal_sheets,
    load_curva_grid,
    load_sheet,
    resolve_source_files,
)
from etl.load import (  # noqa: E402
    load_animales,
    load_catalogs,
    load_cuarentena,
    load_eventos,
    load_eventos_reproductivos,
    load_hitos,
    load_pesajes,
    load_produccion,
    reset_operational_tables,
)
from etl.transform import (  # noqa: E402
    TransformResult,
    build_registry,
    parse_pesajes_sheet,
    parse_produccion_curva,
    parse_repro_events,
    transform_fichas_sheet,
)


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

    # --- SPEC-002: pesajes -------------------------------------------------
    pesaje = files["pesaje"]
    pesajes = []
    for ref in sheets_by_file["pesaje"]:
        df = load_sheet(pesaje, ref.sheet)
        regs, cuar = parse_pesajes_sheet(df, ref.numero_base, pesaje.name, ref.sheet)
        pesajes.extend(regs)
        result.cuarentena.extend(cuar)

    # --- SPEC-002: producción y eventos reproductivos desde CURVA ----------
    curva = files["curva"]
    produccion = []
    eventos_repro = []
    for ref in sheets_by_file["curva"]:
        grid_data = load_curva_grid(curva, ref.sheet)
        evs, cuar_ev = parse_repro_events(
            grid_data["meta"], ref.numero_base, curva.name, ref.sheet)
        eventos_repro.extend(evs)
        result.cuarentena.extend(cuar_ev)
        prods, cuar_pr = parse_produccion_curva(
            grid_data["grid"], grid_data["meses"], ref.numero_base,
            curva.name, ref.sheet)
        produccion.extend(prods)
        result.cuarentena.extend(cuar_pr)

    reglas = Counter(q.regla for q in result.cuarentena)
    print(f"Transformación: {len(result.hitos)} hitos, {len(result.eventos)} eventos, "
          f"{len(pesajes)} pesajes, {len(produccion)} registros de producción, "
          f"{len(eventos_repro)} eventos reproductivos, cuarentena {dict(reglas)}")

    conn = get_connection()
    try:
        reset_operational_tables(conn)
        lotes, tipos, tipos_repro = load_catalogs(conn)
        ids = load_animales(conn, result.animales)
        n_hitos = load_hitos(conn, result.hitos, ids)
        n_eventos = load_eventos(conn, result.eventos, ids, tipos)
        n_pesajes = load_pesajes(conn, pesajes, ids)
        n_prod = load_produccion(conn, produccion, ids)
        n_repro = load_eventos_reproductivos(conn, eventos_repro, ids, tipos_repro)
        n_cuar = load_cuarentena(conn, result.cuarentena)
        conn.commit()
        print(f"Carga OK: {len(ids)} animales, {n_hitos} hitos, {n_eventos} eventos, "
              f"{n_pesajes} pesajes, {n_prod} producciones, {n_repro} eventos reproductivos, "
              f"{n_cuar} filas en cuarentena.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
