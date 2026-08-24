# SPEC-006 · Fase 1 — Dashboard local (Streamlit)

> Estado: **DEFINIDO** — implementación autorizada. Primera capa visual del sistema.
> Lee EXCLUSIVAMENTE las vistas de SPEC-004; no calcula nada propio (D4 heredado).

## 1. Principios

- **Solo lectura:** el dashboard jamás escribe en la base de datos.
- **Cero credenciales en código:** conexión vía `.env` (regla de seguridad del proyecto).
- **Las vistas son la API:** si mañana Robin corrige sus Excel y se re-ingesta,
  el dashboard refleja los cambios sin tocar una línea de código.

## 2. Requisitos funcionales

- **RF-01:** aplicación Streamlit que corre local (`streamlit run app/dashboard.py`).
- **RF-02 · sección Hato:** resumen de animales por lote (v_resumen_hato) con métricas totales.
- **RF-03 · sección Días abiertos:** tabla ordenada desc + promedio del hato;
  resalta vacas sin cubrición registrada.
- **RF-04 · sección Peso:** evolución de peso por animal seleccionable con
  ganancia g/día entre pesajes (v_ganancia_peso).
- **RF-05 · sección Producción:** curva de lactancia por vaca seleccionable con
  fecha real y pico marcado (v_produccion_con_fecha, v_pico_lactancia).
- **RF-06:** selector de animal compartido entre Peso y Producción.

## 3. Criterios de aceptación

- **CA-01:** la app arranca y renderiza las 4 secciones sin errores con la BD real.
- **CA-02:** los totales mostrados coinciden con consultas directas a las vistas.
- **CA-03:** no existe credencial alguna en el código fuente (verificación por grep).
- **CA-04:** al cambiar el animal seleccionado, peso y producción se actualizan.

## 4. Fase 2 — Navegación, filtros y alertas

- **RF-07:** navegación lateral por secciones (Resumen / Días abiertos / Peso /
  Producción) en lugar de una sola página larga.
- **RF-08:** filtro por lote en la barra lateral, aplicado a todas las secciones.
  Las vistas exponen `nombre_lote` para ello (DDL 007 actualizado).
- **RF-09:** sección de alertas en Resumen:
  - vacas con más de **150 días abiertos**;
  - vacas cuya última ganancia de peso fue negativa;
  - vacas sin cubrición registrada tras su parto.
- **RF-10:** los umbrales de alerta son constantes visibles al inicio del código
  y están marcados como PROVISIONALES hasta que Robin los valide (SPEC-005).

### Criterios de aceptación fase 2

- **CA-05:** la navegación cambia de sección sin errores.
- **CA-06:** al filtrar por un lote, las tablas solo muestran animales de ese lote.
- **CA-07:** la vaca 9030 (227 días abiertos) aparece en la lista de alertas críticas.

## 5. Fase 3 — Herramientas para la revisión de Robin

- **RF-11:** botón de descarga a Excel en las tablas clave (días abiertos,
  alertas críticas, ganancias de peso, producción del animal). Robin anota
  sobre estos archivos y devuelve correcciones.
- **RF-12:** en Producción, selección múltiple de vacas para superponer sus
  curvas de lactancia y detectar anomalías visualmente.

### Criterios de aceptación fase 3

- **CA-08:** cada botón de descarga genera un .xlsx con las filas visibles.
- **CA-09:** al seleccionar 2+ vacas en Comparación, la gráfica muestra una
  línea por vaca con leyenda.
