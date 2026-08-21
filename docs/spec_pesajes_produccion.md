# SPEC-002 — Pesajes y Producción (v2 DEFINITIVO)

> Estado: **VALIDADO POR ROBIN** — autorizada la implementación (DDL → pruebas → código).
> Fase SDD: 5 completada; iniciar 6.

## 1. Contexto

Los datos de peso y producción viven en dos fuentes:

- **PESAJE GENERAL CORREGIDO v2** — hoja por animal con columnas `FECHA | PESO (kg) | DÍAS DESDE ANTERIOR | G/DÍA (g)`.
- **CURVA DE PRODUCCIÓN ACTUALIZADO** — hoja por animal con metadatos reproductivos (`FECHA DE PARTO`, `FECHA DE SERVICIO`, `DIAS ABIERTOS`, `PICO DE LACTANCIA`, `PARTO PROBABLE`) y curva de lactancia en pares `Días | Litros`.

## 2. Decisiones ya validadas

| # | Decisión | Validación |
|---|----------|------------|
| D1 | **Pesajes:** se persiste únicamente lo medido (`fecha`, `peso_kg`). Los derivados (`días desde anterior`, `ganancia g/día`) se calculan al consultar, nunca se almacenan. | Robin, 2026-08-20 |
| D2 | **Producción láctea:** se persiste lo medido, no fechas derivadas. *(Matiz tras hallazgo estructural §4.1: lo medido es `mes + día_del_mes + litros`; el año se deduce del mes de parto.)* | Robin, 2026-08-20 |
| D4 | **Días abiertos:** jamás se almacenan. Son aritmética entre fechas persistidas (`servicio/monta − parto`, o `hoy − parto` si está abierta); NULL si falta alguna fecha. Mismo principio D1/D2: guardar lo medido, calcular lo derivado. | Robin, 2026-08-20 |
| D5 | **Monta ≠ Servicio:** `Monta` = reproducción natural por toro; `Servicio` = inseminación artificial. Son eventos distintos en el catálogo. La distinción permite futuros indicadores de eficiencia por método. | Robin, 2026-08-21 |
| D6 | **Tabla nueva `eventos_reproductivos`** separada de `hitos_reproductivos` (estados). Catálogo cerrado de 6 tipos: `Parto`, `Monta`, `Servicio`, `Diagnóstico de Preñez`, `Celo Posparto`, `Secado`. | Robin, 2026-08-21 |
| D7 | **Pico de Lactancia:** nunca se almacena; se calcula desde producción (día de máx litros). | Robin, 2026-08-21 |

## 3. Diseño técnico

### 3.1 Modelo nuevo (DDL 004)

**`pesajes`** — lo medido en báscula:
| Columna | Tipo | Regla |
|---|---|---|
| id | UUID PK | |
| animal_id | UUID FK→animales | NOT NULL, ON DELETE CASCADE |
| fecha | DATE | NOT NULL, CHECK fecha > 1900-01-01 |
| peso_kg | NUMERIC(6,2) | NOT NULL, CHECK > 0 |
| archivo_origen / hoja_origen | TEXT | procedencia obligatoria |

**`produccion_lechera`** — lo medido en ordeño (fiel a CURVA):
| Columna | Tipo | Regla |
|---|---|---|
| id | UUID PK | |
| animal_id | UUID FK→animales | NOT NULL |
| orden_mes | SMALLINT | bloque 0–11 desde el mes del parto |
| mes | SMALLINT | 1–12 (del nombre JUNIO=6…) |
| dia | SMALLINT | 1–31 |
| litros | NUMERIC(5,2) | ≥ 0; celdas vacías no son dato y se omiten |
| archivo_origen / hoja_origen | TEXT | |

El año real NO se almacena: se deduce al consultar (`fecha_parto + orden_mes`). Si falta la fecha de parto, los litros se conservan pero la fecha queda indeterminable — nunca se inventa.

**`eventos_reproductivos`** — hechos fechados:
| Columna | Tipo | Regla |
|---|---|---|
| id | UUID PK | |
| animal_id | UUID FK→animales | NOT NULL |
| tipo_evento | TEXT FK→catálogo cerrado | 6 valores de D6 |
| fecha | DATE | NOT NULL, CHECK > 1900-01-01 |
| archivo_origen / hoja_origen | TEXT | |

### 3.2 Requisitos funcionales

- **RF-01:** Ingesta de pesajes desde PESAJE GENERAL (hoja por animal, identidad por nombre de hoja, igual criterio que SPEC-001).
- **RF-02:** Solo `fecha + peso_kg` persisten. Fecha inválida o peso ≤ 0 → cuarentena con regla.
- **RF-03:** Ingesta de producción desde CURVA: localizar fila de meses, desapivotar bloques `Días/Litros`, omitir celdas vacías.
- **RF-04:** Metadatos reproductivos de CURVA (filas etiqueta/fecha) → `eventos_reproductivos` con mapeo a catálogo cerrado; año 1900 → R1 (cuarentena/omisión).
- **RF-05:** Idempotencia total: TRUNCATE de las tablas nuevas en cada corrida completa.
- **RF-06:** Todo rechazo va a cuarentena con regla, motivo y origen — cero pérdidas silenciosas.
- **RF-07:** Procedencia (archivo+hoja) en el 100% de registros.
- **RF-08:** `dias_abiertos` y pico de lactancia jamás almacenados; fórmulas documentadas para SPEC-004.

### 3.3 Criterios de aceptación

- **CA-01:** Tras ingesta, todo dato rechazado está en cuarentena con regla asignada.
- **CA-02:** Cero filas en `pesajes` con fecha ≤ 1900-01-01 o peso ≤ 0 (CHECKs activos).
- **CA-03:** Cero filas en `produccion_lechera` con litros < 0, mes fuera de 1–12 o día fuera de 1–31.
- **CA-04:** Todo `tipo_evento` pertenece al catálogo cerrado (garantizado por FK).
- **CA-05:** Re-ejecutar la ingesta produce conteos idénticos (idempotencia verificada por prueba).
- **CA-06:** Procedencia verificable en el 100% de las filas nuevas.
- **CA-07:** Suite pytest verde con pruebas unitarias y de aceptación nuevas escritas ANTES del código ETL.

## 4. Hallazgos que el diseño debe respetar

### 4.1 Estructura real de CURVA (verificada 2026-08-21, hoja 12954)

- **Filas 3–4:** línea de tiempo reproductiva con etiquetas y fechas: `1er CELO POSPARTO`, `2do CELO POSPARTO`, `MONTA`, `PARTO`, `PICO DE LACTANCIA`, `PREÑEZ`, `SECADO`, `FECHA DE SERVICIO`.
- **Fila 6:** encabezados de mes en texto (`JUNIO`, `JULIO`, ...) — cada uno abarca un par de columnas `Días | Litros`.
- **Bloques de producción:** los "Días" son **día del calendario (1–31)** dentro del mes del bloque; NO días de lactancia. Verificado: los 12 bloques reinician en 1 y terminan en 28–31.
- El año no está escrito: se deduce secuencialmente desde la `FECHA DE PARTO` (primer bloque = mes del parto).

### 4.2 Datos sucios específicos

- Centinela `1900-01-01` como `FECHA DE SERVICIO` → NULL (regla R1).
- `SECADO = 1900-08-11`: día/mes válidos con año centinela → R1 debe tratar año 1900 como fecha ausente completa.
- `DIAS ABIERTOS = -46188` derivado del centinela → jamás migrar; se recalcula en BD (D4).
- `PARTO PROBABLE = 1900-10-10` → artefacto del mismo centinela.
