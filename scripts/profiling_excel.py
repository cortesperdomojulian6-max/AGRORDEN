"""Perfilador de datos sucios v2 para los Excel fuente del ERP Ganadero AGRORDEN.

Mejoras sobre v1 (hallazgos del primer perfilado):
    1. Auto-detección de la fila de encabezados real por hoja (los Excel usan
       filas de título/fusión antes de los headers).
    2. Escaneo de datos sucios POR VALOR en todas las columnas, no dependiente
       de nombres de columna.
    3. Parseo del nombre de hoja como fuente de identidad:
       '5090-O' -> numero_visible=5090, lote inferido por sufijo.

Reglas detectadas (docs/data_dictionary.md):
    R1: fechas centinela '1900-01-01'.
    R2: identificadores con sufijo ('5090-O', '5090-M').
    R3: celdas de texto mixto (candidatas a separación estructurada).
    R4: condición corporal fuera de [1.0, 5.0].

Uso:
    python scripts/profiling_excel.py            # resumen agregado por archivo
    ETL_VERBOSE=1 python scripts/profiling_excel.py   # detalle hoja por hoja

Configuración (.env, ver .env.example):
    ETL_RAW_DIR    Carpeta de los Excel originales.
    ETL_FILES      Lista explícita de archivos (separada por os.pathsep).
    ETL_VERBOSE    '1' para detalle por hoja.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

REPO_ROOT: Path = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")

SENTINEL_DATE: pd.Timestamp = pd.Timestamp(1900, 1, 1)
SENTINEL_STRINGS: tuple[str, ...] = ("1900-01-01", "1900/01/01", "01/01/1900")
CONDITION_RANGE: tuple[float, float] = (1.0, 5.0)
MIXED_TEXT_MIN_MEAN_LEN: int = 40
HEADER_SCAN_ROWS: int = 25
MAX_SAMPLES: int = 6

# Sufijo de hoja -> lote. Validado por Robin (2026-08-20).
LOTE_BY_LETTER: dict[str, str] = {
    "O": "Ordeño",
    "L": "Levante",
    "M": "Mamon",
    "S": "Silvo",
}

RE_SHEET_ANIMAL = re.compile(r"^\s*(\d+)\s*[-_]\s*([A-Za-z])\s*$")
RE_SHEET_PLAIN_ID = re.compile(r"^\s*(\d+)\s*$")
RE_ID_SUFFIXED_VALUE = re.compile(r"^\s*(\d+)\s*[-_]\s*[A-Za-z]+\s*$")
RE_CONDITION_COLUMN = re.compile(r"(condici[oó]n|corporal|^cc$|_cc$)", re.IGNORECASE)
RE_SENTINEL_TEXT = re.compile(r"1900[-/ ]0?1[-/ ]0?1")


@dataclass
class SheetProfile:
    """Resultado del perfilado de una hoja."""

    name: str
    header_row: int | None = None
    animal_id: str | None = None
    lote_inferido: str | None = None
    rows: int = 0
    columns: int = 0
    null_cells: int = 0
    r1_sentinel_dates: int = 0
    r2_suffixed_ids: int = 0
    r2_samples: list[str] = field(default_factory=list)
    r3_mixed_text_columns: list[str] = field(default_factory=list)
    r4_out_of_range: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def has_findings(self) -> bool:
        return bool(
            self.r1_sentinel_dates
            or self.r2_suffixed_ids
            or self.r3_mixed_text_columns
            or self.r4_out_of_range
            or self.errors
        )


@dataclass
class FileProfile:
    """Agregado de todas las hojas de un archivo."""

    path: Path
    sheets: list[SheetProfile] = field(default_factory=list)
    open_error: str | None = None

    @property
    def animal_sheets(self) -> list[SheetProfile]:
        return [s for s in self.sheets if s.animal_id is not None]

    def lote_distribution(self) -> dict[str, int]:
        dist: dict[str, int] = {}
        for s in self.animal_sheets:
            key = s.lote_inferido or "(sin sufijo)"
            dist[key] = dist.get(key, 0) + 1
        return dist


def resolve_files() -> list[Path]:
    """Resuelve la lista de Excel a perfilar desde variables de entorno."""
    explicit = os.environ.get("ETL_FILES", "").strip()
    if explicit:
        return [Path(p) for p in explicit.split(os.pathsep) if Path(p).is_file()]

    raw_dir = Path(os.environ.get("ETL_RAW_DIR", str(REPO_ROOT / "data" / "raw")))
    if not raw_dir.is_dir():
        raise FileNotFoundError(f"ETL_RAW_DIR no existe: {raw_dir}")

    return sorted(p for p in raw_dir.glob("*.xlsx") if not p.name.startswith("~$"))


def parse_sheet_name(name: str) -> tuple[str | None, str | None]:
    """Extrae (numero_visible, lote) del nombre de la hoja."""
    match = RE_SHEET_ANIMAL.match(name)
    if match:
        return match.group(1), LOTE_BY_LETTER.get(match.group(2).upper())
    match = RE_SHEET_PLAIN_ID.match(name)
    if match:
        return match.group(1), None
    return None, None


def detect_header_row(raw: pd.DataFrame) -> int | None:
    """Detecta la fila de encabezados escaneando las primeras filas.

    Heurística: la fila con más celdas de texto no nulas es el encabezado;
    las filas previas se asumen títulos/celdas fusionadas.
    """
    limit = min(len(raw), HEADER_SCAN_ROWS)
    best_idx: int | None = None
    best_score = 0
    for idx in range(limit):
        cells = raw.iloc[idx].dropna()
        text_cells = sum(1 for v in cells if isinstance(v, str) and v.strip())
        if text_cells > best_score:
            best_score = text_cells
            best_idx = idx
    return best_idx if best_score >= 3 else None


def load_sheet_smart(path: Path, sheet: str) -> tuple[pd.DataFrame, int | None]:
    """Carga una hoja usando la fila de encabezado detectada."""
    raw_head = pd.read_excel(path, sheet_name=sheet, header=None, nrows=HEADER_SCAN_ROWS)
    header_row = detect_header_row(raw_head)
    df = pd.read_excel(path, sheet_name=sheet, header=header_row if header_row is not None else 0)
    return df, header_row


def _count_sentinel_datetime(series: pd.Series) -> int:
    parsed = pd.to_datetime(series, errors="coerce")
    return int((parsed == SENTINEL_DATE).sum())


def _count_sentinel_text(series: pd.Series) -> int:
    texts = series.dropna().astype(str)
    return int(texts.str.contains(RE_SENTINEL_TEXT).sum())


def profile_sheet(df: pd.DataFrame, sheet_name: str) -> SheetProfile:
    """Aplica R1-R4 por valor sobre la hoja ya cargada con su encabezado real."""
    prof = SheetProfile(name=sheet_name, rows=len(df), columns=len(df.columns))
    prof.animal_id, prof.lote_inferido = parse_sheet_name(sheet_name)
    prof.null_cells = int(df.isna().sum().sum())

    for col in df.columns:
        series = df[col]
        col_name = str(col)

        try:
            # R1 por valor: aplica a cualquier columna, con o sin 'fecha' en el nombre.
            if pd.api.types.is_datetime64_any_dtype(series):
                prof.r1_sentinel_dates += int((series == SENTINEL_DATE).sum())
            elif series.dtype == object:
                prof.r1_sentinel_dates += _count_sentinel_datetime(series)
                prof.r1_sentinel_dates += _count_sentinel_text(series)

            # R2 por valor: IDs con sufijo en cualquier columna de texto.
            if series.dtype == object:
                values = series.dropna().astype(str)
                suffixed = values[values.str.match(RE_ID_SUFFIXED_VALUE)]
                prof.r2_suffixed_ids += len(suffixed)
                for value in suffixed.unique()[:MAX_SAMPLES]:
                    sample = f"{col_name}='{value}'"
                    if sample not in prof.r2_samples:
                        prof.r2_samples.append(sample)

            # R3: columnas de texto denso (candidatas a separación).
            if series.dtype == object:
                texts = series.dropna().astype(str)
                if not texts.empty and texts.str.len().mean() >= MIXED_TEXT_MIN_MEAN_LEN:
                    prof.r3_mixed_text_columns.append(col_name)

            # R4: condición corporal fuera de rango (por nombre de columna).
            if RE_CONDITION_COLUMN.search(col_name):
                numeric = pd.to_numeric(series, errors="coerce").dropna()
                lo, hi = CONDITION_RANGE
                prof.r4_out_of_range += int(((numeric < lo) | (numeric > hi)).sum())
        except Exception as exc:  # noqa: BLE001 - aislamiento por columna
            prof.errors.append(f"{col_name}: {exc}")

    prof.r2_samples = prof.r2_samples[:MAX_SAMPLES]
    return prof


def report_file(fp: FileProfile, verbose: bool) -> None:
    """Imprime el perfil agregado de un archivo."""
    line = "=" * 78
    print(f"\n{line}\nARCHIVO: {fp.path.name}\n{line}")
    if fp.open_error:
        print(f"[ERROR] No se pudo abrir: {fp.open_error}")
        return

    animals = fp.animal_sheets
    print(f"Hojas totales           : {len(fp.sheets)}")
    print(f"Hojas de animal parseadas: {len(animals)} "
          f"({len({a.animal_id for a in animals})} IDs únicos)")
    print(f"Distribución por lote   : {fp.lote_distribution()}")

    total_r1 = sum(s.r1_sentinel_dates for s in fp.sheets)
    total_r2 = sum(s.r2_suffixed_ids for s in fp.sheets)
    total_r4 = sum(s.r4_out_of_range for s in fp.sheets)
    sheets_r3 = sorted({c for s in fp.sheets for c in s.r3_mixed_text_columns})
    samples_r2 = sorted({v for s in fp.sheets for v in s.r2_samples})[:MAX_SAMPLES]

    print(f"[R1] Centinelas 1900-01-01 : {total_r1}")
    print(f"[R2] IDs con sufijo        : {total_r2}"
          f"{('  ej: ' + '; '.join(samples_r2)) if samples_r2 else ''}")
    print(f"[R3] Columnas texto mixto  : {', '.join(sheets_r3) if sheets_r3 else 'ninguna'}")
    print(f"[R4] Cond. corporal inválida: {total_r4}")

    if verbose:
        for s in fp.sheets:
            flag = "*" if s.has_findings else " "
            lote = s.lote_inferido or "-"
            print(f" {flag} {s.name[:28]:<28} id={s.animal_id or '-':<7} lote={lote:<8} "
                  f"{s.rows:>4}x{s.columns:<3} hdr={str(s.header_row):<4} "
                  f"R1={s.r1_sentinel_dates:<4} R2={s.r2_suffixed_ids:<4} R4={s.r4_out_of_range}")
            for err in s.errors:
                print(f"     [WARN] {s.name}: {err}")


def main() -> int:
    verbose = os.environ.get("ETL_VERBOSE", "") == "1"
    files = resolve_files()
    if not files:
        print("No se encontraron archivos .xlsx para perfilar.", file=sys.stderr)
        return 2

    print(f"Archivos en alcance: {len(files)}")
    ok = 0
    for path in files:
        fp = FileProfile(path=path)
        try:
            sheet_names = list(pd.read_excel(path, sheet_name=None, nrows=0))
        except Exception as exc:  # noqa: BLE001 - aislamiento por archivo
            fp.open_error = str(exc)
            report_file(fp, verbose)
            continue

        for sheet in sheet_names:
            try:
                df, header_row = load_sheet_smart(path, sheet)
            except Exception as exc:  # noqa: BLE001 - aislamiento por hoja
                sp = SheetProfile(name=sheet)
                sp.errors.append(str(exc))
                fp.sheets.append(sp)
                continue
            sp = profile_sheet(df, sheet)
            sp.header_row = header_row
            fp.sheets.append(sp)

        report_file(fp, verbose)
        ok += 1

    print(f"\nResumen: {ok}/{len(files)} archivo(s) perfilado(s).")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
