"""Pruebas de aceptación SPEC-004: vistas de consulta e indicadores.

Verifican las fórmulas contra la BD real (docs/spec_consultas_indicadores.md).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from etl.config import get_connection


@pytest.fixture(scope="module")
def conn():
    connection = get_connection()
    yield connection
    connection.close()


def _fetch(conn, sql: str):
    with conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchall()


def test_ca01_dias_abiertos_nunca_negativos(conn):
    filas = _fetch(conn, "SELECT dias_abiertos FROM v_dias_abiertos")
    valores = [fila[0] for fila in filas if fila[0] is not None]
    assert all(d >= 0 for d in valores)


def test_ca02_ganancia_5090_coincide_con_excel(conn):
    """5090: 503 kg el 08/01 -> 511 kg el 23/01/2026 = 15 días => 533 g/día."""
    filas = _fetch(
        conn,
        """
        SELECT g_dia FROM v_ganancia_peso
        WHERE numero_visible = '5090'
          AND fecha_anterior = DATE '2026-01-08'
          AND fecha_actual = DATE '2026-01-23'
        """,
    )
    assert filas and int(filas[0][0]) == 533


def test_ca03_fechas_produccion_validas(conn):
    """La vista solo emite fechas de calendario válidas (excluye ej. 30-feb).

    Nota: existen litros registrados en días previos al parto dentro del mes
    del parto (plantilla de Robin). Se muestra fielmente; validación biológica
    queda como pregunta pendiente para Robin (SPEC-005).
    """
    filas = _fetch(
        conn,
        "SELECT fecha_real, fecha_parto FROM v_produccion_con_fecha",
    )
    assert filas, "la vista no devolvió registros"
    for fecha_real, _ in filas:
        assert fecha_real.year >= 2025


def test_ca04_vistas_excluyen_provisionales(conn):
    # Pesajes provisionales existen (SPEC-003): ninguno debe aparecer en la vista.
    total_provisionales = _fetch(
        conn, "SELECT COUNT(*) FROM pesajes WHERE provisional"
    )[0][0]
    en_vista = _fetch(
        conn,
        """
        SELECT COUNT(*) FROM v_ganancia_peso g
        JOIN pesajes p1 ON p1.id_animal = g.id_animal AND p1.fecha = g.fecha_actual
        JOIN pesajes p2 ON p2.id_animal = g.id_animal AND p2.fecha = g.fecha_anterior
        WHERE p1.provisional OR p2.provisional
        """,
    )[0][0]
    if total_provisionales:
        assert en_vista == 0


def test_ca05_resumen_hato_cuadra_con_animales(conn):
    total_vista = _fetch(conn, "SELECT SUM(total) FROM v_resumen_hato")[0][0]
    total_tabla = _fetch(conn, "SELECT COUNT(*) FROM animales")[0][0]
    assert total_vista == total_tabla
