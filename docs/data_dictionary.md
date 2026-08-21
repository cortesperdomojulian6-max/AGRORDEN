# Diccionario de Datos — ERP Ganadero AGRORDEN

> Fuente de verdad: `docs/system_context.md` (secciones 4 y 5).
> Toda columna, tipo o regla aquí descrita proviene del spec aprobado.
> Reglas pecuarias pendientes de validación con Robin quedan marcadas como `[ROBIN]`.

## Convenciones generales

- Claves primarias: `UUID` generados por `gen_random_uuid()` (nativo en PostgreSQL 13+).
- Motor: PostgreSQL.
- Auditoría: columnas `created_at` / `updated_at` (`TIMESTAMPTZ`) en tablas maestras.
- Codificación: `UTF8` (nombres y diagnósticos contienen tildes: "Preñada", "Vacía").

## Reglas de limpieza ETL (datos sucios de origen)

| # | Problema en Excel | Regla de normalización |
|---|-------------------|------------------------|
| R1 | Fechas nulas representadas como `1900-01-01` | Convertir a `NULL`. Prohibido insertar `1900-01-01` en cualquier columna `DATE`. |
| R2 | Identificadores con sufijos: `5090-O`, `5090-M` vs `5090` | Normalizar a la parte numérica base (`5090`) antes de resolver el vínculo contra `animales.numero_visible`. Conservar el sufijo original en observaciones si aporta trazabilidad. **Excepción validada por Robin (2026-08-20):** en hojas `-M` (Mamón) el número es el de la MADRE y el animal es su cría sin chapetear → se crea animal distinto con `numero_visible` compuesto (`10482-M`) y `id_madre` hacia la madre. |
| R3 | Celdas de diagnóstico con texto mixto | Separar en campos estructurados (`producto_aplicado`, `dosis`, `observaciones_clinicas`); el texto residual va a `observaciones_clinicas`. |
| R4 | Condición corporal fuera de rango o vacía | Rechazar valores fuera de `[1.0, 5.0]`; vacío → `NULL`. **Validado con Robin (2026-08-20):** valores imposibles (ej. `511`) probablemente son pesos mal ubicados; van a CUARENTENA con contexto completo, sin conversión automática. |
| R5 | Encabezados repetidos dentro de los datos | Las hojas de FICHAS contienen bloques apilados con sub-encabezados (`HORA`, `OBSERVACION` como valores). El ETL debe filtrar esas filas antes de insertar. |

## Modelo relacional

### `lotes` (catálogo — soporta FK `animales.id_lote_actual`)

| Columna | Tipo | Nulo | Descripción |
|---------|------|------|-------------|
| id_lote | UUID | NO | PK |
| nombre_lote | VARCHAR(50) | NO | Único. Lista cerrada validada por Robin (2026-08-20): Ordeño, Levante, Silvo, Mamon |
| descripcion | TEXT | SÍ | |

### `animales` (tabla maestra)

| Columna | Tipo | Nulo | Descripción |
|---------|------|------|-------------|
| id_interno | UUID | NO | PK, default `gen_random_uuid()` |
| numero_visible | VARCHAR(20) | NO | Único. Identificador físico (ej. "5090"). ETL aplica regla R2. |
| nombre | VARCHAR(100) | SÍ | Ej. "JUANSE", "OREO" |
| fecha_nacimiento | DATE | SÍ | ETL aplica regla R1 |
| sexo | CHAR(1) | NO | Restringido a `M` / `F` |
| raza | VARCHAR(100) | SÍ | |
| id_madre | UUID | SÍ | FK → `animales.id_interno` (auto-referencia, árbol genealógico) |
| id_lote_actual | UUID | SÍ | FK → `lotes.id_lote` |
| caracteristicas | TEXT | SÍ | Descripción física (ej. "Negra con manchas blancas") |

### `cat_tipos_evento` (catálogo — soporta FK `eventos_sanitarios.id_tipo_evento`)

| Columna | Tipo | Nulo | Descripción |
|---------|------|------|-------------|
| id_tipo_evento | UUID | NO | PK |
| nombre_tipo | VARCHAR(100) | NO | Único. Valores del spec: Vacunación, Tratamiento, Revisión `[ROBIN: confirmar lista completa]` |

### `eventos_sanitarios` (transaccional)

| Columna | Tipo | Nulo | Descripción |
|---------|------|------|-------------|
| id_evento | UUID | NO | PK |
| id_animal | UUID | NO | FK → `animales.id_interno` |
| fecha_evento | DATE | NO | ETL aplica regla R1 |
| id_tipo_evento | UUID | NO | FK → `cat_tipos_evento.id_tipo_evento` |
| producto_aplicado | VARCHAR(150) | SÍ | Ej. "Ectoprin", "Hemopar" |
| dosis | VARCHAR(50) | SÍ | Ej. "48 mL" (texto libre: unidades varían) |
| observaciones_clinicas | TEXT | SÍ | Destino del texto mixto (regla R3) |
| condicion_corporal | NUMERIC(2,1) | SÍ | Rango 1–5 (regla R4) |

### `hitos_reproductivos` (transaccional)

| Columna | Tipo | Nulo | Descripción |
|---------|------|------|-------------|
| id_palpacion | UUID | NO | PK |
| id_animal | UUID | NO | FK → `animales.id_interno` |
| fecha_revision | DATE | NO | ETL aplica regla R1 |
| resultado | VARCHAR(30) | NO | Catálogo: "Preñada", "Vacía", "Dinámica Folicular" `[ROBIN: confirmar catálogo]` |
| dias_gestacion_estimados | INTEGER | SÍ | ≥ 0; solo aplica cuando resultado = "Preñada" `[ROBIN: confirmar semántica]` |

## Índices de consulta

| Índice | Tabla | Propósito |
|--------|-------|-----------|
| idx_animales_lote | animales (id_lote_actual) | Inventario por lote |
| idx_animales_madre | animales (id_madre) | Árbol genealógico |
| uq_animales_numero_visible | animales (numero_visible) | Resolución de ID físico durante ETL |
| idx_eventos_animal_fecha | eventos_sanitarios (id_animal, fecha_evento DESC) | Historial clínico cronológico |
| idx_hitos_animal_fecha | hitos_reproductivos (id_animal, fecha_revision DESC) | Línea de tiempo reproductiva |
