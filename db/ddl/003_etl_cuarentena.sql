-- ============================================================================
-- AGRORDEN · ERP Ganadero
-- DDL 003 — Bitácora de cuarentena ETL (reglas R1-R5 del diccionario de datos)
-- Toda fila rechazada durante la migración se registra aquí, nunca se descarta.
-- Ejecución: psql -d agrorden -f db/ddl/003_etl_cuarentena.sql
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS etl_cuarentena (
    id_cuarentena   UUID          NOT NULL DEFAULT gen_random_uuid(),
    origen_archivo  VARCHAR(200)  NOT NULL,
    hoja            VARCHAR(100)  NOT NULL,
    numero_fila     INTEGER,
    regla           VARCHAR(10)   NOT NULL,
    motivo          VARCHAR(300)  NOT NULL,
    payload         JSONB,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT now(),
    CONSTRAINT pk_etl_cuarentena PRIMARY KEY (id_cuarentena),
    CONSTRAINT ck_etl_cuarentena_regla CHECK (regla IN ('R1','R2','R3','R4','R5','ID','OTRO'))
);

CREATE INDEX IF NOT EXISTS idx_cuarentena_regla ON etl_cuarentena (regla);
CREATE INDEX IF NOT EXISTS idx_cuarentena_origen ON etl_cuarentena (origen_archivo, hoja);

COMMIT;
