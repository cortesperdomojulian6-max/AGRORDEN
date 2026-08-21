"""Dashboard AGRORDEN — capa visual de consulta (SPEC-006).

Ejecución:
    streamlit run app/dashboard.py

Principios: solo lectura; conexión por .env; las vistas de SPEC-004 son la API.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from etl.config import get_connection  # noqa: E402

# --- Umbrales de alerta · PROVISIONALES hasta validación de Robin (SPEC-005) ---
UMBRAL_DIAS_ABIERTOS = 150
# -------------------------------------------------------------------------------

st.set_page_config(page_title="AGRORDEN · ERP Ganadero", page_icon="🐄", layout="wide")

V_HATO = ("SELECT COALESCE(nombre_lote,'(sin lote)') AS lote, "
          "hembras, machos, total FROM v_resumen_hato ORDER BY total DESC")
V_DIAS = """
    SELECT numero_visible, nombre_lote, fecha_parto, fecha_cubricion, dias_abiertos
    FROM v_dias_abiertos WHERE dias_abiertos IS NOT NULL
    ORDER BY dias_abiertos DESC
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
V_ANIMALES = """
    SELECT DISTINCT numero_visible FROM (
        SELECT numero_visible FROM v_ganancia_peso
        UNION
        SELECT numero_visible FROM v_produccion_con_fecha
    ) t ORDER BY numero_visible
"""


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
        f"📥 Descargar {nombre} (Excel)",
        buf.getvalue(),
        file_name=f"{nombre}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def barra_lateral() -> tuple[str, str | None]:
    with st.sidebar:
        st.title("🐄 AGRORDEN")
        st.caption("ERP Ganadero")
        seccion = st.radio(
            "Sección",
            ["🏠 Resumen y alertas", "⏱️ Días abiertos", "⚖️ Peso", "🥛 Producción"],
            label_visibility="collapsed",
        )
        lotes = leer_vista(V_HATO)["lote"].tolist()
        lote = st.selectbox("Filtrar por lote", ["Todos"] + lotes)
        st.divider()
        st.caption("El estado de su finca de un vistazo, calculado con los "
                   "registros que usted ya anota.")
    return seccion, None if lote == "Todos" else lote


def alertas(lote: str | None) -> None:
    st.subheader("🚨 A qué le debe prestar atención")
    dias = filtrar_por_lote(leer_vista(V_DIAS), lote)
    peso = leer_vista(V_PESO)
    peso_reciente = peso.sort_values("fecha_actual").groupby(
        "numero_visible", as_index=False).tail(1)

    criticas = dias[dias["dias_abiertos"] > UMBRAL_DIAS_ABIERTOS]
    sin_cubrir = dias[dias["fecha_cubricion"].isna()]
    bajando = peso_reciente[peso_reciente["g_dia"] < 0]

    mensajes = []
    if not criticas.empty:
        lista = ", ".join(criticas["numero_visible"].head(6))
        mas = f" y otras {len(criticas) - 6}" if len(criticas) > 6 else ""
        mensajes.append(
            f"🔴 **{len(criticas)} vacas llevan más de {UMBRAL_DIAS_ABIERTOS} días "
            f"sin quedar preñadas** después de su parto ({lista}{mas}). "
            "Conviene revisarlas con el veterinario.")
    if not sin_cubrir.empty:
        mensajes.append(
            f"🟠 **{len(sin_cubrir)} vacas parieron y no se les ha registrado "
            "monta ni inseminación.** Si ya se sirvieron, falta anotarlo.")
    if not bajando.empty:
        lista = ", ".join(bajando["numero_visible"].head(6))
        mensajes.append(
            f"📉 **{len(bajando)} animales están bajando de peso** según sus "
            f"últimos pesajes ({lista}). Vale la pena revisar su alimentación "
            "o salud.")
    if not mensajes:
        st.success("✅ Todo en orden: no hay alertas para este filtro.")
    for m in mensajes:
        st.markdown(m)

    if not criticas.empty:
        with st.expander(f"Ver tabla de las {len(criticas)} vacas críticas"):
            st.dataframe(
                criticas[["numero_visible", "nombre_lote", "fecha_parto",
                          "dias_abiertos"]],
                use_container_width=True, hide_index=True,
            )
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
    st.header("📋 Resumen del hato")
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
    st.header("⏱️ Días abiertos")
    st.caption("Los **días abiertos** son los días que lleva una vaca sin quedar "
               "preñada desde su último parto. Entre menos días, mejor: lo ideal "
               "es que quede preñada pronto después de parir.")
    dias = filtrar_por_lote(leer_vista(V_DIAS), lote)
    if dias.empty:
        st.info("Sin datos para este filtro.")
        return
    c1, c2 = st.columns(2)
    c1.metric("Vacas con cálculo", len(dias))
    c2.metric("Promedio días abiertos", f"{dias['dias_abiertos'].mean():.0f}")
    top = dias.head(20).copy()

    def semaforo(d: int) -> str:
        if d > UMBRAL_DIAS_ABIERTOS:
            return f"Crítico (>{UMBRAL_DIAS_ABIERTOS})"
        if d >= 100:
            return "Atención (100-150)"
        return "Normal (<100)"

    top["Estado"] = top["dias_abiertos"].apply(semaforo)
    fig = px.bar(
        top, x="dias_abiertos", y="numero_visible", orientation="h",
        color="Estado",
        color_discrete_map={
            f"Crítico (>{UMBRAL_DIAS_ABIERTOS})": "#c0392b",
            "Atención (100-150)": "#e67e22",
            "Normal (<100)": "#27ae60",
        },
        category_orders={
            "Estado": [f"Crítico (>{UMBRAL_DIAS_ABIERTOS})",
                       "Atención (100-150)", "Normal (<100)"],
        },
        labels={"dias_abiertos": "Días abiertos", "numero_visible": "Vaca"},
        title="Las 20 más críticas",
        height=520,
    )
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)
    boton_excel(dias, "dias_abiertos")
    st.dataframe(dias, use_container_width=True, hide_index=True)


def pagina_peso(lote: str | None) -> None:
    st.header("⚖️ Evolución de peso")
    st.caption("Cuánto pesa cada animal y si está engordando o adelgazando "
               "entre un pesaje y otro. La ganancia se mide en **gramos por día**.")
    todo = leer_vista(V_PESO)
    opciones = sorted(set(filtrar_por_lote(todo, lote)["numero_visible"]))
    if not opciones:
        st.info("Sin pesajes para este filtro.")
        return
    animal = st.selectbox("Animal", opciones)
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
        title=f"Peso de {animal}",
    )
    st.plotly_chart(fig, use_container_width=True)
    with st.expander("Tabla de ganancias entre pesajes"):
        st.dataframe(datos, use_container_width=True, hide_index=True)
        boton_excel(datos, f"ganancias_peso_{animal}")


def pagina_produccion(lote: str | None) -> None:
    st.header("🥛 Curva de lactancia")
    st.caption("Litros de leche por día. La curva normal sube después del parto, "
               "llega a un **pico** y luego baja poco a poco hasta el secado.")
    prod = leer_vista(V_PROD)
    pico = leer_vista(V_PICO)
    opciones = sorted(set(filtrar_por_lote(prod, lote)["numero_visible"]))
    if not opciones:
        st.info("Sin producción para este filtro.")
        return
    animal = st.selectbox("Animal", opciones)

    st.subheader("🔍 Comparación entre vacas")
    comparar = st.multiselect(
        "Selecciona 2 o más vacas para superponer sus curvas",
        opciones,
        help="Detecta a simple vista curvas atípicas.",
    )
    if len(comparar) >= 2:
        datos_comp = prod[prod["numero_visible"].isin(comparar)]
        fig_comp = px.line(
            datos_comp, x="fecha_real", y="litros", color="numero_visible",
            labels={"fecha_real": "Fecha real", "litros": "Litros",
                    "numero_visible": "Vaca"},
            title="Curvas superpuestas",
        )
        st.plotly_chart(fig_comp, use_container_width=True)
    elif comparar:
        st.caption("Selecciona al menos una vaca más para comparar.")

    datos = prod[prod["numero_visible"] == animal]
    fila_pico = pico[pico["numero_visible"] == animal]
    c1, c2 = st.columns(2)
    c1.metric("Registros de ordeño", len(datos))
    if not fila_pico.empty:
        c2.metric("Pico de lactancia", f"{fila_pico.iloc[0]['litros_pico']:.1f} L",
                  help=f"El {pd.Timestamp(fila_pico.iloc[0]['fecha_pico']).strftime('%d/%m/%Y')}")
    fig = px.line(
        datos, x="fecha_real", y="litros", markers=True,
        labels={"fecha_real": "Fecha real (parto + mes + día)", "litros": "Litros"},
        title=f"Producción diaria de {animal}",
    )
    st.plotly_chart(fig, use_container_width=True)
    boton_excel(datos, f"produccion_{animal}")


PAGINAS = {
    "🏠 Resumen y alertas": pagina_resumen,
    "⏱️ Días abiertos": pagina_dias_abiertos,
    "⚖️ Peso": pagina_peso,
    "🥛 Producción": pagina_produccion,
}


def main() -> None:
    seccion, lote = barra_lateral()
    PAGINAS[seccion](lote)


if __name__ == "__main__":
    main()
