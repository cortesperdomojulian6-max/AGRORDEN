-- ============================================================================
-- AGRORDEN · ERP Ganadero
-- DDL 008 — Fuente única de verdad (SPEC-007)
-- Fuente de verdad: docs/spec_fuente_unica.md
-- Cambios: etapa_actual en animales; trazabilidad de captura en pesajes
--          (fuente/registrado_por/creado_en); tabla notas_vaca.
-- Ejecución: psql -U agrorden_admin -d agrorden -f db/ddl/008_fuente_unica.sql
-- ============================================================================

BEGIN;

ALTER TABLE animales ADD COLUMN IF NOT EXISTS etapa_actual TEXT;
ALTER TABLE animales ADD COLUMN IF NOT EXISTS foto_principal TEXT;

ALTER TABLE pesajes ADD COLUMN IF NOT EXISTS fuente TEXT DEFAULT 'excel';
ALTER TABLE pesajes ADD COLUMN IF NOT EXISTS registrado_por TEXT;
ALTER TABLE pesajes ADD COLUMN IF NOT EXISTS creado_en TIMESTAMPTZ DEFAULT now();

CREATE TABLE IF NOT EXISTS notas_vaca (
    id              BIGSERIAL PRIMARY KEY,
    id_animal       UUID NOT NULL REFERENCES animales(id_interno) ON DELETE CASCADE,
    observacion     TEXT NOT NULL,
    fecha_registro  DATE NOT NULL DEFAULT CURRENT_DATE,
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT now()
);

GRANT SELECT, INSERT, DELETE, TRUNCATE ON notas_vaca TO agrorden_app;
GRANT UPDATE ON animales TO agrorden_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO agrorden_app;

COMMIT;
