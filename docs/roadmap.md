# ROADMAP · Plan Maestro AGRORDEN

> **Este es el documento brújula del proyecto.** Si buscas qué sigue, por qué
> se hizo en cierto orden o quién hace qué, está aquí. Se actualiza al cerrar
> cada spec. Última actualización: 2026-08-21.

---

## 1. La visión en 5 etapas (acordada con Robin)

El sistema se construye en cascada: cada etapa necesita la anterior.

| # | Etapa | Significado | Estado |
|---|-------|-------------|--------|
| 1 | **ORGANIZACIÓN** | Datos limpios, centralizados, confiables | ✅ Hecha |
| 2 | **RELACIÓN** | Todo conectado: cría→madre, evento→animal, peso→fecha | ✅ Hecha |
| 3 | **CONSULTA** | Ver la información fácilmente (vistas, reportes) | 🔄 Siguiente |
| 4 | **INDICADORES** | Números automáticos: días abiertos, curvas, ganancia g/día | ⬜ |
| 5 | **ALERTAS** | El sistema avisa solo: vacas problema, umbrales vencidos | ⬜ |

## 2. ¿Por qué se empezó por la base de datos?

Porque **no se puede consultar lo que no está organizado ni relacionado**.
El punto de partida era Excel caóticos con centinelas (1900), datos sucios y
números imposibles (`días abiertos = -46188`). Construir pantallas primero
sería pintar una casa sin cimientos: la interfaz mostraría basura más bonita.

El orden real ejecutado fue: perfilado de los Excel → validación de reglas con
Robin → modelo relacional → ETL con limpieza → recién entonces, consultar.

## 3. El orden de CADA funcionalidad (metodología SDD)

Todo spec nuevo sigue siempre estos pasos, sin excepciones:

```
1. PREGUNTAR A ROBIN     la regla de negocio (él valida, nadie inventa)
2. ESCRIBIR EL SPEC      docs/spec_<tema>.md con requisitos + criterios de aceptación
3. ESCRIBIR PRUEBAS      tests/ primero, deben fallar
4. IMPLEMENTAR           código mínimo para poner las pruebas verdes
5. VERIFICAR EN REAL     ingesta a la BD local + criterios de aceptación
6. COMMIT EN backend     mensajes semánticos → merge a main cuando esté estable
```

## 4. Estado del proyecto (specs)

| Spec | Qué entrega | Estado |
|------|-------------|--------|
| SPEC-001 · ETL base | 131 animales, 204 hitos, 364 eventos sanitarios desde Excel | ✅ En `main` |
| SPEC-002 · Pesajes y producción | 711 pesajes, 1,548 producciones, 46 eventos reproductivos | ✅ En `main` |
| SPEC-003 · Recuperación R1 | Rescatar los 114 rechazos con fecha inválida | ⬜ Requiere revisar cuarentena con Robin |
| SPEC-004 · Consultas e indicadores | Vistas SQL: días abiertos, curva por vaca, ganancia de peso | ⬜ **Siguiente** |
| SPEC-005 · Alertas | Umbrales: vacas secas de más, preñez vencida, caídas de producción | ⬜ |
| SPEC-006 · Interfaz web | Pantallas para consultar sin saber SQL | ⬜ Futuro |

## 5. Reparto de trabajo (personas e IA)

### Personas
- **Robin** — autoridad del dominio: valida reglas pecuarias, revisa la
  cuarentena, define catálogos y umbrales. *Sin su sí, no se programa.*
- **Julián** — arquitecto: aprueba specs, decide prioridades, hace push/merge,
  prueba el sistema como usuario final.

### Herramientas IA (trabajar DE LA MANO, no que lo hagan todo)
| Herramienta | Úsala para | No sirve para |
|-------------|-----------|---------------|
| **OpenCode** (terminal) | Todo lo que toca el proyecto real: código, BD, pruebas, git, ingesta. Es el único con acceso a tus archivos. | No le pidas opiniones de dominio ganadero (para eso está Robin). |
| **ChatGPT / Claude** (web) | Segunda opinión: revisar un spec que le pegues, explicar conceptos, proponer indicadores o fórmulas, diseñar pantallas en texto/mockups. | No pueden ejecutar nada ni ver tu repo; todo es copy-paste. |

**Regla práctica:** si la tarea produce *archivos o cambios reales* → OpenCode.
Si produce *ideas, textos o revisiones* → cualquier IA, y tú comparas.

**Regla anti-dependencia:** cada spec lo debes entender tú. Si no puedes
explicar qué hace el código que quedó commiteado, pregúntale a la IA hasta
poder hacerlo — el conocimiento queda en ti, no en la herramienta.

## 6. Mapa de documentos del proyecto

| Documento | Qué contiene |
|-----------|--------------|
| `docs/roadmap.md` | **ESTE documento — el plan** |
| `docs/system_context.md` | Reglas del juego: roles, metodología, seguridad |
| `docs/data_dictionary.md` | Diccionario de datos + reglas de limpieza R1–R5 |
| `docs/profiling_report_2026-08-20.md` | Evidencia del perfilado y validaciones Robin |
| `docs/spec_etl_ingesta.md` | SPEC-001 técnico (RF + CA) |
| `docs/spec_pesajes_produccion.md` | SPEC-002 técnico (D1–D7, RF, CA) |
| `db/ddl/`, `db/seeds/` | Estructura de la BD aplicada |
| `etl/`, `scripts/`, `tests/` | Implementación y pruebas |

## 7. Comandos del día a día

```powershell
# Arrancar / detener la BD local (puerto 5433)
powershell -File scripts/db_start.ps1
powershell -File scripts/db_stop.ps1

# Ingesta completa desde los Excel
python scripts/run_ingest.py

# Pruebas completas (unitarias + aceptación)
python -m pytest tests/ -v
```
