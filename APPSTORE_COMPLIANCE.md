# Dogs Mind — App Store Review Compliance Checklist

**Última actualización:** 2026-06-02 (revisión contra guidelines vivas + findings agente auditor)
**Estado global:** Pre-submission · Fase 1 (PWA cleanup) completa · Fase 2 (Capacitor + IAP) pendiente
**Readiness estimada:** ~62% (ver cálculo al final). 3 bloqueantes duros + 1 reforzado.

Documento interno de referencia. Mapea cada guideline relevante de [App Store Review Guidelines](https://developer.apple.com/app-store/review/guidelines/) al estado actual de Dogs Mind, con evidencia en código.

> **Nota de honestidad (2026-06-02):** la revisión de deltas de junio 2026 la hizo un
> agente auditor SIN acceso a WebSearch en vivo (se le denegó). Por tanto, las
> tendencias de *enforcement* de Apple en Q3-Q4 2025 / Q1 2026 NO están verificadas
> contra fuente primaria, y la existencia/nomenclatura exacta del tipo de producto
> "non-renewing annual" debe re-confirmarse en App Store Connect antes de crear
> productos. Todo lo marcado `[VERIFICAR]` requiere confirmación en fuente Apple
> oficial antes de actuar. No avanzamos código sobre supuestos no verificados.

---

## TL;DR — Bloqueantes para submitar HOY

| # | Bloqueante | Sección | Acción |
|---|---|---|---|
| **1** | Stripe Checkout para tokens (en iOS debe ser IAP) | 3.1.1 | Fase 2: IAP vía RevenueCat/StoreKit2 + webhook App Store Server Notifications V2. **El binario iOS NO puede contener UI/link/copy de Stripe** (ni link externo) |
| **2** | PWA puro sin wrapper nativo | 4.2 | Fase 2: empaquetar con Capacitor + ≥3 features nativas (push, share sheet, photo picker, IAP) |
| **3** | Consentimiento explícito ANTES de enviar datos a IA de terceros | 5.1.2(i) | **Reforzado 13-nov-2025.** Cubierto a nivel signup **+ refuerzo per-acción IMPLEMENTADO (staged 2026-06-06)**: micro-aviso `consent_ai_inline` en anamnesis y entrenamiento, justo en el punto de envío. Pendiente deploy + visual (ver §5.1.2) |
| 4 | (Resuelto Fase 1) URLs públicas /privacy y /terms | 5.1.1(i) | ✅ Hecho — `frontend/privacy.html` y `frontend/terms.html` |

**Lo demás está cubierto o es bajo riesgo.** Detalle por sección abajo.

### Deltas guidelines junio 2026 (vs snapshot 2026-05-26)

- **5.1.2(i) — reforzado (13-nov-2025):** exige disclosure explícito de terceros
  *"including with third-party AI"* + permiso explícito ANTES de compartir datos.
  Anthropic debe nombrarse y el opt-in debe preceder al primer envío de datos. (§5.1.2)
- **4.7 / 4.7.5 — mini-apps y chatbots:** el chat IA con RAG podría leerse como
  "chatbot" bajo 4.7 → conviene content filter + age rating coherente. (§4.7, nueva)
- **4.1(c) — no usar icono/nombre de otro developer:** verificar que "The Dogs' Mind"
  no colisiona con marca/app existente en App Store. (§4.1)
- **Recomendación de producto IAP:** considerar membresía Pro como **Auto-Renewable
  Subscription** en vez de "pago único anual no-renovable" (más limpio para revisores).
  `[VERIFICAR]` — decisión abierta, ver §3.1.2. NO se cambia nada en código aún.
- **No existe sección dedicada a IA** en las guidelines (a jun-2026); solo 5.1.2(i)
  menciona "third-party AI". NO hay requisito formal de label/watermark de IA.

---

## 1. SAFETY

### 1.1 Objectionable Content
**Requisito:** No contenido ofensivo, violento, sexual, religioso inflamatorio.
**Estado:** ✅ N/A — app de conducta canina, contenido profesional.
**Riesgo:** Nulo.

### 1.2 User-Generated Content
**Requisito:** Filtro de contenido + reporte + bloqueo de usuarios abusivos + contacto público.
**Estado:** ✅ Parcial — el LLM filtra contenido inapropiado en anamnesis. NO hay UGC compartido entre usuarios (cada uno ve solo SUS casos) → 1.2 estricto no aplica.
**Evidencia:** No es red social. Si en el futuro se añade "The Council" pro compartido o sección comunidad → revisar.

### 1.4.1 Medical Apps
**Requisito:** Disclaimer de accuracy + recordar consultar profesional + no diagnosticar.
**Estado:** ✅ Disclaimer presente en pantallas de análisis (s-abc, s-full-analysis, s-tracking, s-abc-explained, s-plan-simple, loading) y en ToS §2.
**Evidencia:**
- `frontend/index.html:7517` (s-abc footer)
- `frontend/index.html:7549` (s-full-analysis footer)
- `frontend/index.html:7606` (s-tracking footer)
- `frontend/index.html:7416` (loading_disclaimer)
- `frontend/index.html:7687` (pp_disclaimer en s-plan-simple)
- `frontend/index.html:7748` (at_disclaimer en s-abc-explained)
- `frontend/index.html:16250` (tos_p2 en Terms)
**Nota:** 1.4.1 técnicamente cubre apps médicas para humanos. La conducta canina cae fuera del scope estricto, pero el disclaimer profiláctico protege ante revisores conservadores.

### 1.5 Developer Information
**Requisito:** Método de contacto fácil para soporte.
**Estado:** ✅ Dos emails publicados: `info@thedogsmind.net` (soporte) y `privacy@thedogsmind.net` (privacidad). Presentes en privacy.html, terms.html, pantalla "Mi cuenta y privacidad", y al final de cada policy.
**Evidencia:** `frontend/index.html:7341`, `frontend/privacy.html`, `frontend/terms.html`.

### 1.6 Data Security
**Requisito:** Medidas de seguridad apropiadas.
**Estado:** ✅ HTTPS forzado (Netlify), bcrypt para passwords, JWT HS256 30d.
**Evidencia:** `app/api/routes/auth.py` — bcrypt + JWT.

---

## 2. PERFORMANCE

### 2.1 App Completeness
**Requisito:** Build final, sin placeholders, URLs funcionales, demo account o demo mode.
**Estado:** ⏳ Pendiente al submitar — preparar cuenta demo para revisores Apple (ej: `appstore-review@thedogsmind.net` con 100 tokens precargados y un perro Buddy ejemplo).
**Acción Fase 2:** Crear cuenta demo + documentar credenciales en App Review Notes.

### 2.3.1 No Hidden Features
**Requisito:** Todas las features descritas en Notes for Review.
**Estado:** ⏳ Pendiente — al submitar, redactar notas detalladas (por ej. "el código BOCALAN-AMB activa cuenta cortesía con 12 tokens, distribuido a estudiantes de Bocalan").

### 2.3.10 Platform Focus
**Requisito:** No referencias a Android/Google Play en la versión iOS.
**Estado:** ⚠️ Hoy hay un comentario en código `// Web/Android → POST /payments/pro-checkout → Stripe Checkout` y otro `Sticky pago (Stripe Checkout en Web/Android; IAP en iOS futuro)` — solo en código JS, no visible para usuario. OK.
**Acción Fase 2:** Verificar que la UI iOS no muestra "Disponible en Google Play" ni similar.

### 2.5.1 Public APIs
**Requisito:** Sólo APIs públicas.
**Estado:** ✅ El backend sólo usa APIs Anthropic/Voyage/Stripe documentadas. Capacitor wrapper usa solo WKWebView + plugins oficiales.

### 2.5.2 Self-Contained Bundles (NO downloadable code)
**Requisito:** No descargar código dinámico que cambie features.
**Estado:** ⚠️ Riesgo medio — el SW (service-worker.js) cachea el index.html y lo actualiza vía network-first. Esto **no es** "download code that changes features" en el sentido Apple (es revalidación de cache estándar). Pero un revisor estricto podría preguntar.
**Mitigación:** El SW está bien documentado en comentarios; estrategia network-first explicita la naturaleza estática del recurso. Capacitor mete su propio mecanismo de live-updates (lo desactivamos al empaquetar para no caer en 2.5.2).

### 2.5.6 Web Browser Engine
**Requisito:** Si se navega web, usar WebKit.
**Estado:** ✅ El wrapper Capacitor usa WKWebView nativo en iOS por defecto. Cumple.

### 2.5.14 Recording Disclosure
**Requisito:** Si grabamos cámara/micro/pantalla, consentimiento + indicador visual.
**Estado:** ✅ El vídeo de anamnesis es OPCIONAL, se sube manualmente por el user (no grabamos en background). El icono de cámara del navegador/iOS indica grabación activa.

---

## 3. BUSINESS

### 3.1.1 In-App Purchase ⚠️ BLOQUEANTE
**Requisito:** "If you want to unlock features or functionality within your app… you must use in-app purchase."
**Estado:** ❌ **BLOQUEANTE para iOS App Store.** Hoy los packs de tokens van por Stripe Checkout. En iOS esto se rechazaría.

**Nota estratégica (decisión Teo 2026-05-26):** Mientras esté ACTIVA la promo de
lanzamiento `PRO_PROMO_FREE=true` (Railway), la activación Profesional NO cobra a
nadie (`/payments/pro-checkout` devuelve 503, `/payments/pro-activate-promo` activa
sin pago). La promo se MANTENDRÁ hasta justo antes de subir a App Store, momento
en que se apagará (env var → false) y los nuevos profesionales volverán a pagar
los 20€. Coincidencia útil: cuando apaguemos la promo, ya tenemos que tener el
IAP integrado para Pro también — el orden natural es:
  1. Hoy → promo ON, tokens via Stripe en web (sin App Store)
  2. Pre-launch App Store → integrar IAP (StoreKit2) en Capacitor wrapper
  3. Launch → promo OFF, Stripe en web (sigue), IAP en iOS
**Excepciones que NO aplican:**
- 3.1.3(a) Reader app: no aplica (no es contenido editorial).
- 3.1.3(b) Multiplatform service: aplicable PARCIALMENTE — podemos seguir vendiendo en web Y tener IAP en iOS, pero la iOS NO puede tener UI/link/copy que sugiera comprar en otro sitio.
- 3.1.3(c) Enterprise: solo si vendemos a empresas (corporativo), no a consumers.
- 3.1.3(d) Person-to-person real-time: no aplica (es IA, no humano en directo).
- 3.1.3(f) Free companion: no aplica (la propia iOS también cobra).
**⚠️ Regla dura de blindaje (agente 2026-06-02):** en el build iOS, Stripe debe quedar
**completamente oculto** — no botón, no link, no copy, ni siquiera un enlace externo
"compra más barato en la web". 3.1.1 + 3.1.3(b) prohíben dirigir al usuario fuera del
IAP dentro de la app iOS. Mecanismo: feature flag `IS_IOS_NATIVE` (derivado de
`Capacitor.getPlatform() === 'ios'`) que apaga TODO el path Stripe en el binario iOS.
La web sigue vendiendo por Stripe en paralelo (eso es legítimo).

**Acción Fase 2:**
1. Integrar `@revenuecat/purchases-capacitor` (abstrae StoreKit2 + Google Play Billing). **[Pendiente decisión input #5: RevenueCat vs StoreKit2 nativo.]**
2. Backend: webhook App Store Server Notifications V2 paralelo al de Stripe.
3. Crear productos IAP en App Store Connect: tokens (consumibles) + Pro (tipo a decidir, ver §3.1.2). **[VERIFICAR nomenclatura/IDs al crear.]**
4. UI iOS: `IS_IOS_NATIVE` → IAP en vez de Stripe; Stripe oculto por completo (regla dura arriba).
5. Restore Purchases: añadir botón "Restaurar compras" obligatorio (3.1.1).
6. Tokens no expiran (ya cumplimos: ToS §4 dice "no caducan").

### 3.1.2 Subscriptions
**Requisito:** Si hay subs auto-renovables, mínimo 7 días, info clara, valor continuo.
**Estado:** ✅ Hoy NO usamos subs auto-renovables. Tokens son **consumibles** (one-time IAP), Profesional es **non-renewing one-time** (pago único anual). Más simple, menos compliance.

**[DECISIÓN ABIERTA — VERIFICAR] Tipo de producto para Pro (recomendación agente 2026-06-02):**
El agente auditor recomienda modelar la membresía Pro como **Auto-Renewable
Subscription** en lugar de "pago único anual no-renovable", porque:
- Los revisores Apple leen mejor las auto-renewables (categoría limpia y estándar).
- "Non-renewing annual" es un tipo válido pero ambiguo; algunos revisores lo confunden.
Contras de auto-renewable: activa requisitos extra de 3.1.2 (gestión de suscripción,
copy de renovación, valor continuo, link a "Manage Subscriptions"). 
**Estado de la decisión:** SIN DECIDIR. Pros/contras documentados; se resolverá junto
al input #5 (RevenueCat vs StoreKit2) del founder. `[VERIFICAR]` la existencia y
nomenclatura exacta de "non-renewing annual" en App Store Connect antes de crear
cualquier producto. **No se cambia código ni se crean productos hasta decidir.**

### 3.1.5 Cryptocurrencies
**Estado:** ✅ N/A.

### 3.2.2 Unacceptable Practices
**Requisito:** No inflar clicks, no rate-gating, no loans abusivos.
**Estado:** ✅ N/A.

---

## 4. DESIGN

### 4.1 Copycats
**Estado:** ✅ Producto único en su categoría (análisis ABC conductual canino con IA + LIMA).

### 4.1(c) Nombre / icono de otro developer ✅ VERIFICADO 2026-06-02 — riesgo bajo
**Requisito:** No usar nombre, icono o branding confusamente similar al de otra app/developer.
**Verificación realizada (web search 2026-06-02):**
- ❌ NO existe app "The Dogs' Mind" ni "Dogs Mind" en el App Store. Apps de conducta canina
  existentes (OneMind Dogs, EveryDoggy, Dogo, Puppr) NO colisionan en nombre ni concepto.
  → El App Name está libre para reservar. 4.1(c) (copia de otra APP) = riesgo bajo.
- ⚠️ Existe un libro conocido: *"The Dog's Mind: Understanding Your Dog's Behavior"*
  (Bruce Fogle, Turner Publishing). Título casi idéntico PERO: (a) Apple revisa contra
  otras apps, no libros; (b) nuestra marca es **plural posesiva** ("Dogs'" vs "Dog's") →
  diferenciación; (c) títulos de un solo libro no suelen tener marca registrada protegible.
- También existen servicios (no apps): "My Dogs Mind", "Dogs Mind Training" → sin colisión App Store.
**Decisión:** ✅ **Procedemos con "The Dogs' Mind".** No bloquea submission.
**Riesgo residual:** trademark formal es materia legal ajena al App Store (bajo, no urgente).
Si se quisiera blindaje 100% → búsqueda USPTO/EUIPO + abogado (fuera del camino de compliance).
**Acción cuando haya cuenta paga:** reservar el App Name en App Store Connect cuanto antes
(first-come). Evitar en metadata/keywords cualquier referencia al libro o a Fogle.

### 4.2 Minimum Functionality ⚠️ BLOQUEANTE
**Requisito:** No wrappers web puros; la app debe aportar valor nativo más allá de "una web empaquetada".
**Estado:** ❌ **BLOQUEANTE actualmente** — Dogs Mind hoy es PWA puro.

**⚠️ Regla del founder (2026-06-02): "las funciones son las que hay".** NO se añaden
features de producto nuevas. La app ya es funcionalmente completa y profunda (análisis
ABC con IA, flujos multipantalla, cuentas, seguimiento diario, entrenamiento específico).
La 4.2 se cubre con **capacidades NATIVAS sobre funciones que YA EXISTEN**, no con scope nuevo.

**Acción Fase 2 — capacidades nativas (sin features nuevas):**
- ✅ **IAP** (RevenueCat) — capacidad nativa de comercio; cubre 3.1.1 y aporta valor nativo sustancial.
- ✅ **Push notifications nativas** (desde v1) — recordatorios del seguimiento diario, función YA existente; opt-in. (D-009)
- ✅ **Photo/Video Picker nativo** — implementación nativa de la subida de vídeo de anamnesis que **YA existe** en la app (no es función nueva, es el picker nativo en vez del input web).
- ✅ **Offline / caching nativo** — el SW ya lo da; Capacitor lo refuerza (no es función nueva).
- ❌ ~~Share Sheet / export PDF~~ — **DESCARTADO**: sería función nueva. No se añade (regla "las funciones son las que hay").

Con IAP + Push + Photo Picker nativo + offline, sobre una app de funcionalidad genuina y
profunda, la 4.2 queda cubierta **sin inventar nada**. Ver D-010.

### 4.3 Spam
**Estado:** ✅ App única (un único Bundle ID).

### 4.4 Extensions
**Estado:** ✅ Sin extensions iOS. N/A.

### 4.7 / 4.7.5 Mini-apps, chatbots, HTML5 ⚠️ Nueva consideración (delta jun-2026)
**Requisito:** Apps que ofrecen chatbots / mini-apps HTML5-JS deben cumplir reglas de
contenido, control de edad, y no exponer a menores a contenido inapropiado.
**Estado:** ⚠️ Riesgo bajo-medio. El chat IA con RAG (`daily-followup` coach, asistente)
**podría** interpretarse como "chatbot" bajo 4.7. Mitigaciones que ya tenemos / faltan:
- ✅ El LLM tiene system prompt estricto LIMA + ámbito conducta canina (no chat abierto).
- ✅ El contenido generado es profesional, no UGC entre usuarios.
- 📋 **Falta:** confirmar que el age rating declarado (4+) es coherente con tener un
  componente conversacional IA; algunos revisores piden 12+/17+ para chatbots abiertos.
  Nuestro chat NO es abierto (está acotado a conducta canina) → defendible como 4+,
  pero hay que **documentarlo en Notes for Review** explícitamente.
- 📋 **Falta:** content filter explícito sobre input del usuario (hoy el filtro es
  implícito vía el prompt; conviene un guardrail documentado).
**Acción Fase 2:** redactar en App Review Notes que el "chat" es un asistente acotado
(no chatbot de propósito general), con LIMA enforcement, y justificar age rating 4+.

### 4.8 Sign in with Apple
**Requisito:** Si hay social login (Facebook/Google/etc.), debe ofrecerse Sign in with Apple equivalente.
**Estado:** ✅ Solo auth propia email+password (JWT). Excepción 4.8(1) aplica: *"exclusively uses your company's own account setup."* — 4.8 no se exige.
**Si en el futuro añadimos Google/Apple login:** Apple Sign-In pasa a ser **obligatorio**. Memoria `dogs-mind-future-ideas.md` lo documenta.

### 4.9 Apple Pay
**Estado:** ⚠️ Sólo relevante si usamos Apple Pay para bienes físicos. Como nuestra única vía iOS será IAP, Apple Pay no aplica.

---

## 5. LEGAL

### 5.1.1(i) Privacy Policy
**Requisito:** Link en App Store Connect metadata + accesible in-app + describe data/3rd-parties/retención/derechos.
**Estado:** ✅ Cubierto.
**Evidencia:**
- In-app: pantalla `s-privacy` enlazada desde splash, signup, "Mi cuenta y privacidad" (`frontend/index.html:6696, 7355, 9309`).
- URL pública (App Store Connect): `https://thedogsmind.net/privacy.html` (creada en Fase 1.2).
- Lista de 3rd parties: 9 entidades (Anthropic, Voyage AI, Qdrant, Railway, Netlify, Resend, Plausible, Stripe, Apple) — ES y EN sincronizadas.
- Retención: ToS §4 + privacy §5 (4 años anonimizados post-deletion por Ley 58/2003).
- Derechos GDPR + CCPA explícitos.

### 5.1.1(ii) Permission
**Requisito:** Consentimiento explícito antes de recoger datos, pago no condicionado a data grant, retirada fácil.
**Estado:** ✅ Checkbox obligatorio en signup (`form_consent_html`) + retirada vía "Eliminar mi cuenta".
**Evidencia:** `frontend/index.html:8210-8214`.

### 5.1.1(iii) Data Minimization
**Requisito:** Solo data relevante al core.
**Estado:** ✅ Solo email + teléfono (opcional) + datos del perro (necesarios para el análisis). NO contacts, NO ubicación, NO foto perfil obligatoria.

### 5.1.1(v) Account Sign-In & Deletion
**Requisito:** "If your app supports account creation, you must also offer account deletion within the app."
**Estado:** ✅ Endpoint + UI completos.
**Evidencia:**
- Backend: `app/api/routes/auth.py:392` (`delete_account`) — soft-delete con `deleted_at` + email anonimizado + bloqueo en login.
- Frontend: modal `#delete-account-modal` (`frontend/index.html:7386`) + handler `confirmDeleteAccount` (`frontend/index.html:13267-13310`).
- Acceso: "Mis Tokens → Eliminar mi cuenta".

### 5.1.1(viii) Personal Data from Non-Direct Sources
**Estado:** ✅ Solo recogemos data directa del user. RAG usa corpus clínico interno (Stewart Hilliard etc.), no datos de usuarios.

### 5.1.1(ix) Regulated Industries
**Estado:** ✅ NO somos banking/health-humano/cannabis/gambling. Cuenta operada por persona física documentada (Teodoro Mariscal Diaz, España).

### 5.1.2(i) Data Use & Sharing (3rd-party AI disclosure) ⚠️ REFORZADO 13-nov-2025 — semi-bloqueante
**Requisito (texto vivo):** "Must clearly disclose where personal data will be shared
with third parties, **including with third-party AI**, and obtain explicit permission
before doing so."
**Estado:** 🟡 Cubierto a nivel signup; conviene **gate de consentimiento previo al primer
envío de datos** para máxima robustez ante revisor estricto.
**Evidencia (ya cubierto):**
- Privacy policy lista a Anthropic explícitamente como receptor del texto de anamnesis (`pp_l4_1`).
- Checkbox de consentimiento del signup menciona explícitamente: *"el texto que escriba sobre mi perro (anamnesis, conversaciones) se enviará a **Anthropic (Claude AI, USA)** para generar los análisis"* (`form_consent_html`, `frontend/index.html:8212`).

**Delta 2026-06-02 (qué cambió y qué falta):** la actualización del 13-nov-2025 endurece
el "**before doing so**": el consentimiento debe **preceder** al primer envío de datos a la IA.
- ✅ Hoy: el consentimiento se da en el signup (antes de poder usar nada). En la práctica
  esto YA precede al primer análisis → defendible.
- ✅ **Refuerzo IMPLEMENTADO (staged, sin deploy) 2026-06-06:** micro-aviso explícito en el
  punto exacto de envío, en los **dos** flujos que mandan datos del perro a la IA:
  - **Anamnesis / ABC** (`s-anamnesis`): `<p id="analyze-ai-consent">` justo encima del botón
    "Analizar con IA" (~L9682).
  - **Entrenamiento Específico** (`s-anamnesis-training`): `<p id="tc-ai-consent">` bajo el
    aviso de coste, encima de "Crear plan" (~L9303).
  - Texto (key i18n `consent_ai_inline`, ES+EN): *"Al continuar, el texto sobre tu perro se
    enviará a Anthropic (Claude AI, EE. UU.) para generar el análisis."* / *"By continuing,
    the text about your dog will be sent to Anthropic (Claude AI, USA) to generate the analysis."*
  - **Additive, copy + i18n, sin backend.** Verificado: 7/7 bloques `<script>` pasan
    `node --check`; 2 usos DOM + 2 defs i18n (ES/EN).
  - ⚠️ **NO desplegado** (cautela): editado solo en working tree. Al desplegar requerirá
    **bump de `CACHE_NAME`** (SW) para que usuarios cacheados reciban el copy. Pendiente:
    revisión visual del founder + deploy.

### 5.1.2(vi) Sensitive Data
**Estado:** ✅ NO usamos HomeKit, HealthKit, ClinicalHealthRecords, MovementDisorder, ClassKit, ARKit facial/depth. N/A.

### 5.1.3 Health & Health Research
**Estado:** ✅ NO recogemos health data humano. Datos del perro ≠ Health Data según definición Apple (que es human-clinical). N/A.

### 5.2 Intellectual Property
**Requisito:** No usar material 3rd-party sin permiso; submit como entidad propietaria.
**Estado:** ✅ Operado por Teodoro Mariscal Diaz (mencionado en pp_p1 y tos_p1). Citaciones a Stewart Hilliard en corpus RAG son textuales (no fictional) — material propio del autor con permiso implícito de uso clínico para análisis (NO redistribución directa).
**Acción Fase 2:** Si hay un cite directo de Stewart Hilliard visible al user, añadir atribución explícita en el análisis.

### 5.4 VPN
**Estado:** ✅ N/A.

---

## CHECKLIST PRE-SUBMISSION (Fase 2)

Cuando lleguemos al submission:

- [ ] **Capacitor wrapper** funciona en simulador iPhone + iPad (4.2)
- [ ] **IAP**: productos creados en App Store Connect (tokens 8/24/60 + Pro)
- [ ] **IAP**: webhook App Store Server V2 conectado al backend (3.1.1)
- [ ] **Restore Purchases**: botón visible en "Mis Tokens" (3.1.1)
- [ ] **Features nativas** ≥3 (push, share sheet, photo picker, offline) (4.2)
- [ ] **Cuenta demo** creada para Apple revisor + credenciales en App Review Notes (2.1)
- [ ] **Privacy Policy URL pública** funciona y carga rápido — `https://thedogsmind.net/privacy.html` ✅
- [ ] **Terms URL pública** funciona — `https://thedogsmind.net/terms.html` ✅
- [ ] **App Privacy nutrition labels** en App Store Connect: declarar data collected (Email, Phone, User Content, Customer Support) + linkeo to 3rd parties
- [ ] **Age rating**: 4+ (no contenido objetable) — la app NO es Kids Category
- [ ] **Screenshots** que muestren la app en uso (no splash/login) en 6.5", 5.5", iPad 12.9", iPad 11" (2.3.3)
- [ ] **App description** sin referencias a Android/Google Play (2.3.10)
- [ ] **What's New** descriptivo en cada update (2.3.12)
- [ ] **Notas para revisor**: explicar el flujo de tokens, qué es BOCALAN-AMB, qué es account_type 'professional' (2.3.1)
- [ ] **TestFlight beta** con al menos 2-3 testers reales antes de submitar
- [ ] **Account deletion**: probado en simulador iOS funciona (5.1.1(v))
- [ ] **Sign in with Apple**: NO requerido hoy (4.8(1)) — si añadimos OAuth, pasa a ser obligatorio

---

## CÁLCULO DE READINESS (~62%)

Estimación honesta por bloques (peso aprox. según esfuerzo/riesgo de rechazo):

| Bloque | Peso | Estado | Aporta |
|---|---|---|---|
| Legal/Privacy (5.1.1, policies, deletion, disclaimers) | 20% | ✅ ~95% | 19% |
| Contenido/Safety (1.x, 4.1, 4.8, medical disclaimer) | 15% | ✅ ~90% | 13.5% |
| 5.1.2(i) consent IA reforzado | 10% | ✅ ~95% (gate per-acción staged 2026-06-06; falta deploy) | 9.5% |
| 4.7 chatbot/age-rating | 5% | 🟡 ~60% (falta doc Notes + guardrail) | 3% |
| **3.1.1 IAP** (RevenueCat/StoreKit + webhook + ocultar Stripe iOS) | 25% | ❌ ~0% (no empezado) | 0% |
| **4.2 Wrapper Capacitor + ≥3 features nativas** | 20% | ❌ ~0% (PWA puro) | 0% |
| Assets/metadata (screenshots, demo account, Notes, nutrition labels) | 5% | ⏳ ~20% | 1% |
| **TOTAL** | 100% | | **~62%** |

**Lectura:** lo legal/contenido/UX está prácticamente listo. El 38% restante es
casi todo **trabajo de ingeniería iOS no empezado** (IAP + Capacitor) que depende de:
(a) cuenta Apple Developer paga, (b) decisión RevenueCat vs StoreKit2, (c) decisión
tipo de producto Pro. Sin esos 3 inputs no se puede subir el % de forma honesta.

---

## EVIDENCIAS ARCHIVADAS

**Última verificación de compliance:** 2026-06-02 — revisión de deltas guidelines vivas
(5.1.2(i) reforzado 13-nov-2025, 4.7 chatbots, 4.1(c), recomendación IAP auto-renewable)
por agente auditor. Doc-only, sin cambios de código. Caveat de verificación al inicio del doc.

**Última verificación previa:** 2026-05-26 — Fase 1 (sync ES/EN, URLs públicas, consent IA, disclaimer veterinario).

**Próxima revisión:** Al recibir los inputs del founder (cuenta Apple Dev, RevenueCat/StoreKit2,
tipo producto Pro) → arrancar Fase 2 (Capacitor scaffold + IAP). Decisiones se registran en
`APPSTORE_DECISIONS.md`; progreso en `APPSTORE_TRACKING.md`.
