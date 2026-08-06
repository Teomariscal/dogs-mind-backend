# Dogs Mind — App Store Submission Assets Pack

Materiales de envío para App Store Connect. **Documento de trabajo, cero impacto en prod.**
Se rellena/copia en App Store Connect cuando haya cuenta Apple paga (D-001). Fuente de
verdad de compliance: `APPSTORE_COMPLIANCE.md`. Decisiones: `APPSTORE_DECISIONS.md`.

Creado 2026-06-06. Leyenda: ✅ listo para copiar · 📋 requiere acción del founder · `[VERIFICAR]` confirmar en App Store Connect.

---

## 0. DATOS BASE (constantes del envío)

| Campo | Valor |
|---|---|
| App Name (público) | **The Dogs' Mind** |
| Subtitle | AI for Canine Behavior |
| Bundle ID | `net.thedogsmind.app` (INMUTABLE, D-005) |
| Primary Category | Lifestyle (alt: Education) `[VERIFICAR]` |
| Secondary Category | Education |
| Age Rating | **4+** (justificación §4 abajo) |
| Developer / Seller | Teodoro Mariscal Diaz (persona física, España) |
| Support URL | https://thedogsmind.net |
| Support email | info@thedogsmind.net |
| Privacy email | privacy@thedogsmind.net |
| Marketing URL (opcional) | https://thedogsmind.net |
| Privacy Policy URL | https://thedogsmind.net/privacy.html |
| Terms (EULA) URL | https://thedogsmind.net/terms.html |
| Idiomas | Español (ES) + English (EN) |
| Device Family | iPhone-only (D-006) |
| Copyright | © 2026 Teodoro Mariscal Diaz |

---

## 1. CUENTA DEMO PARA EL REVISOR (guideline 2.1) 📋

El revisor de Apple necesita una cuenta funcional con datos de ejemplo. **El founder la crea**
(es alta de usuario real en prod; el agente no crea cuentas con credenciales).

**Spec de la cuenta a crear:**
- Email: `appstore-review@thedogsmind.net` (alias forward → buzón que el founder controle)
- Password: (el founder elige uno robusto y lo pone en las Notes for Review)
- Estado precargado:
  - **Saldo: 100 tokens** (suficiente para que el revisor pruebe varios análisis sin pagar).
  - **account_type: `professional`** (Pro activo) → así el revisor ve TODAS las features
    (consulta ABC + Entrenamiento Específico + seguimiento diario) sin tener que comprar.
  - **1 perro de ejemplo** ya creado: nombre **Buddy**, border collie, con una consulta ABC
    ya analizada y guardada → el revisor ve la app "con vida", no vacía (cumple 2.1 "sin
    placeholders, build completo").
- ⚠️ Si la promo `PRO_PROMO_FREE` está activa al crear la cuenta, Pro se activa gratis; si ya
  está apagada para el submit, marcar `account_type='professional'` a mano en la DB para la
  cuenta demo (NO debe depender de una compra para que el revisor vea todo).

---

## 2. NOTES FOR REVIEW (App Review Information) ✅

> ✅ **GATE LEVANTADO (2026-06-13):** IAP de RevenueCat + botón Restore implementados y el IAP de
> tokens **probado end-to-end en sandbox** (compra → webhook → tokens acreditados). Estas Notes ya
> describen features REALES → listas para pegar. (Suscripción €19,99/año verificada con precio en ASC.)

> Apple reviewers read English. Texto en inglés, listo para pegar en el campo "Notes" de
> App Store Connect. Cubre 2.1, 2.3.1, 3.1.1, 4.7, 5.1.2(i). **NO es público** (solo lo ve
> el equipo de App Review).

```
DEMO ACCOUNT
Email: appstore-review@thedogsmind.net
Password: Azizam25
This account has Professional access enabled and 100 tokens pre-loaded, so you can
test every feature (behavior analysis, specific-training module, daily follow-up,
AI assistants) without making a purchase.

WHAT THE APP DOES
The Dogs' Mind is a tool for dog owners and canine-behavior professionals. The user
describes their dog's behavior (an "anamnesis"); the app produces a structured,
science-based behavior analysis (ABC functional analysis) and a LIMA-compliant
(Least Intrusive, Minimally Aversive) intervention plan, plus an optional daily
follow-up coach and a specific-training module. Analyses are generated using
Anthropic's Claude AI.

TOKENS & PURCHASES (Guideline 3.1.1)
- Analyses are paid for with "tokens" (consumable In-App Purchases).
- Token packs: 5 (EUR 4.99), 20 (EUR 16.00), 60 (EUR 42.00).
- "Professional" is an auto-renewable subscription (EUR 19.99/year) that unlocks the
  advanced modules and co-branding.
- All purchases inside the iOS app use Apple In-App Purchase exclusively (RevenueCat).
  There is NO external payment path, link, or price reference anywhere in the iOS
  build. (The website sells separately via its own processor; the iOS binary hides it.)
- A "Restore Purchases" button is available in the Tokens screen.

AI ASSISTANTS & AGE RATING (Guideline 4.7 / generative AI)
The app includes AI assistants ("Aigents") and a behavior coach, all powered by
Anthropic's Claude with constrained system prompts centred on dogs and canine care.
AI chat responses include a "Report" control so users can flag inappropriate content
for review. Because the assistants use generative AI with free-text input, the app is
rated 17+.

AI / DATA SHARING CONSENT (Guideline 5.1.2(i))
The text the user writes about their dog is sent to Anthropic (Claude AI, USA) to
generate the analysis. The user gives explicit consent at sign-up (mandatory
checkbox naming Anthropic) and again, inline, at the point of each submission. The
full list of third parties is in the in-app privacy policy and at
https://thedogsmind.net/privacy.html

COURTESY ACCESS CODE
There is an internal courtesy code that grants Professional access plus 10 starter
tokens to selected partner professionals. It is comp (never sold) and is not required
to use any feature. The demo account above does not need it.

ACCOUNT DELETION (Guideline 5.1.1(v))
In-app account deletion is available at: Tokens / account screen -> "Delete my account".

CONTACT
Support: info@thedogsmind.net  |  Privacy: privacy@thedogsmind.net
```

✅ **Password de la cuenta demo ya rellenada** (`Azizam25`). Cuenta verificada (login OK, Pro, 100 tokens).
⏳ Opcional (2.1 "app con vida"): crear un perro de ejemplo en la cuenta demo. Hoy NO existe "Buddy"
   (se quitó la afirmación de las Notes para no prometer algo ausente). El revisor puede crear uno.

---

## 3. APP STORE DESCRIPTION (público — user-facing)

> **Regla dura (memoria)**: la palabra "Bocalán" NUNCA en assets públicos / in-app. Aquí
> NO aparece (solo en Notes for Review, que son privadas). Cero emojis Unicode.

### 3.1 Promotional Text (≤170 car., editable sin re-review)

**ES:**
```
Analisis de conducta canina con IA, basado en ciencia del comportamiento y criterio LIMA. Entiende a tu perro y actua con un plan claro.
```
**EN:**
```
AI-powered canine behavior analysis, grounded in behavior science and LIMA ethics. Understand your dog and act with a clear, structured plan.
```

### 3.2 Keywords (≤100 car., separadas por coma, sin espacios)

**ES:** `perro,conducta,adiestramiento,comportamiento canino,etologia,LIMA,refuerzo positivo,mascota,educacion`
**EN:** `dog,behavior,training,canine,ethology,positive reinforcement,LIMA,pet,dog trainer,puppy`

`[VERIFICAR]` longitud ≤100 al pegar (App Store Connect cuenta caracteres incl. comas).

### 3.3 Description ES (≤4000 car.) ✅

```
The Dogs' Mind convierte lo que observas en tu perro en un analisis de conducta claro y accionable.

Describe el comportamiento de tu perro (que pasa, cuando y en que contexto) y la app genera:

- Un analisis funcional ABC (Antecedente - Conducta - Consecuencia) del problema, con criterio profesional.
- Un plan de intervencion basado en LIMA (Least Intrusive, Minimally Aversive): siempre el metodo menos intrusivo y mas respetuoso, sin coercion ni castigo.
- Un seguimiento diario opcional que te guia paso a paso y se adapta a como evoluciona tu perro.
- Un modulo de Entrenamiento Especifico para objetivos concretos.

Pensado tanto para tutores que quieren entender de verdad a su perro como para profesionales del comportamiento canino que buscan una herramienta de apoyo rapida y rigurosa.

COMO FUNCIONA
1. Crea la ficha de tu perro.
2. Escribe la anamnesis (la historia del comportamiento).
3. Recibe el analisis y el plan.
4. Sigue el acompañamiento diario y ajusta.

CIENCIA, NO TRUCOS
Las respuestas se apoyan en literatura del comportamiento animal y en un enfoque etico LIMA. No usamos ni recomendamos collares de castigo, descargas, ni metodos aversivos.

IMPORTANTE
The Dogs' Mind es una herramienta de apoyo y no sustituye la valoracion de un veterinario o de un profesional del comportamiento presencial, especialmente ante problemas de salud o conductas de agresion.

PRIVACIDAD
El texto que escribes sobre tu perro se procesa con IA (Anthropic / Claude) para generar el analisis, con tu consentimiento explicito. Consulta la politica de privacidad: https://thedogsmind.net/privacy.html

COMPRAS
Los analisis se pagan con tokens (compras dentro de la app). "Professional" es una suscripcion anual que desbloquea los modulos avanzados.
```

### 3.4 Description EN (≤4000 car.) ✅

```
The Dogs' Mind turns what you see in your dog into a clear, actionable behavior analysis.

Describe your dog's behavior (what happens, when, and in what context) and the app generates:

- An ABC functional analysis (Antecedent - Behavior - Consequence) of the problem, with professional rigor.
- An intervention plan based on LIMA (Least Intrusive, Minimally Aversive): always the least intrusive, most respectful method, with no coercion or punishment.
- An optional daily follow-up that guides you step by step and adapts as your dog progresses.
- A Specific Training module for concrete goals.

Built both for owners who genuinely want to understand their dog and for canine-behavior professionals who want a fast, rigorous support tool.

HOW IT WORKS
1. Create your dog's profile.
2. Write the anamnesis (the behavior history).
3. Get the analysis and the plan.
4. Follow the daily coaching and adjust.

SCIENCE, NOT TRICKS
Answers are grounded in animal-behavior literature and a LIMA ethical framework. We never use or recommend shock collars, prong collars, or aversive methods.

IMPORTANT
The Dogs' Mind is a support tool and does not replace an in-person veterinarian or behavior professional, especially for health issues or aggression.

PRIVACY
The text you write about your dog is processed with AI (Anthropic / Claude) to generate the analysis, with your explicit consent. See the privacy policy: https://thedogsmind.net/privacy.html

PURCHASES
Analyses are paid for with tokens (in-app purchases). "Professional" is an annual subscription that unlocks the advanced modules.
```

### 3.5 What's New (v1.0) ✅

**ES:** `Primera version de The Dogs' Mind para iPhone. Analisis de conducta canina con IA, plan LIMA, seguimiento diario y entrenamiento especifico.`
**EN:** `First version of The Dogs' Mind for iPhone. AI canine behavior analysis, LIMA plan, daily follow-up, and specific training.`

---

## 4. AGE RATING — 17+ (decisión founder 2026-06-13) ✅

Declarar **17+** (no 4+). Razón: la app incluye **IA generativa de texto libre** (asistentes
"Aigents" + coach). Apple exige rating alto para chat IA abierto, independientemente de los
guardrails. El founder está conforme con 17+ (público objetivo = profesionales/adultos:
veterinarios, psicólogos, propietarios adultos). En el cuestionario de edad de ASC, responder
**honestamente** sobre el chat IA / contenido generado por el usuario (eso computa el 17+).
Mitigaciones implementadas: **botón "Reportar"** en cada respuesta IA (moderación, `/avatar/report`)
+ system prompts acotados a conducta/cuidado canino. Ver [[dogs-mind-appstore-age-rating]].
- Sin violencia, contenido sexual explícito, juego ni sustancias (esas categorías van "None").
- El 17+ viene del eje IA generativa / UGC, no de contenido ofensivo.
- NO es Kids Category.

---

## 5. APP PRIVACY — NUTRITION LABELS (App Store Connect → App Privacy) ✅

Mapeo de datos para el cuestionario de privacidad. Base: privacy.html (9 terceros) +
`APPSTORE_COMPLIANCE.md` §5.1.x.

**¿Se recogen datos?** Sí.
**¿Se usan datos para rastrearte (tracking cross-app/brokers)?** **NO** → declarar
"Data Not Used to Track You" (no hay ad networks ni data brokers; Plausible es analitica
anonima sin cookies).

| Categoría Apple | Dato | Propósito | ¿Vinculado a identidad? | ¿Tracking? |
|---|---|---|---|---|
| Contact Info | Email Address | App Functionality | Sí | No |
| Contact Info | Phone Number (opcional) | App Functionality | Sí | No |
| User Content | Other User Content (texto de anamnesis + foto/video opcional del perro) | App Functionality | Sí | No |
| Identifiers | User ID (cuenta) | App Functionality | Sí | No |
| Purchases | Purchase History (IAP) | App Functionality | Sí | No |
| Usage Data | Product Interaction (analitica Plausible, anonima) | Analytics | No | No |

Notas:
- **User Content** es la categoría clave: el texto del perro se envía a Anthropic (declararlo
  como compartido con tercero para "App Functionality"). NO se usa para publicidad ni tracking.
- NO declarar: Location, Contacts, Health, Financial Info, Browsing History, Sensitive Info,
  Search History → la app no los recoge (`APPSTORE_COMPLIANCE.md` §5.1.1(iii) data minimization).
- `[VERIFICAR]` al rellenar: si algún SDK nativo (RevenueCat) recoge un identificador propio,
  declararlo en Purchases/Identifiers. RevenueCat usa un App User ID → cubierto por "User ID".

---

## 6. PRODUCTOS IAP A CREAR (App Store Connect) ✅

(Espejo del catálogo de `APPSTORE_DECISIONS.md`. Product IDs INMUTABLES.)

| Producto | Tipo | Precio | Product ID | Grupo |
|---|---|---|---|---|
| 5 tokens | Consumable | €4,99 | `net.thedogsmind.tokens.5` | — |
| 20 tokens | Consumable | €16,00 | `net.thedogsmind.tokens.20` | — |
| 60 tokens | Consumable | €42,00 | `net.thedogsmind.tokens.60` | — |
| Professional | Auto-Renewable Subscription | €20,00/año | `net.thedogsmind.pro.yearly` | `net.thedogsmind.pro` |

Para cada producto: nombre + descripción localizados (ES + EN), price point Apple más cercano,
y para Pro el **copy obligatorio de suscripción** (precio, periodo, "se renueva automáticamente
salvo cancelación", links Términos + Privacidad) junto al botón (3.1.2, D-003).

---

## 7. SCREENSHOTS (2.3.3) 📋 — requiere app corriendo en iOS

- iPhone 6.9" (1320×2868), mínimo 3, máximo 10. iPhone-only (D-006) → con este set basta.
- Mostrar la app EN USO (no splash/login): (1) análisis ABC resultado, (2) plan LIMA / pantalla
  Entrenamiento Específico (estética vibrant), (3) seguimiento diario, (4) ficha del perro.
- Priorizar pantallas vibrant emerald en las 3 primeras (más premium).
- Bloqueado por: Xcode instalado + build corriendo en simulador/iPhone 14.

---

## 8. CHECKLIST DE METADATA AL SUBMITAR

- [ ] App Name reservado: "The Dogs' Mind"
- [ ] Subtitle, Promotional Text, Keywords (ES+EN) pegados
- [ ] Description (ES+EN) pegada
- [ ] What's New v1.0 (ES+EN)
- [ ] Privacy Policy URL + Terms URL en metadata
- [ ] App Privacy nutrition labels rellenadas (§5) + "Data Not Used to Track You"
- [ ] Age rating 4+
- [ ] Productos IAP creados y "Ready to Submit" (§6)
- [ ] Cuenta demo creada + password en Notes for Review (§1, §2)
- [ ] Notes for Review pegadas (§2)
- [ ] Screenshots 6.9" subidos (§7)
- [ ] Promo `PRO_PROMO_FREE` apagada en Railway SIMULTÁNEO con el submit (ver decisiones)
- [ ] Sin referencias a Google Play / Android en la UI iOS (2.3.10)

---

Related: `APPSTORE_COMPLIANCE.md`, `APPSTORE_DECISIONS.md`, `APPSTORE_TRACKING.md`.
```
