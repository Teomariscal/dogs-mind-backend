# Dogs Mind — Punch-list anti-rechazo (auditoría multi-agente 2026-06-08)

Resultado del panel adversarial de 51 agentes (12 guidelines × audit + verify). **21 riesgos
confirmados** (7 blockers, 2 high, resto medium/low), 18 descartados como falso positivo.
**Nada se submite hasta que todos los blockers + high estén en verde.**

Leyenda: ✅ arreglado · 🟡 en curso/gated · ⏳ pendiente · 👤 acción del founder

---

## BLOCKERS

| # | Riesgo (guideline) | Evidencia | Estado |
|---|---|---|---|
| B1 | **`s-pro-signup` muestra "20,00 €" + botón "Pagar 20,00 €" en iOS** (3.1.1/3.1.3b). `dmApplyIosNativeUI` no oculta la pantalla de compra de Pro, solo los packs de tokens. | public/index.html L10551-10574; función L14094-14106 no cubre `#ps-pay-btn`/precios | 🟡 **se resuelve al cablear IAP** (la pantalla pasa a precio+compra StoreKit). Hasta entonces NO submitar. Alternativa interina: gate iOS que oculte precios+CTA respetando la promo gratis |
| B2 | **`s-pro-activate` muestra "20,00 €" + "Continuar al pago" en iOS** (3.1.1). Con promo OFF, `_paApplyPromoUI(false)` restaura precio y CTA sin guard iOS. | public/index.html L10597/10621/10630 | 🟡 igual que B1 (parte de la integración IAP) |
| B3-B5 | **4.2 Minimum Functionality**: binario = WKWebView puro, **0 plugins nativos cableados** (IAP/push/picker son TODOs). Rechazo 4.2 de manual. | mobile/package.json solo @capacitor/cli\|core\|ios; AppDelegate stub; sin .entitlements | 🟡 **es el grueso de Fase 2**: cablear ≥2-3 capacidades nativas reales (IAP RevenueCat + push @capacitor/push-notifications + picker @capacitor/camera) y documentarlas en Notes for Review |
| B6 | **Notes for Review afirman "Restore Purchases" + "IAP exclusivo"** que NO existen → rechazo 2.1/2.3.1 | APPSTORE_ASSETS.md §2 | ✅ marcado pre-submit gate en ASSETS (no usar hasta que IAP+Restore existan). Se cumplirá al cablear IAP |
| B7 | **Falta `NSCameraUsageDescription`** → crash + rechazo privacidad (input vídeo/cámara en anamnesis) | Info.plist sin la string; input L9641 no gateado | ✅ **AÑADIDA** 2026-06-08 (cámara + micro + fototeca) |

## HIGH

| # | Riesgo | Estado |
|---|---|---|
| H8 | Faltan usage strings de foto/micro (mismo origen que B7) | ✅ AÑADIDAS (NSCamera + NSMicrophone + NSPhotoLibrary) |
| H9 | **Cuenta demo con password `[FOUNDER FILLS THIS IN]` y sin crear** → rechazo 2.1 automático | 👤 **founder**: crear cuenta `appstore-review@thedogsmind.net` (100 tokens + professional + perro Buddy), login end-to-end, y pegar password real en Notes (ASSETS §1) |

## MEDIUM

| # | Riesgo | Estado |
|---|---|---|
| M10 | Card Pro muestra "20€/año" + "Pago único anual" + CTA en iOS | 🟡 se resuelve con IAP (precio StoreKit) + fix copy |
| M11 | Copy "Pago único, no se renueva" contradice suscripción auto-renovable (3.1.2). **OJO: es correcto para web (Stripe). El fix iOS debe ir gateado por `dmIsIosNative()`, NO global.** | 🟡 al cablear IAP |
| M12 | Faltan links Términos/Privacidad en el paywall + cláusula de suscripción auto-renovable en terms.html (3.1.2) | 🟡 al cablear IAP (el paywall RevenueCat los lleva) + añadir cláusula EULA |
| M13 | **iPad activado (`device family "1,2"`) contradice D-006 iPhone-only** → fuerza review en iPad de una UI no adaptada | ✅ **CORREGIDO** 2026-06-08: device family `"1"` + orientaciones iPad eliminadas |
| M14 | Chat de texto libre sin guardrail/ámbito visible (4.7) | ⏳ añadir disclaimer de ámbito en UI + guardrail ligero + finalizar Notes 4.7 |
| M15-M16 | Usage strings de vídeo/foto (camera/mic) | ✅ cubierto por B7/H8 |

## LOW

| # | Riesgo | Estado |
|---|---|---|
| L17 | Sin botón "reportar respuesta" en el chat IA (4.7.5) | ⏳ añadir "Reportar respuesta" → info@thedogsmind.net (aditivo, barato) |
| L18 | Rating 4+ defendible pero al límite (depende de que el guardrail del chat exista) | ⏳ se cubre con M14 |

---

## Resumen de acción

- ✅ **Arreglado hoy (autónomo, staged, sin deploy):** usage strings Info.plist (B7/H8), iPad→iPhone-only (M13), Notes gate (B6).
- 🟡 **Se resuelve al cablear IAP (Fase 2, el gran bloque):** B1, B2, B3-B5, M10, M11, M12 → ver `APPSTORE_IAP_PLAN.md`.
- ⏳ **Pulido pre-submit (aditivo):** M14 (guardrail/ámbito chat), L17 (reportar respuesta).
- 👤 **Founder:** H9 (crear cuenta demo + login + password en Notes).

**Falsos positivos notables descartados (18):** p.ej. "card Pro lleva directo a Stripe" (refutado: el guard fail-closed + promo lo neutraliza); "NSPhotoLibrary imprescindible para el picker" (PHPicker no lo exige); varios encuadres de severidad corregidos por los verificadores.

Related: `APPSTORE_IAP_PLAN.md`, `APPSTORE_COMPLIANCE.md`, `APPSTORE_ASSETS.md`, `APPSTORE_DECISIONS.md`.
