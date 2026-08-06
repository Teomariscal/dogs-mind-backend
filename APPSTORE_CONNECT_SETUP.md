# Dogs Mind — Guía de ejecución App Store Connect (Fase 1)

Pasos exactos para configurar App Store Connect + Developer Portal tras pagar la cuenta
(D-001 ✅ 2026-06-08, Apple ID `teomariscald@gmail.com`, Enrollment `6ZYX4DM4WS`).

**Todo esto son clics en la web de Apple → los hace el founder** (el agente no entra a la
cuenta). Cada campo va con su valor exacto: copiar y pegar. Orden importa (hay dependencias).
Valores base en `APPSTORE_ASSETS.md`. Decisiones en `APPSTORE_DECISIONS.md`.

Leyenda: ✅ hecho · ⏳ pendiente · 🔒 bloqueado por dependencia.

---

## ORDEN DE EJECUCIÓN (respetar dependencias)

```
1. Paid Applications Agreement (+ tax + banking)   ──► gate de TODOS los IAP
2. Registrar Bundle ID  net.thedogsmind.app        ──► gate del App record y del build
3. Crear App record (reserva el nombre)            ──► gate de los IAP (se crean dentro)
4. Crear productos IAP (3 tokens + Pro)            ──► necesita 1, 2, 3
5. (Después, con Xcode) APNs Key para push (D-009)
```

---

## PASO 1 · Paid Applications Agreement  ⏳  (LO PRIMERO — bloquea los IAP)

App Store Connect → **Business** (antes "Agreements, Tax, and Banking").
- Aceptar/firmar el **Paid Applications Agreement**.
- Rellenar **Tax** (datos fiscales España, persona física Teodoro Mariscal Diaz).
- Rellenar **Banking** (cuenta donde Apple paga los ingresos).
- ⚠️ **Sin este acuerdo "Active", los IAP no se pueden poner "Ready to Submit" ni vender.**
  Es el cuello de botella más común. Hacerlo ya.

---

## PASO 2 · Registrar el Bundle ID  ⏳

Developer Portal → **Certificates, Identifiers & Profiles** → **Identifiers** → botón **+**.
- Tipo: **App IDs** → **App**.
- **Description:** `The Dogs Mind`
- **Bundle ID:** **Explicit** → `net.thedogsmind.app`   ← INMUTABLE para siempre (D-005)
- **Capabilities** a marcar:
  - **In-App Purchase** (suele venir activada por defecto) — necesaria (3.1.1).
  - **Push Notifications** — para los recordatorios del seguimiento diario (D-009).
  - (NO marcar Sign in with Apple — no se usa, 4.8(1).)
- Register.

---

## PASO 3 · Crear el App record (reserva el nombre)  ⏳

App Store Connect → **Apps** → **+** → **New App**.
- **Platforms:** iOS
- **Name:** `The Dogs' Mind`   ← apóstrofo tipográfico U+2019 ('). first-come, asegurarlo.
- **Primary Language:** **Spanish (Spain)**  (decisión agente, vetoable: founder y mercado
  principal = España; se añade English (U.S.) como localización después).
- **Bundle ID:** seleccionar `net.thedogsmind.app` (el del paso 2).
- **SKU:** `thedogsmind-ios-001`  (identificador interno, no visible al público, libre).
- **User Access:** Full Access.
- Create.

---

## PASO 4 · Crear los productos IAP  ⏳  (dentro del App record)

Precios: usar el **price point de Apple exacto o más cercano** a estos importes (la web cobra
estos; se absorbe la comisión Apple — D catálogo). Si Apple no tiene el importe exacto, elegir
el inmediato. Cada producto necesita **Display Name + Description localizados (ES + EN)** y un
**screenshot de revisión** (vale una captura de la pantalla de compra de la app; se sube cuando
tengamos el build, ver nota al final).

### 4A · Packs de tokens — tipo **Consumable**

App → **Monetization** → **In-App Purchases** → **+**  (×3, tipo Consumable):

| Reference Name (interno) | Product ID | Precio objetivo |
|---|---|---|
| Tokens 5  | `net.thedogsmind.tokens.5`  | €4,99 |
| Tokens 20 | `net.thedogsmind.tokens.20` | €16,00 |
| Tokens 60 | `net.thedogsmind.tokens.60` | €42,00 |

Localización (Display Name ≤30 car · Description ≤45 car):

- **Tokens 5**
  - ES — Display: `5 tokens` · Desc: `Tokens para análisis de conducta y planes.`
  - EN — Display: `5 tokens` · Desc: `Tokens for behavior analyses and plans.`
- **Tokens 20**
  - ES — Display: `20 tokens` · Desc: `Tokens para análisis de conducta y planes.`
  - EN — Display: `20 tokens` · Desc: `Tokens for behavior analyses and plans.`
- **Tokens 60**
  - ES — Display: `60 tokens` · Desc: `Tokens para análisis de conducta y planes.`
  - EN — Display: `60 tokens` · Desc: `Tokens for behavior analyses and plans.`

### 4B · Pro — tipo **Auto-Renewable Subscription** (D-003)

App → **Monetization** → **Subscriptions** → crear **Subscription Group** primero:
- **Subscription Group Reference Name:** `The Dogs Mind Pro`
- **Group Display Name (localizado):** ES `The Dogs' Mind Pro` · EN `The Dogs' Mind Pro`

Dentro del grupo, crear la suscripción:
- **Reference Name:** `Professional (annual)`
- **Product ID:** `net.thedogsmind.pro.yearly`
- **Subscription Duration:** **1 Year**
- **Precio objetivo:** €20,00/año (price point exacto o más cercano)
- Localización (ES + EN):
  - ES — Display: `Profesional` · Desc: `Acceso a módulos avanzados y entrenamiento.`
  - EN — Display: `Professional` · Desc: `Access to advanced modules and training.`
- ⚠️ **Disclosure 3.1.2:** el copy obligatorio de la suscripción (precio, "se renueva
  automáticamente salvo cancelación", links a Términos + Privacidad) va **en el binario iOS,
  junto al botón de compra**. Eso lo cabla el agente en el código (Fase 2 IAP), no en ASC.

### Nota sobre el screenshot de revisión de cada IAP
Apple exige una captura por producto para revisar el IAP. No hace falta que sea perfecta:
sirve una captura de la pantalla "Mis tokens" / pantalla Pro de la app. Se sube cuando
tengamos el build corriendo (tras instalar Xcode). Hasta entonces los IAP quedan en
"Missing Metadata" — es normal, no bloquea crearlos.

---

## PASO 5 · APNs Key para Push (D-009) — más adelante, con Xcode
Developer Portal → Keys → **+** → marcar **Apple Push Notifications service (APNs)** →
descargar el `.p8` (SOLO se descarga una vez; guardarlo en
`~/Documents/Claude/Projects/Dogs Mind credentials/`). Se conecta en Fase 2.

---

## Qué hace el agente en paralelo (sin login Apple)
- Copy y specs de todo lo de arriba (este doc) ✅.
- Preparar la integración RevenueCat en el código (puntos `TODO Fase 2 (IAP)` ya marcados en
  `frontend/index.html`) en cuanto haya: (a) productos creados, (b) RevenueCat API key.
- `npx cap sync ios` + montar el build en cuanto el founder instale **Xcode**.

Related: `APPSTORE_ASSETS.md`, `APPSTORE_DECISIONS.md`, `APPSTORE_TRACKING.md`, `APPSTORE_COMPLIANCE.md`.
