"""Pruebas unitarias de las reglas de transformación (CA-06, R1, R2, R4)."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from etl.extract import SheetRef, parse_sheet_identity  # noqa: E402
from etl.transform import (  # noqa: E402
    clean_date,
    normalize_reproductive,
    build_registry,
)


class TestR1SentinelaFecha:
    def test_centinela_nativo_es_none(self):
        assert clean_date(pd.Timestamp(1900, 1, 1)) is None

    def test_centinela_como_texto_es_none(self):
        assert clean_date("1900-01-01 00:00:00") is None

    def test_fecha_valida_se_conserva(self):
        assert clean_date(pd.Timestamp(2026, 1, 8)).isoformat() == "2026-01-08"

    def test_vacio_es_none(self):
        assert clean_date(None) is None


class TestR5NormalizacionReproductiva:
    @pytest.mark.parametrize("variante", ["PREÑEZ", "Preñez", "preñez", "Preñada", "Peñada"])
    def test_variantes_prenada(self, variante):
        assert normalize_reproductive(variante) == "Preñada"

    @pytest.mark.parametrize("variante", ["vacia", "Vacia", "VACIA"])
    def test_variantes_vacia(self, variante):
        assert normalize_reproductive(variante) == "Vacía"

    def test_hallazgo_ovarico(self):
        assert normalize_reproductive("ovario derecho ovulado, ovario izquierdo estatico") == \
            "Dinámica Folicular"

    def test_posible_prenez_cuenta_como_prenada(self):
        assert normalize_reproductive("posible preñez") == "Preñada"


class TestR2Identidad:
    def test_hoja_con_sufijo_lote(self):
        assert parse_sheet_identity("5090-O") == ("5090", "O")

    def test_hoja_plana(self):
        assert parse_sheet_identity("12954") == ("12954", None)

    def test_hoja_no_animal(self):
        assert parse_sheet_identity("Panel Reproductivo") == (None, None)

    def test_cria_m_tiene_madre_y_registro_madre_auto(self):
        refs = {
            "pesaje": [
                SheetRef(path=Path("x"), sheet="10482-M", numero_base="10482", sufijo="M"),
                SheetRef(path=Path("x"), sheet="10482-O", numero_base="10482", sufijo="O"),
                SheetRef(path=Path("x"), sheet="15821-M", numero_base="15821", sufijo="M"),
            ]
        }
        registry = build_registry(refs)
        cria = registry["10482-M"]
        assert cria.es_cria_sin_chapear is True
        assert cria.madre_numero == "10482"
        assert cria.lote_actual == "Mamon"
        madre = registry["10482"]
        assert madre.es_cria_sin_chapear is False
        assert madre.lote_actual == "Ordeño"
        madre_auto = registry["15821"]
        assert "auto-madre" in madre_auto.fuentes

    def test_cria_y_madre_son_animales_distintos(self):
        refs = {
            "pesaje": [
                SheetRef(path=Path("x"), sheet="10482-M", numero_base="10482", sufijo="M"),
                SheetRef(path=Path("x"), sheet="10482-O", numero_base="10482", sufijo="O"),
            ]
        }
        registry = build_registry(refs)
        assert len(registry) == 2
