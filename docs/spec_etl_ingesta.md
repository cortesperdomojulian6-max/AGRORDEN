# SPEC ETL-001 — Ingesta de Datos Fuente (v1)

> Estado: **IMPLEMENTADO — pruebas en `tests/`**
> Metodología: SDD. Este documento formaliza requisitos y criterios de aceptación
> ANTES de considerar el ETL como completo.
> Fuentes de reglas: `docs/data_dictionary.md` (R1–R5) y validaciones Robin 2026-08-20.

## 1. Alcance

Ingesta desde los 3 Excel oficiales (`data/raw/`) hacia:

| Destino | Origen |
|---|---|
| `animales` | Hojas-animal de FICHAS TECNICAS, CURVA DE PRODUCCIÓN y PESAJE GENERAL |
| `hitos_reproductivos` | Columna `C.PELVICA` de FICHAS TECNICAS |
| `eventos_sanitarios` | Filas de FICHAS con señales sanitarias en `OBSERVACIONES` o texto clínico en `C.PELVICA` |
| `etl_cuarentena` | Todo rechazo (R1, R4, R5, pesajes sin tabla destino) |

**Fuera de alcance v1:** pesajes y curvas de producción (requieren tablas nuevas → nuevo spec con Robin), nombre del animal, fecha de nacimiento.

## 2. Requisitos funcionales

| ID | Requisito |
|----|-----------|
| RF-01 | La identidad se resuelve desde el nombre de hoja: número plano = animal; sufijo `-O/-L/-S` = animal con lote; sufijo `-M` = cría sin chapetear bajo número de la madre. |
| RF-02 | Crías `-M`: `numero_visible` compuesto (`10482-M`), lote `Mamon`, `id_madre` hacia la madre. Si la madre no existe entre las hojas, se auto-registra (sexo `F` provisional, nota en `caracteristicas`). |
| RF-03 (R1) | El centinela `1900-01-01` —como fecha nativa o texto— se convierte en `NULL`. Fila con contenido pero sin fecha válida → cuarentena R1. |
| RF-04 (R5) | Los sub-encabezados apilados dentro de los datos (`HORA`, `OBSERVACION`, …) no generan registros; se reportan una vez por hoja en cuarentena R5. |
| RF-05 | `C.PELVICA` se normaliza al catálogo cerrado `{Preñada, Vacía, Dinámica Folicular}` insensible a mayúsculas, tildes y typos (`Peñada`→Preñada). Texto clínico no reproductivo (`Herida`) → evento sanitario tipo Revisión. |
| RF-06 (R4) | Condición corporal solo persiste si está en `[1.0, 5.0]`; valor imposible (ej. `511`) → cuarentena R4 con contexto de la fila, sin conversión automática. |
| RF-07 | `OBSERVACIONES` con palabras clave sanitarias genera evento con tipo (Vacunación/Tratamiento/Revisión) y producto extraído cuando sea reconocible. |
| RF-08 | Registros de pesaje sin tabla destino en este spec → cuarentena OTRO (no se pierden). |
| RF-09 | Ninguna fila con contenido se descarta silenciosamente: todo rechazo queda en cuarentena con archivo, hoja, fila, regla y motivo. |
| RF-10 | La ingesta es idempotente: recarga completa con resultado estable. |

### Nota controlada
`animales.sexo` es NOT NULL en el spec original y las fuentes no lo declaran. Se asigna `F` provisional (hato lechero; lotes Ordeño/Levante/Mamon son hembras por definición funcional). **Pendiente de validación Robin** — registrado en §5.

## 3. Criterios de aceptación

| ID | Criterio | Verificación |
|----|----------|--------------|
| CA-01 | No existe `1900-01-01` persistido en ninguna columna DATE de las tablas operativas. | SQL sobre BD + CHECKs del DDL |
| CA-02 | Todo animal cuyo `numero_visible` termina en `-M` tiene `id_madre NOT NULL`. | SQL |
| CA-03 | `eventos_sanitarios.condicion_corporal` contiene solo valores `[1,5]` o NULL. | SQL |
| CA-04 | `hitos_reproductivos.resultado` ∈ catálogo cerrado. | SQL |
| CA-05 | Cada hoja-animal de PESAJE corresponde a exactamente un animal distinto (97 hojas → 97 animales con lote). | Conteo SQL vs perfilado |
| CA-06 | Las variantes sucias documentadas se normalizan correctamente (unitarias): `PREÑEZ/Preñez/preñez/Peñada/Preñada`→Preñada; `vacia/VACIA`→Vacía; texto ovárico→Dinámica Folicular. | pytest unitario |
| CA-07 | Re-ejecutar el ETL produce los mismos conteos en todas las tablas (idempotencia RF-10). | pytest integración |

## 4. Pruebas

- `tests/test_transform.py` — unitarias de reglas puras (CA-06, R1, R2, R4).
- `tests/test_acceptance.py` — integración contra la BD local (CA-01…CA-05, CA-07).
- Comando: `python -m pytest tests/ -v`

## 5. Pendientes de validación (bloquean v2, no v1)

- [ ] Confirmar sexo `F` provisional para animales sin declaración explícita.
- [ ] Spec de tablas de pesaje/producción (desbloquea cuarentena OTRO).
- [ ] Revisión manual de los 112 rechazos R1 (¿fechas recuperables?).
