# SPEC-007 · Fuente única de verdad + ficha visual por vaca

> Estado: **BORRADOR — pendiente aprobación de Julián**
> Origen: decisión de Robin tras asesoría con su profesor.
> A partir de este spec, el sistema se basa ÚNICAMENTE en el archivo
> `7.CURVA DE PRODUCCIÓN - ORGANIZADO - RESPALDO - respaldo 20260820_010648.xlsx`.
> Los archivos FICHAS TECNICAS y PESAJE GENERAL quedan OBSOLETOS.

## 1. Decisiones validadas por Robin

- **D8:** solo existen los datos que están en el archivo nuevo (sin fecha de
  nacimiento, sexo ni raza).
- **D9:** el sistema se reduce a las **51 vacas** del archivo.
- **D10:** FICHAS TECNICAS y PESAJE GENERAL quedan obsoletos. Podrán
  revisitarse en el futuro, pero hoy no alimentan el sistema.

## 2. Qué contiene el archivo único (inspeccionado)

- Hoja `Inicio`: portada.
- Hoja `VIENTRES DISPONIBLES DEL SENA ` (con espacio final): catálogo vivo con
  KPIs del hato (51 animales, 21 en ordeño, celos, secados) y tabla por vaca:
  `Etapa actual`, `Fecha de parto`, `Días en lactancia`, `Primer/Próximo celo
  estimado`, `Celo real observado`, `Observaciones`, alertas de secado/parto.
- 51 hojas de vaca nombradas por `numero_visible`: línea de tiempo reproductiva
  (filas 3-4), metadatos (parto, servicio, días abiertos, pico), bloques
  mensuales Días/Litros del año completo, y **2 fotos por vaca** (~250 KB c/u,
  ancladas en la fila 40).

## 3. Alcance

### Fase A · Fotos por vaca
- **RF-01:** script `scripts/extraer_fotos.py` extrae las imágenes de cada hoja
  a `data/fotos/<numero_visible>/foto_1.png`, `foto_2.png` (gitignored).
- **RF-02:** el dashboard muestra la(s) foto(s) en las páginas del animal.

### Fase B · ETL de fuente única
- **RF-03:** el ETL lee exclusivamente del archivo nuevo.
- **RF-04:** del catálogo VIENTRES se persisten solo los datos medidos:
  `etapa_actual`, `celo_real_observado`, `observaciones`. Los campos
  estimados/calculados del Excel (días para celo, alertas) NO se persisten;
  los calculará el sistema (principio D4).
- **RF-05:** la base se reinicia y recarga con las 51 vacas del archivo único
  (los datos históricos de los Excels viejos salen del sistema activo).
- **RF-06:** tabla `animales` gana columna `etapa_actual` y referencia a foto;
  nueva tabla `notas_vaca` para observaciones fechadas de Robin.

### Fase C · Captura directa en el sistema (escalable)
- **RF-07:** formulario de pesaje en el dashboard: seleccionar vaca, fecha y
  kilogramos; validación (fecha no futura, rango de peso plausible, vaca
  existente) y confirmación antes de guardar.
- **RF-08:** todo registro creado por el sistema lleva `fuente='sistema'`,
  `registrado_por` y `creado_en` para auditoría y escalabilidad futura.
- **RF-09:** los pesajes históricos migrados conservan `fuente='excel'`.
- **RF-10:** la misma estructura de captura servirá después para otros datos
  (celos observados, notas, eventos) sin rediseño.

## 4. Pesajes y datos faltantes · decisión validada por Julián

El archivo nuevo **NO contiene pesos**. Se decide **(d) captura dual**:
- El sistema deja el "cupo": el módulo de pesajes queda activo con sus 737
  registros históricos congelados como referencia.
- Los pesos nuevos (y cualquier dato que falte) se podrán registrar
  **directamente en nuestro sistema** mediante formularios, sin depender del
  Excel. Si Robin luego anota pesos en su archivo, también se aceptan.
- **Diseño para escalar:** toda captura directa registra `fuente`
  ('excel' | 'sistema' | futuras vías), `registrado_por` y `creado_en`.
  Así el sistema soporta hoy a un usuario y mañana a varios o una app móvil,
  sin rehacer nada.

## 5. Criterios de aceptación

- **CA-01:** existen 51 carpetas en `data/fotos/`, cada una con sus imágenes.
- **CA-02:** el dashboard muestra la foto al seleccionar una vaca.
- **CA-03:** tras la migración, la BD contiene exactamente 51 animales y su
  producción proviene del archivo único.
- **CA-04:** suite de pruebas actualizada y verde.
