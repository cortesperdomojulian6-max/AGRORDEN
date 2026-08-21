# Reporte de Perfilado de Datos Sucios — 2026-08-20

> Script: `scripts/profiling_excel.py` (v2) · Alcance: los 3 Excel oficiales en `data/raw/`.
> Reglas R1–R4 según `docs/data_dictionary.md`.

## 1. Estructura descubierta

| Archivo | Hojas | Hojas-animal | IDs únicos | Particularidad |
|---|---|---|---|---|
| `FICHAS TECNICAS ACTUALIZADO (1).xlsx` | 133 | 111 | 111 | Encabezados reales NO en fila 1; hojas auxiliares (INICIO, MENÚ, Hoja1) |
| `7.CURVA ... ACTUALIZADO 20260820.xlsx` | 29 | 23 | 23 | Hoja por animal sin sufijo + paneles (Inicio, Panel/Control Reproductivo, SILVO, ID ORDEÑO, Consolidado) |
| `PESAJE GENERAL CORREGIDO v2.xlsx` | 102 | 97 | **87** | Sufijo de lote en nombre de hoja: `-O`, `-L`, `-M`, `-S` |

**Distribución de lotes (PESAJE):** Silvo 50 · Ordeño 21 · Mamon 20 · Levante 6.

**Hallazgo estructural clave (actualizado con regla de Robin):** PESAJE tiene 97 hojas-animal pero solo 87 IDs únicos. Inicialmente se asumió "mismo animal en varios lotes"; **Robin aclaró que NO:** en hojas con sufijo `-M` (Mamón) el número es el de la **madre** y el animal registrado es su **cría aún sin chapetear** (`10482-M` = cría de la vaca `10482`). Al chapear la cría recibirá su número definitivo. Consecuencias para identidad:
- Cada hoja-animal se inserta como un animal distinto.
- Crías no chapeadas: `numero_visible` compuesto (`10482-M`), `id_madre` → madre, lote `Mamon`.
- El sufijo del resto de hojas (`-O`, `-L`, `-S`) sí indica lote del animal.

## 2. Hallazgos por regla

### R1 — Fechas centinela `1900-01-01`
- **2 casos**, ambos en `CURVA DE PRODUCCIÓN`, hoja `12954`: celda con texto `'1900-01-01 00:00:00'`.
- Confirmado: el centinela viaja también como TEXTO, no solo como fecha nativa. El ETL debe normalizar ambas representaciones a `NULL`.

### R2 — Identificadores con sufijo
- En celdas: 0 ocurrencias. El patrón `ID-sufijo` vive en **nombres de hoja** (`5090-O`), no en datos.
- Regla ETL confirmada: parsear nombre de hoja → `numero_visible` + lote inferido (`O→Ordeño, L→Levante, M→Mamon, S→Silvo`) `[ROBIN: validar mapeo]`.

### R3 — Texto mixto / matriz de eventos
- **Evidencia crítica** en FICHAS TECNICAS: la columna `CONDICION CORPORAL` recibe valores de otros tipos de evento. Ejemplo real (hoja `5090`, fila 8):
  ```
  fecha=2026-01-08 | categoria=PREÑEZ | valor=511 | obs='SE HIZO SECADO CON LINCOCELIN'
  ```
  Un `511` en condición corporal es imposible (rango 1–5): la hoja es una **matriz de eventos** donde cada fila es un evento distinto y las columnas numéricas se contaminan entre sí.
- Implicación de diseño: el ETL debe leer FICHAS como *eventos largos* (fecha, categoría, valor, observación) y enrutar cada fila a `eventos_sanitarios` o `hitos_reproductivos` según su categoría `[ROBIN: validar catálogo de categorías]`.

### R4 — Condición corporal fuera de rango
- **8 casos en 8 animales** de FICHAS TECNICAS: `5090, 5091, 12929, 12933, 12936, 12938, 12960, 13181`.
- Hipótesis (validar con Robin): todos son filas de PREÑEZ/palpación cuyo número pertenece a otro campo (días gestación, ID de servicio), no CC real.

## 3. Decisiones de diseño para el ETL

1. Carga con detección automática de fila de encabezados (ya implementada en v2).
2. Normalización de fechas: centinela `1900-01-01` (fecha o texto) → `NULL`; rechazo defensivo ya presente en el DDL.
3. Resolución de identidad: `numero_visible` desde nombre de hoja y/o columna ID; sufijo → lote histórico.
4. FICHAS TECNICAS: transformación de matriz ancha → eventos largos antes de insertar.
5. Cuarentena: filas que violen reglas van a tabla/bitácora de rechazos, nunca se descartan en silencio.

## 4. Pendientes de validación con Robin

- [x] **VALIDADO (Robin, 2026-08-20):** Mapeo sufijo→lote correcto (`O=Ordeño, L=Levante, M=Mamon, S=Silvo`) y lista oficial de lotes cerrada: Ordeño, Levante, Silvo, Mamon.
- [x] **VALIDADO (Robin, 2026-08-20):** Las variantes de `C.PELVICA` (`PREÑEZ/Preñez/preñez/Preñada/Peñada`) son la misma categoría con inconsistencias de escritura. Normalizar insensible a mayúsculas/tildes: variantes de preñez → `Preñada`, `vacia` → `Vacía`, hallazgos ováricos → `Dinámica Folicular`; `confirmada/por confirmada` es atributo de confirmación, no categoría.
- [x] **RESUELTA (Robin, 2026-08-20):** El valor `511` es desconocido para Robin; posiblemente un peso registrado en la columna equivocada. Regla ETL: valores de condición corporal fuera de `[1–5]` van a cuarentena con contexto completo; prohibida la conversión automática a otro campo.
- [x] **RESUELTA (Robin, 2026-08-20):** Animales multi-lote. El ID de las hojas `-M` es el de la madre; el animal es la cría sin chapetear, que recibirá número definitivo al ser chapeada. Cada hoja-animal = un animal distinto en `animales`; crías con `numero_visible` compuesto (`10482-M`) y `id_madre` hacia la madre.
