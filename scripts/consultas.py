"""Consultas e indicadores del hato sin necesidad de SQL (SPEC-004 RF-06).

Uso:
    python scripts/consultas.py            # todos los reportes
    python scripts/consultas.py dias       # solo días abiertos
    python scripts/consultas.py peso       # solo ganancia de peso
    python scripts/consultas.py produccion # solo pico de lactancia
    python scripts/consultas.py hato       # solo resumen del hato
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg2.extras

from etl.config import get_connection

SEPARADOR = "=" * 64


def _imprimir_tabla(titulos: list[str], filas: list[tuple]) -> None:
    if not filas:
        print("  (sin datos)")
        return
    anchos = [len(t) for t in titulos]
    for fila in filas:
        for i, valor in enumerate(fila):
            anchos[i] = max(anchos[i], len(str(valor)))
    linea = " | ".join(str(t).ljust(anchos[i]) for i, t in enumerate(titulos))
    print(linea)
    print("-" * len(linea))
    for fila in filas:
        print(" | ".join(str(v).ljust(anchos[i]) for i, v in enumerate(fila)))


def reporte_hato(conn) -> None:
    print(SEPARADOR)
    print("RESUMEN DEL HATO")
    print(SEPARADOR)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COALESCE(nombre_lote,'(sin lote)'), hembras, machos, total "
            "FROM v_resumen_hato"
        )
        _imprimir_tabla(["LOTE", "HEMBRAS", "MACHOS", "TOTAL"], cur.fetchall())
    print()


def reporte_dias_abiertos(conn, limite: int = 15) -> None:
    print(SEPARADOR)
    print("DÍAS ABIERTOS (más críticos primero)")
    print(SEPARADOR)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT numero_visible, fecha_parto, fecha_cubricion, dias_abiertos
            FROM v_dias_abiertos
            WHERE dias_abiertos IS NOT NULL
            ORDER BY dias_abiertos DESC
            LIMIT %s
            """,
            (limite,),
        )
        _imprimir_tabla(
            ["VACA", "ULT. PARTO", "ULT. CUBRICION", "DIAS ABIERTOS"],
            cur.fetchall(),
        )
        cur.execute(
            "SELECT COUNT(*), ROUND(AVG(dias_abiertos),0) "
            "FROM v_dias_abiertos WHERE dias_abiertos IS NOT NULL"
        )
        n, promedio = cur.fetchone()
        print(f"\n  {n} vacas con cálculo posible · promedio {promedio} días abiertos")
    print()


def reporte_peso(conn, limite: int = 15) -> None:
    print(SEPARADOR)
    print("GANANCIA DE PESO MÁS RECIENTE (g/día)")
    print(SEPARADOR)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT ON (numero_visible)
                numero_visible, fecha_anterior, fecha_actual, peso_actual, g_dia
            FROM v_ganancia_peso
            ORDER BY numero_visible, fecha_actual DESC
            """
        )
        recientes = cur.fetchall()
        ordenadas = sorted(recientes, key=lambda r: r[4] if r[4] is not None else 0)
        peores = ordenadas[: limite // 2]
        mejores = ordenadas[-(limite - limite // 2):][::-1]
        print("  Mayores ganancias:")
        _imprimir_tabla(
            ["VACA", "DESDE", "HASTA", "PESO KG", "G/DIA"],
            mejores,
        )
        print("\n  Mayores pérdidas:")
        _imprimir_tabla(
            ["VACA", "DESDE", "HASTA", "PESO KG", "G/DIA"],
            peores,
        )
    print()


def reporte_produccion(conn, limite: int = 10) -> None:
    print(SEPARADOR)
    print("PICO DE LACTANCIA POR VACA")
    print(SEPARADOR)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT numero_visible, fecha_pico, litros_pico
            FROM v_pico_lactancia
            WHERE litros_pico IS NOT NULL
            ORDER BY litros_pico DESC
            LIMIT %s
            """,
            (limite,),
        )
        _imprimir_tabla(["VACA", "FECHA PICO", "LITROS"], cur.fetchall())
    print()


REPORTES = {
    "hato": reporte_hato,
    "dias": reporte_dias_abiertos,
    "peso": reporte_peso,
    "produccion": reporte_produccion,
}


def main() -> int:
    pedidos = sys.argv[1:] or list(REPORTES)
    conn = get_connection()
    try:
        for nombre in pedidos:
            if nombre in REPORTES:
                REPORTES[nombre](conn)
            else:
                print(f"Reporte desconocido: {nombre}. "
                      f"Opciones: {', '.join(REPORTES)}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
