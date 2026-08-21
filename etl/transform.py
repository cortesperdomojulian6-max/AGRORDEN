"""Transformación: limpieza R1-R5 y resolución de identidad (reglas Robin).

Reglas aplicadas (docs/data_dictionary.md):
    R1  centinela 1900-01-01 -> NULL
    R2  identidad: sufijos de hoja; -M = cría sin chapetear bajo número de madre
    R5  sub-encabezados apilados dentro de los datos
    R4  condición corporal fuera de [1,5] -> cuarentena
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime

import pandas as pd

from etl.extract import LOTE_BY_LETTER, MESES_ES, normalize_label

SENTINEL_DATE: pd.Timestamp = pd.Timestamp(1900, 1, 1)
CONDITION_RANGE: tuple[float, float] = (1.0, 5.0)

RE_HEADER_ROW_VALUES = {"HORA", "OBSERVACION", "OBSERVACIONES", "FECHA"}
RE_PESO_TEXT = re.compile(r"^\s*(\d{2,3}(?:[.,]\d+)?)\s*(kg|k|kgs)?\s*$", re.IGNORECASE)

# Clasificación sanitaria de palabras clave en OBSERVACIONES.
SANITARY_KEYWORDS: dict[str, str] = {
    "aftosa": "Vacunación",
    "bruselosis": "Vacunación",
    "tuberculosis": "Vacunación",
    "prueba": "Revisión",
    "ectoprin": "Tratamiento",
    "ganagras": "Tratamiento",
    "lincocecin": "Tratamiento",
    "antibiot": "Tratamiento",
    "desparasit": "Tratamiento",
    "secado": "Tratamiento",
    "vitamina": "Tratamiento",
    "complejo b": "Tratamiento",
}

KNOWN_PRODUCTS: tuple[str, ...] = (
    "Ectoprin", "Lincocecin", "Ganagras", "Hemopar", "Aftosa",
    "progesterona", "estradiol", "benzoato",
)


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


RE_ISO_DATE = re.compile(r"^\s*\d{4}-\d{1,2}-\d{1,2}")


def clean_date(value) -> date | None:
    """R1: convierte fechas; el centinela 1900-01-01 (fecha o texto) es NULL.

    Formato ISO (YYYY-MM-DD) se parsea sin dayfirst: forzarlo invierte
    día/mes (bug de corrupción detectado por pruebas SPEC-002).
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (datetime, pd.Timestamp)):
        return None if value == SENTINEL_DATE else value.date()
    text = str(value).strip()
    if not text or "1900" in text:
        return None
    parsed = pd.to_datetime(
        value, errors="coerce", dayfirst=not RE_ISO_DATE.match(text)
    )
    if pd.isna(parsed):
        return None
    return None if parsed == SENTINEL_DATE else parsed.date()


def normalize_reproductive(raw_value: str) -> str | None:
    """Normaliza C.PELVICA al catálogo del spec (validado con Robin)."""
    norm = strip_accents(str(raw_value)).strip().upper()
    if not norm:
        return None
    if "PREN" in norm or norm.startswith("PEN"):
        return "Preñada"
    if "VACIA" in norm:
        return "Vacía"
    if "OVARIO" in norm or "OVA " in norm or "OVUL" in norm or "FOLIC" in norm:
        return "Dinámica Folicular"
    return None


@dataclass
class QuarantineRow:
    """Registro para etl_cuarentena."""

    archivo: str
    hoja: str
    fila: int | None
    regla: str
    motivo: str
    payload: dict | None = None


@dataclass
class AnimalRecord:
    """Animal resuelto desde una o varias fuentes."""

    numero_visible: str
    lote_actual: str | None = None
    es_cria_sin_chapear: bool = False
    madre_numero: str | None = None
    nota: str | None = None
    fuentes: set[str] = field(default_factory=set)


@dataclass
class HitoRecord:
    """Hito reproductivo listo para carga."""

    numero_visible: str
    fecha_revision: date
    resultado: str


@dataclass
class EventoRecord:
    """Evento sanitario listo para carga."""

    numero_visible: str
    fecha_evento: date
    tipo_evento: str
    producto_aplicado: str | None
    observaciones_clinicas: str | None
    condicion_corporal: float | None


@dataclass
class PesajeRecord:
    """Pesaje de báscula (SPEC-002 D1): solo lo medido."""

    numero_visible: str
    fecha: date
    peso_kg: float
    archivo_origen: str
    hoja_origen: str


@dataclass
class ProduccionRecord:
    """Registro de ordeño fiel a CURVA (SPEC-002 D2): mes + día + litros.

    El año no se almacena: se deduce al consultar desde la fecha de parto.
    """

    numero_visible: str
    orden_mes: int
    mes: int
    dia: int
    litros: float
    archivo_origen: str
    hoja_origen: str


@dataclass
class EventoReproRecord:
    """Evento reproductivo fechado (SPEC-002 D6)."""

    numero_visible: str
    fecha_evento: date
    tipo_evento: str
    archivo_origen: str
    hoja_origen: str


# Mapeo etiquetas CURVA -> catálogo cerrado (D5/D6 validados por Robin).
# 'Monta' = natural por toro; 'Servicio' = inseminación artificial.
# Orden importa: las etiquetas más específicas van primero porque el
# emparejamiento es por subcadena ('CELO POSPARTO' contiene a 'PARTO').
REPRO_LABEL_MAP: tuple[tuple[str, str], ...] = (
    ("FECHA DE SERVICIO", "Servicio"),
    ("CELO POSPARTO", "Celo Posparto"),
    ("DIAGNOSTICO", "Diagnóstico de Preñez"),
    ("PRENEZ", "Diagnóstico de Preñez"),
    ("SECADO", "Secado"),
    ("MONTA", "Monta"),
    ("PARTO", "Parto"),
)


@dataclass
class TransformResult:
    animales: dict[str, AnimalRecord]
    hitos: list[HitoRecord]
    eventos: list[EventoRecord]
    cuarentena: list[QuarantineRow]


def build_registry(sheets_by_file: dict[str, list]) -> dict[str, AnimalRecord]:
    """Resuelve la identidad de animales a partir de los nombres de hoja.

    Reglas Robin (2026-08-20):
        '-M' -> cría sin chapetear bajo el número de su madre.
        Resto de sufijos -> lote del animal.
        Número plano -> animal sin lote conocido en esa fuente.
    """
    registry: dict[str, AnimalRecord] = {}

    def upsert(numero: str, lote: str | None, fuente: str) -> AnimalRecord:
        record = registry.setdefault(numero, AnimalRecord(numero_visible=numero))
        if lote and not record.lote_actual:
            record.lote_actual = lote
        record.fuentes.add(fuente)
        return record

    for fuente, refs in sheets_by_file.items():
        for ref in refs:
            if ref.sufijo == "M":
                calf = upsert(f"{ref.numero_base}-M", "Mamon", fuente)
                calf.es_cria_sin_chapear = True
                calf.madre_numero = ref.numero_base
            else:
                upsert(ref.numero_base, LOTE_BY_LETTER.get(ref.sufijo or "", None), fuente)

    for record in list(registry.values()):
        if record.es_cria_sin_chapear and record.madre_numero:
            madre = registry.get(record.madre_numero)
            if madre is None:
                madre = AnimalRecord(
                    numero_visible=record.madre_numero,
                    nota="Madre registrada automáticamente desde cría sin chapetear (regla Robin -M)",
                )
                madre.fuentes.add("auto-madre")
                registry[record.madre_numero] = madre
    return registry


def transform_fichas_sheet(
    df: pd.DataFrame,
    ref_numero: str,
    archivo: str,
    hoja: str,
    result: TransformResult,
) -> None:
    """Aplica las reglas de limpieza y enruta filas de una hoja de FICHAS."""
    cols = {strip_accents(str(c)).strip().upper(): c for c in df.columns if isinstance(c, str)}

    def col(*names: str):
        for name in names:
            for key, original in cols.items():
                if name in key:
                    return original
        return None

    c_fecha = col("FECHA")
    c_pelvica = col("C.PELVICA", "PELVICA")
    c_cc = col("CONDICION CORPORAL")
    c_peso = col("PESO")
    c_obs = col("OBSERVACION")

    header_rows_reported = False

    for idx, row in df.iterrows():
        raw_fecha = row[c_fecha] if c_fecha else None

        # R5: sub-encabezados apilados dentro de los datos.
        pelvica_text = str(row[c_pelvica]).strip().upper() if c_pelvica and pd.notna(row[c_pelvica]) else ""
        fecha_is_label = isinstance(raw_fecha, str) and strip_accents(raw_fecha).strip().upper() in RE_HEADER_ROW_VALUES
        if pelvica_text in RE_HEADER_ROW_VALUES or fecha_is_label:
            if not header_rows_reported:
                result.cuarentena.append(QuarantineRow(archivo, hoja, int(idx), "R5",
                                                       "Sub-encabezado repetido dentro de los datos"))
                header_rows_reported = True
            continue

        fecha = clean_date(raw_fecha)
        obs = str(row[c_obs]).strip() if c_obs and pd.notna(row[c_obs]) else None
        has_content = any(pd.notna(row[c]) for c in (c_pelvica, c_cc, c_peso, c_obs) if c)
        if fecha is None:
            if has_content:
                result.cuarentena.append(QuarantineRow(archivo, hoja, int(idx), "R1",
                                                       "Fila con contenido sin fecha válida",
                                                       {"observaciones": obs}))
            continue

        # Hitos reproductivos desde C.PELVICA.
        if c_pelvica and pd.notna(row[c_pelvica]) and pelvica_text:
            resultado = normalize_reproductive(pelvica_text)
            if resultado:
                result.hitos.append(HitoRecord(ref_numero, fecha, resultado))
            elif pelvica_text:
                # Texto clínico no reproductivo (ej. 'Herida') -> evento sanitario Revisión.
                result.eventos.append(EventoRecord(ref_numero, fecha, "Revisión", None,
                                                   f"{pelvica_text}. {obs}" if obs else pelvica_text, None))

        # Condición corporal con validación R4.
        cc_value: float | None = None
        if c_cc and pd.notna(row[c_cc]):
            cc_num = pd.to_numeric(row[c_cc], errors="coerce")
            if pd.notna(cc_num):
                lo, hi = CONDITION_RANGE
                if lo <= cc_num <= hi:
                    cc_value = float(cc_num)
                else:
                    result.cuarentena.append(QuarantineRow(
                        archivo, hoja, int(idx), "R4",
                        f"Condición corporal imposible ({cc_num}); posible peso mal ubicado",
                        {"fila": [str(v) for v in row.dropna().tolist()[:6]]}))

        # Eventos sanitarios por palabra clave en OBSERVACIONES.
        if obs:
            obs_norm = strip_accents(obs).lower()
            tipo = next((t for kw, t in SANITARY_KEYWORDS.items() if kw in obs_norm), None)
            if tipo:
                producto = next((p for p in KNOWN_PRODUCTS if p.lower() in obs_norm), None)
                result.eventos.append(EventoRecord(ref_numero, fecha, tipo, producto, obs, cc_value))
            elif cc_value is None and not (c_pelvica and pd.notna(row[c_pelvica])):
                peso_match = RE_PESO_TEXT.match(str(row[c_peso])) if c_peso and pd.notna(row[c_peso]) else None
                if peso_match:
                    result.cuarentena.append(QuarantineRow(
                        archivo, hoja, int(idx), "OTRO",
                        "Registro de pesaje sin tabla destino en spec v1",
                        {"peso": peso_match.group(1), "observaciones": obs}))


# ---------------------------------------------------------------------------
# SPEC-002: pesajes, producción CURVA y eventos reproductivos
# ---------------------------------------------------------------------------

def parse_pesajes_sheet(
    df: pd.DataFrame,
    numero_visible: str,
    archivo: str,
    hoja: str,
) -> tuple[list[PesajeRecord], list[QuarantineRow]]:
    """RF-02: extrae (fecha, peso) de una hoja de PESAJE GENERAL.

    Solo persiste lo medido (D1). Fecha inválida/centinela -> R1;
    peso no numérico o <= 0 -> R3; fila vacía se omite sin ruido.
    """
    registros: list[PesajeRecord] = []
    cuarentena: list[QuarantineRow] = []
    cols = {strip_accents(str(c)).strip().upper(): c for c in df.columns if isinstance(c, str)}
    c_fecha = next((cols[k] for k in cols if "FECHA" in k), None)
    c_peso = next((cols[k] for k in cols if "PESO" in k), None)
    if c_fecha is None or c_peso is None:
        cuarentena.append(QuarantineRow(
            archivo, hoja, None, "OTRO",
            "Hoja de pesaje sin columnas FECHA/PESO reconocibles"))
        return registros, cuarentena

    for idx, row in df.iterrows():
        raw_fecha, raw_peso = row[c_fecha], row[c_peso]
        if pd.isna(raw_fecha) and pd.isna(raw_peso):
            continue
        fecha = clean_date(raw_fecha)
        if fecha is None:
            cuarentena.append(QuarantineRow(
                archivo, hoja, int(idx), "R1",
                "Pesaje con fecha inválida o centinela 1900",
                {"peso": str(raw_peso)}))
            continue
        peso = pd.to_numeric(raw_peso, errors="coerce")
        if pd.isna(peso) or peso <= 0:
            cuarentena.append(QuarantineRow(
                archivo, hoja, int(idx), "R3",
                f"Peso imposible o no numérico ({raw_peso})",
                {"fecha": str(fecha)}))
            continue
        registros.append(PesajeRecord(numero_visible, fecha, float(peso), archivo, hoja))
    return registros, cuarentena


def parse_repro_events(
    meta: dict,
    numero_visible: str,
    archivo: str,
    hoja: str,
) -> tuple[list[EventoReproRecord], list[QuarantineRow]]:
    """RF-04: convierte las etiquetas reproductivas de CURVA en eventos fechados.

    Centinela exacto 1900-01-01 = ausencia legítima del evento -> omisión
    silenciosa. Cualquier otra fecha del año 1900 (ej. SECADO=1900-08-11,
    spec §4.2) es dato corrupto -> cuarentena R1.
    """
    eventos: list[EventoReproRecord] = []
    cuarentena: list[QuarantineRow] = []
    for label, value in meta.items():
        label_norm = normalize_label(label)
        tipo = next((t for key, t in REPRO_LABEL_MAP if key in label_norm), None)
        if tipo is None:
            continue
        if isinstance(value, (datetime, pd.Timestamp)):
            parsed = clean_date(value)
        elif isinstance(value, str):
            parsed = clean_date(value)
        else:
            continue
        if parsed is None:
            continue
        if parsed.year == 1900:
            cuarentena.append(QuarantineRow(
                archivo, hoja, None, "R1",
                f"{tipo}: fecha con año centinela 1900 ({value})",
                {"etiqueta": label}))
            continue
        eventos.append(EventoReproRecord(numero_visible, parsed, tipo, archivo, hoja))
    return eventos, cuarentena


def parse_produccion_curva(
    grid: pd.DataFrame,
    bloques: list[tuple[str, int, int]],
    numero_visible: str,
    archivo: str,
    hoja: str,
) -> tuple[list[ProduccionRecord], list[QuarantineRow]]:
    """RF-03: desapivota los bloques mensuales Días/Litros de una hoja CURVA.

    Celda vacía de litros = ausencia de medición -> omisión silenciosa.
    Día inválido o litros negativos -> R3. Mes desconocido -> OTRO.
    """
    registros: list[ProduccionRecord] = []
    cuarentena: list[QuarantineRow] = []
    for orden, (nombre, c_dia, c_litro) in enumerate(bloques):
        mes = MESES_ES.get(nombre)
        if mes is None:
            cuarentena.append(QuarantineRow(
                archivo, hoja, None, "OTRO",
                f"Bloque mensual desconocido '{nombre}'"))
            continue
        for idx, row in grid.iterrows():
            if c_litro >= len(row):
                continue
            litros = pd.to_numeric(row[c_litro], errors="coerce")
            if pd.isna(litros):
                continue
            dia_raw = row[c_dia] if c_dia < len(row) else None
            dia = pd.to_numeric(dia_raw, errors="coerce")
            if pd.isna(dia) or not (1 <= dia <= 31) or float(dia) != int(dia):
                cuarentena.append(QuarantineRow(
                    archivo, hoja, int(idx), "R3",
                    f"Día inválido en bloque {nombre} ({dia_raw})",
                    {"litros": float(litros)}))
                continue
            if litros < 0:
                cuarentena.append(QuarantineRow(
                    archivo, hoja, int(idx), "R3",
                    f"Litros negativos en bloque {nombre} ({litros})",
                    {"dia": int(dia)}))
                continue
            registros.append(ProduccionRecord(
                numero_visible, orden, mes, int(dia), float(litros), archivo, hoja))
    return registros, cuarentena
