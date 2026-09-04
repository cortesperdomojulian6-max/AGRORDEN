"""Pruebas de aceptación CA-01..CA-07 contra la BD local (spec_etl_ingesta.md §3).

Requieren la instancia PostgreSQL de AGRORDEN activa (scripts/db_start.ps1).
Si no hay conexión, las pruebas de integración se marcan SKIP (no FAIL).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from etl.config import get_connection  # noqa: E402

pytestmark = pytest.mark.acceptance


def fetch_all(query: str) -> list[tuple]:
    try:
        conn = get_connection()
    except Exception:
        pytest.skip("Instancia PostgreSQL AGRORDEN no disponible")
    try:
        with conn.cursor() as cur:
            cur.execute(query)
            return cur.fetchall()
    finally:
        conn.close()


def test_ca01_no_existe_centinela_1900():
    rows = fetch_all(
        """
        SELECT
          (SELECT count(*) FROM animales WHERE fecha_nacimiento = DATE '1900-01-01') +
          (SELECT count(*) FROM eventos_sanitarios WHERE fecha_evento = DATE '1900-01-01') +
          (SELECT count(*) FROM hitos_reproductivos WHERE fecha_revision = DATE '1900-01-01');
        """
    )
    assert rows[0][0] == 0


def test_ca02_toda_cria_m_tiene_madre():
    rows = fetch_all(
        "SELECT count(*) FROM animales WHERE numero_visible LIKE '%-M' AND id_madre IS NULL"
    )
    assert rows[0][0] == 0


def test_ca03_condicion_corporal_en_rango():
    rows = fetch_all(
        """
        SELECT count(*) FROM eventos_sanitarios
        WHERE condicion_corporal IS NOT NULL
          AND (condicion_corporal < 1.0 OR condicion_corporal > 5.0)
        """
    )
    assert rows[0][0] == 0


def test_ca04_resultado_en_catalogo_cerrado():
    rows = fetch_all(
        """
        SELECT DISTINCT resultado FROM hitos_reproductivos
        WHERE resultado NOT IN ('Preñada', 'Vacía', 'Dinámica Folicular')
        """
    )
    assert rows == []


def test_ca05_hojas_pesaje_corresponden_a_animales_con_lote():
    """Animales en lotes Ordeño/Levante/Silvo/Mamon-M (fuente única migración + SPEC-009)."""
    esperado = 76
    rows = fetch_all(
        """
        SELECT count(*) FROM animales a
        JOIN lotes l ON l.id_lote = a.id_lote_actual
        WHERE l.nombre_lote IN ('Ordeño', 'Levante', 'Silvo')
           OR (l.nombre_lote = 'Mamon' AND a.numero_visible LIKE '%-M')
        """
    )
    assert rows[0][0] == esperado


def test_ca07_idempotencia_conteos_estables():
    """Re-ejecutar el sincronizador SPEC-009 no altera los conteos (idempotente)."""
    sync = (Path(__file__).resolve().parent.parent / "scripts" / "sincronizar_2026.py")
    tablas = ["animales", "hitos_reproductivos", "eventos_sanitarios", "etl_cuarentena"]
    conteos_1 = {t: fetch_all(f"SELECT count(*) FROM {t}")[0][0] for t in tablas}

    import subprocess
    result = subprocess.run([sys.executable, str(sync)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr

    conteos_2 = {t: fetch_all(f"SELECT count(*) FROM {t}")[0][0] for t in tablas}
    assert conteos_1 == conteos_2


def test_ca08_conteos_baseline_fuente_unica():
    """Valida conteos post-sincronización SPEC-009 (últimos 3 archivos)."""
    assert fetch_all("SELECT count(*) FROM animales")[0][0] == 87
    assert fetch_all("SELECT count(*) FROM pesajes")[0][0] == 731
    assert fetch_all("SELECT count(*) FROM produccion_lechera")[0][0] == 1428
    assert fetch_all("SELECT count(*) FROM eventos_reproductivos")[0][0] == 139
    assert fetch_all("SELECT count(*) FROM notas_vaca")[0][0] == 4
    assert fetch_all("SELECT count(*) FROM hitos_reproductivos")[0][0] == 10
    assert fetch_all("SELECT count(*) FROM eventos_sanitarios")[0][0] == 0
    assert fetch_all("SELECT count(*) FROM etl_cuarentena")[0][0] == 0
