-- ============================================================================
-- AGRORDEN · ERP Ganadero
-- DDL 006 — Marcador de provisionalidad (SPEC-003 fase 1)
-- Fuente de verdad: docs/spec_recuperacion_cuarentena.md
-- Ejecución: psql -d agrorden -f db/ddl/006_provisionales.sql
-- ============================================================================

BEGIN;

ALTER TABLE pesajes
    ADD COLUMN IF NOT EXISTS provisional BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE produccion_lechera
    ADD COLUMN IF NOT EXISTS provisional BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE eventos_sanitarios
    ADD COLUMN IF NOT EXISTS provisional BOOLEAN NOT NULL DEFAULT FALSE;

COMMIT;
