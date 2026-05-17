// Dogs Mind Service Worker — v141 (upload vídeo funcional en anamnesis activado): sustituye el teaser visual "BETA PRIVADA · Solo profesionales acreditados" por la zona de upload real conectada al JS attachVideo/handleVideoSelect/handleVideoDrop ya existente. Nuevos elementos HTML en s-anamnesis (#inp-video, #video-drop-zone, #video-drop-label, #video-preview-wrap, #video-preview-el, #video-file-info) que el JS llevaba referenciando pero NO existían (eran dead code hasta ahora). input file con capture="environment" para grabación directa desde cámara iPhone + accept multi-formato. Drop zone clickable + drag/drop. Preview con HTMLVideoElement controls + botón "Quitar vídeo" min-height 44px (touch target). i18n nuevo anam_video_remove ES+EN. Validación duración 10s (HTMLVideoElement metadata) y cobro 4 tokens ya implementados en v139. Mismo espacio visual aproximado que el teaser anterior. Revertible — para rollback basta git revert del commit.
//
// ESTRATEGIA:
//   • Navegaciones / HTML same-origin: NETWORK-FIRST con fallback a cache.
//     → El usuario online siempre ve la última versión sin tocar nada.
//     → Si pierde red, recibe la última versión cacheada (offline-tolerant).
//
//   • CDN images (jsdelivr) y Google Fonts: cache-first (estables, externos).
//
//   • Otros assets same-origin (imágenes, manifest, iconos PWA): cache-first.
//     → Velocidad. Si cambian con mismo nombre, los headers HTTP de Netlify
//       (must-revalidate) más el bump del CACHE_NAME garantizan refresh.
//
//   • API Railway: nunca intercepta — siempre red directa.
//
// CONTRATO: tras un deploy de Netlify y un navigate del usuario, recibe HTML
// nuevo automáticamente sin necesidad de borrar caché. Esto resuelve el
// problema histórico de "tras update tengo que limpiar caché".

const CACHE_NAME = 'dogs-mind-v141';

// Assets a pre-cachear en install — solo el esqueleto crítico para offline
const PRECACHE_ASSETS = [
  '/manifest.json',
  '/icons/icon-192x192.png',
  '/icons/icon-512x512.png',
];

const API_ORIGIN = 'https://dogs-mind-backend-production.up.railway.app';

// ── INSTALL: pre-cache shell + saltar espera del SW antiguo ───────────────
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(PRECACHE_ASSETS))
      .then(() => self.skipWaiting())
  );
});

// ── ACTIVATE: borrar caches antiguos + tomar control ──────────────────────
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys
          .filter(k => k !== CACHE_NAME)
          .map(k => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

// ── FETCH: routing logic ──────────────────────────────────────────────────
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // Nunca interceptar non-GET ni API — siempre red directa
  if (request.method !== 'GET' || url.origin === API_ORIGIN) {
    return;
  }

  // 1. Navegaciones (HTML del documento principal) → network-first.
  //    Detección por mode='navigate' (estándar moderno) o destination='document'.
  //    Esto es lo que cambia respecto a la versión anterior (cache-first).
  if (request.mode === 'navigate' || request.destination === 'document') {
    event.respondWith(networkFirst(request));
    return;
  }

  // 2. CDN externo (jsdelivr) — cache-first, recursos inmutables por URL
  if (url.hostname === 'cdn.jsdelivr.net') {
    event.respondWith(cacheFirst(request));
    return;
  }

  // 3. Google Fonts — cache-first
  if (url.hostname.includes('googleapis.com') || url.hostname.includes('gstatic.com')) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // 4. Assets same-origin (imágenes locales, manifest, iconos, etc.) — cache-first.
  //    Los headers HTTP de Netlify (must-revalidate) garantizan refresh cuando cambian.
  if (url.origin === self.location.origin) {
    event.respondWith(cacheFirst(request));
    return;
  }
});

// ── ESTRATEGIAS ───────────────────────────────────────────────────────────

/**
 * Network-first: prioriza red, fallback a cache si offline.
 * Pensado para HTML: garantiza versión más reciente cuando hay conectividad.
 */
async function networkFirst(request) {
  try {
    const response = await fetch(request);
    if (response && response.ok) {
      // Actualizar cache en background con la versión nueva
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone()).catch(() => {/* ignorar errores de cache */});
    }
    return response;
  } catch (err) {
    // Offline: intentar servir versión cacheada
    const cached = await caches.match(request);
    if (cached) return cached;
    // Sin cache (primera carga sin red): respuesta mínima
    return new Response(
      '<!doctype html><html><head><meta charset="utf-8"><title>Offline</title></head>' +
      '<body style="font-family:system-ui;padding:40px;text-align:center;color:#444;">' +
      '<h1>Sin conexión</h1><p>Reintenta cuando recuperes la red.</p></body></html>',
      { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } }
    );
  }
}

/**
 * Cache-first: prioriza cache, fallback a red. Para assets estables.
 */
async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;

  try {
    const response = await fetch(request);
    if (response && response.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone()).catch(() => {/* ignorar errores de cache */});
    }
    return response;
  } catch {
    return new Response('Offline', { status: 503, statusText: 'Service Unavailable' });
  }
}
