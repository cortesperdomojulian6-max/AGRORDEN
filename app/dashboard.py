"""Dashboard AGRORDEN — capa visual de consulta (SPEC-006).

Ejecución:
    streamlit run app/dashboard.py

Principios: solo lectura; conexión por .env; las vistas de SPEC-004 son la API.
Identidad visual: lenguaje "chapeta" de agrorden-vision.html — tipografía
Fraunces/IBM Plex, paleta potrero-hueso-hierro-paja, tarjetas con esquina de
ear-tag. La lógica de datos no cambia: solo presentación.
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
    page_title="AGRORDEN · Orden del hato",
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

FUENTES = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,300..900'
    '&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500;600;700'
    '" rel="stylesheet">'
)


def fotos_de(animal: str) -> list[Path]:
    carpeta = CARPETA_FOTOS / str(animal)
    return sorted(carpeta.glob("foto_*")) if carpeta.exists() else []


CSS_GLOBAL = """
<style>
:root {
  --ink:#211C16; --ink-soft:#57503F;
  --hide:#E7DCC2; --hide-dark:#D9C89C; --bone:#FAF6EC;
  --pasture:#233B29; --pasture-2:#33553B; --pasture-soft:#DCE6DA;
  --iron:#9A4522; --iron-soft:#F3E1D4;
  --straw:#B9862E; --straw-soft:#F5EAD3;
  --moss:#5C7A4E; --moss-soft:#E6EDDF;
  --line:#CBB98F;
  --sombra: 0 10px 30px rgba(33,28,22,.10);
}
html, body { background:var(--hide); }
[data-testid="stAppViewContainer"] {
  background:var(--hide);
  background-image: radial-gradient(circle at 1px 1px,
    rgba(33,28,22,.05) 1px, transparent 0);
  background-size:22px 22px;
}
[data-testid="stHeader"] { background:transparent; }
.block-container { padding-top:2rem; padding-bottom:3rem; max-width:1180px; }

h1 { font-family:'Fraunces', Georgia, serif !important; color:var(--ink) !important;
     font-weight:600 !important; letter-spacing:-.2px; }
h2, h3 { font-family:'Fraunces', Georgia, serif !important; color:var(--ink) !important; }

.cabecera-eyebrow { font-size:11px; letter-spacing:2px; text-transform:uppercase;
  color:var(--ink-soft); font-weight:600; margin-bottom:5px; }
.cabecera-titulo { font-family:'Fraunces', Georgia, serif; font-size:clamp(25px,3vw,32px);
  font-weight:600; color:var(--ink); letter-spacing:-.2px; line-height:1.15; }
.cabecera-nota { color:var(--ink-soft); font-size:13.5px; margin-top:7px;
  max-width:640px; line-height:1.55; }
.bloque-cabecera { margin-bottom:20px; }

.tag { background:var(--bone); border:1px solid var(--line);
  border-radius:14px 14px 14px 4px; position:relative; }
.tag::before { content:""; position:absolute; top:10px; left:10px; width:9px; height:9px;
  border-radius:50%; background:var(--hide);
  box-shadow: inset 0 1px 2px rgba(33,28,22,.35); pointer-events:none; }
.tag.sin-hueco::before { display:none; }

.kpi-row { display:flex; gap:14px; flex-wrap:wrap; margin:4px 0 18px 0; }
.kpi { flex:1 1 190px; padding:17px 18px 15px; box-shadow:var(--sombra); }
.kpi .top { display:flex; justify-content:space-between; align-items:center; gap:8px; }
.kpi .label { font-size:11px; letter-spacing:1.2px; text-transform:uppercase;
  font-weight:600; color:var(--ink-soft); }
.kpi .trend { font-family:'IBM Plex Mono',monospace; font-size:10.5px; font-weight:600;
  padding:3px 8px; border-radius:999px; white-space:nowrap; }
.kpi .trend.ok   { background:var(--moss-soft); color:var(--moss); }
.kpi .trend.ojo  { background:var(--straw-soft); color:#8A5F16; }
.kpi .trend.malo { background:var(--iron-soft); color:var(--iron); }
.kpi .value { font-family:'Fraunces', Georgia, serif; font-size:36px; font-weight:600;
  line-height:1.05; color:var(--ink); margin-top:9px; }
.kpi .sub { font-size:12px; color:var(--ink-soft); margin-top:4px; }
.kpi.accent-pasture { border-top:3px solid var(--pasture); }
.kpi.accent-moss    { border-top:3px solid var(--moss); }
.kpi.accent-straw   { border-top:3px solid var(--straw); }
.kpi.accent-iron    { border-top:3px solid var(--iron); }

.tarjeta { padding:18px 20px 16px; box-shadow:var(--sombra); margin-bottom:16px; }
.tarjeta-titulo { font-family:'Fraunces', Georgia, serif; font-size:18px;
  font-weight:600; color:var(--ink); }
.tarjeta-nota { font-size:12.5px; color:var(--ink-soft); margin:2px 0 12px 0;
  line-height:1.5; }

.libro-row { display:flex; align-items:center; gap:12px; padding:11px 4px;
  border-bottom:1px dashed var(--line); }
.libro-row:last-child { border-bottom:none; }
.libro-bandera { width:4px; align-self:stretch; border-radius:3px; flex:0 0 4px; }
.libro-bandera.hierro { background:var(--iron); }
.libro-bandera.paja   { background:var(--straw); }
.libro-cuerpo { flex:1; min-width:0; }
.libro-titulo { font-size:13.5px; font-weight:600; color:var(--ink); }
.libro-sub { font-size:12px; color:var(--ink-soft); margin-top:1px; line-height:1.45; }
.libro-chapeta { font-family:'IBM Plex Mono',monospace; font-size:11.5px; font-weight:600;
  background:var(--hide); border:1px solid var(--line);
  border-radius:8px 8px 8px 2px; padding:5px 9px 5px 16px; white-space:nowrap;
  position:relative; color:var(--ink); }
.libro-chapeta::before { content:""; position:absolute; left:6px; top:50%;
  transform:translateY(-50%); width:4px; height:4px; border-radius:50%;
  background:var(--hide-dark); }

.chips-partos { display:flex; flex-wrap:wrap; gap:9px; }
.chip-parto { font-family:'IBM Plex Mono',monospace; background:var(--pasture-soft);
  border:1px solid #C3D3C0; border-radius:10px 10px 10px 3px; padding:9px 12px 8px 19px;
  font-size:12px; position:relative; min-width:120px; color:var(--ink-soft); }
.chip-parto::before { content:""; position:absolute; left:9px; top:11px; width:5px;
  height:5px; border-radius:50%; background:#fff;
  box-shadow: inset 0 1px 1px rgba(33,28,22,.25); }
.chip-parto b { display:block; font-size:13px; color:var(--pasture); font-weight:700; }
.chip-parto span { font-family:'IBM Plex Sans',sans-serif; font-size:11px; }

.estado-grid { display:flex; gap:14px; flex-wrap:wrap; margin:12px 0 16px 0; }
.estado-card { flex:1 1 170px; box-shadow:var(--sombra); padding:16px 18px 14px;
  border-top:4px solid var(--piedra, var(--line)); }
.estado-card .num { font-family:'Fraunces', Georgia, serif; font-size:34px;
  font-weight:600; color:var(--ink); line-height:1.1; }
.estado-card .tit { font-size:11.5px; font-weight:700; letter-spacing:1.2px;
  text-transform:uppercase; margin-top:5px; color:var(--ink-soft); }
.estado-card .det { color:var(--ink-soft); font-size:12px; margin-top:3px; }
.estado-card.revisar  { border-top-color:var(--iron); }
.estado-card.revisar .tit { color:var(--iron); }
.estado-card.atencion { border-top-color:var(--straw); }
.estado-card.atencion .tit { color:#8A5F16; }
.estado-card.ok       { border-top-color:var(--moss); }
.estado-card.ok .tit { color:var(--moss); }

.aviso-suave { background:var(--straw-soft); border-left:4px solid var(--straw);
  border-radius:10px 10px 10px 3px; padding:12px 15px; margin:7px 0;
  color:#6B5416; font-size:14.5px; }
.aviso-fuerte { background:var(--iron-soft); border-left:4px solid var(--iron);
  border-radius:10px 10px 10px 3px; padding:12px 15px; margin:7px 0;
  color:#6E3013; font-size:14.5px; }
.nota-leer { background:rgba(250,246,236,.85); border:1px dashed var(--line);
  border-radius:10px 10px 10px 3px; padding:12px 15px; margin:8px 0 2px 0;
  color:var(--ink-soft); font-size:14px; line-height:1.5; }

.marca { font-family:'Fraunces', Georgia, serif; margin-bottom:14px; }
.marca .logo { font-size:21px; font-weight:700; color:var(--bone); letter-spacing:.5px; }
.marca .slogan { margin-top:3px; color:#C7D3C4; font-size:9.5px;
  letter-spacing:1.6px; text-transform:uppercase;
  font-family:'IBM Plex Sans',sans-serif; }
.usuario-riel { display:flex; align-items:center; gap:10px; margin-top:14px;
  padding-top:14px; border-top:1px solid rgba(255,255,255,.12); }
.usuario-riel .avatar { width:32px; height:32px; border-radius:9px;
  background:var(--straw); color:var(--ink); font-family:'Fraunces',serif;
  font-weight:700; font-size:13px; display:flex; align-items:center;
  justify-content:center; flex:0 0 32px; }
.usuario-riel .quien { font-size:12.5px; line-height:1.35; }
.usuario-riel .quien b { display:block; color:#FAF6EC; font-size:12.5px; }
.usuario-riel .quien span { color:#B9C4B4; font-size:11px; }

[data-testid="stSidebar"] { background:var(--pasture); border-right:none; }
[data-testid="stSidebar"] * { color:#D8E0D3; }
[data-testid="stSidebar"] hr { border-color:rgba(255,255,255,.14); }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
  color:#B9C4B4 !important; font-size:12px; line-height:1.5; }
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover div:first-child {
  background:rgba(255,255,255,.08); border-radius:8px; }
[data-testid="stSidebar"] [data-testid="stSelectbox"] label,
[data-testid="stSidebar"] [data-testid="stRadio"] label { font-weight:500; }

[data-testid="stMetric"] { display:none; }
.stDownloadButton button, .stButton button {
  background:var(--bone); color:var(--ink); border:1px solid var(--line);
  border-radius:12px 12px 12px 3px; font-weight:600;
  font-family:'IBM Plex Sans',sans-serif; }
.stDownloadButton button:hover, .stButton button:hover {
  background:var(--hide); color:var(--ink); border-color:var(--hide-dark); }

.js-plotly-plot .plotly .modebar { background:transparent !important; }

@media (max-width:640px) {
  .block-container { padding-top:1.2rem; }
  .kpi .value { font-size:29px; }
  .estado-card .num { font-size:27px; }
}
</style>
"""

CSS_FICHA = """
<style>
.ficha { display:block; max-width:720px; margin:0 auto 18px auto;
  box-shadow:var(--sombra); border-radius:16px 16px 16px 4px; overflow:hidden;
  background:var(--bone); border:1px solid var(--line); }
.ficha-hero { position:relative; height:clamp(200px, 34vw, 280px);
  background:linear-gradient(165deg,#2B4A33,#16281B); }
.ficha-hero img.principal { width:100%; height:100%; object-fit:cover;
  display:block; }
.ficha-velo { position:absolute; inset:0; pointer-events:none;
  background:linear-gradient(180deg,rgba(10,16,10,.05) 40%,rgba(10,16,10,.62) 100%); }
.ficha-chapeta { position:absolute; top:16px; left:16px;
  background:var(--bone); color:var(--ink);
  font-family:'IBM Plex Mono',monospace; font-weight:700; font-size:15px;
  padding:7px 12px 6px 20px; border-radius:10px 10px 10px 2px;
  box-shadow:0 3px 10px rgba(0,0,0,.28); }
.ficha-chapeta::before { content:""; position:absolute; left:8px; top:50%;
  transform:translateY(-50%); width:5px; height:5px; border-radius:50%;
  background:var(--hide-dark); }
.ficha-inferior { position:absolute; bottom:13px; left:16px; right:16px;
  display:flex; justify-content:space-between; align-items:flex-end;
  gap:10px; pointer-events:none; }
.ficha-estado { background:var(--moss); color:#fff; font-size:10.5px; font-weight:700;
  letter-spacing:1.1px; text-transform:uppercase; padding:4px 11px;
  border-radius:999px; box-shadow:0 2px 8px rgba(0,0,0,.3); }
.ficha-lote { color:rgba(255,255,255,.85); font-size:11.5px;
  font-family:'IBM Plex Mono',monospace; text-shadow:0 1px 3px rgba(0,0,0,.5); }
.ficha-mini { position:absolute; right:16px; top:16px; width:66px; height:66px;
  border-radius:10px 10px 10px 3px; object-fit:cover;
  border:3px solid rgba(250,246,236,.94); box-shadow:0 2px 12px rgba(0,0,0,.45); }
.vaca-foto { cursor:zoom-in; }
.ficha-cuerpo { padding:20px 22px 18px; }
.ficha-stats { display:flex; gap:10px; flex-wrap:wrap; margin-bottom:16px; }
.fstat { flex:1 1 130px; background:var(--hide); border:1px solid var(--line);
  border-radius:10px 10px 10px 3px; padding:10px 12px; min-width:0; }
.fstat .l { font-size:10px; text-transform:uppercase; letter-spacing:.9px;
  color:var(--ink-soft); font-weight:600; }
.fstat .v { font-family:'Fraunces', Georgia, serif; font-size:20px; font-weight:600;
  margin-top:3px; color:var(--ink); }
.ficha-secciones { display:flex; flex-wrap:wrap; gap:16px; }
.fsec { flex:1 1 220px; min-width:0; }
.fsec h4 { font-size:11px; letter-spacing:1.3px; text-transform:uppercase;
  color:var(--pasture); font-weight:700; margin:0 0 7px; }
.fsec .fila { display:flex; justify-content:space-between; gap:10px; font-size:13px;
  padding:6px 0; border-bottom:1px dashed var(--line); }
.fsec .fila:last-child { border-bottom:none; }
.fsec .fila .k { color:var(--ink-soft); }
.fsec .fila .v { font-weight:600; color:var(--ink); text-align:right; }
.fsec .fila .v.mono { font-family:'IBM Plex Mono',monospace; font-weight:600; }
.ficha-avisos { margin-top:16px; }
.aviso-ficha { border-radius:10px 10px 10px 3px; padding:11px 14px;
  font-size:13.5px; line-height:1.5; margin-bottom:8px; }
.aviso-ficha.revisar { background:var(--iron-soft); border:1px solid #E5C9B4;
  color:#6E3013; }
.aviso-ficha.nota { background:var(--pasture-soft); border:1px solid #C3D3C0;
  color:#33472F; }
@media (max-width:640px) {
  .ficha-cuerpo { padding:14px 15px 14px; }
  .fstat { flex:1 1 44%; padding:9px 11px; }
  .fstat .v { font-size:18px; }
  .ficha-mini { width:52px; height:52px; }
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
    'border-radius:12px 12px 12px 4px;box-shadow:0 24px 90px rgba(0,0,0,.65);user-select:none;}' +
    '#ag-lb .cerrar{position:absolute;top:12px;right:22px;color:#FAF6EC;' +
    'font-size:38px;line-height:1;cursor:pointer;font-family:Georgia,serif;}' +
    '#ag-lb .ayuda{position:absolute;bottom:15px;left:0;right:0;text-align:center;' +
    'color:rgba(250,246,236,.72);font:12.5px Georgia,serif;letter-spacing:.5px;}';
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

PALETA_GRAFICAS = ["#233B29", "#9A4522", "#B9862E", "#33553B", "#5C7A4E"]

COLORES_ETAPA = {
    "ORDEÑO": "#5C7A4E",
    "PREÑEZ": "#33553B",
    "VACIA": "#9A4522",
    "HORRA": "#B9862E",
    "REPRODUCTOR": "#6B5740",
}


def color_etapa(etapa: str) -> str:
    etapa_up = (etapa or "").upper()
    for clave, color in COLORES_ETAPA.items():
        if clave in etapa_up:
            return color
    return "#57503F"


def estilizar(fig, titulo: str | None = None):
    fig.update_layout(
        font=dict(family="'IBM Plex Sans', sans-serif", size=13, color="#211C16"),
        title=dict(text=titulo, font=dict(family="'Fraunces', Georgia, serif",
                                          size=17, color="#211C16"), x=0.01),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(gridcolor="#D9CDA8", zeroline=False),
        yaxis=dict(gridcolor="#D9CDA8", zeroline=False),
        legend=dict(bgcolor="#FAF6EC", bordercolor="#CBB98F", borderwidth=1),
        margin=dict(l=10, r=10, t=46 if titulo else 16, b=10),
        hovermode="closest",
    )
    return fig


def cabecera(eyebrow: str, titulo: str, nota: str | None = None) -> None:
    html = ('<div class="bloque-cabecera">'
            f'<div class="cabecera-eyebrow">{eyebrow}</div>'
            f'<div class="cabecera-titulo">{titulo}</div>')
    if nota:
        html += f'<div class="cabecera-nota">{nota}</div>'
    st.markdown(html + "</div>", unsafe_allow_html=True)


def kpis(*placas: dict) -> None:
    html = '<div class="kpi-row">'
    for p in placas:
        trend = ""
        if p.get("tendencia"):
            texto, clase = p["tendencia"]
            trend = f'<span class="trend {clase}">{texto}</span>'
        html += (
            f'<div class="tag kpi accent-{p.get("acento", "pasture")} sin-hueco">'
            f'<div class="top"><span class="label">{p["etiqueta"]}</span>{trend}</div>'
            f'<div class="value">{p["valor"]}</div>'
            f'<div class="sub">{p.get("detalle", "")}</div></div>'
        )
    st.markdown(html + "</div>", unsafe_allow_html=True)


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
    return pd.Timestamp(valor).strftime("%d/%m/%y")


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
                "SELECT nombre_lote, fecha_parto, dias_abiertos "
                "FROM v_dias_abiertos WHERE numero_visible = %s",
                (animal,),
            )
            fila = cur.fetchone()
            if fila:
                lote, parto, abiertos = fila
            else:
                lote, parto, abiertos = (None, None, None)

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
        "etapa": etapa, "parto": parto, "abiertos": abiertos, "lote": lote,
        "pico_litros": pico_litros, "pico_fecha": pico_fecha,
        "prom_litros": prom_litros, "peso_actual": peso_actual,
        "g_dia": g_dia, "num_partos": num_partos, "notas": notas,
    }


def ficha_vaca_html(animal: str) -> str | None:
    fotos = fotos_de(animal)
    d = datos_ficha(animal)
    if not fotos and d["etapa"] is None:
        return None

    def fstat(lbl: str, val: str) -> str:
        return (f'<div class="fstat"><div class="l">{lbl}</div>'
                f'<div class="v">{val}</div></div>')

    def fila(k: str, v: str, mono: bool = False) -> str:
        clase = "v mono" if mono else "v"
        return (f'<div class="fila"><span class="k">{k}</span>'
                f'<span class="{clase}">{v}</span></div>')

    stats_html = "".join([
        fstat("Peso actual", f"{d['peso_actual']:.0f} kg"
              if d["peso_actual"] is not None else "Pendiente"),
        fstat("Días sin preñar", f"{d['abiertos']:.0f}"
              if d["abiertos"] is not None else "—"),
        fstat("Partos", str(d["num_partos"])),
        fstat("Producción", f"{d['prom_litros']:.1f} L"
              if d["prom_litros"] is not None else "—"),
    ])

    seccion_repro = "".join([
        fila("Último parto", fecha_corta(d["parto"])
             if d["parto"] is not None else "Sin registro", mono=True),
        fila("Días sin preñar", f"{d['abiertos']:.0f}"
             if d["abiertos"] is not None else "—", mono=True),
        fila("Estado", d["etapa"] or "Sin registro"),
    ])
    seccion_prod = "".join([
        fila("Pico lactancia", f"{d['pico_litros']:.0f} L"
             if d["pico_litros"] is not None else "—", mono=True),
        fila("Fecha pico", fecha_corta(d["pico_fecha"])
             if d["pico_fecha"] is not None else "—", mono=True),
        fila("Promedio", f"{d['prom_litros']:.1f} L/día"
             if d["prom_litros"] is not None else "—", mono=True),
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
        '<div class="ficha-avisos">' + avisos_html + "</div>" if avisos_html else ""
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
                f'<img class="ficha-mini vaca-foto" alt="Segunda foto de {animal}" '
                f'src="data:image/jpeg;base64,{b64_2}">'
            )

    lote_txt = f"Lote {d['lote']}" if d["lote"] else "AGRORDEN"
    return (
        CSS_FICHA
        + '<div class="ficha">'
        + '<div class="ficha-hero">' + foto_principal + '<div class="ficha-velo"></div>'
        + mini
        + f'<div class="ficha-chapeta">N.º {animal}</div>'
        + '<div class="ficha-inferior">'
        + f'<span class="ficha-estado" style="background:{color_etapa(d["etapa"])}">'
        + f'{d["etapa"] or "SIN REGISTRO"}</span>'
        + f'<span class="ficha-lote">{lote_txt}</span>'
        + "</div></div>"
        + '<div class="ficha-cuerpo">'
        + f'<div class="ficha-stats">{stats_html}</div>'
        + '<div class="ficha-secciones">'
        + '<div class="fsec"><h4>Reproducción</h4>' + seccion_repro + "</div>"
        + '<div class="fsec"><h4>Producción</h4>' + seccion_prod + "</div>"
        + "</div>"
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
            '<div class="slogan">Orden del hato</div></div>',
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
        st.markdown('<div class="usuario-riel"><div class="avatar">JC</div>'
                    '<div class="quien"><b>Julián Cortés</b>'
                    "<span>Desarrollador</span></div></div>",
                    unsafe_allow_html=True)
    return seccion, None if lote == "Todos" else lote


def alertas(lote: str | None) -> None:
    dias = filtrar_por_lote(leer_vista(V_DIAS), lote)
    peso = leer_vista(V_PESO)
    peso_reciente = peso.sort_values("fecha_actual").groupby(
        "numero_visible", as_index=False).tail(1)

    criticas = dias[dias["dias_abiertos"] > UMBRAL_DIAS_ABIERTOS]
    sin_cubrir = dias[dias["fecha_cubricion"].isna()]
    bajando = peso_reciente[peso_reciente["g_dia"] < 0]

    filas = []
    for r in criticas.itertuples():
        filas.append(
            '<div class="libro-row"><div class="libro-bandera hierro"></div>'
            '<div class="libro-cuerpo">'
            f'<div class="libro-titulo">{r.dias_abiertos:.0f} días sin preñar</div>'
            f'<div class="libro-sub">{r.nombre_lote or "Sin lote"} · '
            f'último parto {fecha_corta(r.fecha_parto)}</div></div>'
            f'<div class="libro-chapeta">N.º {r.numero_visible}</div></div>'
        )
    for r in bajando.itertuples():
        filas.append(
            '<div class="libro-row"><div class="libro-bandera paja"></div>'
            '<div class="libro-cuerpo">'
            f'<div class="libro-titulo">Pérdida de peso · {abs(r.g_dia):.0f} g/día</div>'
            f'<div class="libro-sub">{r.nombre_lote or "Sin lote"} · '
            f'pesaje del {fecha_corta(r.fecha_actual)}</div></div>'
            f'<div class="libro-chapeta">N.º {r.numero_visible}</div></div>'
        )
    for r in sin_cubrir.itertuples():
        filas.append(
            '<div class="libro-row"><div class="libro-bandera paja"></div>'
            '<div class="libro-cuerpo">'
            '<div class="libro-titulo">Parió y no hay monta registrada</div>'
            '<div class="libro-sub">Si ya se sirvió, falta anotarlo</div></div>'
            f'<div class="libro-chapeta">N.º {r.numero_visible}</div></div>'
        )

    if filas:
        st.markdown(
            '<div class="tag tarjeta"><div class="tarjeta-titulo">'
            "Qué requiere atención</div>"
            '<div class="tarjeta-nota">Ordenado de más a menos urgente.</div>'
            + "".join(filas) + "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown('<div class="tag tarjeta"><div class="tarjeta-titulo">'
                    "Qué requiere atención</div>"
                    '<div class="tarjeta-nota">Todo en orden: no hay alertas '
                    "para este filtro.</div></div>", unsafe_allow_html=True)

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
    eyebrow = f"Finca · {lote}" if lote else "Finca · todos los lotes"
    cabecera(eyebrow, "Resumen del hato",
             "Así está su hato hoy, calculado con los registros que usted ya anota.")
    hato = leer_vista(V_HATO)
    if lote:
        hato = hato[hato["lote"] == lote]
    total = int(hato["total"].sum())
    hembras = int(hato["hembras"].sum())
    pct_hembras = f"{100 * hembras / total:.0f}%" if total else "—"
    kpis(
        {"etiqueta": "Animales", "valor": str(total),
         "detalle": f"en {len(hato)} lotes" + (" activos" if not lote else ""),
         "acento": "pasture"},
        {"etiqueta": "Hembras", "valor": str(hembras),
         "detalle": "del total del hato", "tendencia": (pct_hembras, "ok"),
         "acento": "moss"},
        {"etiqueta": "Lotes" if not lote else "Lote seleccionado",
         "valor": str(int((hato["total"] > 0).sum()) if not lote else lote),
         "acento": "straw"},
    )
    if not lote:
        fig_hato_tabla = hato.rename(columns={
            "lote": "Lote", "hembras": "Hembras", "machos": "Machos",
            "total": "Total"})
        st.dataframe(fig_hato_tabla, use_container_width=True, hide_index=True)
    else:
        st.dataframe(hato, use_container_width=True, hide_index=True)
    st.divider()
    st.markdown('<h3 style="font-family:\'Fraunces\',Georgia,serif;font-size:20px;'
                'margin-bottom:4px;">A qué le debe prestar atención</h3>',
                unsafe_allow_html=True)
    alertas(lote)


def pagina_dias_abiertos(lote: str | None) -> None:
    eyebrow = f"Finca · {lote}" if lote else "Finca · todos los lotes"
    cabecera(eyebrow, "Días abiertos",
             "Los <strong>días abiertos</strong> son los días que lleva una vaca "
             "sin quedar preñada desde su último parto. Entre menos días, mejor: "
             "lo ideal es que quede preñada pronto después de parir.")
    dias = filtrar_por_lote(leer_vista(V_DIAS), lote)
    proximos = filtrar_por_lote(leer_vista(V_PROX_PARTOS), lote)

    if dias.empty and proximos.empty:
        st.info("Sin datos para este filtro.")
        return

    if not dias.empty:
        kpis(
            {"etiqueta": "Promedio de días sin preñar",
             "valor": f"{dias['dias_abiertos'].mean():.0f}",
             "detalle": "entre las vacas evaluadas", "acento": "pasture"},
            {"etiqueta": "Vacas evaluadas", "valor": str(len(dias)),
             "detalle": "con último parto registrado", "acento": "straw"},
        )

        criticas = dias[dias["dias_abiertos"] > UMBRAL_DIAS_ABIERTOS]
        atencion = dias[(dias["dias_abiertos"] >= 100)
                        & (dias["dias_abiertos"] <= UMBRAL_DIAS_ABIERTOS)]
        bien = dias[dias["dias_abiertos"] < 100]

        st.markdown(
            '<div class="estado-grid">'
            f'<div class="tag estado-card revisar sin-hueco">'
            f'<div class="num">{len(criticas)}</div>'
            '<div class="tit">Por revisar</div>'
            f'<div class="det">más de {UMBRAL_DIAS_ABIERTOS} días sin preñar</div></div>'
            f'<div class="tag estado-card atencion sin-hueco">'
            f'<div class="num">{len(atencion)}</div>'
            '<div class="tit">En atención</div>'
            f'<div class="det">entre 100 y {UMBRAL_DIAS_ABIERTOS} días</div></div>'
            f'<div class="tag estado-card ok sin-hueco">'
            f'<div class="num">{len(bien)}</div>'
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
                "Al día": "#5C7A4E", "En atención": "#B9862E",
                "Por revisar": "#9A4522",
            },
            text="Vacas",
        )
        fig_hato.update_traces(
            textposition="inside", insidetextanchor="middle",
            textfont=dict(color="#FFFFFF", size=15,
                          family="'IBM Plex Sans', sans-serif"),
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
        st.markdown(
            '<div class="tag tarjeta"><div class="tarjeta-titulo">'
            "Partos que se acercan</div>"
            '<div class="tarjeta-nota">Téngalas en la mira para atender el '
            "parto a tiempo.</div>"
            '<div class="chips-partos">'
            + "".join(
                f'<div class="chip-parto"><b>N.º {r.numero_visible}</b>'
                f"<span>{fecha_corta(r.fecha_parto)}</span></div>"
                for r in proximos.itertuples())
            + "</div></div>",
            unsafe_allow_html=True,
        )
        export = proximos.rename(columns={
            "numero_visible": "Vaca", "nombre_lote": "Lote",
            "fecha_parto": "Parto esperado",
        })
        boton_excel(export, "partos_proximos")


def pagina_peso(lote: str | None) -> None:
    eyebrow = f"Finca · {lote}" if lote else "Finca · todos los lotes"
    cabecera(eyebrow, "Evolución de peso",
             "Cuánto pesa cada animal y si está engordando o adelgazando entre un "
             "pesaje y otro. La ganancia se mide en <strong>gramos por día</strong>.")
    todo = leer_vista(V_PESO)
    opciones = sorted(set(filtrar_por_lote(todo, lote)["numero_visible"]))
    if not opciones:
        st.info("Sin pesajes para este filtro.")
        return
    animal = st.selectbox("Animal", opciones)
    mostrar_ficha(animal)
    datos = todo[todo["numero_visible"] == animal].sort_values("fecha_actual")
    ultimo = datos.iloc[-1]
    tendencia = None
    if pd.notna(ultimo["g_dia"]):
        tendencia = (f"{ultimo['g_dia']:+.0f} g/día",
                     "ok" if ultimo["g_dia"] >= 0 else "malo")
    kpis(
        {"etiqueta": "Peso actual", "valor": f"{ultimo['peso_actual']:.0f} kg",
         "detalle": f"último pesaje {fecha_corta(ultimo['fecha_actual'])}",
         "acento": "pasture", "tendencia": tendencia},
        {"etiqueta": "Pesajes registrados", "valor": str(len(datos)),
         "acento": "straw"},
    )
    fig = px.line(
        datos, x="fecha_actual", y="peso_actual", markers=True,
        labels={"fecha_actual": "Fecha", "peso_actual": "Peso (kg)"},
    )
    fig.update_traces(line_color="#9A4522", marker_color="#9A4522")
    fig.add_annotation(
        x=ultimo["fecha_actual"], y=ultimo["peso_actual"],
        text=f"Último pesaje: {ultimo['peso_actual']:.0f} kg",
        showarrow=True, arrowhead=2, arrowcolor="#9A4522",
        font=dict(color="#6E3013", size=14),
    )
    estilizar(fig, f"Peso de N.º {animal}")
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
            clase = "aviso-suave"
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
    eyebrow = f"Finca · {lote}" if lote else "Finca · todos los lotes"
    cabecera(eyebrow, "Curva de lactancia",
             "Litros de leche por día. La curva normal sube después del parto, "
             "llega a un <strong>pico</strong> y luego baja poco a poco hasta "
             "el secado.")
    prod = leer_vista(V_PROD)
    pico = leer_vista(V_PICO)
    opciones = sorted(set(filtrar_por_lote(prod, lote)["numero_visible"]))
    if not opciones:
        st.info("Sin producción para este filtro.")
        return
    animal = st.selectbox("Animal", opciones)
    mostrar_ficha(animal)

    st.markdown('<h3 style="font-family:\'Fraunces\',Georgia,serif;font-size:20px;'
                'margin-bottom:4px;">Comparación entre vacas</h3>',
                unsafe_allow_html=True)
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
    valor_pico = (f"{fila_pico.iloc[0]['litros_pico']:.1f} L"
                  if not fila_pico.empty else "—")
    kpis(
        {"etiqueta": "Registros de ordeño", "valor": str(len(datos)),
         "acento": "pasture"},
        {"etiqueta": "Pico de lactancia", "valor": valor_pico,
         "detalle": fecha_corta(fila_pico.iloc[0]["fecha_pico"])
         if not fila_pico.empty else "sin dato",
         "acento": "straw"},
    )
    fig = px.line(
        datos, x="fecha_real", y="litros", markers=True,
        labels={"fecha_real": "Fecha", "litros": "Litros de leche al día"},
    )
    fig.update_traces(line_color="#233B29", marker_color="#233B29")
    promedio = datos["litros"].mean()
    fig.add_hline(
        y=promedio, line_dash="dash", line_color="#9A4522",
        annotation_text=f"Su promedio: {promedio:.1f} L",
        annotation_position="top left",
    )
    if not fila_pico.empty:
        p = fila_pico.iloc[0]
        fig.add_annotation(
            x=p["fecha_pico"], y=p["litros_pico"],
            text=f"Mejor día: {p['litros_pico']:.0f} L",
            showarrow=True, arrowhead=2, arrowcolor="#B9862E",
            font=dict(color="#8A5F16", size=14),
        )
    estilizar(fig, f"Leche diaria de N.º {animal}")
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
    st.markdown(FUENTES, unsafe_allow_html=True)
    st.markdown(CSS_GLOBAL, unsafe_allow_html=True)
    seccion, lote = barra_lateral()
    PAGINAS[seccion](lote)


if __name__ == "__main__":
    main()
