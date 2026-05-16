// Dogs Mind Service Worker — v135 (Programa de delegaciones por país, decisión Teo 2026-05-16 con respuestas A1/B1/C1/D2: cada delegación (Bocalán México, Bocalán Argentina, etc.) tiene un código único legible tipo BOCALAN-MX que sus equipos comparten con clientes finales; al registrarse vía ?invite=BOCALAN-MX el usuario queda atribuido permanentemente a la delegación vía users.delegation_id FK inmutable + recibe 5+3=8 tokens de bienvenida + role 'user' normal. Backend: nueva tabla delegations (code, name, country, welcome_bonus_tokens DEFAULT 3, commission_pct_web DEFAULT 10, commission_pct_ios DEFAULT 5, active), nueva columna nullable users.delegation_id, nuevos endpoints admin GET/POST/PATCH /admin/delegations + GET /admin/delegations/report con agregados por delegación (users_count, paying_users_count, total_revenue_eur, commission_due_eur) para calcular comisiones a delegaciones sin exponer datos individuales. Resolución de invite_code en /auth/register: 1) check tabla delegations 2) check AMBASSADOR_CODE env 3) sin match → role user normal. Frontend: AuthResponse incluye delegation_name opcional, toast post-registro dinámico que usa tokens reales y nombre de delegación cuando aplica ('Bienvenido por cortesía de Bocalán México! Tienes 8 tokens'). Backwards-compat 100% — usuarios pre-feature mantienen delegation_id=NULL. DESPLEGADO STAGING beta.thedogsmind.net, PROD aún no.)
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

const CACHE_NAME = 'dogs-mind-v135';

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
