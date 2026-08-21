"""SPEC-003 fase 1: aplica recuperación de cuarentena con datos provisionales.

Ejecutar DESPUÉS de scripts/run_ingest.py (es idempotente):
    python scripts/aplicar_provisionales.py

Tratamiento por categoría (docs/spec_recuperacion_cuarentena.md):
    OTRO (26) -> pesajes REALES (tenían fecha válida, faltaba destino)
    R1 con texto (8) -> evento sanitario PROVISIONAL fecha 1901-01-01
    R4 (8) -> evento sanitario PROVISIONAL con CC nula y valor original citado
    R3 (18) -> produccion_lechera PROVISIONAL litros=0
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from etl.config import RAW_DIR, get_connection
from etl.extract import MESES_ES, load_sheet, parse_sheet_identity, resolve_source_files
from etl.transform import (
    RE_PESO_TEXT,
    SANITARY_KEYWORDS,
    clean_date,
    strip_accents,
)

FECHA_PROVISIONAL = date(1901, 1, 1)


def _animal_de_hoja(hoja: str) -> str:
    """Número de animal visible a partir del nombre de hoja (regla -M incluida)."""
    numero, sufijo = parse_sheet_identity(str(hoja))
    if numero is None:
        return str(hoja)
    return f"{numero}-M" if sufijo == "M" else numero


def _cargar_cuarentena() -> pd.DataFrame:
    conn = get_connection()
    try:
        return pd.read_sql(
            """
            SELECT origen_archivo AS archivo, hoja, numero_fila AS idx,
                   regla, motivo, payload
            FROM etl_cuarentena
            WHERE regla IN ('R1', 'R3', 'R4', 'OTRO')
            ORDER BY hoja, numero_fila
            """,
            conn,
        )
    finally:
        conn.close()


def _pesos_reales_otro(cuar: pd.DataFrame, paths: dict) -> list[tuple]:
    """OTRO: peso + fecha reales leídos de la hoja original de FICHAS."""
    filas = []
    cache: dict[tuple[str, str], pd.DataFrame] = {}
    for _, q in cuar[cuar.regla == "OTRO"].iterrows():
        clave = (q.archivo, q.hoja)
        if clave not in cache:
            cache[clave] = load_sheet(paths[q.archivo], q.hoja)
        df = cache[clave]
        if q.idx >= len(df):
            continue
        row = df.iloc[int(q.idx)]
        cols = {strip_accents(str(c)).strip().upper(): c for c in df.columns}
        c_fecha = next((cols[k] for k in cols if "FECHA" in k), None)
        c_peso = next((cols[k] for k in cols if "PESO" in k), None)
        fecha = clean_date(row[c_fecha]) if c_fecha else None
        # El peso en FICHAS suele ser texto tipo "340 kg": usar el regex del ETL.
        match = RE_PESO_TEXT.match(str(row[c_peso])) if c_peso and pd.notna(row[c_peso]) else None
        if fecha is None or not match:
            continue
        peso = float(match.group(1).replace(",", "."))
        if peso <= 0:
            continue
        filas.append((q.hoja, fecha, peso, q.archivo))
    return filas


def _tipo_por_texto(texto: str) -> str | None:
    norm = strip_accents(texto).lower()
    return next((t for kw, t in SANITARY_KEYWORDS.items() if kw in norm), None)


def main() -> int:
    files = resolve_source_files(RAW_DIR)
    paths = {p.name: p for p in files.values()}
    cuar = _cargar_cuarentena()

    pesos = _pesos_reales_otro(cuar, paths)

    r1 = cuar[(cuar.regla == "R1") & (cuar.payload.notna())]
    r1 = r1[r1.payload.apply(lambda p: bool((p or {}).get("observaciones")))]

    r4 = cuar[cuar.regla == "R4"]
    r3 = cuar[cuar.regla == "R3"]

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Limpieza idempotente de provisionales de la corrida anterior.
            # Los pesajes derivados de OTRO provienen de FICHAS: se identifican
            # por archivo_origen (la ingesta normal solo llena desde PESAJE).
            cur.execute("DELETE FROM pesajes WHERE provisional")
            cur.execute("DELETE FROM pesajes WHERE archivo_origen = %s",
                        (files["fichas"].name,))
            cur.execute("DELETE FROM eventos_sanitarios WHERE provisional")
            cur.execute("DELETE FROM produccion_lechera WHERE provisional")

            # 1) Pesajes REALES desde OTRO.
            for hoja, fecha, peso, archivo in pesos:
                cur.execute(
                    """
                    INSERT INTO pesajes
                        (id_animal, fecha, peso_kg, archivo_origen, hoja_origen, provisional)
                    SELECT id_interno, %s, %s, %s, %s, FALSE
                    FROM animales WHERE numero_visible = %s
                    """,
                    (fecha, peso, archivo, hoja, _animal_de_hoja(hoja)),
                )

            # 2) Eventos PROVISIONALES desde R1 con texto.
            for _, q in r1.iterrows():
                texto = (q.payload or {}).get("observaciones", "")
                tipo = _tipo_por_texto(texto) or "Revisión"
                cur.execute(
                    """
                    INSERT INTO eventos_sanitarios
                        (id_animal, fecha_evento, id_tipo_evento,
                         observaciones_clinicas, provisional)
                    SELECT id_interno, %s,
                           (SELECT id_tipo_evento FROM cat_tipos_evento WHERE nombre_tipo = %s),
                           %s, TRUE
                    FROM animales WHERE numero_visible = %s
                    """,
                    (
                        FECHA_PROVISIONAL,
                        tipo,
                        f"[PROVISIONAL sin fecha] {texto}",
                        _animal_de_hoja(q.hoja),
                    ),
                )

            # 3) Eventos PROVISIONALES desde R4 (CC imposible): la fila original
            #    nunca entró a eventos_sanitarios; se lee fecha y valor crudo
            #    directamente de la hoja de FICHAS.
            cache_r4: dict[tuple[str, str], pd.DataFrame] = {}
            for _, q in r4.iterrows():
                clave = (q.archivo, q.hoja)
                if clave not in cache_r4:
                    cache_r4[clave] = load_sheet(paths[q.archivo], q.hoja)
                df_hoja = cache_r4[clave]
                if q.idx >= len(df_hoja):
                    continue
                fila = df_hoja.iloc[int(q.idx)]
                cols_h = {strip_accents(str(c)).strip().upper(): c for c in df_hoja.columns}
                c_fecha = next((cols_h[k] for k in cols_h if "FECHA" in k), None)
                c_cc = next((cols_h[k] for k in cols_h if "CONDICION" in k), None)
                fecha_real = clean_date(fila[c_fecha]) if c_fecha else None
                cc_crudo = fila[c_cc] if c_cc else None
                cur.execute(
                    """
                    INSERT INTO eventos_sanitarios
                        (id_animal, fecha_evento, id_tipo_evento,
                         observaciones_clinicas, provisional)
                    SELECT id_interno, %s,
                           (SELECT id_tipo_evento FROM cat_tipos_evento WHERE nombre_tipo = 'Revisión'),
                           %s, TRUE
                    FROM animales WHERE numero_visible = %s
                    """,
                    (
                        fecha_real or FECHA_PROVISIONAL,
                        f"[PROVISIONAL] CC imposible ({cc_crudo}) pendiente Robin",
                        _animal_de_hoja(q.hoja),
                    ),
                )

            # 4) Producción PROVISIONAL desde R3: se conserva el mes del bloque
            #    si el motivo lo menciona; día y litros van en 1/0 marcadores.
            for _, q in r3.iterrows():
                mes = 1
                match = re.search(r"bloque ([A-ZÁÉÍÓÚ]+)", q.motivo or "")
                if match:
                    mes = MESES_ES.get(strip_accents(match.group(1)), 1)
                cur.execute(
                    """
                    INSERT INTO produccion_lechera
                        (id_animal, orden_mes, mes, dia, litros,
                         archivo_origen, hoja_origen, provisional)
                    SELECT id_interno, 0, %s, 1, 0, %s, %s, TRUE
                    FROM animales WHERE numero_visible = %s
                    """,
                    (mes, q.archivo, q.hoja, _animal_de_hoja(q.hoja)),
                )

        conn.commit()
        print(f"Provisionales aplicados: {len(pesos)} pesajes reales (OTRO), "
              f"{len(r1)} eventos R1, {len(r4)} eventos R4, {len(r3)} producciones R3.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
