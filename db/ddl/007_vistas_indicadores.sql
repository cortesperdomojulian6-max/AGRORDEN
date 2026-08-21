-- ============================================================================
-- AGRORDEN · ERP Ganadero
-- DDL 007 — Vistas de consulta e indicadores (SPEC-004)
-- Fuente de verdad: docs/spec_consultas_indicadores.md
-- Principios: indicadores calculados al consultar (D4); excluyen provisionales.
-- Ejecución: psql -d agrorden -f db/ddl/007_vistas_indicadores.sql
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- RF-01 · Días abiertos por vaca
-- Última cubrición (Monta/Servicio) posterior al último parto; si no existe,
-- se cuenta desde el parto hasta hoy. Sin parto conocido -> NULL.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_dias_abiertos AS
WITH ultimo_parto AS (
    SELECT id_animal, MAX(fecha_evento) AS fecha_parto
    FROM eventos_reproductivos er
    JOIN cat_eventos_reproductivos c ON c.id_tipo_evento = er.id_tipo_evento
    WHERE c.nombre_tipo = 'Parto'
    GROUP BY id_animal
),
ultima_cubricion AS (
    SELECT er.id_animal, MAX(er.fecha_evento) AS fecha_cubricion
    FROM eventos_reproductivos er
    JOIN cat_eventos_reproductivos c ON c.id_tipo_evento = er.id_tipo_evento
    WHERE c.nombre_tipo IN ('Monta', 'Servicio')
    GROUP BY id_animal
)
SELECT
    a.id_interno,
    a.numero_visible,
    p.fecha_parto,
    u.fecha_cubricion,
    CASE
        WHEN p.fecha_parto IS NULL THEN NULL
        WHEN p.fecha_parto > CURRENT_DATE THEN NULL  -- parto futuro (probable): aún no aplica
        WHEN u.fecha_cubricion > p.fecha_parto
            THEN u.fecha_cubricion - p.fecha_parto
        ELSE CURRENT_DATE - p.fecha_parto
    END AS dias_abiertos,
    l.nombre_lote
FROM animales a
LEFT JOIN ultimo_parto p ON p.id_animal = a.id_interno
LEFT JOIN ultima_cubricion u ON u.id_animal = a.id_interno
LEFT JOIN lotes l ON l.id_lote = a.id_lote_actual;

-- ----------------------------------------------------------------------------
-- RF-02 · Ganancia de peso entre pesajes consecutivos (g/día)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_ganancia_peso AS
SELECT
    p1.id_animal,
    a.numero_visible,
    p2.fecha AS fecha_anterior,
    p1.fecha AS fecha_actual,
    p2.peso_kg AS peso_anterior,
    p1.peso_kg AS peso_actual,
    (p1.fecha - p2.fecha) AS dias,
    ROUND(
        (p1.peso_kg - p2.peso_kg) / NULLIF(p1.fecha - p2.fecha, 0) * 1000
    ) AS g_dia,
    l.nombre_lote
FROM pesajes p1
JOIN pesajes p2
    ON p2.id_animal = p1.id_animal
   AND NOT p2.provisional
   AND p2.fecha = (
       SELECT MAX(p3.fecha) FROM pesajes p3
       WHERE p3.id_animal = p1.id_animal
         AND p3.fecha < p1.fecha
         AND NOT p3.provisional
   )
JOIN animales a ON a.id_interno = p1.id_animal
LEFT JOIN lotes l ON l.id_lote = a.id_lote_actual
WHERE NOT p1.provisional;

-- ----------------------------------------------------------------------------
-- RF-03 · Producción láctea con fecha real (parto + orden_mes + día)
-- Excluye días inexistentes en el mes resultante (ej. 30 de febrero).
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_produccion_con_fecha AS
WITH base AS (
    SELECT
        pl.id_registro,
        pl.id_animal,
        a.numero_visible,
        pl.orden_mes,
        pl.mes,
        pl.dia,
        pl.litros,
        up.fecha_parto,
        (date_trunc('month', up.fecha_parto)
             + make_interval(months => pl.orden_mes))::date AS mes_objetivo
    FROM produccion_lechera pl
    JOIN animales a ON a.id_interno = pl.id_animal
    JOIN (
        SELECT er.id_animal, MAX(fecha_evento) AS fecha_parto
        FROM eventos_reproductivos er
        JOIN cat_eventos_reproductivos c ON c.id_tipo_evento = er.id_tipo_evento
        WHERE c.nombre_tipo = 'Parto'
        GROUP BY er.id_animal
    ) up ON up.id_animal = pl.id_animal
    WHERE NOT pl.provisional
)
SELECT
    id_registro,
    base.id_animal,
    a.numero_visible,
    orden_mes,
    dia,
    litros,
    fecha_parto,
    (mes_objetivo + (dia - 1))::date AS fecha_real,
    l.nombre_lote
FROM base
JOIN animales a ON a.id_interno = base.id_animal
LEFT JOIN lotes l ON l.id_lote = a.id_lote_actual
WHERE dia <= EXTRACT(
    DAY FROM (date_trunc('month', mes_objetivo)
              + interval '1 month - 1 day')
);

-- ----------------------------------------------------------------------------
-- RF-04 · Pico de lactancia por vaca (D7: calculado, nunca almacenado)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_pico_lactancia AS
SELECT DISTINCT ON (id_animal)
    id_animal,
    numero_visible,
    fecha_real AS fecha_pico,
    litros AS litros_pico,
    nombre_lote
FROM v_produccion_con_fecha
ORDER BY id_animal, litros DESC, fecha_real ASC;

-- ----------------------------------------------------------------------------
-- RF-05 · Resumen del hato: animales por lote y estado reproductivo vigente
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_resumen_hato AS
SELECT
    l.nombre_lote,
    COUNT(*) FILTER (WHERE a.sexo = 'F') AS hembras,
    COUNT(*) FILTER (WHERE a.sexo = 'M') AS machos,
    COUNT(*) AS total
FROM animales a
LEFT JOIN lotes l ON l.id_lote = a.id_lote_actual
GROUP BY l.nombre_lote
ORDER BY total DESC;

CREATE OR REPLACE VIEW v_estado_reproductivo_actual AS
SELECT DISTINCT ON (h.id_animal)
    h.id_animal,
    a.numero_visible,
    h.fecha_revision,
    h.resultado
FROM hitos_reproductivos h
JOIN animales a ON a.id_interno = h.id_animal
ORDER BY h.id_animal, h.fecha_revision DESC;

COMMIT;
