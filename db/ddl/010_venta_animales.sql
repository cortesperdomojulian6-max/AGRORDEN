-- ============================================================================
-- AGRORDEN · ERP Ganadero
-- DDL 010 — Venta de animales
-- Marca la venta de un animal: etapa 'VENDIDA' + fecha_venta.
-- Las vistas operativas excluyen animales VENDIDA (desaparecen del hato).
-- Ejecución: psql -d agrorden -f db/ddl/010_venta_animales.sql
-- ============================================================================

BEGIN;

ALTER TABLE animales
    ADD COLUMN IF NOT EXISTS fecha_venta DATE;

COMMENT ON COLUMN animales.fecha_venta IS
    'Fecha en que el animal salió del hato (venta). etapa_actual= VENDIDA';

-- ----------------------------------------------------------------------------
-- Vista hato: excluir vendidas (RF-05)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_resumen_hato AS
SELECT
    l.nombre_lote,
    COUNT(*) FILTER (WHERE a.sexo = 'F') AS hembras,
    COUNT(*) FILTER (WHERE a.sexo = 'M') AS machos,
    COUNT(*) AS total
FROM animales a
LEFT JOIN lotes l ON l.id_lote = a.id_lote_actual
WHERE a.etapa_actual IS DISTINCT FROM 'VENDIDA'
GROUP BY l.nombre_lote
ORDER BY total DESC;

-- ----------------------------------------------------------------------------
-- Vista días abiertos: excluir vendidas (RF-01)
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
    GROUP BY er.id_animal
)
SELECT
    a.id_interno,
    a.numero_visible,
    l.nombre_lote,
    p.fecha_parto,
    u.fecha_cubricion,
    CASE
        WHEN p.fecha_parto IS NULL THEN NULL
        WHEN p.fecha_parto > CURRENT_DATE THEN NULL
        WHEN u.fecha_cubricion > p.fecha_parto
            THEN u.fecha_cubricion - p.fecha_parto
        ELSE CURRENT_DATE - p.fecha_parto
    END AS dias_abiertos
FROM animales a
LEFT JOIN ultimo_parto p ON p.id_animal = a.id_interno
LEFT JOIN ultima_cubricion u ON u.id_animal = a.id_interno
LEFT JOIN lotes l ON l.id_lote = a.id_lote_actual
WHERE a.etapa_actual IS DISTINCT FROM 'VENDIDA';

-- ----------------------------------------------------------------------------
-- Vista ganancia de peso: excluir vendidas (RF-02)
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
WHERE NOT p1.provisional
  AND a.etapa_actual IS DISTINCT FROM 'VENDIDA';

-- La vista vigente en BD define fecha_real como timestamp; se recrea desde cero
DROP VIEW IF EXISTS v_pico_lactancia;
DROP VIEW IF EXISTS v_produccion_con_fecha;

-- ----------------------------------------------------------------------------
-- Vista producción con fecha real: excluir vendidas (RF-03)
-- ----------------------------------------------------------------------------
CREATE VIEW v_produccion_con_fecha AS
WITH base AS (
    SELECT
        pl.id_registro,
        pl.id_animal,
        a.numero_visible,
        pl.orden_mes,
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
    base.id_registro,
    base.id_animal,
    a.numero_visible,
    (base.mes_objetivo + (base.dia - 1))::date AS fecha_real,
    base.litros,
    base.fecha_parto,
    l.nombre_lote
FROM base
JOIN animales a ON a.id_interno = base.id_animal
LEFT JOIN lotes l ON l.id_lote = a.id_lote_actual
WHERE base.dia <= EXTRACT(
    DAY FROM (date_trunc('month', base.mes_objetivo)
              + interval '1 month - 1 day')
)
  AND base.id_animal NOT IN (
      SELECT id_interno FROM animales WHERE etapa_actual = 'VENDIDA'
  );

-- ----------------------------------------------------------------------------
-- Vista pico de lactancia: excluye producciones de vendidas vía base
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
-- Vista estado reproductivo vigente: excluir vendidas
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_estado_reproductivo_actual AS
SELECT DISTINCT ON (h.id_animal)
    h.id_animal,
    a.numero_visible,
    h.fecha_revision,
    h.resultado
FROM hitos_reproductivos h
JOIN animales a ON a.id_interno = h.id_animal
WHERE a.etapa_actual IS DISTINCT FROM 'VENDIDA'
ORDER BY h.id_animal, h.fecha_revision DESC;

-- ----------------------------------------------------------------------------
-- Vista 7 pasos: excluir vendidas (hato reproductivo y jóvenes)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_reproduccion_7_pasos AS
WITH repro AS (
    SELECT a.id_interno,
           (SELECT max(ee.fecha_evento) FROM eventos_reproductivos ee
             JOIN cat_eventos_reproductivos cc ON cc.id_tipo_evento = ee.id_tipo_evento
            WHERE ee.id_animal = a.id_interno AND cc.nombre_tipo = 'Parto')    AS fecha_parto,
           (SELECT max(ee.fecha_evento) FROM eventos_reproductivos ee
             JOIN cat_eventos_reproductivos cc ON cc.id_tipo_evento = ee.id_tipo_evento
            WHERE ee.id_animal = a.id_interno AND cc.nombre_tipo = 'Servicio') AS fecha_servicio,
           (SELECT h.resultado FROM hitos_reproductivos h
             WHERE h.id_animal = a.id_interno
             ORDER BY h.fecha_revision DESC, h.created_at DESC LIMIT 1)        AS diag_resultado,
           (SELECT max(h.fecha_revision) FROM hitos_reproductivos h
             WHERE h.id_animal = a.id_interno)                                 AS fecha_diag
    FROM animales a
),
base AS (
    SELECT r.*,
           CASE WHEN r.fecha_parto IS NOT NULL THEN r.fecha_parto + 45 ELSE NULL END AS base1_celo,
           CASE WHEN r.fecha_servicio IS NOT NULL THEN r.fecha_servicio + 21 ELSE NULL END AS base2_celo
    FROM repro r
)
SELECT a.id_interno,
       a.numero_visible,
       a.nombre,
       a.sexo,
       a.etapa_actual,
       b.fecha_parto,
       b.fecha_servicio,
       b.diag_resultado,
       b.fecha_diag,
       b.fecha_parto + 305 AS fecha_secado_programada,
       b.fecha_parto + 285 AS fecha_secado_alerta,
       CASE WHEN b.fecha_servicio IS NOT NULL THEN b.fecha_servicio + 282 ELSE NULL END AS fecha_parto_probable,
       fn_siguiente_celo(COALESCE(b.base2_celo, b.base1_celo), CURRENT_DATE) AS fecha_proximo_celo,
       m.paso,
       m.titulo,
       m.detalle AS detalle_paso,
       CASE
           WHEN b.diag_resultado = 'Preñada' THEN 'PREÑADA (SIN ALERTA DE CELO)'
           WHEN b.diag_resultado = 'Vacía'  THEN 'VACIA'
           WHEN m.paso = 1 THEN 'SIN FECHA PARTO'
           WHEN m.paso = 3 THEN 'SERVIDA - ESPERANDO RETORNO'
           WHEN m.paso = 4 THEN '¡OBSERVAR RETORNO DE CELO!'
           WHEN m.paso = 5 THEN 'REVISIÓN VETERINARIA (PALPACIÓN)'
           WHEN m.paso = 2 AND fn_dias_para_celo(COALESCE(b.base2_celo, b.base1_celo), CURRENT_DATE) <= 14
               THEN 'CELO EN 1-14 DÍAS'
           WHEN m.paso = 2 THEN 'AGENDADO'
           ELSE NULL
       END AS estado_reproductivo,
       fn_dias_para_celo(COALESCE(b.base2_celo, b.base1_celo), CURRENT_DATE) AS dias_para_celo,
       CASE WHEN b.fecha_parto IS NOT NULL THEN CURRENT_DATE - b.fecha_parto ELSE NULL END AS dias_lactancia,
       CASE WHEN b.fecha_parto IS NOT NULL THEN (b.fecha_parto + 305) - CURRENT_DATE ELSE NULL END AS dias_para_secado,
       CASE WHEN b.fecha_servicio IS NOT NULL THEN (b.fecha_servicio + 282) - CURRENT_DATE ELSE NULL END AS dias_para_parto
FROM animales a
LEFT JOIN base b ON b.id_interno = a.id_interno
CROSS JOIN LATERAL fn_paso_reproductivo(
    b.fecha_parto, b.fecha_servicio, b.diag_resultado, CURRENT_DATE
) m
WHERE a.etapa_actual IS DISTINCT FROM 'VENDIDA'
  AND NOT (
    a.etapa_actual IN ('MAMON', 'LEVANTE', 'MAUTE', 'TERNERA', 'TERNEROS')
    OR EXISTS (
        SELECT 1 FROM lotes lr
        WHERE lr.id_lote = a.id_lote_actual
          AND lr.nombre_lote IN ('Levante', 'Mamon', 'Maute', 'Ternera')
    )
)
UNION ALL
-- Grupos jóvenes (levante/mamon/maute/ternera): sin ciclo reproductivo aún.
SELECT a.id_interno, a.numero_visible, a.nombre, a.sexo, a.etapa_actual,
       NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
       0, 'SIN CICLO', 'Sin ciclo reproductivo (grupo ' || COALESCE(l.nombre_lote, '?') || ')',
       NULL, NULL, NULL, NULL, NULL
FROM animales a
JOIN lotes l ON l.id_lote = a.id_lote_actual
WHERE a.etapa_actual IS DISTINCT FROM 'VENDIDA'
  AND (a.etapa_actual IN ('MAMON', 'LEVANTE', 'MAUTE', 'TERNERA', 'TERNEROS')
   OR l.nombre_lote IN ('Levante', 'Mamon', 'Maute', 'Ternera'));

GRANT SELECT ON v_reproduccion_7_pasos TO agrorden_app;
GRANT SELECT ON v_resumen_hato, v_dias_abiertos, v_ganancia_peso,
    v_produccion_con_fecha, v_pico_lactancia, v_estado_reproductivo_actual
    TO agrorden_app;

COMMIT;