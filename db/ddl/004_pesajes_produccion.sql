-- ============================================================================
-- AGRORDEN · ERP Ganadero
-- DDL 004 — Pesajes, producción láctea y eventos reproductivos (PostgreSQL >= 13)
-- Fuente de verdad: docs/spec_pesajes_produccion.md (D1–D7 validadas por Robin)
-- Ejecución: psql -d agrorden -f db/ddl/004_pesajes_produccion.sql
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- Catálogo: tipos de evento reproductivo
-- Lista cerrada aprobada por Robin (D6, 2026-08-21).
-- Monta = natural por toro · Servicio = inseminación artificial (D5).
-- Valores semilla en db/seeds/005_seed_eventos_reproductivos.sql
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cat_eventos_reproductivos (
    id_tipo_evento      UUID          NOT NULL DEFAULT gen_random_uuid(),
    nombre_tipo         VARCHAR(100)  NOT NULL,
    CONSTRAINT pk_cat_eventos_reproductivos PRIMARY KEY (id_tipo_evento),
    CONSTRAINT uq_cat_eventos_repro_nombre UNIQUE (nombre_tipo)
);

-- ----------------------------------------------------------------------------
-- Transaccional: pesajes de báscula (D1)
-- Se persiste SOLO lo medido (fecha + peso). Los derivados (días desde el
-- anterior, ganancia g/día) se calculan al consultar, jamás se almacenan.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pesajes (
    id_pesaje           UUID           NOT NULL DEFAULT gen_random_uuid(),
    id_animal           UUID           NOT NULL,
    fecha               DATE           NOT NULL,
    peso_kg             NUMERIC(6,2)   NOT NULL,
    archivo_origen      TEXT           NOT NULL,
    hoja_origen         TEXT           NOT NULL,
    created_at          TIMESTAMPTZ    NOT NULL DEFAULT now(),
    CONSTRAINT pk_pesajes PRIMARY KEY (id_pesaje),
    CONSTRAINT ck_pesajes_peso_positivo CHECK (peso_kg > 0),
    -- Defensiva ETL (regla R1): cualquier fecha del año 1900 es centinela
    -- de dato ausente (incluye variantes tipo 1900-08-11 halladas en CURVA)
    CONSTRAINT ck_pesajes_fecha CHECK (fecha >= DATE '1901-01-01'),
    CONSTRAINT fk_pesajes_animal FOREIGN KEY (id_animal)
        REFERENCES animales (id_interno)
        ON DELETE CASCADE
);

-- ----------------------------------------------------------------------------
-- Transaccional: producción láctea diaria (D2)
-- Fiel al formato CURVA: litros del día `dia` del mes `mes`, en el bloque
-- `orden_mes` contado desde la fecha de parto. El año NO se almacena: se
-- deduce al consultar (fecha_parto + orden_mes); si el parto es desconocido
-- la fecha queda indeterminable y nunca se inventa.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS produccion_lechera (
    id_registro         UUID           NOT NULL DEFAULT gen_random_uuid(),
    id_animal           UUID           NOT NULL,
    orden_mes           SMALLINT       NOT NULL,
    mes                 SMALLINT       NOT NULL,
    dia                 SMALLINT       NOT NULL,
    litros              NUMERIC(5,2)   NOT NULL,
    archivo_origen      TEXT           NOT NULL,
    hoja_origen         TEXT           NOT NULL,
    created_at          TIMESTAMPTZ    NOT NULL DEFAULT now(),
    CONSTRAINT pk_produccion_lechera PRIMARY KEY (id_registro),
    CONSTRAINT ck_produccion_litros CHECK (litros >= 0),
    CONSTRAINT ck_produccion_orden_mes CHECK (orden_mes BETWEEN 0 AND 11),
    CONSTRAINT ck_produccion_mes CHECK (mes BETWEEN 1 AND 12),
    CONSTRAINT ck_produccion_dia CHECK (dia BETWEEN 1 AND 31),
    CONSTRAINT fk_produccion_animal FOREIGN KEY (id_animal)
        REFERENCES animales (id_interno)
        ON DELETE CASCADE
);

-- ----------------------------------------------------------------------------
-- Transaccional: eventos reproductivos fechados (D6)
-- Hechos ocurridos en una fecha (Parto, Monta, Servicio...), separados de
-- los estados de hitos_reproductivos (Preñada/Vacía/Dinámica Folicular).
-- dias_abiertos NUNCA se almacena aquí (D4): es aritmética al consultar.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eventos_reproductivos (
    id_evento           UUID           NOT NULL DEFAULT gen_random_uuid(),
    id_animal           UUID           NOT NULL,
    id_tipo_evento      UUID           NOT NULL,
    fecha_evento        DATE           NOT NULL,
    archivo_origen      TEXT           NOT NULL,
    hoja_origen         TEXT           NOT NULL,
    created_at          TIMESTAMPTZ    NOT NULL DEFAULT now(),
    CONSTRAINT pk_eventos_reproductivos PRIMARY KEY (id_evento),
    CONSTRAINT ck_eventos_repro_fecha CHECK (fecha_evento >= DATE '1901-01-01'),
    CONSTRAINT fk_eventos_repro_animal FOREIGN KEY (id_animal)
        REFERENCES animales (id_interno)
        ON DELETE RESTRICT,
    CONSTRAINT fk_eventos_repro_tipo FOREIGN KEY (id_tipo_evento)
        REFERENCES cat_eventos_reproductivos (id_tipo_evento)
        ON DELETE RESTRICT
);

-- ----------------------------------------------------------------------------
-- Índices de consulta
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_pesajes_animal_fecha
    ON pesajes (id_animal, fecha DESC);

CREATE INDEX IF NOT EXISTS idx_produccion_animal_orden
    ON produccion_lechera (id_animal, orden_mes, dia);

CREATE INDEX IF NOT EXISTS idx_eventos_repro_animal_fecha
    ON eventos_reproductivos (id_animal, fecha_evento DESC);

-- ----------------------------------------------------------------------------
-- Permisos: el ETL opera como agrorden_app
-- ----------------------------------------------------------------------------
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE
    ON pesajes, produccion_lechera, eventos_reproductivos
    TO agrorden_app;

GRANT SELECT ON cat_eventos_reproductivos TO agrorden_app;

COMMIT;
