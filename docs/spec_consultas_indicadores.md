# SPEC-004 — Consultas e indicadores (v1)

> Estado: **DEFINIDO** — implementación autorizada. Etapa 3 (CONSULTA) e inicio
> de la etapa 4 (INDICADORES) del roadmap. Umbrales y alertas quedan para SPEC-005.

## 1. Principios

- **D4 (heredado):** los indicadores se calculan al consultar, jamás se almacenan.
- **SPEC-003 RF-05:** todo indicador excluye registros provisionales.
- Las vistas son la API de consulta: el futuro frontend (SPEC-006) solo leerá vistas.

## 2. Requisitos funcionales

- **RF-01 · `v_dias_abiertos`:** por vaca, días entre el último parto y la última
  cubrición (Monta o Servicio) posterior al parto; si aún no hay cubrición,
  desde el parto hasta hoy. Sin parto conocido → NULL (nunca inventar).
- **RF-02 · `v_ganancia_peso`:** por animal, entre cada par de pesajes
  consecutivos: días transcurridos y ganancia g/día = Δpeso / días × 1000.
- **RF-03 · `v_produccion_con_fecha`:** convierte `produccion_lechera` a fechas
  reales usando el último parto: `mes_del_parto + orden_mes`, día `dia`.
  Los días inexistentes en el mes resultante (ej. 30 de febrero) se excluyen.
- **RF-04 · `v_pico_lactancia`:** por vaca, su día de máximos litros (D7: calculado).
- **RF-05 · `v_resumen_hato`:** animales por lote y estado reproductivo vigente
  (último hito registrado por vaca).
- **RF-06:** script `scripts/consultas.py` que imprime los reportes anteriores
  sin requerir SQL.

## 3. Criterios de aceptación

- **CA-01:** ningún valor de `dias_abiertos` es negativo ni usa centinelas.
- **CA-02:** la ganancia g/día de la vaca 5090 entre 08/01 y 23/01/2026 es 533
  ((511−503)/15×1000), verificable contra el Excel original.
- **CA-03:** ninguna fecha producida por `v_produccion_con_fecha` es inválida
  (día fuera del mes) ni anterior a la fecha de parto usada.
- **CA-04:** las cuatro vistas excluyen registros `provisional`.
- **CA-05:** suite pytest verde incluyendo pruebas de las fórmulas contra la BD real.

## 4. Pendientes descubiertos (pregunta para Robin)

- **P1 · Partos futuros:** 6 vacas tienen `Parto` con fecha posterior a hoy
  (2026-10-21/22, 2027-02-21, 2027-03-17/24). ¿Son partos probables de preñadas
  anotados en la casilla equivocada, o errores de dedo? Mientras tanto la vista
  los trata como "aún sin parto" (días abiertos NULL).
- **P2 · Litros antes del parto:** algunas hojas registran litros en días del
  mes del parto anteriores a la fecha de parto. ¿La plantilla se llena completa
  o hay datos reales ahí?
