# Dogs Mind — DESIGN & FUNCTION LOCK

Documento de anclaje inviolable. Establecido 2026-05-13.

**TODA modificación a algo listado en este documento requiere instrucción explícita de Teo** ("desancla X, cambia a Y"). Sin esa orden, lo de aquí permanece como está.

---

## 1. Ubicaciones canónicas de archivos (LOCKED)

### Frontend
- **`frontend/index.html`** → archivo único de la SPA, fuente de verdad.
- **`frontend/teo-mariscal-v3.html`** → mirror exacto del anterior (cp tras cada cambio).
- **`frontend/service-worker.js`** → SW de la PWA. Bump de versión obligatorio tras cambio frontend.
- **`frontend/assets/images/`** → directorio canónico de imágenes del producto. Servidas por Netlify. **Cero referencias jsdelivr en `index.html`** (eliminadas 12-may, no reintroducir).
  - `img-00.webp` … `img-21.*` (12 archivos directos)
  - `scenes/dog-profile-hero.webp`, `scenes/seguimiento-hero.webp`
  - `icons/icon-home-with-dog.png`
- **`frontend/manifest.json`** + **`frontend/icons/`** → PWA install (no tocar).

### Backend
- **`app/main.py`** → punto de entrada FastAPI.
- **`app/api/routes/`** → routers HTTP. Estructura locked.
- **`app/services/`** → AI services (clinical_ai, intervention_ai, avatar_ai, daily_followup_coach).
- **`app/core/anthropic_error.py`** → helper traducción de errores 529/429/timeout. Aplicado en intervention/analysis/avatar routers. **No revertir.**
- **`app/models/`** → Pydantic models. Cambios a schemas requieren migración + smoke test.

### Deploys
- **Prod**: `thedogsmind.net` → Netlify site `152389f9-0282-46b5-a929-db9f9b142912` (`thedogsmind-prod`).
- **Staging**: `beta.thedogsmind.net` → Netlify site default (`thedogsmindbeta`).
- **Backend**: Railway `dogs-mind-backend-production.up.railway.app`. Auto-redeploy tras push origin/main.

---

## 2. Funciones JS críticas (LOCKED)

### `goTo(id)` (línea ~9130 de index.html)
Cambio de pantalla. **Controla la visibilidad del `#global-nav`** según:
- `noNav = ['s-splash','s-login','s-refine','s-tour-intro','s-account-type','s-pro-area','s-pro-activate','s-pro-company']` → nav nunca visible aquí.
- Sin JWT (`localStorage.getItem('dm_jwt')`) → nav nunca visible.
- Resto + JWT → nav visible.

**Comportamiento esperado y aprobado por Teo**: la nav solo aparece logueado. No es bug.

### `openDailyFollowup(...)` (IIFE final)
Daily-followup entrypoint. Lee plan_text de `_dfPlanCache` si no se pasa explícito.

### `acceptIntervention(...)`
Activa daily-followup en backend. Hook desde s-records "Seguimiento diario".

### `_dfInviteCheck()` (IIFE final)
Modal invitación 1×día al check-in con avatar Niaz. Flag localStorage por fecha.

### `_dfRecordsBadgeLoad()` (IIFE final)
Badge cyan top-right en s-records para casos con daily-followup activo.

### `renderHomeDogs()` (IIFE final)
Renderiza Buddy/Laika placeholder si no hay sesión. **Buddy/Laika con sus fotos son el estado por defecto sin login**. No es bug.

### Startup IIFE (línea ~9039)
Garantiza que `s-splash` es la primera pantalla y `#global-nav` arranca `display:none`. **No tocar**.

---

## 3. Selectores CSS LOCKED por pantalla

Reglas duras:
- **Nunca** modificar selectores globales (`.action-card`, `.card-title`, `.section-title`, `.btn-hero`, etc.) sin scope a `#screen-id`.
- **Siempre** usar `#screen-id .clase { propiedad: valor !important; }` para overrides.
- **Siempre** verificar visualmente con preview MCP antes de commit, y pedir captura a Teo antes de deploy si el preview no puede cargar prod real.

### Pantallas con CSS scope-locked vibrant emerald (no tocar sin orden)
1. `#s-home` (líneas 5899-5970): hero, halos cyan/green intensos, grid radial mask, cards verde sage `#c8d8bf` (Registros, Aigents, Insight) + Analysis blanca CTA.
2. `#s-records` — vibrant emerald + badge cyan daily-followup.
3. `#s-abc`, `#s-tracking`, `#s-full-analysis` — vibrant emerald.
4. `#s-anamnesis` — vibrant header, form cream, pomerania-paracaidista con `:not(.pomerania-paracaidas)` defensivo.
5. `#s-tokens`, `#s-plan-simple`, `#s-abc-explained`, `#s-abc-translated`.
6. `#s-loading-analysis`, `#s-privacy`, `#s-terms`.

### Pantallas con identidad propia (NO aplicar vibrant)
- `#s-profile` (CV Teo, editorial halo amber + foto fundida).
- `#s-splash`, `#s-login`, `#s-pro-area`, `#s-aigents-intro` (premium identity).

---

## 4. Estado bloqueado por commit

| Commit | Fecha | Locked |
|---|---|---|
| `6592aea` | 2026-05-16 | **ROOT CAUSE real** chat-bar iPhone 14: iOS auto-zoom al focus en textarea con font-size <16px. Fix `#s-chat .chat-ta font-size:16px!important` (mínimo iOS para mantener escala 1.0). SW v133. **VERIFICADO POR TEO: "funciona bien, enhorabuena"**. Anclado. |
| `4f5fb18` | 2026-05-16 | Fix flexbox chat-bar (no era root cause pero defensa en profundidad): `#s-chat .chat-ta min-width:0!important + flex:1 1 0%!important`, `.send flex-shrink:0!important + flex-grow:0!important`, `.chat-bar padding-right ampliado`. SW v132. |
| `c06bb37` | 2026-05-16 | Pro cortesía via invite: nuevo endpoint backend `/payments/pro-activate-courtesy` valida `PRO_INVITE_CODE` env, activa `account_type=professional` + 10 tokens cortesía SIN Stripe, permanente. Frontend `#ps-invite` en s-pro-signup autofilleado por IIFE invite. psSubmit detecta invite → llama courtesy endpoint, skip datos empresa (3B). Listener reactivo: botón "Pagar 20€" → "Activar gratis (cortesía)". SW v131. |
| `60c3b08` | 2026-05-16 | Link embajador con auto-fill: IIFE startup lee `?invite=CODE` (o `?code=`), persiste en `localStorage.dm_pending_invite`, prellena `#reg-invite` con marcado verde sage sutil. Tras registro exitoso se limpia. Tokens embajador bajados 15→8 (auth.py + payments.py + toast frontend). SW v130. |
| `9007f15` | 2026-05-16 | Fix chat Aigents send button tapado: s-chat añadido a noNav array → #global-nav se oculta durante el chat (el chat tiene su propio back button en header). El botón ↑ enviar queda libre. SW v129. |
| `ac836cb` | 2026-05-16 | Keyboard-aware layout mobile: visualViewport API listener actualiza --kbd-h dinámico. .phone mobile <768px usa padding-bottom: var(--kbd-h) → cuando aparece teclado iOS, la chat-bar y inputs no quedan tapados. SW v128. |
| `6de2a96` | 2026-05-16 | i18n s-records: textos hardcoded en JS (renderRecords, statusLabel, changeRecordStatus) ahora usan _i18nText(). Nuevas claves rec_status_*/rec_tag_*/rec_btn_*. EN: In Progress / Resolved / Closed, ABC Analysis, LIMA Plan, + Follow-up, Status, + New Consultation, Daily follow-up. SW v127. **VERIFICADO POR TEO: "idioma solucionado"**. |
| `a419c5e` | 2026-05-16 | Mario peek recuperado flotando arriba derecha en s-aigents-intro. Animación aigPeekFloat 4.2s ease-in-out infinite (translateY/rotate/scale sutil). Posición right:-32px top:-110px relativo al span del título. SW v126. |
| `a5d5051` | 2026-05-16 | Fix s-aigents-intro: .aig-peek display:none (Mario asomando entre letras 'Aigents' aparecía visible POR ENCIMA en mobile iOS, no detrás como pretendía z-index:-1). SW v125. |
| `b4c8234` | 2026-05-16 | Fix download PDF mobile 3-tier: (1) navigator.share({files}) menú nativo iOS Acrobat/Archivos/AirDrop, no saca de la app. (2) window.open(blobUrl, '_blank') fallback nueva pestaña. (3) <a download> último fallback desktop. SW v124. |
| `427113a` | 2026-05-16 | Fix nav atrapado tras descargar PDF: botón verde grande mobile-friendly al final del footer en s-abc-translated ('Volver al análisis' → s-abc) y s-plan-simple ('Volver al plan' → s-tracking). i18n ES + EN. Header sticky con back ← se mantiene. SW v123. **VERIFICADO POR TEO: "ok"**. Anclado. |
| `d38ba42` | 2026-05-16 | Copy s-tokens: 'consume 3 tokens' -> 'consume aproximadamente 3 tokens' (ES) / 'approximately 3 tokens' (EN). Coste real varia segun complejidad. SW v122. **VERIFICADO**. |
| `84ac5e5` | 2026-05-16 | Footer s-tokens: quitado PayPal enganoso (backend Stripe). Reemplazado por icono SVG tarjeta + 'Pago seguro con tarjeta' / 'Secure card payment'. PayPal Business pendiente integracion (Smart Buttons SDK + dev.paypal.com app). SW v121. **VERIFICADO POR TEO: "mejor quitemos paypal"**. Anclado. |
| `c66c22c` | 2026-05-16 | s-tokens packs: avatares Aigent en cuadrado redondeado 44x44 reemplazan cuadrados blancos vacios. Pack 5 -> Ale. Pack 20 (preferida) -> Mario. Pack 60 (pro) -> Cecilia. SW v120. **VERIFICADO POR TEO: "el resto OK"**. Anclado. |
| `5a47f65` | 2026-05-16 | **FIX MOBILE CREAM REFORZADO**: en <768px .phone bg vibrant #0e1f1a + position:fixed inset:0 + width/height 100% con !important + body overflow:hidden. Garantiza que la app SIEMPRE cubre el viewport real del dispositivo, sin gap por URL bar dinamica de iOS Safari (dvh recalc) ni rubber-band scroll. Mi regla mobile-only va antes en cascade que la regla base de .phone, !important imprescindible. Desktop intacto. SW v119. **VERIFICADO POR TEO: "solucionado la banda crema"**. Anclado. |
| `3c0e37b` | 2026-05-16 | Fix mobile overscroll (intento parcial v118) + eyebrow s-account-type: nueva key i18n 'account_type_eyebrow' = 'Perfil de Usuario' / 'User Profile' tras conflicto con 'at_eyebrow' duplicado que sombreaba a s-abc-translated. SW v118. |
| `51901e1` | 2026-05-16 | Feat Macho/Hembra anamnesis + fix daily-followup lang con CRITICAL LANGUAGE INSTRUCTION en user_msg coach. SW v117. |
| `749a367` | 2026-05-15 | Fix #1 s-profile scroll mobile (overflow-y:auto !important) + fix #2 intervention lang EN respetado. SW v116. |
| `598fbd7` | 2026-05-15 | **DAILY TIP + Recargar tokens**: nuevo endpoint backend GET /tip/today?lang con cache DB (date, lang) + Haiku 4.5 prompt psicologia del aprendizaje canino + variedad 14 dias (sin repetir tip en ventana). Frontend loadDailyTip() fetch async no-bloqueante con cache localStorage + fallback i18n. Donut tokens en s-home envuelto en button .token-slot con label "Recargar tokens" debajo (i18n ES/EN), click navega a s-tokens (3 packs Stripe). SW v115. **VERIFICADO POR TEO en prod: "esta ok"**. Anclado. |
| `ad97a83` | 2026-05-13 | Fix #4+#5: ocultar placeholders vacios dog-photo en s-tracking y s-full-analysis. SW v114. **VERIFICADO POR TEO**. Anclado. |
| `83b069f` | 2026-05-13 | **RESPONSIVE TWO-MODE**: mobile <768px app full viewport del dispositivo real (sin marco mockup); desktop >=768px telefono ficticio centrado (390x844, bezel iPhone, notch, status-bar, sombra premium). body sin padding/flex en mobile, body con flex-center + padding:20px en desktop. SW v113. **VERIFICADO POR TEO en prod: "correcto splash super correcto"**. Anclado. |
| `65b4f6f` | 2026-05-13 | Fix #7 s-profile: cv-cta-wrap relative + ocultar bottom-nav legacy duplicado. SW v112. **VERIFICADO POR TEO en prod**. Anclado. |
| `8c63307` | 2026-05-13 | Fix REFORZADO solape menu hamburguesa s-home: topbar position:sticky z-index:100 + menu-btn 44x44 z-index:101 + dropdown z-index:200 + hero margin-top:16px. SW v111. **VERIFICADO POR TEO en prod tras borrar caché**. Anclado. |
| `bf27e06` | 2026-05-13 | Fix inicial solape (z-index:10 + margin:12px) - superado por 8c63307. SW v110. |
| `2b8c116` | 2026-05-13 | Fase 1 assets locales (15 archivos) + cards s-home verde sage `#c8d8bf` con Analysis BLANCA destacando + SW v109. **VERIFICADO POR TEO en prod**. Anclado. |
| `afa79c1` | 2026-05-13 | Revert v109 anterior con tester live. |
| `8cba77f` | 2026-05-12 | Helper anthropic_error.py → 503/429/504 user-friendly. |
| `3e382f4` | 2026-05-12 | Cleanup vars --orange + inline cream zombies. SW v108. |

---

## 5. Reglas duras vigentes (memoria)

Ver memoria del usuario:
- `feedback_dogs_mind_verificacion_visual_obligatoria_hard.md`
- `feedback_dogs_mind_workflow_anclado.md`
- `feedback_solo_modificar_lo_pedido.md`
- `feedback_no_arriesgar_appstore.md`
- `feedback_no_inventar_ni_falsas_soluciones.md`
- `feedback_dogs_mind_no_tocar_precios.md`
- `feedback_dogs_mind_no_huellas.md`
- `feedback_dogs_mind_no_emojis.md`
- `feedback_pre_deploy_nav_check.md` (verificar `#global-nav` antes de prod).

---

## 6. Cómo desbloquear algo

1. Teo me dice explícitamente "desancla X, cambia a Y" (X = item de este documento, Y = el nuevo estado).
2. Análisis de riesgos previos (¿qué bugs podrían producirse?).
3. Aplico cambio scope-locked.
4. **Verificación visual MÍA** (preview MCP local).
5. **Verificación visual TUYA** (yo te muestro captura, tú confirmas).
6. Deploy.
7. Si yo no pude verificar prod real → **pido captura tuya antes de seguir, no después**.
8. Actualizo este documento con el nuevo estado canónico.
