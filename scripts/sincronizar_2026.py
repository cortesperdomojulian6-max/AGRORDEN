r"""Sincronizador 2026 — AGRORDEN ERP Ganadero (SPEC-009).

Recarga idempotente desde los 3 archivos fuente oficiales de
C:\Users\Julian Cortes\Desktop\AGRORDEN:

    * AGROORDEN.xlsx                        -> panel de vientres + fichas
                                              (etapas, eventos reproductivos,
                                               producción diaria del hato)
    * PESAJE GENERAL ... v4 - AUTOMATICO.xlsm -> pesajes de báscula por grupo
                                              (Ordeño/Levante/Mamon/Silvo)
    * Formulaciones_Integrales...xlsx       -> inventario, formulaciones,
                                              requerimientos y costos

Uso:
    python scripts/sincronizar_2026.py
"""

from __future__ import annotations

import datetime as dt
import os
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")

SRC_DIR = Path(r"C:\Users\Julian Cortes\Desktop\AGRORDEN")
AGROORDEN = SRC_DIR / "AGROORDEN.xlsx"
PESAJE = SRC_DIR / "PESAJE GENERAL CORREGIDO v4 - AUTOMATICO.xlsm"
FORMULACIONES = SRC_DIR / "Formulaciones_Integrales_Multinutrientes (1) (1).xlsx"

MESES_ES = {
    "ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4,
    "MAYO": 5, "JUNIO": 6, "JULIO": 7, "AGOSTO": 8,
    "SEPTIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12,
}

ETAPAS_ALLOWED = {
    "ORDEÑO", "ORDEÑO VACIA", "ORDEÑO EMBRION",
    "PREÑEZ", "PREÑADA", "VACIA",
    "HORRA", "VACA HORRA", "VACA VACIA",
    "NOVILLA (H)", "NOVILLA HORRA", "NOVILLA VACIA",
    "NOVILLA EMBRION", "NOVILLA HORRA EMBRION",
    "POSIBLE PREÑEZ", "PROBLEMA",
    "REPRODUCTOR", "TORO", "TERNERA", "TERNEROS",
    "MAMON", "LEVANTE", "MAUTE", "SILVO", "VENDIDA",
}

RE_EVENTO = {
    "1ER CELO POSPARTO": "Celo Posparto",
    "2DO CELO POSPARTO": "Celo Posparto",
    "MONTA": "Monta",
    "PARTO": "Parto",
    "SECADO": "Secado",
    "FECHA DE SERVICIO": "Servicio",
}

RE_SHEET_SUFIX = re.compile(r"^(\d+)-([A-Za-z])$")


def strip_acc(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text)
                   if unicodedata.category(c) != "Mn")


def norm(text) -> str:
    return strip_acc(str(text)).strip().upper()


ETAPAS_OK = {norm(e) for e in ETAPAS_ALLOWED}


def to_date(v) -> dt.date | None:
    if v is None:
        return None
    if isinstance(v, pd.Timestamp):
        return v.date()
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    if isinstance(v, (float, int)) and not np.isnan(v):
        v = str(v)
    s = str(v).strip()
    if not s or re.match(r"^\d{2,3}([.,]\d{1,5})?$", s) or "1900" in s:
        return None
    try:
        return dt.datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def connect_admin():
    return psycopg2.connect(
        host="localhost",
        port=5433,
        dbname="agrorden",
        user="agrorden_admin",
        password=os.environ["PG_SUPER_PASSWORD"],
    )


# ---------------------------------------------------------------------------
# 1) Panel de vientres (AGROORDEN.xlsx)
# ---------------------------------------------------------------------------
def parse_vientres():
    df = pd.read_excel(AGROORDEN, sheet_name="VIENTRES DISPONIBLES DEL SENA ",
                       header=None)
    out: dict[str, dict] = {}
    for r in range(14, 63):          # filas Excel 15..63
        numero = df.iat[r, 1]
        if numero is None or (isinstance(numero, float) and np.isnan(numero)):
            continue
        numero = str(int(numero)).strip()
        etapa = df.iat[r, 2]
        parto_raw = df.iat[r, 3]
        servicio_raw = df.iat[r, 18]
        diag = df.iat[r, 19]
        estado = df.iat[r, 8]
        obs = df.iat[r, 11]
        etapa_s = str(etapa).strip() if isinstance(etapa, str) else None
        if etapa_s == "": etapa_s = None
        diag_s = str(diag).strip() if isinstance(diag, str) else None
        diag_res = ("Preñada" if diag_s and "PREN" in strip_acc(diag_s).upper()
                    else None)
        estado_s = str(estado).strip() if isinstance(estado, str) else None
        obs_s = str(obs).strip() if isinstance(obs, str) else None
        parto = to_date(parto_raw)
        servicio = to_date(servicio_raw)
        out[numero] = {
            "etapa": etapa_s,
            "parto": parto,
            "servicio": servicio,
            "diag": diag_res,
            "estado": estado_s,
            "obs": obs_s,
        }
    return out


# ---------------------------------------------------------------------------
# 2) Fichas de AGROORDEN.xlsx (eventos reproductivos + producción)
# ---------------------------------------------------------------------------
def parse_fichas(vientres):
    nombres = [n for n in pd.ExcelFile(AGROORDEN).sheet_names
               if re.fullmatch(r"\d+", n)]
    dfs = pd.read_excel(AGROORDEN, sheet_name=nombres, header=None)
    hoy = dt.date.today()

    eventos: list[tuple[str, str, dt.date]] = []
    produccion: list[tuple[str, int, int, int, float]] = []
    produccion_hoja: dict[str, float] = {}
    diag_hitos: list[tuple[str, str, dt.date]] = []
    errores: list[str] = []

    for nm in sorted(nombres, key=lambda x: int(x)):
        df = dfs[nm]
        numero = str(int(nm))
        vi = vientres.get(numero, {})
        nrows, ncols = df.shape

        # --- eventos reproductivos desde filas Excel 3-4 (cols A..H) ---
        fechas = {}
        for j in range(min(8, ncols)):
            label = norm(df.iat[2, j])  # fila Excel 3
            val = df.iat[3, j]          # fila Excel 4
            d = to_date(val)
            if d and 2000 <= d.year and d <= hoy:
                fechas[label] = d
        for label, d in fechas.items():
            tipo = RE_EVENTO.get(label)
            if tipo:
                eventos.append((numero, tipo, d))
        if vi.get("parto") and vi["parto"].year >= 2000 and vi["parto"] <= hoy:
            eventos.append((numero, "Parto", vi["parto"]))
        if vi.get("servicio") and vi["servicio"].year >= 2000 and vi["servicio"] <= hoy:
            eventos.append((numero, "Servicio", vi["servicio"]))
        if vi.get("diag"):
            fecha_diag = (fechas.get("PRENEZ") or vi.get("servicio")
                          or vi.get("parto")
                          or (dt.date.today() - dt.timedelta(days=30)))
            diag_hitos.append((numero, "Preñada", fecha_diag))

        # --- producción: grid mensual (meses en fila Excel 6, datos fila 8+) ---
        bloques = []
        for c in range(3, min(27, ncols), 2):   # columnas Excel D..Z (4..26)
            mes = MESES_ES.get(norm(df.iat[5, c]))
            if mes is not None and c + 1 < ncols:
                bloques.append((mes, c, c + 1))
        if bloques:
            total_mes_hoja = 0.0
            for orden, (mes, c_dia, c_litro) in enumerate(bloques):
                for r in range(7, min(40, nrows)):  # filas Excel 8..39
                    dia_raw = df.iat[r, c_dia]
                    lit_raw = df.iat[r, c_litro]
                    if dia_raw is None or (isinstance(dia_raw, float) and np.isnan(dia_raw)):
                        continue
                    try:
                        dia = int(float(dia_raw))
                        lit = float(lit_raw)
                    except (TypeError, ValueError):
                        continue
                    if not (0 <= dia <= 31):
                        continue
                    if lit is None or np.isnan(lit) or lit < 0:
                        continue
                    total_mes_hoja += lit
                    produccion.append((numero, orden, mes, dia, lit))
            produccion_hoja[numero] = round(total_mes_hoja, 2)
            b15 = df.iat[14, 1]  # fila Excel 15, col B
            if isinstance(b15, (int, float)) and abs(float(b15) - total_mes_hoja) > 0.02:
                errores.append(f"{numero}: TOTAL LITROS(B15)={b15} vs grid={total_mes_hoja:.2f}")
    return eventos, produccion, produccion_hoja, diag_hitos, errores


# ---------------------------------------------------------------------------
# 3) PESAJE ... v4 - AUTOMATICO.xlsm
# ---------------------------------------------------------------------------
def parse_pesaje():
    xl = pd.ExcelFile(PESAJE)

    cat_lote = {"ORDENO": "Ordeño", "LEVANTE": "Levante",
                "MAMON": "Mamon", "SILVO": "Silvo"}
    orden_adulto = {"ORDENO": 0, "SILVO": 1, "LEVANTE": 2, "MAMON": 3}

    indice: dict[str, tuple[str, str, int]] = {}  # numero -> (sexo, lote, score)
    for name in xl.sheet_names:
        cn = norm(name)
        if not cn.startswith("INDICE"):
            continue
        cat = cn.replace("INDICE ", "")
        lote = cat_lote.get(cat)
        if lote is None:
            continue
        score = orden_adulto.get(cat, 9)
        df = pd.read_excel(xl, sheet_name=name, header=None, usecols="A:I")
        for r in range(3, len(df)):   # filas Excel 4+
            numero = df.iat[r, 1]
            if numero is None or (isinstance(numero, float) and np.isnan(numero)):
                continue
            numero = str(int(numero)).strip()
            sexo = df.iat[r, 2]
            sexo_s = str(sexo).strip().upper() if sexo is not None else "-"
            old = indice.get(numero)
            if old is None or score < old[2]:
                indice[numero] = (sexo_s, lote, score)

    pesajes: list[tuple[str, dt.date, float, str]] = []
    fichas_etapa: dict[str, str] = {}
    ficha_sheets = [n for n in xl.sheet_names if RE_SHEET_SUFIX.match(n)]
    for name in ficha_sheets:
        m = RE_SHEET_SUFIX.match(name)
        numero = m.group(1)
        df = pd.read_excel(xl, sheet_name=name, header=None)
        etap = df.iat[4, 1] if len(df) > 4 else None   # fila Excel 5, col B
        fichas_etapa.setdefault(numero, None)
        if isinstance(etap, str) and etap.strip():
            fichas_etapa[numero] = etap.strip().upper()
        for r in range(1, len(df)):   # filas Excel 2+
            d = to_date(df.iat[r, 0])
            if d is None:
                continue
            b = df.iat[r, 1]
            try:
                peso = float(b)
            except (TypeError, ValueError):
                continue
            if peso <= 0 or d.year < 2000 or d > dt.date.today():
                continue
            pesajes.append((numero, d, peso, name))
    return indice, pesajes, fichas_etapa


# ---------------------------------------------------------------------------
# 4) Formulaciones_Integrales...xlsx
# ---------------------------------------------------------------------------
def parse_formulaciones():
    xl = pd.ExcelFile(FORMULACIONES)

    ws = pd.read_excel(xl, sheet_name="INVENTARIO", header=None)
    materias = []
    for r in range(1, len(ws)):
        nombre = ws.iat[r, 0]
        if not isinstance(nombre, str) or not nombre.strip():
            continue
        if norm(nombre).startswith(("TOTAL", "NOTA")):
            continue
        materias.append({"nombre": nombre.strip(),
                         "unidad": ws.iat[r, 1], "presentacion": ws.iat[r, 2],
                         "cantidad": ws.iat[r, 3], "total_kg": ws.iat[r, 4],
                         "precio_bulto": ws.iat[r, 5], "precio_kg": ws.iat[r, 6],
                         "valor_total": ws.iat[r, 7]})

    ws = pd.read_excel(xl, sheet_name="Formulaciones Integrales 100kg", header=None)
    formulas = []
    r = 0
    while r < len(ws) - 1:
        cab = ws.iat[r, 0]
        sub = ws.iat[r + 1, 0]
        if (isinstance(cab, str) and strip_acc(cab).upper().startswith("FORMULACION")
                and isinstance(sub, str) and "MATERIA" in sub.upper()):
            items = []
            rr = r + 2
            while rr < len(ws):
                name = ws.iat[rr, 0]
                if not isinstance(name, str) or not name.strip():
                    break
                if norm(name).startswith("TOTAL"):
                    break
                items.append({"nombre": name.strip(),
                              "cantidad": ws.iat[rr, 1], "proporcion": ws.iat[rr, 2],
                              "prot": ws.iat[rr, 4], "carb": ws.iat[rr, 6],
                              "min": ws.iat[rr, 8], "vit": ws.iat[rr, 10],
                              "fib": ws.iat[rr, 12]})
                rr += 1
            formulas.append({"nombre": cab.strip(), "items": items})
            r = rr + 1
        else:
            r += 1

    ws = pd.read_excel(xl, sheet_name="Costos de Producción", header=None)
    costos = {}
    for r in range(5, 9):
        nombre = ws.iat[r, 0]
        if not isinstance(nombre, str) or not nombre.strip():
            continue
        costos[norm(nombre)] = {"nombre": nombre.strip(), "kg": ws.iat[r, 1],
                                "costo_total": ws.iat[r, 2], "costo_kg": ws.iat[r, 3]}

    ws = pd.read_excel(xl, sheet_name="Requerimiento Nutricional", header=None)
    reqs = []
    for r in range(7, len(ws)):
        grupo = ws.iat[r, 1]
        if not isinstance(grupo, str) or not grupo.strip():
            continue
        reqs.append({"grupo": grupo.strip(), "rango": ws.iat[r, 2],
                     "proposito": ws.iat[r, 3], "consumo": ws.iat[r, 4],
                     "pb": ws.iat[r, 5], "ndt": ws.iat[r, 6],
                     "fdn": ws.iat[r, 7], "ca_p": ws.iat[r, 8],
                     "estrategia": ws.iat[r, 9]})
    return materias, formulas, costos, reqs


# ---------------------------------------------------------------------------
# 5) Carga en PostgreSQL
# ---------------------------------------------------------------------------
def main() -> int:
    print("Leyendo archivos fuente...", flush=True)
    vientres = parse_vientres()
    eventos, produccion, prod_totales, diag_hitos, errores = parse_fichas(vientres)
    indice, pesajes, fichas_etapa = parse_pesaje()
    materias, formulas, costos, reqs = parse_formulaciones()

    print(f"VIENTRES {len(vientres)} | eventos {len(eventos)} | producción {len(produccion)} "
          f"| PESAJE animales {len(indice)} pesajes {len(pesajes)} | fórmulas {len(formulas)}",
          flush=True)

    conn = connect_admin()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT nombre_lote, id_lote::text FROM lotes")
            lotes = dict(cur.fetchall())
            cur.execute("SELECT numero_visible, id_interno::text, sexo, etapa_actual "
                        "FROM animales")
            existentes = {n: {"id": i, "sexo": s, "etapa": e}
                          for n, i, s, e in cur.fetchall()}
            cur.execute("SELECT nombre_tipo, id_tipo_evento::text FROM cat_eventos_reproductivos")
            tipos_repro = dict(cur.fetchall())
    except Exception:
        conn.rollback()
        raise

    # --- animales: upsert ---
    target_ids: dict[str, str] = {}
    created, updated = 0, 0
    todos = set(existentes) | set(vientres) | set(indice) | set(fichas_etapa)
    for numero in sorted(todos, key=lambda x: (len(x), x)):
        vi = vientres.get(numero, {})
        idx = indice.get(numero)
        sexo = None
        if idx:
            raw = idx[0]
            if raw.startswith("M"):
                sexo = "M"
            elif raw.startswith("H"):
                sexo = "F"
        if sexo is None and numero in existentes:
            sexo = existentes[numero]["sexo"]
        if sexo is None:
            sexo = "F"
        etapa = vi.get("etapa")
        if not etapa and numero in fichas_etapa:
            etapa = fichas_etapa[numero]
        if not etapa and idx:
            etapa = idx[1].upper()
        if not etapa and numero in existentes:
            etapa = existentes[numero]["etapa"]
        if etapa and norm(etapa) not in ETAPAS_OK:
            print(f"  [!] etapa desconocida '{etapa}' para {numero} -> se omite", flush=True)
            etapa = None
        if etapa:
            etapa = str(etapa).strip()
        # Un animal marcado VENDIDA no vuelve al hato en posteriores sincronizaciones:
        # la venta (DDL 009/010) prevalece sobre la etapa del Excel.
        if numero in existentes and existentes[numero]["etapa"] == "VENDIDA":
            etapa = "VENDIDA"
        lote = None
        if numero not in existentes and idx:
            lote = idx[1]
        if numero not in existentes:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO animales (numero_visible, sexo, etapa_actual, id_lote_actual) "
                    "VALUES (%s, %s, %s, (SELECT id_lote FROM lotes WHERE nombre_lote=%s)) "
                    "RETURNING id_interno::text",
                    (numero, sexo, etapa, lote))
                nid = cur.fetchone()[0]
            target_ids[numero] = nid
            created += 1
        else:
            target_ids[numero] = existentes[numero]["id"]
            fields, args = [], []
            if etapa and etapa != existentes[numero]["etapa"]:
                fields.append("etapa_actual = %s")
                args.append(etapa)
            if sexo and sexo != existentes[numero]["sexo"]:
                fields.append("sexo = %s")
                args.append(sexo)
            if fields:
                args.append(target_ids[numero])
                with conn.cursor() as cur:
                    cur.execute(
                        f"UPDATE animales SET {', '.join(fields)} WHERE id_interno=%s", args)
                updated += 1

    # --- eventos reproductivos: reconstruir ---
    with conn.cursor() as cur:
        cur.execute("DELETE FROM eventos_reproductivos")
    seen = set()
    ev_rows = []
    for numero, tipo, fecha in eventos:
        if numero not in target_ids:
            continue
        key = (numero, tipo, fecha)
        if key in seen:
            continue
        seen.add(key)
        t = tipos_repro.get(tipo)
        if not t:
            continue
        ev_rows.append((target_ids[numero], t, fecha, AGROORDEN.name, numero))
    with conn.cursor() as cur:
        if ev_rows:
            psycopg2.extras.execute_values(
                cur,
                "INSERT INTO eventos_reproductivos "
                "(id_animal, id_tipo_evento, fecha_evento, archivo_origen, hoja_origen) VALUES %s",
                ev_rows)

    # --- hitos de diagnóstico (preñez) del panel ---
    with conn.cursor() as cur:
        cur.execute("SELECT id_animal, resultado, fecha_revision FROM hitos_reproductivos")
        ya = {(a, r, f) for a, r, f in cur.fetchall()}
    hito_rows = []
    for numero, resultado, fecha in diag_hitos:
        if numero not in target_ids:
            continue
        if (target_ids[numero], "Preñada", fecha) in ya:
            continue
        hito_rows.append((target_ids[numero], fecha, "Preñada"))
    with conn.cursor() as cur:
        if hito_rows:
            psycopg2.extras.execute_values(
                cur,
                "INSERT INTO hitos_reproductivos (id_animal, fecha_revision, resultado) VALUES %s",
                hito_rows)

    # --- producción: reconstruir desde grid mensual de fichas ---
    with conn.cursor() as cur:
        cur.execute("DELETE FROM produccion_lechera")
    prod_rows = []
    for numero, orden_mes, mes, dia, lit in produccion:
        if numero not in target_ids:
            continue
        prod_rows.append((target_ids[numero], orden_mes, mes, dia, lit,
                          AGROORDEN.name, numero))
    with conn.cursor() as cur:
        if prod_rows:
            psycopg2.extras.execute_values(
                cur,
                "INSERT INTO produccion_lechera "
                "(id_animal, orden_mes, mes, dia, litros, archivo_origen, hoja_origen) VALUES %s",
                prod_rows)

    # --- pesajes: reconstruir (se respetan capturas del sistema) ---
    with conn.cursor() as cur:
        cur.execute("DELETE FROM pesajes WHERE COALESCE(fuente, 'excel') <> 'sistema'")
    dedup = {}
    for numero, fecha, peso, hoja in pesajes:
        if numero not in target_ids:
            continue
        dedup[(numero, fecha)] = (numero, fecha, peso, hoja)
    peso_rows = [(target_ids[n], f, p, PESAJE.name, h, "excel")
                 for n, f, p, h in dedup.values()]
    with conn.cursor() as cur:
        if peso_rows:
            psycopg2.extras.execute_values(
                cur,
                "INSERT INTO pesajes "
                "(id_animal, fecha, peso_kg, archivo_origen, hoja_origen, fuente) VALUES %s",
                peso_rows)

    # --- alimentación / formulaciones ---
    with conn.cursor() as cur:
        cur.execute("TRUNCATE alimentacion_formulacion_insumo, alimentacion_formulacion, "
                    "alimentacion_materia_prima, alimentacion_requerimiento")
        for mp in materias:
            cur.execute(
                "INSERT INTO alimentacion_materia_prima "
                "(nombre, unidad_bulto, presentacion_kg, cantidad, total_kg, "
                " precio_bulto_cop, precio_kg_cop, valor_total_cop) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (mp["nombre"][:150], mp["unidad"], mp["presentacion"], mp["cantidad"],
                 mp["total_kg"], mp["precio_bulto"], mp["precio_kg"], mp["valor_total"]))
        cur.execute("SELECT nombre, id_materia_prima::text FROM alimentacion_materia_prima")
        mat_id = dict(cur.fetchall())

        def costo_para(nombre_formula: str):
            key = norm(nombre_formula)
            for pat in ("CRIA", "LEVANTE", "LECHERIA"):
                if pat in key:
                    for ck, cv in costos.items():
                        if pat in ck:
                            return cv
            return {}

        for f in formulas:
            dato = costo_para(f["nombre"])
            cur.execute(
                "INSERT INTO alimentacion_formulacion "
                "(nombre, categoria, total_mezcla_kg, costo_total_cop, costo_kg_cop) "
                "VALUES (%s,%s,%s,%s,%s) ON CONFLICT (nombre) DO NOTHING",
                (f["nombre"], "INTEGRAL",
                 dato.get("kg") if dato else None,
                 dato.get("costo_total") if dato else None,
                 dato.get("costo_kg") if dato else None))
            cur.execute("SELECT id_formulacion::text FROM alimentacion_formulacion "
                        "WHERE nombre=%s", (f["nombre"],))
            fid = cur.fetchone()[0]
            for item in f["items"]:
                cur.execute(
                    "INSERT INTO alimentacion_formulacion_insumo "
                    "(id_formulacion, id_materia_prima, materia_prima_texto, cantidad_kg, "
                    " proporcion, aporte_proteina_kg, aporte_carbohidratos_kg, "
                    " aporte_minerales_kg, aporte_vitaminas_kg, aporte_fibra_kg) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (fid, mat_id.get(item["nombre"]), item["nombre"], item["cantidad"],
                     item["proporcion"], item["prot"], item["carb"], item["min"],
                     item["vit"], item["fib"]))
        for rq in reqs:
            cur.execute(
                "INSERT INTO alimentacion_requerimiento "
                "(grupo_etario, rango_peso, proposito, consumo_ms_pv, proteina_bruta, "
                " energia_ndt, fibra_fdn, minerales_ca_p, estrategia) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (rq["grupo"], rq["rango"], rq["proposito"], rq["consumo"], rq["pb"],
                 rq["ndt"], rq["fdn"], rq["ca_p"], rq["estrategia"]))

        conn.commit()

    n_hitos = len(hito_rows)
    print(f"\nCarga OK: animales creados={created} actualizados={updated} | "
          f"eventos_repro={len(ev_rows)} | hitos_preñez={n_hitos} | "
          f"producción={len(prod_rows)} | pesajes={len(peso_rows)}", flush=True)
    if errores:
        print("AVISOS de consistencia (TOTAL LITROS hoja vs grid):", flush=True)
        for e in errores[:25]:
            print("  -", e, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())