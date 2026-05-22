// Dogs Mind Service Worker — v155 (fix caso activo 2026-05-23): _resolveActiveRecord ahora ata la resolución al contenido EN PANTALLA (match exacto por analysis/plan) en vez de 'el último guardado con análisis'. Bug: al pulsar Explica/Plan simple sobre un análisis NUEVO sin guardar (Bartolo), resolvía al caso anterior guardado (Franklin). Afecta a abc-explained, plan-simple y seguimiento (resolución compartida). v154 = refresh nombres en sync. (refresh nombres en sync 2026-05-21): syncBackendCases ahora refresca nombre/raza/edad de records ya sincronizados que estaban vacíos (rellena huecos desde GET /cases tras el backfill de client_dog_name), sin pisar records locales con nombre real. Resuelve casos que quedaron 'Sin nombre' en dispositivos sincronizados antes del backfill. Backend: migrate guarda client_dog_* + backfill aplicado. v153 = límites de casos por cuenta. (límites de casos por cuenta 2026-05-20): backend aplica límite de casos activos por account_type — particular=2, professional=20, corporativo=ilimitado (cases.py _max_cases_for, en create_case y /cases/migrate). Frontend: acceptIntervention detecta skipped_quota y muestra toast "Has alcanzado el máximo de X casos. Borra uno". Particulares con >2 casos existentes quedan bloqueados para crear hasta borrar (no se borra nada retroactivo). v152 = auto-persist al aceptar.
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

const CACHE_NAME = 'dogs-mind-v155';

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
