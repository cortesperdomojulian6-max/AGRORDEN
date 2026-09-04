-- ============================================================================
-- AGRORDEN · ERP Ganadero
-- DDL 011 — Historial de Partos y Terneros
-- Tabla de terneros, numero_parto en eventos, vistas de historial.
-- Ejecución: psql -d agrorden -f db/ddl/011_historial_partos.sql
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- 1. Tabla terneros
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS terneros (
    id_ternero    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    id_parto      UUID NOT NULL REFERENCES eventos_reproductivos(id_evento) ON DELETE CASCADE,
    sexo          CHAR(1) NOT NULL CHECK (sexo IN ('M', 'F')),
    peso_kg       NUMERIC(5,2),
    vivo          BOOLEAN NOT NULL DEFAULT TRUE,
    observaciones TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE terneros IS 'Terneros nacidos en cada parto del hato';
COMMENT ON COLUMN terneros.id_parto IS 'FK al evento de tipo Parto en eventos_reproductivos';
COMMENT ON COLUMN terneros.sexo IS 'M = macho, F = hembra';
COMMENT ON COLUMN terneros.vivo IS 'TRUE = vivo al nacer, FALSE = mortinato';

GRANT SELECT, INSERT, UPDATE, DELETE ON terneros TO agrorden_app;

-- ----------------------------------------------------------------------------
-- 2. ALTER eventos_reproductivos: numero_parto
-- ----------------------------------------------------------------------------
ALTER TABLE eventos_reproductivos
    ADD COLUMN IF NOT EXISTS numero_parto SMALLINT;

COMMENT ON COLUMN eventos_reproductivos.numero_parto IS
    'Orden secuencial del parto para esta vaca (1, 2, 3...)';

-- ----------------------------------------------------------------------------
-- 3. Vista historial de partos
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_historial_partos AS
SELECT
    a.numero_visible,
    er.fecha_evento AS fecha_parto,
    er.numero_parto,
    t.sexo AS ternero_sexo,
    t.peso_kg AS ternero_peso,
    t.vivo AS ternero_vivo,
    t.observaciones AS ternero_obs,
    t.id_ternero,
    er.id_evento AS id_parto,
    -- Días abiertos: desde este parto hasta el siguiente servicio
    (SELECT MIN(er2.fecha_evento)
     FROM eventos_reproductivos er2
     JOIN cat_eventos_reproductivos c2 ON c2.id_tipo_evento = er2.id_tipo_evento
     WHERE er2.id_animal = a.id_interno
       AND c2.nombre_tipo IN ('Monta', 'Servicio')
       AND er2.fecha_evento > er.fecha_evento
    ) - er.fecha_evento AS dias_abiertos,
    -- Próximo parto (para calcular duración de la lactancia)
    (SELECT MIN(er3.fecha_evento)
     FROM eventos_reproductivos er3
     JOIN cat_eventos_reproductivos c3 ON c3.id_tipo_evento = er3.id_tipo_evento
     WHERE er3.id_animal = a.id_interno
       AND c3.nombre_tipo = 'Parto'
       AND er3.fecha_evento > er.fecha_evento
    ) AS fecha_proximo_parto
FROM eventos_reproductivos er
JOIN cat_eventos_reproductivos c ON c.id_tipo_evento = er.id_tipo_evento
JOIN animales a ON a.id_interno = er.id_animal
LEFT JOIN terneros t ON t.id_parto = er.id_evento
WHERE c.nombre_tipo = 'Parto'
  AND a.etapa_actual IS DISTINCT FROM 'VENDIDA'
ORDER BY a.numero_visible, er.fecha_evento;

GRANT SELECT ON v_historial_partos TO agrorden_app;

-- ----------------------------------------------------------------------------
-- 4. Vista producción por parto (particionada por lactancia)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_produccion_por_parto AS
WITH partos AS (
    SELECT
        er.id_evento AS id_parto,
        er.id_animal,
        er.fecha_evento AS fecha_parto,
        er.numero_parto,
        LEAD(er.fecha_evento) OVER (
            PARTITION BY er.id_animal ORDER BY er.fecha_evento
        ) AS fecha_fin_lactancia
    FROM eventos_reproductivos er
    JOIN cat_eventos_reproductivos c ON c.id_tipo_evento = er.id_tipo_evento
    WHERE c.nombre_tipo = 'Parto'
)
SELECT
    p.id_parto,
    a.numero_visible,
    p.numero_parto,
    p.fecha_parto,
    p.fecha_fin_lactancia,
    vcf.fecha_real AS fecha_produccion,
    pl.litros,
    (vcf.fecha_real - p.fecha_parto)::INT AS dias_post_parto
FROM partos p
JOIN animales a ON a.id_interno = p.id_animal
JOIN produccion_lechera pl ON pl.id_animal = p.id_animal
JOIN v_produccion_con_fecha vcf ON vcf.id_registro = pl.id_registro
WHERE vcf.fecha_real >= p.fecha_parto
  AND (p.fecha_fin_lactancia IS NULL OR vcf.fecha_real < p.fecha_fin_lactancia)
  AND NOT pl.provisional;

GRANT SELECT ON v_produccion_por_parto TO agrorden_app;

-- ----------------------------------------------------------------------------
-- 5. Función para auto-asignar numero_parto
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_asignar_numero_parto()
RETURNS TRIGGER AS $$
DECLARE
    v_max SMALLINT;
    v_is_parto BOOLEAN;
BEGIN
    SELECT nombre_tipo = 'Parto' INTO v_is_parto
    FROM cat_eventos_reproductivos
    WHERE id_tipo_evento = NEW.id_tipo_evento;

    IF NOT v_is_parto THEN
        RETURN NEW;
    END IF;

    SELECT COALESCE(MAX(numero_parto), 0) INTO v_max
    FROM eventos_reproductivos
    WHERE id_animal = NEW.id_animal;

    NEW.numero_parto := v_max + 1;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger: auto-asignar numero_parto al insertar cualquier evento
CREATE OR REPLACE TRIGGER trg_numero_parto
    BEFORE INSERT ON eventos_reproductivos
    FOR EACH ROW
    EXECUTE FUNCTION fn_asignar_numero_parto();

COMMIT;
