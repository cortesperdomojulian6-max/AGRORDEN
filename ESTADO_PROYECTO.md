# ESTADO DEL PROYECTO AGRORDEN

> **PARA EL ASISTENTE:** Si el usuario dice "CONTINUAR AGRORDEN" (o pide retomar el
> proyecto), lee este archivo completo antes de hacer nada más. Continúa desde la
> sección "PRÓXIMOS PASOS" y respeta la regla de oro de abajo.

## REGLA DE ORO (el dueño la estableció explícitamente)

**NADA se comitea ni se hace push sin aprobación explícita del usuario.**
Los cambios se dejan pendientes para que él los revise primero. No crear commits
"por buena práctica". Solo comitear cuando él lo ordene.

## CONTEXTO

- Cliente final: **Robin**, productor ganadero, NO técnico. Todo lo que ve en
  pantalla debe estar en lenguaje llano, sin jerga técnica.
- El profesor definió: existe UNA SOLA fuente de verdad = el archivo más reciente
  en Descargas: `7.CURVA DE PRODUCCIÓN - ORGANIZADO - RESPALDO - respaldo
  20260820_010648.xlsx` (~40 MB). Copia en `data/raw/`. Los demás Excel son
  obsoletos; no usarlos nunca más.
- Ese archivo trae: catálogo "VIENTRES DISPONIBLES DEL SENA" (51 vacas) + una hoja
  por vaca con curva de producción anual, línea reproductiva y **2 fotos cada una**.
- No existen datos de nacimiento/sexo/raza. El hato operativo son solo las 51 vacas.

## ESTADO ACTUAL (verificado)

### Base de datos (PostgreSQL localhost:5433, credenciales en `.env`)
| Tabla | Registros | Nota |
|---|---|---|
| animales | 51 | con `etapa_actual` nueva (ORDEÑO, VACIA, HORRA...) |
| produccion_lechera | 1428 | año completo del archivo único |
| eventos_reproductivos | 86 | líneas de tiempo por hoja |
| pesajes | 334 | `fuente='excel'` |
| notas_vaca | 3 | observaciones de Robin |
| hitos_reproductivos | 0 | obsoleta, queda vacía |

### Especificaciones (docs/)
SPEC-001..004 (ETL), SPEC-005 (alertas), SPEC-006 (dashboard), **SPEC-007**
(`docs/spec_fuente_unica.md`) = fuente única + fotos + captura directa.
Fases de SPEC-007: A ✅ fotos · B ✅ migración · C ⬜ formularios de captura.

### Hecho y verificado en las últimas sesiones
1. `scripts/extraer_fotos.py` → 102 fotos en `data/fotos/<numero>/foto_1.jpg|2.jpg`
   (carpeta excluida de git vía .gitignore).
2. `db/ddl/008_fuente_unica.sql` aplicado: `animales.etapa_actual`,
   `pesajes.fuente/registrado_por/creado_en`, tabla `notas_vaca`, grants.
3. `scripts/migrar_fuente_unica.py` ejecutado con éxito (correr como admin:
   usa `PG_SUPER_PASSWORD`; TRUNCATE requiere ownership). Idempotente: borra todo
   lo que no sea de las 51 vacas y recarga producción/eventos del archivo único.
4. Dashboard (`app/dashboard.py`) — REDISEÑADO (agosto 2026) con identidad de
   campo: paleta verde bosque/crema/terracota en `.streamlit/config.toml` +
   CSS propio, SIN adornos emoji, tipografía seria, métricas como fichas blancas.
   - Ficha de perfil por vaca: foto grande con nombre encima, insignia de etapa,
     tarjetas de estadísticas, sección de salud/reproducción y avisos.
     100% responsiva (probada a 390px).
   - Visor de fotos: clic para ampliar, rueda/pellizco para acercar, arrastre
     para mover, Esc para salir (inyección JS vía components.html, id `ag-lb`).
   - Días abiertos: CORREGIDO error que rompía la página (plotly exigía
     orientation="h", no "horizontal"); tarjetas de estado propias; gráfica del
     hato arreglada; fechas dd/mm/aaaa; sección nueva "Partos que se acercan"
     (18 vacas con parto futuro anotado por Robin).
5. Servidor: `python -m streamlit run app/dashboard.py --server.port 8501`
   Reiniciar SOLO el dashboard: matar el PID del puerto 8501 (Get-NetTCPConnection),
   NUNCA todos los python (derribó la BD una vez; se levanta con
   scripts/db_start.ps1).

### PENDIENTE EN GIT (no comiteado — esperando revisión/aprobación del dueño)
```
 M .gitignore                  (data/fotos/)
 M app/dashboard.py            (ficha perfil + barra hato + fotos)
 ?? db/ddl/008_fuente_unica.sql
 ?? docs/spec_fuente_unica.md
 ?? scripts/extraer_fotos.py
 ?? scripts/migrar_fuente_unica.py
```

## PRÓXIMOS PASOS (en orden)

1. ~~Feedback del dueño sobre la ficha~~ **APROBADO (2026-08-23)**: rediseño de
   campo validado por Julián; cambios comiteados por ramas (backend/front → main).
   Descartado del proyecto: `scripts/aplicar_provisionales.py` (sistema
   provisional obsoleto tras la migración SPEC-007).
2. **Actualizar pruebas**: los ~45 tests esperan el mundo viejo (131 animales,
   737 pesajes...) y algunos referencian el script descartado
   (`tests/test_consultas.py` → provisionales). Hay que reescribir expectativas
   a las 51 vacas y quitar referencias muertas (ver CA-04 en spec_dashboard).
3. **Fase C de SPEC-007 — captura directa (RF-07..10)**: formulario en Streamlit
   para registrar pesajes (y luego celos/partos) DESDE EL SISTEMA, guardando
   `fuente='sistema'`, `registrado_por`. Diseñado para escalar siempre.
4. Pesajes: decidir si se migran también desde el archivo único cuando Robin los
   incluya ahí, o quedan como flujo de captura manual (decisión (d) en spec §4).

## REGLA DE RAMAS (establecida por el dueño, 2026-08-23)

- `backend`: todo lo de datos (ETL, DDL, migraciones, scripts de datos).
- `front`: todo lo visual (app/dashboard.py, .streamlit/, estética).
- `main`: siempre con lo estable; se actualiza SOLO por merge de las anteriores.
- El trabajo se comitea en SU rama según corresponda; nunca mezclar capas.

## LECCIONES TÉCNICAS (para no repetir errores)

- NUNCA editar archivos con Get-Content/Set-Content en PowerShell: corrompe UTF-8
  (y truncó dashboard.py una vez; se restauró desde git). Usar herramienta Edit o
  python con bytes.
- PowerShell: `cmd1; if ($?) { cmd2 }` se rompe silencioso si python escribe a
  stderr — preferir comandos sueltos o verificar salida real.
- Las vistas SQL nuevas van con columnas AL FINAL (CREATE OR REPLACE no permite
  insertar en medio de la lista).
- Verificar SIEMPRE tras escribir un archivo: tamaño > 0 + tokens presentes +
  ast.parse (un archivo vacío parsea "bien").
- Tests idempotencia reinician tablas operativas: después de correrlos hay que
  reaplicar `aplicar_provisionales.py` si el mundo viejo sigue vigente (ya no
  aplica tras migración, pero documentado por si se revive).
