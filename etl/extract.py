"""Extracción: lectura de los Excel fuente con detección de encabezados.

Estructuras descubiertas en el perfilado (docs/profiling_report_2026-08-20.md):
    FICHAS TECNICAS : hoja por animal, encabezados profundos (fila ~19).
    CURVA/PESAJE    : hoja por animal (con o sin sufijo de lote) + paneles.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

HEADER_SCAN_ROWS: int = 25

RE_SHEET_ANIMAL = re.compile(r"^\s*(\d+)\s*[-_]\s*([A-Za-z])\s*$")
RE_SHEET_PLAIN_ID = re.compile(r"^\s*(\d+)\s*$")

# Sufijo -> lote. Validado por Robin (2026-08-20).
LOTE_BY_LETTER: dict[str, str] = {
    "O": "Ordeño",
    "L": "Levante",
    "M": "Mamon",
    "S": "Silvo",
}


@dataclass(frozen=True)
class SheetRef:
    """Referencia a una hoja de animal dentro de un archivo."""

    path: Path
    sheet: str
    numero_base: str
    sufijo: str | None


def resolve_source_files(raw_dir: Path) -> dict[str, Path]:
    """Localiza los 3 archivos fuente por patrón de nombre."""
    patterns = {
        "fichas": "FICHAS TECNICAS*.xlsx",
        "curva": "7.CURVA*ACTUALIZADO*.xlsx",
        "pesaje": "PESAJE GENERAL*.xlsx",
    }
    found: dict[str, Path] = {}
    for key, pattern in patterns.items():
        matches = [p for p in raw_dir.glob(pattern) if not p.name.startswith("~$")]
        if len(matches) != 1:
            raise FileNotFoundError(f"Se esperaba 1 archivo para '{key}', hubo {len(matches)}: {pattern}")
        found[key] = matches[0]
    return found


def parse_sheet_identity(sheet_name: str) -> tuple[str | None, str | None]:
    """Devuelve (numero_base, letra_sufijo) si la hoja es de animal."""
    match = RE_SHEET_ANIMAL.match(sheet_name)
    if match:
        return match.group(1), match.group(2).upper()
    match = RE_SHEET_PLAIN_ID.match(sheet_name)
    if match:
        return match.group(1), None
    return None, None


def iter_animal_sheets(path: Path):
    """Genera SheetRef para cada hoja de animal del archivo."""
    names = list(pd.read_excel(path, sheet_name=None, nrows=0))
    for sheet in names:
        numero, sufijo = parse_sheet_identity(str(sheet))
        if numero is not None:
            yield SheetRef(path=path, sheet=str(sheet), numero_base=numero, sufijo=sufijo)


def detect_header_row(raw: pd.DataFrame) -> int | None:
    """Fila con más celdas de texto no nulas entre las primeras filas."""
    limit = min(len(raw), HEADER_SCAN_ROWS)
    best_idx: int | None = None
    best_score = 0
    for idx in range(limit):
        cells = raw.iloc[idx].dropna()
        score = sum(1 for v in cells if isinstance(v, str) and v.strip())
        if score > best_score:
            best_score = score
            best_idx = idx
    return best_idx if best_score >= 3 else None


def load_sheet(path: Path, sheet: str) -> pd.DataFrame:
    """Carga una hoja usando su fila de encabezado real."""
    raw_head = pd.read_excel(path, sheet_name=sheet, header=None, nrows=HEADER_SCAN_ROWS)
    header_row = detect_header_row(raw_head)
    return pd.read_excel(path, sheet_name=sheet, header=header_row if header_row is not None else 0)
