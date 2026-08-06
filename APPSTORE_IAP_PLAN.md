# Dogs Mind — Plan de integración IAP (RevenueCat) · iOS

Plan de ejecución para cablear las compras in-app en iOS (guideline 3.1.1). Pieza grande de
Fase 2. **Capa elegida: RevenueCat** (`@revenuecat/purchases-capacitor`, D-007). El binario iOS
ya oculta Stripe (D-002, `IS_IOS_NATIVE`); aquí se conecta el IAP en esos mismos puntos.

Estado: **planificado, sin código aún.** Creado 2026-06-08 mientras corre el audit anti-rechazo.

## Prerrequisitos (gates antes de ejecutar)

| # | Gate | Quién | Estado |
|---|---|---|---|
| 1 | Paid Applications Agreement **Activo** | Apple (~24h tras firmar) | 🟡 firmado 2026-06-08, "Procesando" |
| 2 | Cuenta bancaria verificada | Apple | 🟡 Revolut "En proceso" |
| 3 | Productos IAP creados en App Store Connect | founder/agente | ⏳ (specs en `APPSTORE_ASSETS.md` §6) |
| 4 | Cuenta RevenueCat + API keys (público iOS + secreto) | founder | ⏳ |
| 5 | Productos mapeados en RevenueCat (entitlement "pro" + offerings) | agente | ⏳ |

⚠️ Sin el agreement Activo (gate 1) los productos no pasan a "Ready to Submit" y el IAP sandbox no cobra.

## Catálogo (espejo de `APPSTORE_ASSETS.md` §6 / `APPSTORE_DECISIONS.md`)

| Producto | Tipo | Precio | Product ID |
|---|---|---|---|
| 5 tokens | Consumable | €4,99 | `net.thedogsmind.tokens.5` |
| 20 tokens | Consumable | €16,00 | `net.thedogsmind.tokens.20` |
| 60 tokens | Consumable | €42,00 | `net.thedogsmind.tokens.60` |
| Professional | Auto-Renewable Sub (1 año) | €20,00 | `net.thedogsmind.pro.yearly` (grupo `net.thedogsmind.pro`) |

RevenueCat: entitlement **`pro`** ligado a `net.thedogsmind.pro.yearly`. Tokens = consumibles
(no dan entitlement; se acreditan vía backend al validar la compra).

## Arquitectura de la integración

```
iOS app (Capacitor)
  └─ @revenuecat/purchases-capacitor  (Purchases.configure con API key pública iOS)
       ├─ comprar tokens (consumible)  → onPurchase → POST backend /iap/validate → acreditar tokens
       ├─ comprar Pro (sub)            → entitlement "pro" activo → POST backend → account_type='professional'
       └─ Restore Purchases (botón obligatorio 3.1.1)
  Backend (FastAPI)
       ├─ POST /iap/validate         (valida con RevenueCat REST o recibo; idempotente)
       └─ webhook App Store Server Notifications V2  (paralelo al de Stripe; renovaciones/refunds)
```

Fuente de verdad de entitlement Pro = backend (`account_type`). Antes de ofrecer el IAP de Pro,
comprobar si ya es Pro (p.ej. activado en web) para NO cobrar dos veces.

## Puntos de anclaje en el código (YA marcados)

En `frontend/index.html`, los 3 guards `IS_IOS_NATIVE` llevan comentario `TODO Fase 2 (IAP)`:
- **`recargar(pack)`** (~L14659) — compra de packs de tokens → aquí `Purchases.purchaseStoreProduct(tokens.N)`.
- **`psSubmit`** rama Stripe (~L12906) — compra Pro (con datos empresa) → aquí compra de `pro.yearly`.
- **`paGoToCheckout`** (~L13086) — compra Pro directa → aquí compra de `pro.yearly`.
- Las ramas **promo/cortesía** van ANTES de los guards → se mantienen (no son Stripe).
- **Restore Purchases**: añadir botón en `s-tokens` (obligatorio 3.1.1) → `Purchases.restorePurchases()`.

## Pasos de ejecución (cuando se abran los gates)

1. **App Store Connect:** crear los 4 productos (specs `APPSTORE_ASSETS.md` §6) + copy localizado ES/EN + screenshot de revisión por producto (vale captura de la pantalla de compra). Para Pro: copy de suscripción (3.1.2).
2. **RevenueCat:** crear app iOS, pegar el shared secret de App Store Connect, mapear los 4 productos, crear entitlement `pro` + un offering por defecto con los packages.
3. **Plugin:** `npm i @revenuecat/purchases-capacitor` en `mobile/`, `npx cap sync ios`.
4. **Frontend (additive, gated por `IS_IOS_NATIVE`, INERTE en web):** `Purchases.configure` al iniciar en iOS; implementar compra en los 3 anclajes; botón Restore; manejar estados (loading, éxito, cancelado, error).
5. **Backend:** endpoint de validación idempotente + webhook ASSN V2 (acreditar tokens / set professional / manejar refund-revoke). Paralelo al de Stripe (web intacto).
6. **Pruebas sandbox:** usuario sandbox de App Store; comprar cada pack + Pro; verificar acreditación, Restore, y que la web sigue con Stripe.
7. **Code-review por agentes** de toda la integración (riesgo de bug alto) + verificación de doble cobro y de idempotencia.

## Coordinación con la promo

`PRO_PROMO_FREE` sigue ACTIVA hasta el submit. Al publicar: apagar promo **simultáneo** a tener el IAP de Pro funcionando (si no, usuarios iOS sin vía de compra Pro). Web Stripe NUNCA se corta.

## Riesgos / cautela
- Idempotencia en la acreditación de tokens (no acreditar dos veces por reintentos/webhook+validate).
- Doble cobro Pro web vs iOS → chequear entitlement backend antes de ofrecer compra.
- Seguir AL PIE DE LA LETRA la doc de RevenueCat para iOS (productos "Ready to Submit" antes del build).
- Todo el código iOS additive y fail-closed; cero regresión en web/Android.

Related: `APPSTORE_ASSETS.md`, `APPSTORE_DECISIONS.md` (D-002/D-003/D-007), `APPSTORE_TRACKING.md`, `APPSTORE_COMPLIANCE.md` §3.1.1.
