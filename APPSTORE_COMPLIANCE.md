# Dogs Mind — App Store Review Compliance Checklist

**Última actualización:** 2026-05-26
**Estado global:** Pre-submission · Fase 1 (PWA cleanup) completa · Fase 2 (Capacitor + IAP) pendiente

Documento interno de referencia. Mapea cada guideline relevante de [App Store Review Guidelines](https://developer.apple.com/app-store/review/guidelines/) al estado actual de Dogs Mind, con evidencia en código.

---

## TL;DR — Bloqueantes para submitar HOY

| # | Bloqueante | Sección | Acción |
|---|---|---|---|
| **1** | Stripe Checkout para tokens (en iOS debe ser IAP) | 3.1.1 | Fase 2: integrar StoreKit2 + webhook App Store Server Notifications V2 |
| **2** | PWA puro sin wrapper nativo | 4.2 | Fase 2: empaquetar con Capacitor + añadir features nativas (push, share sheet, photo picker, IAP) |
| **3** | (Resuelto en Fase 1) URLs públicas /privacy y /terms | 5.1.1(i) | ✅ Hecho — `frontend/privacy.html` y `frontend/terms.html` |

**Lo demás está cubierto o es bajo riesgo.** Detalle por sección abajo.

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
**Acción Fase 2:**
1. Integrar `@revenuecat/purchases-capacitor` (abstrae StoreKit2 + Google Play Billing).
2. Backend: webhook App Store Server Notifications V2 paralelo al de Stripe.
3. Crear productos IAP en App Store Connect: `dm_tokens_pack_8`, `dm_tokens_pack_24`, `dm_tokens_pack_60`, `dm_pro_membership_yearly`.
4. UI iOS: detectar `Capacitor.getPlatform() === 'ios'` → renderizar botón "Comprar tokens" que dispare IAP en vez de Stripe Checkout.
5. Restore Purchases: añadir botón "Restaurar compras" obligatorio (3.1.1).
6. Tokens no expiran (ya cumplimos: ToS §4 dice "no caducan").

### 3.1.2 Subscriptions
**Requisito:** Si hay subs auto-renovables, mínimo 7 días, info clara, valor continuo.
**Estado:** ✅ NO usamos subs auto-renovables. Tokens son **consumibles** (one-time IAP), Profesional es **non-renewing one-time** (pago único anual). Más simple, menos compliance.

### 3.1.5 Cryptocurrencies
**Estado:** ✅ N/A.

### 3.2.2 Unacceptable Practices
**Requisito:** No inflar clicks, no rate-gating, no loans abusivos.
**Estado:** ✅ N/A.

---

## 4. DESIGN

### 4.1 Copycats
**Estado:** ✅ Producto único en su categoría (análisis ABC conductual canino con IA + LIMA).

### 4.2 Minimum Functionality ⚠️ BLOQUEANTE
**Requisito:** No wrappers web puros.
**Estado:** ❌ **BLOQUEANTE actualmente** — Dogs Mind hoy es PWA puro.
**Acción Fase 2:** Wrapper Capacitor + features nativas:
- ✅ IAP (cubre 3.1.1 y aporta valor nativo).
- 📋 Push notifications nativas (recordatorios de seguimiento diario).
- 📋 Share Sheet nativo (compartir análisis como PDF).
- 📋 Photo Picker nativo (subir vídeo de anamnesis).
- 📋 Offline mode (SW ya lo da, Capacitor lo refuerza).
Con al menos 3-4 de éstos, 4.2 está cubierto sin riesgo.

### 4.3 Spam
**Estado:** ✅ App única (un único Bundle ID).

### 4.4 Extensions
**Estado:** ✅ Sin extensions iOS. N/A.

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

### 5.1.2 Data Use & Sharing (3rd-party AI disclosure) ⚠️ Recientemente reforzado
**Requisito:** "Must clearly disclose where personal data will be shared with third parties, **including with third-party AI**, and obtain explicit permission before doing so."
**Estado:** ✅ Reforzado en Fase 1.3.
**Evidencia:**
- Privacy policy lista a Anthropic explícitamente como receptor del texto de anamnesis (`pp_l4_1`).
- Checkbox de consentimiento del signup ahora menciona explícitamente: *"el texto que escriba sobre mi perro (anamnesis, conversaciones) se enviará a **Anthropic (Claude AI, USA)** para generar los análisis"* (`form_consent_html`, `frontend/index.html:8212`).

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

## EVIDENCIAS ARCHIVADAS

**Última verificación de compliance:** 2026-05-26 — commit `<pendiente>` cubre Fase 1 (sync ES/EN, URLs públicas, consent IA, disclaimer veterinario).

**Próxima revisión:** Antes de iniciar Fase 2 (Capacitor + IAP).
