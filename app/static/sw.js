// AGRORDEN Service Worker — cache de assets estáticos
// No cachea datos dinámicos (consultas SQL, formularios).

const CACHE_NAME = 'agrorden-v1';
const STATIC_ASSETS = [
  '/',
  '/static/manifest.json',
  '/static/logoagro.png',
];

// Instalar: pre-cachear assets estáticos
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch(() => {
        // Silenciar errores de cache en desarrollo
        console.log('[SW] Cache skip en desarrollo');
      });
    })
  );
  self.skipWaiting();
});

// Activar: limpiar caches viejos
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    })
  );
  self.clients.claim();
});

// Fetch: network-first para datos, cache-first para assets estáticos
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Solo manejar requests del mismo origen
  if (url.origin !== location.origin) return;

  // Assets estáticos: cache-first
  if (url.pathname.startsWith('/static/') || url.pathname === '/') {
    event.respondWith(
      caches.match(request).then((cached) => {
        return cached || fetch(request).then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          }
          return response;
        });
      })
    );
    return;
  }

  // Streamlit widgets y datos: network-first (nunca cachear)
  // No interceptar: st(widgets), _stcore, streamlit
  if (url.pathname.includes('_stcore') || url.pathname.includes('streamlit')) {
    return;
  }

  // Todo lo demás: network-first con fallback a cache
  event.respondWith(
    fetch(request).then((response) => {
      if (response.ok && request.method === 'GET') {
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
      }
      return response;
    }).catch(() => {
      return caches.match(request);
    })
  );
});
