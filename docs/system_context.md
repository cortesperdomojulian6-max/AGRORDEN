# SYSTEM CONTEXT: ERP GANADERO (Spec-Driven Development)

## 1. DESCRIPCIÓN GENERAL Y OBJETIVO
Plataforma web profesional orientada a la gestión, centralización, consulta y análisis inteligente de información ganadera. Su objetivo es migrar y estructurar datos provenientes de múltiples archivos Excel fragmentados hacia un motor de base de datos relacional robusto, evolucionando desde un simple repositorio de datos hacia un sistema preventivo de soporte para la toma de decisiones (Organización -> Relación -> Consulta -> Indicadores -> Alertas).

## 2. ROLES Y RESPONSABILIDADES DEL EQUIPO
* **Robin:** Autoridad absoluta en el dominio ganadero y técnico pecuario. Valida todas las reglas de negocio, métricas biológicas (días abiertos, umbrales de vacas problema) y diagnósticos.
* **Julián:** Arquitecto de software y desarrollador responsable de la infraestructura técnica, control de versiones, despliegue local (OpenCode, VS Code, GitHub Desktop) y bases de datos.
* **Agentes de IA (Claude / ChatGPT / Terminal):** Asistentes técnicos estrictamente sujetos al cumplimiento de especificaciones y directrices de código limpio. **Cero vibe-coding:** No se inventan reglas de negocio ni matemáticas no validadas.

## 3. METODOLOGÍA DE DESARROLLO (SDD)
El Spec-Driven Development rige todo el ciclo de vida del software:
1. Descubrimiento y comprensión estricta del dominio.
2. Definición formal de requisitos y diccionario de datos.
3. Validación de reglas de negocio con Robin.
4. Diseño del modelo relacional de base de datos.
5. Especificación técnica y criterios de aceptación.
6. Implementación de código, pruebas y migración (ETL).

## 4. MODELO RELACIONAL DE DATOS (ARQUITECTURA BASE)
El sistema abandona el modelo basado en hojas de Excel desconectadas para unificar la información en torno al animal como entidad central:

### A. Tabla Maestra: `animales`
Centraliza la información estática, inventario y genealogía.
* `id_interno` (UUID) - Primary Key.
* `numero_visible` (String, Unique) - Identificador físico del animal (Ej. "5090").
* `nombre` (String, Nullable) - Ej. "JUANSE", "OREO".
* `fecha_nacimiento` (Date)
* `sexo` (String) - M / F.
* `raza` (String)
* `id_madre` (UUID, FK a `animales`) - Para árbol genealógico.
* `id_lote_actual` (UUID, FK a `lotes`) - Ordeño, Levante, Silvo, Mamon.
* `caracteristicas` (Text) - Descripción física (Ej. "Negra con manchas blancas").

### B. Tabla Transaccional: `eventos_sanitarios`
Absorbe historiales clínicos, tratamientos y diagnósticos de fichas técnicas.
* `id_evento` (UUID) - Primary Key.
* `id_animal` (UUID, FK a `animales`).
* `fecha_evento` (Date).
* `id_tipo_evento` (UUID, FK a catálogo: Vacunación, Tratamiento, Revisión).
* `producto_aplicado` (String) - Ej. "Ectoprin", "Hemopar".
* `dosis` (String) - Ej. "48 mL".
* `observaciones_clinicas` (Text).
* `condicion_corporal` (Decimal) - Rango de 1 a 5.

### C. Tabla Transaccional: `hitos_reproductivos`
Separa los eventos de palpación, celos y servicios de los tratamientos con fármacos.
* `id_palpacion` (UUID) - Primary Key.
* `id_animal` (UUID, FK a `animales`).
* `fecha_revision` (Date).
* `resultado` (String) - Catálogo: "Preñada", "Vacía", "Dinámica Folicular".
* `dias_gestacion_estimados` (Integer).

## 5. RESTRICCIONES TÉCNICAS Y PROTOCOLOS DE SEGURIDAD
* **Manejo de Datos Sucios (ETL):** Los scripts de migración deben limpiar valores nulos erróneos (ej. fechas técnicas como `1900-01-01`), unificar sufijos de identificadores (ej. limpiar `-O` o `-M` para enlazar correctamente al ID numérico) y separar celdas de texto mixto.
* **Seguridad:** Prohibido absoluto de hardcodear credenciales. Uso obligatorio de variables de entorno (`.env`).
* **Control de Versiones:** Commits semánticos orientados a la funcionalidad ganadera (ej. `feat: implementa tabla eventos_sanitarios`). Respeto estricto del `.gitignore` (exclusión de archivos `.env` y de los Excel originales con datos de la finca).