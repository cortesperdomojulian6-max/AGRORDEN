"""Carga: escritura transaccional en PostgreSQL con cuarentena."""

from __future__ import annotations

import psycopg2
import psycopg2.extras

from etl.transform import AnimalRecord, EventoRecord, HitoRecord, QuarantineRow

SEXO_PROVISIONAL = "F"


def reset_operational_tables(conn) -> None:
    """Limpieza para recarga completa en desarrollo (orden por dependencias)."""
    with conn.cursor() as cur:
        cur.execute(
            "TRUNCATE etl_cuarentena, hitos_reproductivos, eventos_sanitarios, animales CASCADE"
        )


def load_catalogs(conn) -> tuple[dict[str, str], dict[str, str]]:
    """Devuelve {nombre: uuid} de lotes y tipos de evento."""
    with conn.cursor() as cur:
        cur.execute("SELECT nombre_lote, id_lote::text FROM lotes")
        lotes = dict(cur.fetchall())
        cur.execute("SELECT nombre_tipo, id_tipo_evento::text FROM cat_tipos_evento")
        tipos = dict(cur.fetchall())
    return lotes, tipos


def load_animales(conn, registry: dict[str, AnimalRecord]) -> dict[str, str]:
    """Inserta animales y devuelve mapa numero_visible -> id_interno.

    Dos pasadas: primero animales sin madre (incluye auto-madres), luego crías.
    """
    ids: dict[str, str] = {}
    ordered = sorted(registry.values(), key=lambda r: r.es_cria_sin_chapear)

    with conn.cursor() as cur:
        for record in ordered:
            madre_id = ids.get(record.madre_numero) if record.madre_numero else None
            caracteristicas = record.nota
            cur.execute(
                """
                INSERT INTO animales (numero_visible, sexo, id_lote_actual, id_madre, caracteristicas)
                VALUES (%s, %s,
                        (SELECT id_lote FROM lotes WHERE nombre_lote = %s),
                        %s, %s)
                RETURNING id_interno::text
                """,
                (
                    record.numero_visible,
                    SEXO_PROVISIONAL,
                    record.lote_actual,
                    madre_id,
                    caracteristicas,
                ),
            )
            ids[record.numero_visible] = cur.fetchone()[0]
    return ids


def load_hitos(conn, hitos: list[HitoRecord], ids: dict[str, str]) -> int:
    rows = [
        (ids[h.numero_visible], h.fecha_revision, h.resultado)
        for h in hitos
        if h.numero_visible in ids
    ]
    if rows:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur,
                "INSERT INTO hitos_reproductivos (id_animal, fecha_revision, resultado) VALUES %s",
                rows,
            )
    return len(rows)


def load_eventos(
    conn,
    eventos: list[EventoRecord],
    ids: dict[str, str],
    tipos: dict[str, str],
) -> int:
    rows = [
        (
            ids[e.numero_visible],
            e.fecha_evento,
            tipos.get(e.tipo_evento),
            e.producto_aplicado,
            e.observaciones_clinicas,
            e.condicion_corporal,
        )
        for e in eventos
        if e.numero_visible in ids and e.tipo_evento in tipos
    ]
    if rows:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO eventos_sanitarios
                    (id_animal, fecha_evento, id_tipo_evento, producto_aplicado,
                     observaciones_clinicas, condicion_corporal)
                VALUES %s
                """,
                rows,
            )
    return len(rows)


def load_cuarentena(conn, rows: list[QuarantineRow]) -> int:
    if not rows:
        return 0
    data = [(q.archivo, q.hoja, q.fila, q.regla, q.motivo, psycopg2.extras.Json(q.payload))
            for q in rows]
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO etl_cuarentena
                (origen_archivo, hoja, numero_fila, regla, motivo, payload)
            VALUES %s
            """,
            data,
        )
    return len(rows)
