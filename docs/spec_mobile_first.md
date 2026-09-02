# SPEC-008 · Mobile-First + Notificaciones

> Estado: **EN PROGRESO** — Fase A (mobile-first) en implementación.
> Metodología: SDD fase 2→4. Precedente: SPEC-006 (dashboard), SPEC-007 (fuente única).

## 1. Contexto

Robin necesita controlar el hato desde su celular. La app actual (Streamlit) fue
diseñada para escritorio y no funciona bien en móvil: los botones se ven genéricos,
el nav se desborda, y no hay notificaciones. La referencia de Robin es
[controlganadero.app](https://controlganadero.app/) — una app nativa con alertas,
offline y chips electrónicos.

**Decisión clave:** Streamlit NO es una app móvil nativa. El camino más realista es:
- Convertir Streamlit en **PWA** (Progressive Web App) → se instala en el celular
- Agregar **push notifications** del navegador → alertas nativas (gratis)
- Rediseñar el CSS con enfoque **mobile-first** → 100% responsive
- **WhatsApp** queda para futuro cuando se escale (SPEC-009+)

## 2. Decisiones validadas

| # | Decisión | Validación |
|---|----------|------------|
| D1 | Streamlit se mantiene como framework; no se reescribe en React Native | Julián,成本/escalabilidad |
| D2 | La PWA se instala desde el navegador (no requiere Play Store/App Store) | Robin, demo al profesor |
| D3 | Push notifications del navegador como canal principal (gratis, nativo) | Robin, costo $0 |
| D4 | WhatsApp queda para futuro cuando se escale (SPEC-009+) | Robin |
| D5 | El diseño mobile-first prioriza: Resumen → Alertas → Acciones rápidas | Robin, facilidad de uso |

## 3. Alcance

### Fase A · Rediseño mobile-first (RF-01..RF-06)

| ID | Requisito |
|----|-----------|
| **RF-01** | **Nav mobile:** en pantallas < 720px, la barra de navegación se convierte en un menú inferior fijo (bottom nav) con los 5 items principales (Resumen, Animales, Días, + Pesaje, + Repro). Los items secundarios (+ Nota, + Vaca) se mueven a un menú "Más" desplegable. |
| **RF-02** | **Tarjetas de animal:** en mobile, las tarjetas del catálogo ocupan ancho completo (1 columna) con foto a la izquierda, nombre/etapa/lote a la derecha, y peso abajo. Tap = abrir ficha. |
| **RF-03** | **Ficha de vaca:** en mobile, la hero image ocupa todo el ancho, los stats se apilan en 2 columnas, y los botones (Editar, Vender, Volver) se apilan verticalmente con ancho completo. |
| **RF-04** | **Formularios:** en mobile, los formularios de pesaje/repro/nota usan un solo campo por fila (sin `st.columns(2)`), con botones de acción anchos y fijos al fondo. |
| **RF-05** | **KPIs del resumen:** en mobile, los 3 KPIs se apilan verticalmente (1 columna) con íconos grandes y números prominentes. |
| **RF-06** | **Touch targets:** todos los botones y elementos interactivos tienen mínimo 44×44px (estándar Apple/Google) para facilitar uso con el dedo. |

### Fase B · PWA + Push Notifications (RF-07..RF-10)

| ID | Requisito |
|----|-----------|
| **RF-07** | **Manifest PWA:** archivo `manifest.json` con nombre "AGRORDEN", ícono, colores del tema, display: standalone. Permite "Agregar a pantalla de inicio" en Android/iOS. |
| **RF-08** | **Service Worker:** cache de assets estáticos (CSS, íconos, fonts) para carga instantánea en revisitas. No cachea datos dinámicos. |
| **RF-09** | **Push notifications:** componente que solicita permiso del navegador y envía notificaciones cuando hay alertas (parto próximo, vacía de mucho tiempo). Funciona en Android; iOS requiere instalación como PWA. |
| **RF-10** | **Badge en ícono:** cuando hay alertas pendientes, el ícono de la PWA muestra un número (Badging API). |

### Fase C · Alertas en la app (RF-11..RF-14)

| ID | Requisito |
|----|-----------|
| **RF-11** | **Panel de alertas:** en el Resumen, sección "Alertas activas" con tarjetas coloreadas por prioridad (rojo = urgente, amarillo = revisar). |
| **RF-12** | **Tipos de alerta:** (a) Parto próximo (≤7 días), (b) Días abiertos altos (>120), (c) Producción cayendo (>20% vs pico), (d) Sin pesaje reciente (>30 días). |
| **RF-13** | **Detalle de alerta:** al tocar una alerta, se abre la ficha de la vaca con el contexto de la alerta resaltado. |
| **RF-14** | **Trigger de notificación:** cuando se detecta una alerta nueva, se dispara push notification automáticamente. |

## 4. Criterios de aceptación

- **CA-01:** El dashboard se abre en un celular Android/iOS y el nav se muestra como bottom nav sin desbordamiento.
- **CA-02:** Las tarjetas del catálogo se ven completas en una pantalla de 360px de ancho (sin scroll horizontal).
- **CA-03:** La ficha de una vaca se lee completa en mobile sin hacer zoom.
- **CA-04:** Los botones de acción son tocables con el dedo (mínimo 44×44px).
- **CA-05:** La PWA se instala en Android (Chrome → "Agregar a pantalla de inicio") y en iOS (Safari → Compartir → "Agregar a pantalla de inicio").
- **CA-06:** Las push notifications aparecen en la barra de notificaciones del celular.
- **CA-07:** No se envían notificaciones duplicadas en el mismo día para la misma vaca y tipo.
- **CA-08:** La app funciona sin conexión (PWA cache) mostrando los últimos datos cargados.

## 5. Fuera de alcance (SPEC-009+)

- WhatsApp Business API (cuando se escale)
- App nativa (React Native / Flutter)
- Identificación electrónica (chips RFID/NFC)
- Báscula Bluetooth
- IA ganadera
- Multi-usuario / work team
