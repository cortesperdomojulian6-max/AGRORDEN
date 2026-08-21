-- ============================================================================
-- AGRORDEN · ERP Ganadero
-- SEED 002 — Catálogos iniciales (idempotente)
-- Lotes: lista cerrada validada por Robin (2026-08-20).
-- Tipos de evento: citados en spec; [ROBIN] confirmar si hay más.
-- Ejecución: psql -d agrorden -f db/seeds/002_seed_catalogos.sql
-- ============================================================================

BEGIN;

INSERT INTO lotes (nombre_lote) VALUES
    ('Ordeño'),
    ('Levante'),
    ('Silvo'),
    ('Mamon')
ON CONFLICT (nombre_lote) DO NOTHING;

INSERT INTO cat_tipos_evento (nombre_tipo) VALUES
    ('Vacunación'),
    ('Tratamiento'),
    ('Revisión')
ON CONFLICT (nombre_tipo) DO NOTHING;

COMMIT;
