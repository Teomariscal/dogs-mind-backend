// Dogs Mind Service Worker — v170 (Entrenamiento Específico Fase 2 SLIM, 2026-05-29): nuevo flujo "Nueva consulta" con selector A/B Pro: "Problema de conducta" (anamnesis clínica ABC existente, sin cambio) vs "Entrenamiento específico" (formulario 9 campos + análisis Sonnet con plan operante por fases). Backend: endpoint POST /training-analysis ya desplegado en commit e72ec07 (gate Pro vía env var TRAINING_CONSULT_AUDIENCE, coste 3 tokens igual que análisis clínico, refund automático en error). Frontend SLIM: 3 pantallas nuevas (s-consult-type selector, s-anamnesis-training formulario, s-training-result render markdown), funciones JS (goToConsultType, submitTrainingConsult, _mdToHtml seguro anti-XSS, _tcReinforcersChanged excluyente "nada le motiva"), 2 botones Records actualizados a goToConsultType, i18n ES/EN ~55 strings. Particular y no-auth → directo a s-anamnesis (cero cambio). Daily-followup adapt + tag Records + 9 entry points adicionales quedan para Fase 2.1. v169 (nueva consulta desde ficha del perro, 2026-05-28): la pantalla s-dog-profile en modo edit añade un botón "+ Nueva consulta para [nombre]" (debajo de "Guardar cambios", encima de "Eliminar perro"). Al pulsarlo se setea `window._anamnesisPrefillFromDog` con {name, breed, age} y se navega a s-anamnesis, que rellena los inputs inp-dog-name/inp-breed/inp-dog-age si están vacíos (respeta borrador v162). Edad calculada desde birth_year ("X años"/"X year(s)"). Los demás 11+ entry-points a s-anamnesis NO se ven afectados (prefill solo activo si la variable global está seteada, se limpia tras aplicar). i18n ES/EN nuevas. Frontend-only, sin backend. v168 (self-healing casos huérfanos, 2026-05-28): nueva función frontend `reconcileOrphanCases()` que al login y al entrar a s-records detecta records locales sin `backend_case_id` (por glitch de red al aceptar plan, casos pre-v152, etc.) y los migra al backend en background. Throttle 1×sesión, cap 10 huérfanos por pasada. Backend: endpoint POST /cases/migrate ahora devuelve `case_id` también en `skipped_duplicate` para que el frontend pueda recuperar el id de casos ya migrados pero con backend_case_id perdido (antes solo lo devolvía en `created` → si el caso ya estaba en backend, frontend no podía repararlo). Cambio backend retrocompat: campo `case_id` ya era Optional en MigrateResponseItem. v167 (fix daily-followup post-submit, 2026-05-27): backend GET /cases/{id}/daily-followup/today ahora devuelve `exercises_results` y `theory_answer_index` cuando el día ya está completado; frontend `loadToday` los lee para mostrar chips marcados y opción de teoría seleccionada al re-entrar al check-in tras haberlo guardado (antes el usuario veía los ejercicios vacíos y disabled — "como si no se hubiera rellenado nada"). Schema response: 2 campos opcionales aditivos (clientes viejos los ignoran). v166 (Promo Profesional GRATIS toggleable, 2026-05-26): nueva env var backend PRO_PROMO_FREE (true/false) que activa una promo de lanzamiento donde CUALQUIER usuario puede activar cuenta Profesional sin pagar los 20€. Nuevos endpoints backend: GET /payments/pro-promo-status (público, devuelve boolean) y POST /payments/pro-activate-promo (auth, activa account_type=professional SIN tokens cortesia extra — solo el estatus). Salvaguarda: cuando PRO_PROMO_FREE=true, /payments/pro-checkout devuelve 503 (nadie puede pagar aunque el frontend tenga un bug). Frontend: ambos flujos Pro (s-pro-signup y s-pro-activate) consultan el estado al hidratar y, si activo, ocultan empresa/logo/bundle/courtesy, cambian total/CTA a "Activar GRATIS" y el submit llama al endpoint promo en vez de Stripe. Toggle por Railway env var → un redeploy backend basta para encender/apagar la promo sin tocar frontend. v165 = App Store compliance Fase 1, 2026-05-26: (1) sincroniza la lista de 3rd parties en privacy policy ES con EN (añade Voyage AI, Netlify, Resend, Stripe, Apple — antes solo había 4, ahora 9 — fix GDPR real); (2) añade /privacy.html y /terms.html como páginas estáticas autocontenidas (URL pública estable para App Store Connect, con toggle ES/EN, sin SW); (3) refuerza el consentimiento de signup mencionando explícitamente que el texto se envía a Anthropic (Claude AI, USA) — cumple 5.1.2 reciente sobre 3rd-party AI disclosure; (4) añade disclaimer "no sustituye veterinario" como footer discreto en s-abc, s-full-analysis y s-tracking (antes solo estaba en explain/plan-simple/loading) — cubre 1.4.1 medical-adjacent ante revisores Apple. Sin cambios de lógica, solo strings/copy/HTML estático. APPSTORE_COMPLIANCE.md añadido en raíz del repo como checklist interno. v164 = i18n EN tarjetas Part A/B 2026-05-26: añade traducciones EN al diccionario para anam_resume_* (Continuar/Descartar/confirm) y pending_analysis_* (Ver/Descartar/confirm), antes ausentes (mostraban fallback ES). Sin cambios de lógica, solo strings. v163 = persistir análisis pagado 2026-05-25, Part B: tras el éxito de /analysis se guarda {anamnesis, analysisText, sources, dogName, ts} en localStorage 'dm_pending_analysis_<userHash>' antes de pintar ABC; si el usuario cierra la app sin "Aceptar plan", al volver a s-home aparece una tarjeta discreta "Ver / Descartar" que rehidrata s-abc SIN volver a llamar a /analysis (no se vuelve a cobrar). Se limpia al aceptar (tras setRecords), al descartar, y al logout. NO se limpia en errores. Coexiste con el borrador de anamnesis (Part A, clave dm_anam_draft_*) — son cosas distintas. v162 = autoguardado borrador anamnesis 2026-05-25: la anamnesis se autoguarda en localStorage (debounced, por usuario vía _hashEmail) y al volver a #s-anamnesis se ofrece retomar (tarjeta discreta Continuar/Descartar, sin autorestaurar). Se limpia al enviar con éxito y al logout; NO en el catch de error. No persiste el vídeo. v161 = módulo Inspiración Profesional (beta) 2026-05-24: card home solo-profesionales + pantalla #s-training (Adiestramiento Avanzado) con hero vídeo precacheado. v156 = síntesis ABC: ocultar subsección vacía. (síntesis ABC: ocultar subsección vacía 2026-05-23): renderItems oculta la caja Y su header cuando la subsección viene vacía o solo '—' (p.ej. ED sin detonante discreto), en vez de mostrar un bullet '—' que se veía roto. Complementa el fix de prompt (síntesis concisa, v backend). v155 = fix caso activo por contenido. (fix caso activo 2026-05-23): _resolveActiveRecord ahora ata la resolución al contenido EN PANTALLA (match exacto por analysis/plan) en vez de 'el último guardado con análisis'. Bug: al pulsar Explica/Plan simple sobre un análisis NUEVO sin guardar (Bartolo), resolvía al caso anterior guardado (Franklin). Afecta a abc-explained, plan-simple y seguimiento (resolución compartida). v154 = refresh nombres en sync. (refresh nombres en sync 2026-05-21): syncBackendCases ahora refresca nombre/raza/edad de records ya sincronizados que estaban vacíos (rellena huecos desde GET /cases tras el backfill de client_dog_name), sin pisar records locales con nombre real. Resuelve casos que quedaron 'Sin nombre' en dispositivos sincronizados antes del backfill. Backend: migrate guarda client_dog_* + backfill aplicado. v153 = límites de casos por cuenta. (límites de casos por cuenta 2026-05-20): backend aplica límite de casos activos por account_type — particular=2, professional=20, corporativo=ilimitado (cases.py _max_cases_for, en create_case y /cases/migrate). Frontend: acceptIntervention detecta skipped_quota y muestra toast "Has alcanzado el máximo de X casos. Borra uno". Particulares con >2 casos existentes quedan bloqueados para crear hasta borrar (no se borra nada retroactivo). v152 = auto-persist al aceptar.
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

const CACHE_NAME = 'dogs-mind-v170';

// Assets a pre-cachear en install — solo el esqueleto crítico para offline
const PRECACHE_ASSETS = [
  '/manifest.json',
  '/icons/icon-192x192.png',
  '/icons/icon-512x512.png',
  '/assets/videos/inspiracion-hero.mp4',
];

const API_ORIGIN = 'https://dogs-mind-backend-production.up.railway.app';

// ── INSTALL: pre-cache shell. NO skipWaiting: el SW nuevo ESPERA hasta que ──
// el usuario pulse "Actualizar" (postMessage SKIP_WAITING) o cierre la app.
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(PRECACHE_ASSETS))
  );
});

// ── MESSAGE: el banner "Actualizar" pide activar el SW nuevo bajo demanda ──
self.addEventListener('message', event => {
  if (event.data && event.data.type === 'SKIP_WAITING') self.skipWaiting();
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
