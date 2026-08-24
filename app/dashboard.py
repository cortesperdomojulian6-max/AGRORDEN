"""Dashboard AGRORDEN — capa visual de consulta (SPEC-006).

Ejecución:
    streamlit run app/dashboard.py

Principios: solo lectura; conexión por .env; las vistas de SPEC-004 son la API.
Identidad visual: paleta de campo (verde bosque, crema, terracota), tipografía
sobria, sin adornos gratuitos. Diseño responsivo de escritorio a celular.
"""
from __future__ import annotations

import base64
import io
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from etl.config import get_connection  # noqa: E402

UMBRAL_DIAS_ABIERTOS = 150

st.set_page_config(
    page_title="AGRORDEN · Gestión ganadera",
    page_icon=":herb:",
    layout="wide",
)

V_HATO = ("SELECT COALESCE(nombre_lote,'(sin lote)') AS lote, "
          "hembras, machos, total FROM v_resumen_hato ORDER BY total DESC")
V_DIAS = """
    SELECT numero_visible, nombre_lote, fecha_parto, fecha_cubricion, dias_abiertos
    FROM v_dias_abiertos WHERE dias_abiertos IS NOT NULL
    ORDER BY dias_abiertos DESC
"""
V_PROX_PARTOS = """
    SELECT numero_visible, nombre_lote, fecha_parto
    FROM v_dias_abiertos WHERE fecha_parto > CURRENT_DATE
    ORDER BY fecha_parto ASC
"""
V_PESO = """
    SELECT numero_visible, nombre_lote, fecha_anterior, fecha_actual,
           peso_actual, g_dia
    FROM v_ganancia_peso ORDER BY numero_visible, fecha_actual
"""
V_PROD = """
    SELECT numero_visible, nombre_lote, fecha_real, litros
    FROM v_produccion_con_fecha ORDER BY numero_visible, fecha_real
"""
V_PICO = "SELECT numero_visible, fecha_pico, litros_pico FROM v_pico_lactancia"

CARPETA_FOTOS = Path(__file__).resolve().parent.parent / "data" / "fotos"


def fotos_de(animal: str) -> list[Path]:
    carpeta = CARPETA_FOTOS / str(animal)
    return sorted(carpeta.glob("foto_*")) if carpeta.exists() else []


CSS_GLOBAL = """
<style>
:root {
  --verde:#2E4B2F; --verde-osc:#223A23; --tinta:#24301F; --piedra:#75806C;
  --crema:#F6F4EC; --blanco:#FFFFFF; --borde:#E4E0D3;
  --terracota:#B4552D; --paja:#C99A3C; --musgo:#5F7F4A;
}
html, body, [data-testid="stAppViewContainer"] { background: var(--crema); }
[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top:1.6rem; padding-bottom:3rem; max-width:1180px; }
h1 { color:var(--verde-osc) !important; font-weight:700; letter-spacing:-.3px; }
h2, h3 { color:var(--verde-osc) !important; font-weight:700; }
[data-testid="stMarkdownContainer"] p, li { color:var(--tinta); }

.marca { font-family:Georgia,'Times New Roman',serif; margin-bottom:10px; }
.marca .logo { font-size:25px; font-weight:700; color:var(--verde-osc);
               letter-spacing:3.5px; border-bottom:2px solid var(--terracota);
               display:inline-block; padding-bottom:6px; }
.marca .slogan { margin-top:7px; color:var(--piedra); font-size:11.5px;
                 letter-spacing:1.6px; text-transform:uppercase; }

[data-testid="stSidebar"] { background:#EFEBDD; border-right:1px solid var(--borde); }
[data-testid="stSidebar"] hr { border-color:var(--borde); margin:14px 0; }

[data-testid="stMetric"] { background:var(--blanco); border:1px solid var(--borde);
  border-radius:14px; padding:14px 16px; box-shadow:0 1px 3px rgba(36,48,31,.05); }
[data-testid="stMetricLabel"] p { color:var(--piedra) !important; font-size:11.5px;
  text-transform:uppercase; letter-spacing:1.1px; font-weight:600; }
[data-testid="stMetricValue"] { color:var(--tinta); font-weight:700; }

.stDownloadButton button, .stButton button {
  background:var(--verde); color:#fff; border:none; border-radius:10px;
  font-weight:600; }
.stDownloadButton button:hover, .stButton button:hover {
  background:var(--verde-osc); color:#fff; }

.aviso { background:#FBF6EE; border-left:4px solid var(--terracota);
  border-radius:10px; padding:13px 16px; margin:7px 0; color:#6E3A1E; font-size:15px; }
.aviso-ojo { background:#FAF5E7; border-left:4px solid var(--paja);
  border-radius:10px; padding:13px 16px; margin:7px 0; color:#6B5416; font-size:15px; }
.aviso-ok { background:#F2F5EC; border-left:4px solid var(--musgo);
  border-radius:10px; padding:13px 16px; margin:7px 0; color:#3C5230; font-size:15px; }
.nota-leer { background:#F3F0E4; border:1px dashed #D8D2BC; border-radius:10px;
  padding:12px 15px; margin:8px 0 2px 0; color:#57604A; font-size:14.5px; }

.estado-grid { display:flex; gap:14px; flex-wrap:wrap; margin:12px 0 4px 0; }
.estado-card { flex:1 1 170px; background:var(--blanco); border:1px solid var(--borde);
  border-radius:16px; padding:16px 18px; border-top:4px solid var(--piedra); }
.estado-card .num { font-size:34px; font-weight:700; color:var(--tinta); line-height:1.1; }
.estado-card .tit { font-size:12.5px; font-weight:700; letter-spacing:1.1px;
  text-transform:uppercase; margin-top:5px; color:var(--piedra); }
.estado-card .det { color:var(--piedra); font-size:12.5px; margin-top:3px; }
.estado-card.revisar  { border-top-color:var(--terracota); }
.estado-card.revisar .tit { color:var(--terracota); }
.estado-card.atencion { border-top-color:var(--paja); }
.estado-card.atencion .tit { color:#96742B; }
.estado-card.ok       { border-top-color:var(--musgo); }
.estado-card.ok .tit { color:var(--musgo); }

.prox-lista { display:flex; flex-wrap:wrap; gap:10px; margin:10px 0 4px 0; }
.prox-item { background:var(--blanco); border:1px solid var(--borde);
  border-radius:12px; padding:9px 13px; font-size:13.5px; color:var(--tinta); }
.prox-item b { color:var(--verde-osc); }
.prox-item span { color:var(--piedra); }

@media (max-width:640px) {
  .block-container { padding-top:1rem; }
  .estado-card .num { font-size:27px; }
}
</style>
"""

CSS_FICHA = """
<style>
.vaca-card { font-family:'Segoe UI',sans-serif; background:#FFFFFF;
             border:1px solid #E4E0D3; border-radius:20px; overflow:hidden;
             box-shadow:0 4px 22px rgba(36,48,31,.09); max-width:640px;
             margin:0 auto 10px auto; }
.hero { position:relative; height:clamp(190px, 32vw, 270px);
        background:linear-gradient(160deg,#33402C,#1C2418); }
.hero img.principal { width:100%; height:100%; object-fit:cover; display:block; }
.velo { position:absolute; inset:0; pointer-events:none;
        background:linear-gradient(180deg,rgba(0,0,0,0) 32%,rgba(12,17,9,.78) 100%); }
.titulo { position:absolute; left:20px; right:20px; bottom:15px; pointer-events:none; }
.nombre-fila { display:flex; align-items:center; gap:12px; flex-wrap:wrap; }
.nombre-vaca { color:#ffffff; font-size:clamp(22px,4vw,29px); font-weight:700;
               line-height:1.15; letter-spacing:.3px;
               text-shadow:0 1px 4px rgba(0,0,0,.5); font-family:Georgia,serif; }
.pill { padding:4px 11px; border-radius:999px; font-size:11.5px; font-weight:700;
        color:#ffffff; letter-spacing:1.2px; text-transform:uppercase;
        box-shadow:0 1px 4px rgba(0,0,0,.3); }
.sub-hero { margin-top:7px; color:rgba(255,255,255,.82); font-size:12.5px;
            letter-spacing:1.4px; text-transform:uppercase; font-weight:500; }
.mini-foto { position:absolute; right:16px; bottom:16px; width:72px; height:72px;
             border-radius:16px; object-fit:cover;
             border:3px solid rgba(255,255,255,.94);
             box-shadow:0 2px 12px rgba(0,0,0,.45); }
.vaca-foto { cursor:zoom-in; }
.cuerpo { padding:18px; display:flex; flex-direction:column; gap:14px;
          background:#F9F7F0; }
.stats { display:flex; gap:12px; flex-wrap:wrap; }
.stat { flex:1 1 140px; background:#ffffff; border:1px solid #E4E0D3;
        border-radius:16px; padding:13px 15px; min-width:0;
        box-shadow:0 1px 3px rgba(36,48,31,.05); }
.stat .lbl { font-size:11px; color:#75806C; letter-spacing:1.1px;
             text-transform:uppercase; font-weight:600; }
.stat .val { font-size:21px; font-weight:700; color:#24301F; line-height:1.35; }
.seccion { background:#ffffff; border:1px solid #E4E0D3; border-radius:16px;
           padding:16px 18px; display:flex; flex-direction:column; gap:11px; }
.seccion h4 { margin:0; font-size:13px; font-weight:700; color:#2E4B2F;
              letter-spacing:1.3px; text-transform:uppercase; }
.fila { display:flex; justify-content:space-between; align-items:center; gap:12px;
        font-size:14.5px; padding-bottom:9px; border-bottom:1px solid #F0EDE2; }
.fila:last-child { padding-bottom:0; border-bottom:none; }
.fila .k { color:#75806C; }
.fila .v { font-weight:600; color:#24301F; text-align:right; }
.aviso-ficha { border-radius:12px; padding:12px 14px; font-size:14px; line-height:1.45; }
.aviso-ficha.revisar { background:#FBF0E8; border:1px solid #EBD3C2; color:#6E3A1E; }
.aviso-ficha.nota    { background:#F2F4EA; border:1px solid #DFE3CE; color:#44523A; }
@media (max-width:640px) {
  .cuerpo { padding:13px; }
  .stat { flex:1 1 44%; padding:11px 12px; }
  .stat .val { font-size:18px; }
  .mini-foto { width:56px; height:56px; border-radius:13px; }
  .fila { font-size:13.5px; }
}
</style>
"""

LIGHTBOX_JS = """
<script>
(function(){
  var d = window.parent.document;
  if (d.getElementById('ag-lb')) return;
  var st = d.createElement('style');
  st.textContent =
    '#ag-lb{position:fixed;inset:0;background:rgba(24,28,20,.94);display:none;' +
    'z-index:999999;cursor:grab;touch-action:none;}' +
    '#ag-lb.abierto{display:block;}' +
    '#ag-lb img{position:absolute;left:50%;top:50%;max-width:92vw;max-height:86vh;' +
    'border-radius:10px;box-shadow:0 24px 90px rgba(0,0,0,.65);user-select:none;}' +
    '#ag-lb .cerrar{position:absolute;top:12px;right:22px;color:#F6F4EC;' +
    'font-size:38px;line-height:1;cursor:pointer;font-family:Georgia,serif;}' +
    '#ag-lb .ayuda{position:absolute;bottom:15px;left:0;right:0;text-align:center;' +
    'color:rgba(246,244,236,.72);font:12.5px Georgia,serif;letter-spacing:.5px;}';
  d.head.appendChild(st);
  var lb = d.createElement('div');
  lb.id = 'ag-lb';
  lb.innerHTML = '<span class="cerrar">&times;</span>' +
    '<img draggable="false" alt="Foto ampliada del animal">' +
    '<div class="ayuda">Gire la rueda para acercar · arrastre para mover · Esc para salir</div>';
  d.body.appendChild(lb);
  var img = lb.querySelector('img');
  var z = 1, tx = 0, ty = 0, moviendo = false, px = 0, py = 0, pellizco = 0;
  function aplicar(){
    img.style.transform = 'translate(calc(-50% + ' + tx + 'px), calc(-50% + ' +
      ty + 'px)) scale(' + z + ')';
  }
  function abrir(src){ z = 1; tx = 0; ty = 0; aplicar(); img.src = src;
    lb.classList.add('abierto'); }
  function cerrar(){ lb.classList.remove('abierto'); }
  d.addEventListener('click', function(e){
    var f = e.target.closest ? e.target.closest('.vaca-foto') : null;
    if (f) { e.preventDefault(); abrir(f.getAttribute('src')); }
  });
  lb.querySelector('.cerrar').addEventListener('click', cerrar);
  lb.addEventListener('click', function(e){ if (e.target === lb) cerrar(); });
  d.addEventListener('keydown', function(e){ if (e.key === 'Escape') cerrar(); });
  lb.addEventListener('wheel', function(e){
    e.preventDefault();
    z = Math.min(8, Math.max(1, z * (e.deltaY < 0 ? 1.18 : 0.85)));
    if (z === 1) { tx = 0; ty = 0; }
    aplicar();
  }, {passive:false});
  function inicio(x,y){ moviendo = true; px = x; py = y; lb.style.cursor='grabbing'; }
  function mover(x,y){ if(!moviendo) return; tx += x - px; ty += y - py;
    px = x; py = y; aplicar(); }
  function fin(){ moviendo = false; lb.style.cursor='grab'; }
  lb.addEventListener('mousedown', function(e){
    if (e.target !== img) return; e.preventDefault();
    inicio(e.clientX, e.clientY); });
  window.parent.addEventListener('mousemove', function(e){ mover(e.clientX, e.clientY); });
  window.parent.addEventListener('mouseup', fin);
  lb.addEventListener('touchstart', function(e){
    if (e.touches.length === 1) inicio(e.touches[0].clientX, e.touches[0].clientY);
    else if (e.touches.length === 2) {
      var a = e.touches[0].clientX - e.touches[1].clientX;
      var b = e.touches[0].clientY - e.touches[1].clientY;
      pellizco = Math.sqrt(a*a + b*b);
    }
  }, {passive:true});
  lb.addEventListener('touchmove', function(e){
    if (e.touches.length === 1 && !pellizco) {
      e.preventDefault(); mover(e.touches[0].clientX, e.touches[0].clientY);
    } else if (e.touches.length === 2 && pellizco) {
      e.preventDefault();
      var a = e.touches[0].clientX - e.touches[1].clientX;
      var b = e.touches[0].clientY - e.touches[1].clientY;
      var dist = Math.sqrt(a*a + b*b);
      z = Math.min(8, Math.max(1, z * dist / pellizco));
      pellizco = dist; aplicar();
    }
  }, {passive:false});
  lb.addEventListener('touchend', function(){ fin(); pellizco = 0; });
})();
</script>
"""

PALETA_GRAFICAS = ["#55803C", "#B4552D", "#C99A3C", "#3F6E5A", "#8C7B4B"]

COLORES_ETAPA = {
    "ORDEÑO": "#55803C",
    "PREÑEZ": "#3F6E5A",
    "VACIA": "#B4552D",
    "HORRA": "#9C8A54",
    "REPRODUCTOR": "#6B5740",
}


def color_etapa(etapa: str) -> str:
    etapa_up = (etapa or "").upper()
    for clave, color in COLORES_ETAPA.items():
        if clave in etapa_up:
            return color
    return "#75806C"


def estilizar(fig, titulo: str | None = None):
    fig.update_layout(
        font=dict(family="'Segoe UI', sans-serif", size=13, color="#24301F"),
        title=dict(text=titulo, font=dict(size=17, color="#223A23"), x=0.01),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(gridcolor="#E7E2D4", zeroline=False),
        yaxis=dict(gridcolor="#E7E2D4", zeroline=False),
        legend=dict(bgcolor="#FFFFFF", bordercolor="#E4E0D3", borderwidth=1),
        margin=dict(l=10, r=10, t=46 if titulo else 16, b=10),
        hovermode="closest",
    )
    return fig


@st.cache_data(ttl=300)
def leer_vista(sql: str) -> pd.DataFrame:
    conn = get_connection()
    try:
        return pd.read_sql(sql, conn)
    finally:
        conn.close()


def filtrar_por_lote(df: pd.DataFrame, lote: str | None) -> pd.DataFrame:
    if not lote or "nombre_lote" not in df.columns:
        return df
    lote_df = "(sin lote)" if pd.isna(lote) else lote
    return df[df["nombre_lote"].fillna("(sin lote)") == lote_df]


def boton_excel(df: pd.DataFrame, nombre: str) -> None:
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    st.download_button(
        f"Descargar {nombre} (Excel)",
        buf.getvalue(),
        file_name=f"{nombre}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def fecha_corta(valor) -> str:
    return pd.Timestamp(valor).strftime("%d/%m/%Y")


@st.cache_data(ttl=300)
def datos_ficha(animal: str) -> dict:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT etapa_actual FROM animales WHERE numero_visible = %s",
                (animal,),
            )
            fila = cur.fetchone()
            etapa = fila[0] if fila else None

            cur.execute(
                "SELECT COUNT(*) FROM eventos_reproductivos er "
                "JOIN animales a ON a.id_interno = er.id_animal "
                "JOIN cat_eventos_reproductivos c "
                "  ON c.id_tipo_evento = er.id_tipo_evento "
                "WHERE a.numero_visible = %s AND c.nombre_tipo = 'Parto'",
                (animal,),
            )
            num_partos = cur.fetchone()[0]

            cur.execute(
                "SELECT observacion FROM notas_vaca n "
                "JOIN animales a ON a.id_interno = n.id_animal "
                "WHERE a.numero_visible = %s ORDER BY n.fecha_registro DESC",
                (animal,),
            )
            notas = [f[0] for f in cur.fetchall()]

            cur.execute(
                "SELECT fecha_parto, dias_abiertos FROM v_dias_abiertos "
                "WHERE numero_visible = %s",
                (animal,),
            )
            fila = cur.fetchone()
            parto, abiertos = (fila if fila else (None, None))

            cur.execute(
                "SELECT litros_pico, fecha_pico FROM v_pico_lactancia "
                "WHERE numero_visible = %s",
                (animal,),
            )
            fila = cur.fetchone()
            pico_litros, pico_fecha = (fila if fila else (None, None))

            cur.execute(
                "SELECT AVG(litros) FROM v_produccion_con_fecha "
                "WHERE numero_visible = %s",
                (animal,),
            )
            prom_litros = cur.fetchone()[0]

            cur.execute(
                "SELECT peso_actual, g_dia FROM v_ganancia_peso "
                "WHERE numero_visible = %s ORDER BY fecha_actual DESC LIMIT 1",
                (animal,),
            )
            fila = cur.fetchone()
            peso_actual, g_dia = (fila if fila else (None, None))
    finally:
        conn.close()
    return {
        "etapa": etapa, "parto": parto, "abiertos": abiertos,
        "pico_litros": pico_litros, "pico_fecha": pico_fecha,
        "prom_litros": prom_litros, "peso_actual": peso_actual,
        "g_dia": g_dia, "num_partos": num_partos, "notas": notas,
    }


def ficha_vaca_html(animal: str) -> str | None:
    fotos = fotos_de(animal)
    d = datos_ficha(animal)
    if not fotos and d["etapa"] is None:
        return None

    def stat(lbl: str, val: str) -> str:
        return (f'<div class="stat"><div class="lbl">{lbl}</div>'
                f'<div class="val">{val}</div></div>')

    def fila(k: str, v: str) -> str:
        return (f'<div class="fila"><span class="k">{k}</span>'
                f'<span class="v">{v}</span></div>')

    stats_html = "".join([
        stat("Peso actual", f"{d['peso_actual']:.0f} kg"
             if d["peso_actual"] is not None else "Pendiente"),
        stat("Producción", f"{d['prom_litros']:.1f} L/día"
             if d["prom_litros"] is not None else "—"),
        stat("Partos registrados", str(d["num_partos"])),
    ])

    filas_html = "".join([
        fila("Último parto", fecha_corta(d["parto"]) if d["parto"] is not None else "—"),
        fila("Días sin preñar", f"{d['abiertos']:.0f} días"
             if d["abiertos"] is not None else "—"),
        fila("Estado reproductivo", d["etapa"] or "Sin registro"),
        fila("Pico de leche",
             f"{d['pico_litros']:.0f} L ({fecha_corta(d['pico_fecha'])})"
             if d["pico_litros"] is not None else "—"),
    ])

    avisos = []
    if d["abiertos"] is not None and d["abiertos"] > UMBRAL_DIAS_ABIERTOS:
        avisos.append(
            '<div class="aviso-ficha revisar">Esta vaca lleva '
            f'<strong>{d["abiertos"]:.0f} días</strong> sin quedar preñada '
            "después de su parto. Conviene presentarla al veterinario.</div>"
        )
    for nota in d["notas"][:2]:
        avisos.append(
            f'<div class="aviso-ficha nota"><strong>Anotación de campo:</strong> '
            f"{nota}</div>"
        )
    avisos_html = "".join(avisos)
    bloque_avisos = (
        '<div class="seccion"><h4>Avisos</h4>' + avisos_html + "</div>"
        if avisos_html else ""
    )

    foto_principal = ""
    mini = ""
    if fotos:
        b64_1 = base64.b64encode(Path(fotos[0]).read_bytes()).decode()
        foto_principal = (
            f'<img class="principal vaca-foto" alt="Foto de la vaca {animal}" '
            f'src="data:image/jpeg;base64,{b64_1}">'
        )
        if len(fotos) > 1:
            b64_2 = base64.b64encode(Path(fotos[1]).read_bytes()).decode()
            mini = (
                f'<img class="mini-foto vaca-foto" alt="Segunda foto de {animal}" '
                f'src="data:image/jpeg;base64,{b64_2}">'
            )

    return (
        CSS_FICHA
        + '<div class="vaca-card">'
        + '<div class="hero">' + foto_principal + '<div class="velo"></div>' + mini
        + '<div class="titulo">'
        + '<div class="nombre-fila">'
        + f'<span class="nombre-vaca"># {animal}</span>'
        + f'<span class="pill" style="background:{color_etapa(d["etapa"])}">'
        + f'{d["etapa"] or "SIN REGISTRO"}</span>'
        + "</div>"
        + '<div class="sub-hero">Registro productivo individual</div>'
        + "</div></div>"
        + '<div class="cuerpo">'
        + f'<div class="stats">{stats_html}</div>'
        + '<div class="seccion"><h4>Salud y reproducción</h4>'
        + filas_html + "</div>"
        + bloque_avisos
        + "</div></div>"
    )


def mostrar_ficha(animal: str) -> None:
    html = ficha_vaca_html(animal)
    if html:
        st.markdown(html, unsafe_allow_html=True)
        components.html(LIGHTBOX_JS, height=0)


def barra_lateral() -> tuple[str, str | None]:
    with st.sidebar:
        st.markdown(
            '<div class="marca"><div class="logo">AGRORDEN</div>'
            '<div class="slogan">Gestión ganadera</div></div>',
            unsafe_allow_html=True,
        )
        seccion = st.radio(
            "Sección",
            ["Resumen y alertas", "Días abiertos", "Peso", "Producción"],
            label_visibility="collapsed",
        )
        lotes = leer_vista(V_HATO)["lote"].tolist()
        lote = st.selectbox("Filtrar por lote", ["Todos"] + lotes)
        st.divider()
        st.caption("El estado de su finca de un vistazo, calculado con los "
                   "registros que usted ya anota.")
    return seccion, None if lote == "Todos" else lote


def alertas(lote: str | None) -> None:
    st.subheader("A qué le debe prestar atención")
    dias = filtrar_por_lote(leer_vista(V_DIAS), lote)
    peso = leer_vista(V_PESO)
    peso_reciente = peso.sort_values("fecha_actual").groupby(
        "numero_visible", as_index=False).tail(1)

    criticas = dias[dias["dias_abiertos"] > UMBRAL_DIAS_ABIERTOS]
    sin_cubrir = dias[dias["fecha_cubricion"].isna()]
    bajando = peso_reciente[peso_reciente["g_dia"] < 0]

    mensajes = []
    if not bajando.empty:
        lista = ", ".join(bajando["numero_visible"].head(6))
        mensajes.append(
            f'<div class="aviso"><strong>{len(bajando)} animales están bajando '
            "de peso</strong> según sus últimos pesajes (" + lista + "). Vale la "
            "pena revisar su alimentación o salud.</div>")
    if not criticas.empty:
        lista = ", ".join(criticas["numero_visible"].head(6))
        mas = f" y otras {len(criticas) - 6}" if len(criticas) > 6 else ""
        mensajes.append(
            f'<div class="aviso"><strong>{len(criticas)} vacas llevan más de '
            f"{UMBRAL_DIAS_ABIERTOS} días sin quedar preñadas</strong> después "
            "de su parto (" + lista + mas + "). Conviene revisarlas con el "
            "veterinario.</div>")
    if not sin_cubrir.empty:
        mensajes.append(
            f'<div class="aviso-ojo"><strong>{len(sin_cubrir)} vacas parieron y '
            "no se les ha registrado monta ni inseminación.</strong> Si ya se "
            "sirvieron, falta anotarlo.</div>")
    if not mensajes:
        st.markdown('<div class="aviso-ok"><strong>Todo en orden:</strong> no '
                    "hay alertas para este filtro.</div>", unsafe_allow_html=True)
    for m in mensajes:
        st.markdown(m, unsafe_allow_html=True)

    if not criticas.empty:
        with st.expander(f"Ver tabla de las {len(criticas)} vacas críticas"):
            t = criticas.copy()
            t["fecha_parto"] = t["fecha_parto"].map(
                lambda v: fecha_corta(v) if pd.notna(v) else "")
            t = t.rename(columns={
                "numero_visible": "Vaca", "nombre_lote": "Lote",
                "fecha_parto": "Último parto",
                "dias_abiertos": "Días sin preñar"})
            st.dataframe(t, use_container_width=True, hide_index=True)
            boton_excel(criticas, "vacas_criticas_dias_abiertos")
    if not bajando.empty:
        with st.expander(f"Ver tabla de los {len(bajando)} animales bajando de peso"):
            st.dataframe(
                bajando[["numero_visible", "nombre_lote", "fecha_actual",
                         "peso_actual", "g_dia"]],
                use_container_width=True, hide_index=True,
            )
            boton_excel(bajando, "animales_perdiendo_peso")


def pagina_resumen(lote: str | None) -> None:
    st.header("Resumen del hato")
    st.caption("Cuántos animales hay en cada lote de la finca.")
    hato = leer_vista(V_HATO)
    if lote:
        hato = hato[hato["lote"] == lote]
    c1, c2 = st.columns(2)
    c1.metric("Animales", int(hato["total"].sum()))
    c2.metric("Lotes" if not lote else "Lote seleccionado",
              int((hato["total"] > 0).sum()) if not lote else lote)
    st.dataframe(hato, use_container_width=True, hide_index=True)
    st.divider()
    alertas(lote)


def pagina_dias_abiertos(lote: str | None) -> None:
    st.header("Días abiertos")
    st.caption("Los **días abiertos** son los días que lleva una vaca sin quedar "
               "preñada desde su último parto. Entre menos días, mejor: lo ideal "
               "es que quede preñada pronto después de parir.")
    dias = filtrar_por_lote(leer_vista(V_DIAS), lote)
    proximos = filtrar_por_lote(leer_vista(V_PROX_PARTOS), lote)

    if dias.empty and proximos.empty:
        st.info("Sin datos para este filtro.")
        return

    if not dias.empty:
        c1, c2 = st.columns(2)
        c1.metric("Promedio de días sin preñar", f"{dias['dias_abiertos'].mean():.0f}")
        c2.metric("Vacas evaluadas", len(dias))

        criticas = dias[dias["dias_abiertos"] > UMBRAL_DIAS_ABIERTOS]
        atencion = dias[(dias["dias_abiertos"] >= 100)
                        & (dias["dias_abiertos"] <= UMBRAL_DIAS_ABIERTOS)]
        bien = dias[dias["dias_abiertos"] < 100]

        st.markdown(
            '<div class="estado-grid">'
            f'<div class="estado-card revisar"><div class="num">{len(criticas)}</div>'
            '<div class="tit">Por revisar</div>'
            f'<div class="det">más de {UMBRAL_DIAS_ABIERTOS} días sin preñar</div></div>'
            f'<div class="estado-card atencion"><div class="num">{len(atencion)}</div>'
            '<div class="tit">En atención</div>'
            f'<div class="det">entre 100 y {UMBRAL_DIAS_ABIERTOS} días</div></div>'
            f'<div class="estado-card ok"><div class="num">{len(bien)}</div>'
            '<div class="tit">Al día</div>'
            '<div class="det">menos de 100 días</div></div>'
            + "</div>",
            unsafe_allow_html=True,
        )

        def grupo(d: int) -> str:
            if d > UMBRAL_DIAS_ABIERTOS:
                return "Por revisar"
            if d >= 100:
                return "En atención"
            return "Al día"

        resumen = (
            dias.assign(Grupo=dias["dias_abiertos"].apply(grupo))
            .groupby("Grupo", observed=True).size().reset_index(name="Vacas")
        )
        orden = ["Al día", "En atención", "Por revisar"]
        resumen["Grupo"] = pd.Categorical(resumen["Grupo"], orden, ordered=True)
        resumen = resumen.sort_values("Grupo")
        resumen["Hato"] = "Hato"
        fig_hato = px.bar(
            resumen, x="Vacas", y="Hato", color="Grupo",
            orientation="h",
            color_discrete_map={
                "Al día": "#5F7F4A", "En atención": "#C99A3C",
                "Por revisar": "#B4552D",
            },
            text="Vacas",
        )
        fig_hato.update_traces(
            textposition="inside", insidetextanchor="middle",
            textfont=dict(color="#FFFFFF", size=15, family="'Segoe UI', sans-serif"),
            marker_line_width=0,
        )
        estilizar(fig_hato, "Así está su hato hoy")
        fig_hato.update_layout(
            barmode="stack", height=175, yaxis_title=None, xaxis_title=None,
            legend_title_text=None,
        )
        st.plotly_chart(fig_hato, use_container_width=True)

        tabla = dias.copy()
        tabla["Estado"] = tabla["dias_abiertos"].apply(grupo)
        tabla["fecha_parto"] = tabla["fecha_parto"].map(
            lambda v: fecha_corta(v) if pd.notna(v) else "")
        tabla["fecha_cubricion"] = tabla["fecha_cubricion"].map(
            lambda v: fecha_corta(v) if pd.notna(v) else "")
        tabla = tabla.rename(columns={
            "numero_visible": "Vaca",
            "nombre_lote": "Lote",
            "fecha_parto": "Último parto",
            "fecha_cubricion": "Última monta o servicio",
            "dias_abiertos": "Días sin preñar",
        })
        st.dataframe(
            tabla[["Vaca", "Lote", "Último parto", "Última monta o servicio",
                   "Días sin preñar", "Estado"]],
            use_container_width=True, hide_index=True,
        )
        boton_excel(tabla, "dias_abiertos")

    if not proximos.empty:
        st.subheader("Partos que se acercan")
        st.caption("Estas vacas tienen un parto anotado para los próximos meses. "
                   "Téngalas en la mira para atender el parto a tiempo.")
        items = "".join(
            f'<div class="prox-item"><b>{r.numero_visible}</b><br>'
            f'<span>{fecha_corta(r.fecha_parto)}</span></div>'
            for r in proximos.itertuples()
        )
        st.markdown(f'<div class="prox-lista">{items}</div>', unsafe_allow_html=True)
        export = proximos.rename(columns={
            "numero_visible": "Vaca", "nombre_lote": "Lote",
            "fecha_parto": "Parto esperado",
        })
        boton_excel(export, "partos_proximos")


def pagina_peso(lote: str | None) -> None:
    st.header("Evolución de peso")
    st.caption("Cuánto pesa cada animal y si está engordando o adelgazando "
               "entre un pesaje y otro. La ganancia se mide en **gramos por día**.")
    todo = leer_vista(V_PESO)
    opciones = sorted(set(filtrar_por_lote(todo, lote)["numero_visible"]))
    if not opciones:
        st.info("Sin pesajes para este filtro.")
        return
    animal = st.selectbox("Animal", opciones)
    mostrar_ficha(animal)
    datos = todo[todo["numero_visible"] == animal].sort_values("fecha_actual")
    ultimo = datos.iloc[-1]
    c1, c2, c3 = st.columns(3)
    c1.metric("Peso actual", f"{ultimo['peso_actual']:.0f} kg")
    c2.metric("Pesajes registrados", len(datos))
    c3.metric("Última ganancia",
              f"{ultimo['g_dia']:.0f} g/día" if pd.notna(ultimo["g_dia"]) else "n/d")
    fig = px.line(
        datos, x="fecha_actual", y="peso_actual", markers=True,
        labels={"fecha_actual": "Fecha", "peso_actual": "Peso (kg)"},
    )
    fig.update_traces(line_color="#55803C", marker_color="#2E4B2F")
    fig.add_annotation(
        x=ultimo["fecha_actual"], y=ultimo["peso_actual"],
        text=f"Último pesaje: {ultimo['peso_actual']:.0f} kg",
        showarrow=True, arrowhead=2, arrowcolor="#5F7F4A",
        font=dict(color="#3C5230", size=14),
    )
    estilizar(fig, f"Peso de {animal}")
    st.plotly_chart(fig, use_container_width=True)
    if pd.notna(ultimo["g_dia"]):
        if ultimo["g_dia"] >= 0:
            texto = (
                f"Cada punto es un pesaje. El último fue el "
                f"{fecha_corta(ultimo['fecha_actual'])} con "
                f"{ultimo['peso_actual']:.0f} kg, y el animal está "
                f"<strong>engordando</strong> a razón de "
                f"{ultimo['g_dia']:.0f} gramos por día."
            )
            clase = "nota-leer"
        else:
            texto = (
                f"Cada punto es un pesaje. El último fue el "
                f"{fecha_corta(ultimo['fecha_actual'])} con "
                f"{ultimo['peso_actual']:.0f} kg, pero el animal está "
                f"<strong>bajando de peso</strong> ({abs(ultimo['g_dia']):.0f} "
                "gramos por día menos). Revise su alimentación o salud."
            )
            clase = "aviso"
        st.markdown(f'<div class="{clase}"><strong>Cómo leer esta gráfica: </strong>'
                    f"{texto}</div>", unsafe_allow_html=True)
    with st.expander("Tabla de ganancias entre pesajes"):
        t = datos.copy()
        for col in ("fecha_anterior", "fecha_actual"):
            t[col] = t[col].map(lambda v: fecha_corta(v) if pd.notna(v) else "")
        t = t.rename(columns={
            "numero_visible": "Animal", "nombre_lote": "Lote",
            "fecha_anterior": "Pesaje anterior", "fecha_actual": "Último pesaje",
            "peso_actual": "Peso (kg)", "g_dia": "Gramos por día",
        })
        st.dataframe(t, use_container_width=True, hide_index=True)
        boton_excel(datos, f"ganancias_peso_{animal}")


def pagina_produccion(lote: str | None) -> None:
    st.header("Curva de lactancia")
    st.caption("Litros de leche por día. La curva normal sube después del parto, "
               "llega a un **pico** y luego baja poco a poco hasta el secado.")
    prod = leer_vista(V_PROD)
    pico = leer_vista(V_PICO)
    opciones = sorted(set(filtrar_por_lote(prod, lote)["numero_visible"]))
    if not opciones:
        st.info("Sin producción para este filtro.")
        return
    animal = st.selectbox("Animal", opciones)
    mostrar_ficha(animal)

    st.subheader("Comparación entre vacas")
    comparar = st.multiselect(
        "Selecciona 2 o más vacas para superponer sus curvas",
        opciones,
        help="Detecta a simple vista curvas atípicas.",
    )
    if len(comparar) >= 2:
        datos_comp = prod[prod["numero_visible"].isin(comparar)]
        fig_comp = px.line(
            datos_comp, x="fecha_real", y="litros", color="numero_visible",
            color_discrete_sequence=PALETA_GRAFICAS,
            labels={"fecha_real": "Fecha", "litros": "Litros de leche al día",
                    "numero_visible": "Vaca"},
        )
        estilizar(fig_comp, "Comparación de vacas")
        st.plotly_chart(fig_comp, use_container_width=True)
        st.caption("Cada color es una vaca. Si la línea de una vaca queda muy "
                   "por debajo de las demás todo el tiempo, esa vaca produce "
                   "menos y vale la pena revisarla.")
    elif comparar:
        st.caption("Selecciona al menos una vaca más para comparar.")

    datos = prod[prod["numero_visible"] == animal]
    fila_pico = pico[pico["numero_visible"] == animal]
    c1, c2 = st.columns(2)
    c1.metric("Registros de ordeño", len(datos))
    if not fila_pico.empty:
        c2.metric("Pico de lactancia", f"{fila_pico.iloc[0]['litros_pico']:.1f} L",
                  help=f"El {fecha_corta(fila_pico.iloc[0]['fecha_pico'])}")
    fig = px.line(
        datos, x="fecha_real", y="litros", markers=True,
        labels={"fecha_real": "Fecha", "litros": "Litros de leche al día"},
    )
    fig.update_traces(line_color="#3F6E5A", marker_color="#2E4B2F")
    promedio = datos["litros"].mean()
    fig.add_hline(
        y=promedio, line_dash="dash", line_color="#B4552D",
        annotation_text=f"Su promedio: {promedio:.1f} L",
        annotation_position="top left",
    )
    if not fila_pico.empty:
        p = fila_pico.iloc[0]
        fig.add_annotation(
            x=p["fecha_pico"], y=p["litros_pico"],
            text=f"Mejor día: {p['litros_pico']:.0f} L",
            showarrow=True, arrowhead=2, arrowcolor="#B4552D",
            font=dict(color="#6E3A1E", size=14),
        )
    estilizar(fig, f"Leche diaria de {animal}")
    st.plotly_chart(fig, use_container_width=True)
    boton_excel(datos, f"produccion_{animal}")
    if not fila_pico.empty:
        p = fila_pico.iloc[0]
        st.markdown(
            '<div class="nota-leer"><strong>Cómo leer esta gráfica: </strong>'
            "cada punto es un día de ordeño. La línea punteada es su promedio "
            f"({promedio:.1f} L). El punto marcado es su mejor día "
            f"({fecha_corta(p['fecha_pico'])} con {p['litros_pico']:.0f} litros)."
            "</div>",
            unsafe_allow_html=True,
        )


PAGINAS = {
    "Resumen y alertas": pagina_resumen,
    "Días abiertos": pagina_dias_abiertos,
    "Peso": pagina_peso,
    "Producción": pagina_produccion,
}


def main() -> None:
    st.markdown(CSS_GLOBAL, unsafe_allow_html=True)
    seccion, lote = barra_lateral()
    PAGINAS[seccion](lote)


if __name__ == "__main__":
    main()
