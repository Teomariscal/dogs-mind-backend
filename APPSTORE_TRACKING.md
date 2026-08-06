# Dogs Mind — App Store Tracking Board

Board operativo de la publicación en App Store. Organizado por **fase y dependencia**
(no por cuenta atrás). Cada ítem: estado · bloqueado-por · nota. **Regla dura: guardar
todo siempre.** Esta es la foto de "dónde estamos" para retomar en cualquier sesión.

Leyenda estado: ✅ hecho · 🟡 en curso · ⏳ pendiente · 🔒 bloqueado · ❌ no empezado

---

## FASE 0 — Preparación que NO requiere cuenta Apple paga (se puede hacer YA)

| Ítem | Estado | Bloqueado por | Nota |
|---|---|---|---|
| Auditoría compliance vs guidelines vivas | ✅ | — | `APPSTORE_COMPLIANCE.md` (rev. 2026-06-02) |
| Decision log + tracking board | ✅ | — | Este doc + `APPSTORE_DECISIONS.md` |
| Verificar nombre 4.1(c) "The Dogs' Mind" | ✅ | — | Sin app colisionante; libro Fogle "The Dog's Mind" = riesgo bajo, procedemos (D en COMPLIANCE §4.1c) |
| Definir catálogo IAP (IDs, precios) en papel | ⏳ | D-003 (tipo Pro) | tokens consumibles + Pro |
| Scaffold Capacitor en local (simulador) | 🟡 | Xcode (founder) | **YA EXISTE** en `mobile/` (Cap 8.3, SPM, appId `net.thedogsmind.app`, webDir `../frontend`). 2026-06-04: icono iOS = logo aprobado, display name `The Dogs' Mind`, orientación portrait-only. Falta: instalar Xcode → `npx cap sync ios` + abrir + run en simulador |
| Implementar flag `IS_IOS_NATIVE` (oculta Stripe) | ✅ | — | D-002 · 3.1.1. **Scaffold HECHO y vivo en prod (SW v196)**: `dmIsIosNative()` (fail-closed) + `dmApplyIosNativeUI()` + 3 entradas Stripe blindadas (recargar/psSubmit/paGoToCheckout). Inerte en web (verificado 3 vías: code review + `node --check` 7/7 + en prod sin regresión). Falta solo cablear IAP en los `TODO Fase 2`. Provenance: commiteado mezclado en commits training v195/v196 |
| Borrador assets (screenshots, textos, demo acct) | ⏳ | — | se pulen al final |
| Refuerzo consent IA per-acción (copy + i18n) | 🟡 | deploy (founder) | §5.1.2(i). **IMPLEMENTADO staged 2026-06-06** (key `consent_ai_inline` en anamnesis + entrenamiento). Additive, `node --check` OK. Sin deploy: falta visual + bump SW al desplegar |

## FASE 1 — Requiere cuenta Apple paga (espera al pago del founder)

| Ítem | Estado | Bloqueado por | Nota |
|---|---|---|---|
| Pagar Apple Developer Program | ✅ | — | **PAGADO 2026-06-08** · Apple ID `teomariscald@gmail.com` · Enrollment `6ZYX4DM4WS` · €99/año |
| **Paso a paso completo Fase 1** | ✅ | — | **`APPSTORE_CONNECT_SETUP.md`**: orden + cada campo con su valor + copy IAP ES/EN |
| Firmar Paid Applications Agreement (+tax+banking) | 🟡 | Apple (verificación ~24h) | **HECHO 2026-06-08**: acuerdo firmado (estado "Procesando"), W-8BEN Activo + Certificate of Foreign Status enviado (Art.12/0%, Owner), cuenta **Revolut ES (3706)** EUR añadida ("En proceso", ~24h, locked 24h). Se activará solo. ⭐ Banca a migrar a Luxemburgo en futuro. DSA trader status DIFERIDO a pre-publicación |
| Reservar App Name "The Dogs' Mind" | ✅ | — | **HECHO 2026-06-08**. App iOS v1.0 creada, SKU `thedogsmind-ios-001`, idioma Español (España). Verificar luego que el título lleva apóstrofo ' y no tilde ´ (editable hasta 1ª publicación) |
| Registrar Bundle ID `net.thedogsmind.app` | ✅ | — | **HECHO 2026-06-08**. App ID "The Dogs Mind" · capabilities IAP + Push · Team ID `XW9545NR8J` |
| Crear productos IAP reales (3 tokens + Pro) | ⏳ | founder + agreement | copy ES/EN lista. Setup guide §4 |
| Certificados/provisioning de distribución | ⏳ | Xcode | se generan desde Xcode al firmar el build |

## FASE 2 — Ingeniería iOS (IAP + nativo)

| Ítem | Estado | Bloqueado por | Nota |
|---|---|---|---|
| Integrar IAP (RevenueCat) | ❌ | Fase 1 (cuenta paga) | RevenueCat (D-007). Anclajes ya marcados `TODO Fase 2 (IAP)` en los 3 guards de `IS_IOS_NATIVE` |
| Webhook App Store Server Notifications V2 | ❌ | IAP | paralelo a Stripe |
| Restore Purchases (botón obligatorio) | ❌ | IAP | 3.1.1 |
| ≥3 features nativas (push, share, photo picker) | ❌ | scaffold + input #6 | 4.2 |
| Smoke test en simulador + device físico | ✅ (sim) | device físico pendiente | **2026-06-08 ✅ APP CORRIENDO EN SIMULADOR** (iPhone 16, iOS 26.5). BUILD SUCCEEDED, instalada y lanzada (PID ok), splash renderiza perfecto (no white screen). `IS_IOS_NATIVE` activo en binario nativo. Pendiente: (a) ver pantalla tokens logueado (necesita cuenta demo/login) para confirmar Stripe oculto visualmente; (b) run en iPhone 14 físico (needs signing team XW9545NR8J) |

## AUDITORÍA ANTI-RECHAZO (2026-06-08) → `APPSTORE_AUDIT_FINDINGS.md`

Panel multi-agente (51 agentes, 12 guidelines). 21 riesgos confirmados (7 blockers, 2 high).
- ✅ Arreglado hoy: usage strings Info.plist (NSCamera/NSMic/NSPhoto), iPad→iPhone-only (device family `1`), gate pre-submit en Notes for Review.
- 🟡 Al cablear IAP (Fase 2): pantallas de compra Pro ocultas/IAP en iOS (agujero D-002), 4.2 features nativas, copy suscripción, links T&C.
- ⏳ Pulido: guardrail/ámbito chat (4.7), botón "reportar respuesta".
- 👤 Founder: crear cuenta demo + password real en Notes.

## FASE 3 — Pre-submit y review

| Ítem | Estado | Bloqueado por | Nota |
|---|---|---|---|
| Demo account para revisor Apple | 🟡 | founder (crear cuenta) | **Spec redactada** en `APPSTORE_ASSETS.md` §1 (appstore-review@, 100 tokens, Pro, perro Buddy). Falta que el founder la cree |
| Screenshots 6.9" (iPhone-only) | ❌ | app corriendo en iOS | 2.3.3. iPhone-only (D-006) |
| App Privacy nutrition labels | ✅ | — | **Mapeo completo** en `APPSTORE_ASSETS.md` §5 (+ "Data Not Used to Track You"). Listo para pegar |
| Notes for Review (tokens, código cortesía, chat acotado 4.7) | ✅ | — | **Redactadas (EN)** en `APPSTORE_ASSETS.md` §2. Falta solo password demo |
| App Store copy ES/EN (desc, keywords, subtitle, What's New) | ✅ | — | **Redactado** en `APPSTORE_ASSETS.md` §3 (sin "Bocalán" público, sin emojis) |
| Apagar promo `PRO_PROMO_FREE` justo antes de submit | ⏳ | — | env var Railway → false |
| TestFlight beta interna (testers reales) | ✅ | founder instala | **2026-06-09 ✅ EN TESTFLIGHT, 100% autónomo vía key Admin.** Build 1 (id `580bb9f6-ddc4-4582-b308-25a19b8a5811`) VALID + `READY_FOR_BETA_TESTING` (compliance auto-OK por ITSAppUsesNonExemptEncryption). Grupo interno "Internal" (id `3d98316a-77f2-49e4-81d3-9771243f6d12`) creado, build asignado, tester `teomariscald@gmail.com` añadido — todo por API. Falta solo: founder instala desde app TestFlight. **API keys**: App Manager `3V2RQKK7S4` + Admin `26Q473G2V8` (Issuer `4af2188f-87d6-459c-88ea-793b67971435`), .p8 en credentials + `~/.appstoreconnect/private_keys/`. Helpers Ruby en `/tmp/asc_*.rb`. App ASC id `6777848632`. Device "Niaz iPhone" registrado (`BV52Z89H3Q`) solo para desbloquear el archive. ⚠️ El build TestFlight tiene los blockers del audit SIN arreglar (Pro screens Stripe, 4.2 sin features nativas) — es solo para probar en hardware, NO submittable |
| Submit + gestionar ciclo de rejection | 🔒 | todo lo anterior | — |

---

## ESTADO ACTUAL (snapshot 2026-06-06)

- **Readiness ~72%.** Los 7 inputs cerrados; scaffold Capacitor ya existe; icono App Store
  resuelto y desplegado; icono iOS nativo = logo aprobado; **`IS_IOS_NATIVE` (D-002) scaffold
  HECHO y vivo en prod**. El resto es ingeniería iOS (IAP) + pack de assets pre-submit.
- **Cuello de botella inmediato:** **Xcode NO instalado** (solo CommandLineTools) + cuenta
  Apple sin pagar. Ambas son acciones del founder. node v26 / npm 11 OK; SPM (no CocoaPods).
- **✅ Hecho 2026-06-06:** (a) `IS_IOS_NATIVE` (D-002, 3.1.1) verificado inerte en web (3 vías) y
  confirmado vivo en prod (SW v196); (b) **pack de assets pre-submit redactado** en
  `APPSTORE_ASSETS.md` (Notes for Review EN, copy App Store ES/EN, nutrition labels, spec demo
  account, productos IAP, age rating, screenshots spec, checklist). Docs + memoria actualizadas.
- **✅ Hecho 2026-06-06 (cont.):** refuerzo consent IA per-acción (§5.1.2) **implementado
  staged** en `frontend/index.html` (anamnesis + entrenamiento), additive, `node --check` OK,
  SIN deploy. Pendiente: revisión visual del founder + deploy con bump de `CACHE_NAME`.
- **Pendiente del founder (acciones que solo él puede hacer):**
  - Revisar visualmente el refuerzo consent IA y dar OK a deploy (con bump SW).
  - Crear cuenta demo (`APPSTORE_ASSETS.md` §1) + rellenar password en Notes for Review.
  - Instalar Xcode + pagar Apple Developer → desbloquea Fase 1 + ingeniería IAP (Fase 2).
- **Hecho 2026-06-04 (wrapper):** icono iOS desde logo aprobado (`make_ios_appicon.py`),
  display name con apóstrofo tipográfico, orientación portrait-only. Sin deploy (mobile/ no se deploya).
- **Gating del founder para el primer build real:** (1) instalar Xcode (Mac App Store, macOS Tahoe),
  (2) pagar Apple Developer. Con eso: `npx cap sync ios` + abrir + run en simulador/iPhone 14.
