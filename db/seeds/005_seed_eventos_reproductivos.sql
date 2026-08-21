-- ============================================================================
-- AGRORDEN · ERP Ganadero
-- SEED 005 — Catálogo de eventos reproductivos (idempotente)
-- Lista cerrada aprobada por Robin (D6, 2026-08-21):
--   Parto · Monta (toro) · Servicio (inseminación) ·
--   Diagnóstico de Preñez · Celo Posparto · Secado
-- Ejecución: psql -d agrorden -f db/seeds/005_seed_eventos_reproductivos.sql
-- ============================================================================

BEGIN;

INSERT INTO cat_eventos_reproductivos (nombre_tipo) VALUES
    ('Parto'),
    ('Monta'),
    ('Servicio'),
    ('Diagnóstico de Preñez'),
    ('Celo Posparto'),
    ('Secado')
ON CONFLICT (nombre_tipo) DO NOTHING;

COMMIT;
