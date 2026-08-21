-- ============================================================================
-- AGRORDEN · ERP Ganadero
-- DDL 001 — Esquema relacional base (PostgreSQL >= 13)
-- Fuente de verdad: docs/system_context.md + docs/data_dictionary.md
-- Ejecución: psql -d agrorden -f db/ddl/001_schema_ganadero.sql
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- Catálogo: lotes de manejo
-- Soporta la FK animales.id_lote_actual.
-- [ROBIN] Valores semilla en db/seeds/002_seed_catalogos.sql
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lotes (
    id_lote         UUID         NOT NULL DEFAULT gen_random_uuid(),
    nombre_lote     VARCHAR(50)  NOT NULL,
    descripcion     TEXT,
    CONSTRAINT pk_lotes PRIMARY KEY (id_lote),
    CONSTRAINT uq_lotes_nombre UNIQUE (nombre_lote)
);

-- ----------------------------------------------------------------------------
-- Tabla maestra: animales
-- Entidad central del sistema: inventario estático y genealogía.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS animales (
    id_interno        UUID         NOT NULL DEFAULT gen_random_uuid(),
    numero_visible    VARCHAR(20)  NOT NULL,
    nombre            VARCHAR(100),
    fecha_nacimiento  DATE,
    sexo              CHAR(1)      NOT NULL,
    raza              VARCHAR(100),
    id_madre          UUID,
    id_lote_actual    UUID,
    caracteristicas   TEXT,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT pk_animales PRIMARY KEY (id_interno),
    CONSTRAINT uq_animales_numero_visible UNIQUE (numero_visible),
    CONSTRAINT ck_animales_sexo CHECK (sexo IN ('M', 'F')),
    -- Defensiva ETL (regla R1): prohibido persistir el centinela de fecha nula
    CONSTRAINT ck_animales_fecha_nacimiento CHECK (
        fecha_nacimiento IS NULL OR fecha_nacimiento <> DATE '1900-01-01'
    ),
    CONSTRAINT fk_animales_madre FOREIGN KEY (id_madre)
        REFERENCES animales (id_interno)
        ON DELETE SET NULL,
    CONSTRAINT fk_animales_lote FOREIGN KEY (id_lote_actual)
        REFERENCES lotes (id_lote)
        ON DELETE SET NULL
);

-- ----------------------------------------------------------------------------
-- Catálogo: tipos de evento sanitario
-- Soporta la FK eventos_sanitarios.id_tipo_evento.
-- [ROBIN] Valores semilla en db/seeds/002_seed_catalogos.sql
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cat_tipos_evento (
    id_tipo_evento  UUID          NOT NULL DEFAULT gen_random_uuid(),
    nombre_tipo     VARCHAR(100)  NOT NULL,
    CONSTRAINT pk_cat_tipos_evento PRIMARY KEY (id_tipo_evento),
    CONSTRAINT uq_cat_tipos_evento_nombre UNIQUE (nombre_tipo)
);

-- ----------------------------------------------------------------------------
-- Transaccional: eventos sanitarios
-- Absorbe historiales clínicos, tratamientos y diagnósticos de fichas técnicas.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eventos_sanitarios (
    id_evento               UUID           NOT NULL DEFAULT gen_random_uuid(),
    id_animal               UUID           NOT NULL,
    fecha_evento            DATE           NOT NULL,
    id_tipo_evento          UUID           NOT NULL,
    producto_aplicado       VARCHAR(150),
    dosis                   VARCHAR(50),
    observaciones_clinicas  TEXT,
    condicion_corporal      NUMERIC(2,1),
    created_at              TIMESTAMPTZ    NOT NULL DEFAULT now(),
    CONSTRAINT pk_eventos_sanitarios PRIMARY KEY (id_evento),
    CONSTRAINT ck_eventos_condicion_corporal CHECK (
        condicion_corporal IS NULL
        OR (condicion_corporal >= 1.0 AND condicion_corporal <= 5.0)
    ),
    -- Defensiva ETL (regla R1)
    CONSTRAINT ck_eventos_fecha CHECK (
        fecha_evento <> DATE '1900-01-01'
    ),
    CONSTRAINT fk_eventos_animal FOREIGN KEY (id_animal)
        REFERENCES animales (id_interno)
        ON DELETE RESTRICT,
    CONSTRAINT fk_eventos_tipo FOREIGN KEY (id_tipo_evento)
        REFERENCES cat_tipos_evento (id_tipo_evento)
        ON DELETE RESTRICT
);

-- ----------------------------------------------------------------------------
-- Transaccional: hitos reproductivos
-- Palpaciones, celos y servicios, separados de tratamientos con fármacos.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS hitos_reproductivos (
    id_palpacion               UUID          NOT NULL DEFAULT gen_random_uuid(),
    id_animal                  UUID          NOT NULL,
    fecha_revision             DATE          NOT NULL,
    resultado                  VARCHAR(30)   NOT NULL,
    dias_gestacion_estimados   INTEGER,
    created_at                 TIMESTAMPTZ   NOT NULL DEFAULT now(),
    CONSTRAINT pk_hitos_reproductivos PRIMARY KEY (id_palpacion),
    -- Catálogo cerrado definido en el spec; [ROBIN] confirmar valores finales
    CONSTRAINT ck_hitos_resultado CHECK (
        resultado IN ('Preñada', 'Vacía', 'Dinámica Folicular')
    ),
    CONSTRAINT ck_hitos_dias_gestacion CHECK (
        dias_gestacion_estimados IS NULL OR dias_gestacion_estimados >= 0
    ),
    -- Defensiva ETL (regla R1)
    CONSTRAINT ck_hitos_fecha CHECK (
        fecha_revision <> DATE '1900-01-01'
    ),
    CONSTRAINT fk_hitos_animal FOREIGN KEY (id_animal)
        REFERENCES animales (id_interno)
        ON DELETE RESTRICT
);

-- ----------------------------------------------------------------------------
-- Índices de consulta (docs/data_dictionary.md § Índices)
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_animales_lote
    ON animales (id_lote_actual);

CREATE INDEX IF NOT EXISTS idx_animales_madre
    ON animales (id_madre);

CREATE INDEX IF NOT EXISTS idx_eventos_animal_fecha
    ON eventos_sanitarios (id_animal, fecha_evento DESC);

CREATE INDEX IF NOT EXISTS idx_hitos_animal_fecha
    ON hitos_reproductivos (id_animal, fecha_revision DESC);

-- ----------------------------------------------------------------------------
-- Auditoría: updated_at automático en tabla maestra animales
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_animales_updated_at ON animales;
CREATE TRIGGER trg_animales_updated_at
    BEFORE UPDATE ON animales
    FOR EACH ROW
    EXECUTE FUNCTION fn_set_updated_at();

COMMIT;
