"""Pruebas unitarias SPEC-002: pesajes, producción CURVA y eventos reproductivos.

Contratos definidos en docs/spec_pesajes_produccion.md §3.2 (RF-01..RF-04).
Escritas ANTES de la implementación (flujo SDD).
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from etl.extract import MESES_ES
from etl.transform import (
    EventoReproRecord,
    PesajeRecord,
    ProduccionRecord,
    parse_pesajes_sheet,
    parse_produccion_curva,
    parse_repro_events,
)

ARCHIVO = "PESAJE GENERAL CORREGIDO v2.xlsx"
HOJA = "5090-O"


# ---------------------------------------------------------------------------
# RF-02 · parse_pesajes_sheet
# ---------------------------------------------------------------------------

def _pesajes_df(fechas, pesos):
    return pd.DataFrame({"FECHA": fechas, "PESO (kg)": pesos})


def test_pesajes_validos_solo_lo_medido():
    df = _pesajes_df(
        ["2026-01-08", "2026-01-23"],
        [503.0, 511.0],
    )
    registros, cuarentena = parse_pesajes_sheet(df, "5090", ARCHIVO, HOJA)
    assert cuarentena == []
    assert registros == [
        PesajeRecord("5090", date(2026, 1, 8), 503.0, ARCHIVO, HOJA),
        PesajeRecord("5090", date(2026, 1, 23), 511.0, ARCHIVO, HOJA),
    ]


def test_pesajes_peso_imposible_va_a_cuarentena():
    df = _pesajes_df(["2026-01-08", "2026-02-01"], [503.0, 0.0])
    registros, cuarentena = parse_pesajes_sheet(df, "5090", ARCHIVO, HOJA)
    assert len(registros) == 1
    assert len(cuarentena) == 1
    assert cuarentena[0].regla == "R3"
    assert "peso" in cuarentena[0].motivo.lower()


def test_pesajes_fecha_centinela_va_a_cuarentena():
    df = _pesajes_df([pd.Timestamp(1900, 1, 1)], [480.0])
    registros, cuarentena = parse_pesajes_sheet(df, "5090", ARCHIVO, HOJA)
    assert registros == []
    assert len(cuarentena) == 1
    assert cuarentena[0].regla == "R1"


def test_pesajes_fila_vacia_se_omite_silenciosamente():
    df = _pesajes_df([None, "2026-01-08"], [None, 503.0])
    registros, cuarentena = parse_pesajes_sheet(df, "5090", ARCHIVO, HOJA)
    assert cuarentena == []
    assert len(registros) == 1


def test_pesajes_peso_no_numerico_va_a_cuarentena():
    df = _pesajes_df(["2026-01-08"], ["sin dato"])
    registros, cuarentena = parse_pesajes_sheet(df, "5090", ARCHIVO, HOJA)
    assert registros == []
    assert len(cuarentena) == 1
    assert cuarentena[0].regla == "R3"


# ---------------------------------------------------------------------------
# RF-04 · parse_repro_events (mapeo etiquetas CURVA -> catálogo cerrado D6)
# ---------------------------------------------------------------------------

def _meta(**kwargs):
    base = {
        "PARTO": pd.Timestamp(2026, 6, 16),
        "MONTA": pd.Timestamp(2025, 9, 4),
        "FECHA DE SERVICIO": pd.Timestamp(1900, 1, 1),
        "PREÑEZ": pd.Timestamp(2026, 8, 5),
        "1ER CELO POSPARTO": pd.Timestamp(2026, 7, 31),
        "2DO CELO POSPARTO": pd.Timestamp(2026, 8, 21),
        "SECADO": pd.Timestamp(1900, 8, 11),
    }
    base.update(kwargs)
    return base


def test_eventos_mapean_al_catalogo_cerrado():
    """El centinela 1900-01-01 de FECHA DE SERVICIO omite 'Servicio' (regla R1)."""
    eventos, cuarentena = parse_repro_events(_meta(), "12954", "curva.xlsx", "12954")
    tipos = sorted(e.tipo_evento for e in eventos)
    assert tipos == sorted([
        "Parto", "Monta", "Diagnóstico de Preñez",
        "Celo Posparto", "Celo Posparto",
    ])  # 'Secado' ausente: su fecha 1900-08-11 va a cuarentena R1 (ver test abajo)
    parto = next(e for e in eventos if e.tipo_evento == "Parto")
    assert parto.fecha_evento == date(2026, 6, 16)


def test_eventos_monta_y_servicio_son_distintos():
    meta = _meta()
    meta["FECHA DE SERVICIO"] = pd.Timestamp(2026, 8, 5)
    eventos, _ = parse_repro_events(meta, "12954", "curva.xlsx", "12954")
    monta = next(e for e in eventos if e.tipo_evento == "Monta")
    servicio = next(e for e in eventos if e.tipo_evento == "Servicio")
    assert monta.fecha_evento == date(2025, 9, 4)
    assert servicio.fecha_evento == date(2026, 8, 5)


def test_eventos_sentinela_exacto_se_omite_silenciosamente():
    """1900-01-01 = ausencia legítima del evento; no ensucia la cuarentena."""
    eventos, cuarentena = parse_repro_events(_meta(), "12954", "curva.xlsx", "12954")
    servicio = [e for e in eventos if e.tipo_evento == "Servicio"]
    assert servicio == []
    assert all("Servicio" not in q.motivo for q in cuarentena)


def test_eventos_ano_1900_variante_va_a_cuarentena_r1():
    """SECADO=1900-08-11: día/mes válidos con año centinela -> R1 (spec §4.2)."""
    eventos, cuarentena = parse_repro_events(_meta(), "12954", "curva.xlsx", "12954")
    assert all(e.tipo_evento != "Secado" for e in eventos)
    assert any(q.regla == "R1" and "Secado" in q.motivo for q in cuarentena)


def test_eventos_etiqueta_desconocida_se_ignora():
    meta = _meta()
    meta["DATO RARO"] = pd.Timestamp(2026, 1, 1)
    eventos, cuarentena = parse_repro_events(meta, "12954", "curva.xlsx", "12954")
    assert all(e.tipo_evento != "DATO RARO" for e in eventos)


# ---------------------------------------------------------------------------
# RF-03 · parse_produccion_curva (desapivotar bloques mensuales)
# ---------------------------------------------------------------------------

def _grid_bloques(columnas_por_bloque):
    """Construye un grid crudo: lista de (nombre_mes, dias[], litros[])."""
    cols, ancho = [], 0
    bloques = []
    for nombre, dias, litros in columnas_por_bloque:
        cols.append((nombre, ancho, ancho + 1))
        bloques.append((dias, litros))
        ancho += 2
    filas = max((len(d) for d, _ in bloques), default=0)
    data = [[None] * ancho for _ in range(filas)]
    for (dias, litros), (_, cd, cl) in zip(bloques, cols):
        for i in range(filas):
            if i < len(dias):
                data[i][cd] = dias[i]
                data[i][cl] = litros[i]
    return pd.DataFrame(data), cols


def test_meses_es_cubre_doce_meses():
    assert len(MESES_ES) == 12
    assert MESES_ES["JUNIO"] == 6
    assert MESES_ES["DICIEMBRE"] == 12


def test_produccion_desapivota_bloques_y_omite_vacios():
    grid, cols = _grid_bloques([
        ("JUNIO", [1, 2, 3], [2.0, None, 6.0]),
        ("JULIO", [1, 2], [3.5, 4.0]),
    ])
    registros, cuarentena = parse_produccion_curva(grid, cols, "12954", "curva.xlsx", "12954")
    assert cuarentena == []
    assert registros == [
        ProduccionRecord("12954", 0, 6, 1, 2.0, "curva.xlsx", "12954"),
        ProduccionRecord("12954", 0, 6, 3, 6.0, "curva.xlsx", "12954"),
        ProduccionRecord("12954", 1, 7, 1, 3.5, "curva.xlsx", "12954"),
        ProduccionRecord("12954", 1, 7, 2, 4.0, "curva.xlsx", "12954"),
    ]


def test_produccion_litros_negativo_va_a_cuarentena():
    grid, cols = _grid_bloques([("AGOSTO", [5], [-1.0])])
    registros, cuarentena = parse_produccion_curva(grid, cols, "12954", "curva.xlsx", "12954")
    assert registros == []
    assert len(cuarentena) == 1
    assert cuarentena[0].regla == "R3"


def test_produccion_dia_invalido_va_a_cuarentena():
    grid, cols = _grid_bloques([("AGOSTO", [32], [3.0])])
    registros, cuarentena = parse_produccion_curva(grid, cols, "12954", "curva.xlsx", "12954")
    assert registros == []
    assert len(cuarentena) == 1
    assert cuarentena[0].regla == "R3"


def test_produccion_mes_desconocido_se_reporta():
    grid, cols = _grid_bloques([("MESX", [1], [2.0])])
    registros, cuarentena = parse_produccion_curva(grid, cols, "12954", "curva.xlsx", "12954")
    assert registros == []
    assert len(cuarentena) == 1
