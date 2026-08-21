# SPEC-003 · Fase 1 — Recuperación de cuarentena con datos provisionales

> Estado: **VALIDADO CON JULIÁN Y ROBIN** (2026-08-21).
> Robin corregirá los valores reales después; por ahora los registros rotos
> entran con datos provisionales claramente marcados para no bloquear el sistema.

## 1. Principio

Solo se toca lo que está roto. Lo correcto entra como dato real.

| Categoría | Filas | Tratamiento |
|---|---|---|
| R1 casi vacías | 106 | Descartadas permanentemente (basura estructural, sin información) |
| OTRO · pesos con fecha válida en FICHAS | 26 | **Dato REAL**: se cargan a `pesajes` (ya tienen fecha legible; solo faltaba tabla destino) |
| R1 con texto y sin fecha | 8 | **PROVISIONAL**: evento sanitario con fecha marcadora `1901-01-01` |
| R4 · condición corporal imposible | 8 | **PROVISIONAL**: evento con fecha real conservada, CC nula, valor original en observaciones |
| R3 · día/litros imposibles en CURVA | 18 | **PROVISIONAL**: registro en `produccion_lechera` con `litros = 0`, `dia = 1` si el día es ilegible |

## 2. Reglas técnicas

- **RF-01:** las tablas `pesajes`, `produccion_lechera` y `eventos_sanitarios`
  reciben columna `provisional BOOLEAN NOT NULL DEFAULT FALSE`.
- **RF-02:** la fecha marcadora de provisionalidad es `1901-01-01`: pasa los
  CHECKs defensivos pero es obviamente falsa para cualquier humano.
- **RF-03:** todo registro provisional conserva en su campo de texto el motivo
  y el valor original cuando existe (trazabilidad hacia la cuarentena).
- **RF-04:** el proceso es idempotente: se ejecuta tras cada ingesta completa.
- **RF-05:** los indicadores futuros (SPEC-004) deben excluir provisionales:
  `WHERE NOT provisional`.

## 3. Criterios de aceptación

- **CA-01:** tras aplicar, `pesajes` contiene exactamente 26 filas nuevas reales
  provenientes de OTRO, con fecha distinta de 1901-01-01.
- **CA-02:** existen 8 eventos provisionales con fecha `1901-01-01` (R1 con texto).
- **CA-03:** existen 8 eventos provisionales con CC nula y valor original citado (R4).
- **CA-04:** existen 18 producciones provisionales con `litros = 0` (R3).
- **CA-05:** ningún registro real tiene `provisional = TRUE`; ningún provisional
  la tiene en `FALSE`.
- **CA-06:** re-ejecutar el script produce conteos idénticos (idempotencia).
