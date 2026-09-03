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
- El profesor definió: existe UNA SOLA fuente de verdad = los archivos Excel en
  `C:\Users\Julian Cortes\Desktop\AGRORDEN`.
- Fuentes de datos: AGROORDEN.xlsx (panel vientres + fichas), PESAJE GENERAL (pesajes),
  Formulaciones (inventario/alimentación).
- El hato operativo son **86 animales** (tras sync con los 3 archivos 2026).

## ESTADO ACTUAL (verificado)

### Base de datos (PostgreSQL localhost:5433, credenciales en `.env`)
| Tabla | Registros | Nota |
|---|---|---|
| animales | 86 | con `etapa_actual`, `fecha_venta`, `foto_principal` |
| produccion_lechera | 1428 | año completo |
| eventos_reproductivos | 139 | líneas de tiempo por vaca |
| pesajes | 731 | `fuente='excel'` o `'sistema'` |
| notas_vaca | 0 | Robin aún no usa |
| hitos_reproductivos | 10 | |
| eventos_sanitarios | 0 | |
| etl_cuarentena | 0 | |
| lotes | catálogo | Ordeño, Levante, Silvo, Mamon, etc. |

### Dashboard (`app/dashboard.py`)
- Interfaz web con header propio HTML, navegación por pills, bottom nav mobile.
- Secciones: Resumen, Animales, Días abiertos, Peso, Producción.
- Formularios de captura: pesaje, reproducción, nota, nueva vaca.
- Ficha de animal con foto, stats, reproducción, producción, avisos.
- Venta y reactivación de animales (con `st.dialog`).
- Alertas: partos próximos, días abiertos altos, peso bajando, sin monta.
- Lightbox para fotos (zoom, arrastre, pinch-to-touch).
- Responsive: bottom nav en mobile, tarjetas adaptables, touch targets 44px.

### Especificaciones (docs/)
| Spec | Estado |
|------|--------|
| SPEC-001..004 (ETL) | ✅ Completados |
| SPEC-005 (alertas) | ✅ Implementadas |
| SPEC-006 (dashboard) | ✅ Implementado |
| SPEC-007 (fuente única) | ✅ Fases A y B completas |
| SPEC-008 (mobile-first) | 🔄 Fase A implementada, Fase B/C pendientes |

### Ramas
- `main`: estado estable, merges con aprobación.
- `front`: desarrollo visual.
- `backend`: BD, ETL, migraciones.

## PRÓXIMOS PASOS (en orden)

1. **Fase B del SPEC-008** — PWA (manifest.json + service worker) para que se instale como app en el celular.
2. **Fase C del SPEC-008** — Panel de alertas refinado, push notifications.
3. **Mejoras de UX** — Bottom nav con "Más" para items secundarios, COLORES_ETAPA completo.

## LECCIONES TÉCNICAS (para no repetir errores)

- NUNCA editar archivos con Get-Content/Set-Content en PowerShell: corrompe UTF-8.
- Las vistas SQL nuevas van con columnas AL FINAL (CREATE OR REPLACE no permite insertar en medio).
- Verificar SIEMPRE tras escribir un archivo: tamaño > 0 + tokens presentes + ast.parse.
- Tests idempotencia reinician tablas operativas.
- `sincronizar_2026.py` preserva animales VENDIDA durante re-sync.
