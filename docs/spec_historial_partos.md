# SPEC-009 — Historial de Partos y Terneros

**Fecha:** 2026-08-29
**Estado:** Propuesta
**Solicitante:** Robin (vía Julian)

## Contexto

Robin necesita ver el historial reproductivo completo de cada vaca:
- Cuántos partos ha tenido
- Para cada parto: fecha, ternero nacido (sexo, peso, vivo/muerto)
- Curva de lactancia de ese parto específico
- Días abiertos entre partos

Actualmente la DB solo almacena la fecha del parto en `eventos_reproductivos`
sin datos del ternero ni asociación con la lactancia.

## Objetivo

1. **Tabla `terneros`** — datos del ternero nacido en cada parto
2. **Campo `numero_parto`** — orden secuencial del parto (1°, 2°, 3°...)
3. **Vista `v_historial_partos`** — partos con datos del ternero y lactancia
4. **UI en ficha** — sección "Historial de Partos" expandible por parto
5. **Gráfica por parto** — curva de lactancia filtrada por período de ese parto

## Schema

### Nueva tabla: `terneros`

```sql
CREATE TABLE terneros (
    id_ternero    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    id_parto      UUID NOT NULL REFERENCES eventos_reproductivos(id_evento),
    sexo          CHAR(1) NOT NULL CHECK (sexo IN ('M', 'F')),
    peso_kg       NUMERIC(5,2),
    vivo          BOOLEAN NOT NULL DEFAULT TRUE,
    observaciones TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### ALTER: `eventos_reproductivos`

```sql
ALTER TABLE eventos_reproductivos
    ADD COLUMN numero_parto SMALLINT;

COMMENT ON COLUMN eventos_reproductivos.numero_parto IS
    'Orden secuencial del parto para esta vaca (1, 2, 3...)';
```

### Vista: `v_historial_partos`

```sql
CREATE VIEW v_historial_partos AS
SELECT
    a.numero_visible,
    er.fecha_parto,
    er.numero_parto,
    t.sexo AS ternero_sexo,
    t.peso_kg AS ternero_peso,
    t.vivo AS ternero_vivo,
    t.observaciones AS ternero_obs,
    -- Días abiertos: desde este parto hasta el siguiente servicio
    (SELECT MIN(er2.fecha_evento)
     FROM eventos_reproductivos er2
     JOIN cat_eventos_reproductivos c2 ON c2.id_tipo_evento = er2.id_tipo_evento
     WHERE er2.id_animal = a.id_interno
       AND c2.nombre_tipo IN ('Monta', 'Servicio')
       AND er2.fecha_evento > er.fecha_evento
    ) - er.fecha_parto AS dias_abiertos,
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
```

### Vista: `v_produccion_por_parto`

```sql
CREATE VIEW v_produccion_por_parto AS
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
    pl.fecha_registro AS fecha_produccion,
    pl.litros,
    -- Días desde el parto
    pl.fecha_registro - p.fecha_parto AS dias_post_parto
FROM partos p
JOIN produccion_lechera pl ON pl.id_animal = p.id_animal
    AND pl.fecha_registro >= p.fecha_parto
    AND (p.fecha_fin_lactancia IS NULL OR pl.fecha_registro < p.fecha_fin_lactancia)
JOIN animales a ON a.id_interno = p.id_animal
WHERE NOT pl.provisional
  AND a.etapa_actual IS DISTINCT FROM 'VENDIDA';
```

## UI

### Sección en ficha de animal

Ubicación: debajo de los datos básicos, antes de las gráficas actuales.

```
╔══════════════════════════════════════════════════════════════╗
║  HISTORIAL DE PARTOS (3 partos registrados)                ║
╠══════════════════════════════════════════════════════════════╣
║  ┌─ 1° Parto ─ 12 Mar 2024 ─────────────────────────────┐  ║
║  │  Ternero: Macho | 38.5 kg | ✅ Vivo                  │  ║
║  │  Días abiertos: 62 días                               │  ║
║  │  Lactancia: 305 días | Pico: 28.5 L                  │  ║
║  │  [Ver curva de lactancia] [Ver pesajes]               │  ║
║  └───────────────────────────────────────────────────────┘  ║
║  ┌─ 2° Parto ─ 5 Nov 2024 ──────────────────────────────┐  ║
║  │  Ternera: Hembra | 35.0 kg | ✅ Viva                  │  ║
║  │  Días abiertos: 48 días                               │  ║
║  │  Lactancia: 280 días (en curso)                       │  ║
║  │  [Ver curva de lactancia] [Ver pesajes]               │  ║
║  └───────────────────────────────────────────────────────┘  ║
║  ┌─ 3° Parto ─ 20 Jul 2025 ─────────────────────────────┐  ║
║  │  Ternero: Sin registrar                              │  ║
║  │  [Registrar ternero]                                  │  ║
║  └───────────────────────────────────────────────────────┘  ║
╚══════════════════════════════════════════════════════════════╝
```

### Funcionalidades

1. **Expandir/colapsar** cada parto con `st.expander`
2. **Registrar ternero** — formulario dentro del expander
3. **Gráfica de lactancia** — Plotly filtrada por el período de ese parto
4. **Días abiertos** — calculados entre partos

## Archivos a modificar

1. `db/ddl/011_historial_partos.sql` — schema (nuevo)
2. `app/dashboard.py` — UI en `ficha_vaca_html` + `mostrar_ficha`
3. `tests/test_acceptance.py` — baseline si cambia
4. `docs/spec_historial_partos.md` — spec (nuevo)

## Tests

1. La vista `v_historial_partos` retorna los 27 partos existentes
2. La vista `v_produccion_por_parto` retorna producción particionada
3. Los 47 tests existentes siguen pasando

## Validación con Robin

- [ ] ¿Las columnas del ternero son suficientes? (sexo, peso, vivo, obs)
- [ ] ¿Quiere ver también el historial de pesajes por parto?
- [ ] ¿Quiere poder editar un ternero registrado?
- [ ] ¿El orden de los partos debe ser manual o automático?
