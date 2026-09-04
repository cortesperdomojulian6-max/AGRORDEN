-- ============================================================================
-- AGRORDEN · ERP Ganadero
-- DDL 009 — Sincronización "los últimos 3 archivos" (SPEC-009)
-- Fuente de verdad: AGROORDEN.xlsx (panel vientres + fichas + Consolidado),
--                  PESAJE GENERAL ... v4 - AUTOMATICO.xlsm,
--                  Formulaciones_Integrales_Multinutrientes (1) (1).xlsx
-- Cambios: etapas ampliadas; máquina de reproducción de 7 pasos (función +
--          vista en vivo); tablas de alimentación (inventario, formulaciones,
--          requerimientos, metas de ganancia de peso).
-- Ejecución: psql -U agrorden_admin -d agrorden -f db/ddl/009_agroorden_2026.sql
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- 1) Etapas: catálogo abierto a los valores reales de las fuentes 2026
-- ----------------------------------------------------------------------------
ALTER TABLE animales DROP CONSTRAINT IF EXISTS check_etapa_actual;

ALTER TABLE animales ADD CONSTRAINT check_etapa_actual CHECK (
    etapa_actual IS NULL OR etapa_actual IN (
        'ORDEÑO', 'ORDEÑO VACIA', 'ORDEÑO EMBRION',
        'PREÑEZ', 'PREÑADA', 'VACIA',
        'HORRA', 'VACA HORRA', 'VACA VACIA',
        'NOVILLA (H)', 'NOVILLA HORRA', 'NOVILLA VACIA',
        'NOVILLA EMBRION', 'NOVILLA HORRA EMBRION',
        'POSIBLE PREÑEZ', 'PROBLEMA',
        'REPRODUCTOR', 'TORO', 'TERNERA', 'TERNEROS',
        'MAMON', 'LEVANTE', 'MAUTE', 'SILVO',
        'VENDIDA'
    )
);

-- ----------------------------------------------------------------------------
-- 2) Máquina de reproducción: "LOS 7 PASOS DEL PROCESO" (panel VIENTRES)
--    Implementada como función + vista en vivo: se recalcula con cada
--    consulta y nunca se congela (fecha de referencia = CURRENT_DATE).
--
--    Reglas traducidas de la guía rápida del archivo:
--      PASO 1 · sin parto ni servicio → anotar fechas
--      PASO 2 · abierta → celos cada 21 días desde el día 45 posparto
--      PASO 3 · servida, día 0-17 → esperar retorno
--      PASO 4 · día 18-24 → observar retorno
--      PASO 5 · día ≥25 sin retorno ni diagnóstico → palpación
--      PASO 6 · diagnóstico PREÑADA → gestación en curso
--      PASO 7 · diagnóstico VACÍA → servir de nuevo (regresa al paso 3)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_dias_para_celo(base date, hoy date)
RETURNS int
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT CASE WHEN base IS NULL OR hoy IS NULL THEN NULL
                ELSE (base + (21 * GREATEST(0, CEIL((hoy - base) / 21.0)::int))::int) - hoy
           END
$$;

CREATE OR REPLACE FUNCTION fn_siguiente_celo(base date, hoy date)
RETURNS date
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT CASE WHEN base IS NULL OR hoy IS NULL THEN NULL
                ELSE base + (21 * GREATEST(0, CEIL((hoy - base) / 21.0)::int))::int
           END
$$;

CREATE OR REPLACE FUNCTION fn_paso_reproductivo(
    p_parto date,
    p_servicio date,
    p_diag_resultado text,
    p_hoy date DEFAULT CURRENT_DATE
)
RETURNS TABLE (paso int, titulo text, detalle text)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_hoy date := COALESCE(p_hoy, CURRENT_DATE);
    v_dias int;
BEGIN
    -- Diagnóstico domina sobre las fechas (guía: se apagan las alertas)
    IF p_diag_resultado = 'Preñada' THEN
        RETURN QUERY SELECT 6, 'PREÑADA', 'PREÑADA: gestación en curso'; RETURN;
    ELSIF p_diag_resultado = 'Vacía' THEN
        RETURN QUERY SELECT 7, 'VACíA', 'VACÍA: servir de nuevo (regresa al paso 3)'; RETURN;
    END IF;

    -- Sin datos reproductivos
    IF p_parto IS NULL AND p_servicio IS NULL THEN
        RETURN QUERY SELECT 1, 'SIN REGISTRO',
                            'FALTA REGISTRAR PARTO O SERVICIO EN SU HOJA'; RETURN;
    END IF;

    -- Abierta (hay parto, sin servicio)
    IF p_servicio IS NULL THEN
        RETURN QUERY SELECT 2, 'ABIERTA',
                            'ABIERTA: celos cada 21 días hasta servir'; RETURN;
    END IF;

    -- Servida: el reloj corre desde el servicio
    v_dias := v_hoy - p_servicio;
    IF v_dias < 0 THEN v_dias := 0; END IF;
    IF v_dias <= 17 THEN
        RETURN QUERY SELECT 3, 'SERVIDA',
                            'SERVIDA: va día ' || v_dias || ' de 21'; RETURN;
    ELSIF v_dias <= 24 THEN
        RETURN QUERY SELECT 4, 'VIGILAR RETORNO',
                            'VIGILAR RETORNO DE CELO: va día ' || v_dias || ' de 21'; RETURN;
    ELSE
        RETURN QUERY SELECT 5, 'SIN RETORNO',
                            'SIN RETORNO: llevar a palpación veterinaria'; RETURN;
    END IF;
END;
$$;

-- Vista en vivo: estado reproductivo + 7 pasos de cada animal del hato
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
WHERE NOT (
    a.etapa_actual IN ('MAMON', 'LEVANTE', 'MAUTE', 'TERNERA', 'TERNEROS')
    OR EXISTS (
        SELECT 1 FROM lotes lr
        WHERE lr.id_lote = a.id_lote_actual
          AND lr.nombre_lote IN ('Levante', 'Mamon', 'Maute', 'Ternera')
    )
)
UNION ALL
-- Grupos jóvenes (levante/mamon/maute/ternera): sin ciclo reproductivo aún.
-- Nota: el lote físico 'Silvo' contiene también vacas del hato reproductivo,
-- de modo que NO se excluyen aquí: ellas pasan por la máquina de 7 pasos.
SELECT a.id_interno, a.numero_visible, a.nombre, a.sexo, a.etapa_actual,
       NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
       0, 'SIN CICLO', 'Sin ciclo reproductivo (grupo ' || COALESCE(l.nombre_lote, '?') || ')',
       NULL, NULL, NULL, NULL, NULL
FROM animales a
JOIN lotes l ON l.id_lote = a.id_lote_actual
WHERE a.etapa_actual IN ('MAMON', 'LEVANTE', 'MAUTE', 'TERNERA', 'TERNEROS')
   OR l.nombre_lote IN ('Levante', 'Mamon', 'Maute', 'Ternera');

GRANT SELECT ON v_reproduccion_7_pasos TO agrorden_app;

-- ----------------------------------------------------------------------------
-- 3) Alimentación y costos (Formulaciones_Integrales_Multinutrientes)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS alimentacion_materia_prima (
    id_materia_prima   UUID          NOT NULL DEFAULT gen_random_uuid(),
    nombre             VARCHAR(150)  NOT NULL,
    unidad_bulto       SMALLINT,
    presentacion_kg    NUMERIC(8,2),
    cantidad           INTEGER,
    total_kg           NUMERIC(10,2),
    precio_bulto_cop   NUMERIC(14,2),
    precio_kg_cop      NUMERIC(12,2),
    valor_total_cop    NUMERIC(16,2),
    CONSTRAINT pk_alim_materia PRIMARY KEY (id_materia_prima),
    CONSTRAINT uq_alim_materia_nombre UNIQUE (nombre)
);

CREATE TABLE IF NOT EXISTS alimentacion_formulacion (
    id_formulacion    UUID          NOT NULL DEFAULT gen_random_uuid(),
    nombre            VARCHAR(150)  NOT NULL,
    categoria         VARCHAR(50),
    total_mezcla_kg   NUMERIC(10,2),
    costo_total_cop   NUMERIC(16,2),
    costo_kg_cop      NUMERIC(14,2),
    CONSTRAINT pk_alim_formulacion PRIMARY KEY (id_formulacion),
    CONSTRAINT uq_alim_formulacion_nombre UNIQUE (nombre)
);

CREATE TABLE IF NOT EXISTS alimentacion_formulacion_insumo (
    id_insumo_formulacion   UUID         NOT NULL DEFAULT gen_random_uuid(),
    id_formulacion          UUID         NOT NULL,
    id_materia_prima        UUID,
    materia_prima_texto     VARCHAR(150),
    cantidad_kg             NUMERIC(10,2),
    proporcion              NUMERIC(10,6),
    aporte_proteina_kg      NUMERIC(10,2),
    aporte_carbohidratos_kg NUMERIC(10,2),
    aporte_minerales_kg     NUMERIC(10,2),
    aporte_vitaminas_kg     NUMERIC(10,2),
    aporte_fibra_kg         NUMERIC(10,2),
    costo_cop               NUMERIC(14,2),
    pct_costo               NUMERIC(10,6),
    CONSTRAINT pk_alim_insumo PRIMARY KEY (id_insumo_formulacion),
    CONSTRAINT fk_alim_insumo_formulacion FOREIGN KEY (id_formulacion)
        REFERENCES alimentacion_formulacion (id_formulacion) ON DELETE CASCADE,
    CONSTRAINT fk_alim_insumo_materia FOREIGN KEY (id_materia_prima)
        REFERENCES alimentacion_materia_prima (id_materia_prima) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS alimentacion_requerimiento (
    id_requerimiento  UUID         NOT NULL DEFAULT gen_random_uuid(),
    grupo_etario      VARCHAR(120) NOT NULL,
    rango_peso        VARCHAR(90),
    proposito         TEXT,
    consumo_ms_pv     VARCHAR(30),
    proteina_bruta    VARCHAR(30),
    energia_ndt       VARCHAR(30),
    fibra_fdn         VARCHAR(30),
    minerales_ca_p    VARCHAR(30),
    estrategia        TEXT,
    CONSTRAINT pk_alim_requerimiento PRIMARY KEY (id_requerimiento),
    CONSTRAINT uq_alim_requerimiento_grupo UNIQUE (grupo_etario)
);

CREATE TABLE IF NOT EXISTS meta_ganancia_peso (
    categoria        VARCHAR(20) NOT NULL PRIMARY KEY,
    minimo_g_dia     INTEGER     NOT NULL,
    maximo_g_dia     INTEGER     NOT NULL,
    clasificacion    VARCHAR(80) NOT NULL,
    tipo_evaluacion  VARCHAR(30) NOT NULL
);

INSERT INTO meta_ganancia_peso (categoria, minimo_g_dia, maximo_g_dia, clasificacion, tipo_evaluacion)
VALUES ('MAMON', 400, 700, 'BAJO / DENTRO DE META / ALTO', 'CRECIMIENTO'),
       ('LEVANTE', 500, 800, 'BAJO / DENTRO DE META / ALTO', 'CRECIMIENTO'),
       ('SILVO', 400, 600, 'BAJO / DENTRO DE META / ALTO', 'CRECIMIENTO'),
       ('ORDENO', -250, 250, 'PERDIDA FUERTE / ESTABLE / GANANCIA FUERTE', 'MANTENCION')
ON CONFLICT (categoria) DO NOTHING;

GRANT SELECT ON alimentacion_materia_prima,
                 alimentacion_formulacion,
                 alimentacion_formulacion_insumo,
                 alimentacion_requerimiento,
                 meta_ganancia_peso TO agrorden_app;

COMMIT;