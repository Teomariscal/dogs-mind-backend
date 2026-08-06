# Dogs Mind — App Store Decision Log

Registro de decisiones arquitectónicas y operativas para la publicación en App Store.
Cada entrada: fecha · decisión · estado · razón · implicaciones. **Regla dura del founder:
guardar TODO siempre para próximas sesiones.** Este doc es la fuente de verdad de "qué
decidimos y por qué" para que cualquier sesión futura retome sin perder contexto.

**Objetivo único e innegociable:** app publicada y funcionando en App Store. Las comisiones
de Apple NO son criterio de decisión. No se ofrecen alternativas a "subir a App Store".

**REGLA DURA (founder 2026-06-09) — MÁXIMOS RECURSOS ANTI-RECHAZO:** en este proyecto de
launch, **el coste NUNCA va por encima de la efectividad**. Para todo lo anti-rechazo usar los
**máximos recursos al alcance**: modelos más potentes disponibles (Fable 5 cuando esté en el
selector; mientras, Opus), paneles multi-agente grandes, varias pasadas de verificación
adversarial. No escatimar en tokens/agentes cuando reduzca el riesgo de rechazo. Ver el
**gate pre-launch** en `APPSTORE_PRELAUNCH_GATE.md` (se ejecuta antes de CADA intento de submit).

---

## INPUTS DEL FOUNDER (los 7 críticos para arrancar Capacitor + IAP)

| # | Input | Estado | Respuesta / valor |
|---|---|---|---|
| 1 | Apple Developer Program | ✅ **RECIBIDO 2026-06-02** | Tiene cuenta, **NO pagada aún**. Pagará al llegar a Madrid el **domingo** (o mañana si algo lo bloquea). Ver D-001. |
| 2 | Bundle ID | 🟡 **Recomendado, falta OK final** | **`net.thedogsmind.app`** (corrige `com.` → coincide con dominio real `.net`). Ver D-005. INMUTABLE para siempre. |
| 3 | Versión de Xcode | ✅ **RECIBIDO 2026-06-02** | macOS **Tahoe** (macOS 26). No tiene Xcode aún → descargará el último desde Mac App Store. Tahoe soporta el Xcode más reciente. |
| 4 | Hardware iOS | ✅ **RECIBIDO 2026-06-02** | **iPhone 14** (device físico para test) + MacBook Pro + MacBook Air + iMac. Dispuesto a comprar iPad. **→ NO hace falta iPad, ver D-006.** Falta confirmar chip/RAM del Mac que dedicará a Xcode. |
| 5 | IAP: RevenueCat vs StoreKit2 | ✅ **RECIBIDO 2026-06-02** | **RevenueCat** (founder). Ver D-007. |
| 6 | Plan de push notifications | ✅ **DECIDIDO (yo, regla #8)** | Nativo `@capacitor/push-notifications` + APNs, recordatorios daily-followup, opt-in. Ver D-009. |
| 7 | Capacitor Live Updates: sí/no | ✅ **DECIDIDO (yo, regla #8)** | **NO** en v1 (riesgo 2.5.2). Ver D-008. |

**Inputs cerrados:** #1 (cuenta, paga domingo), #3 (macOS Tahoe, descargará Xcode), #4
(iPhone 14 + Macs, sin iPad), #5 (RevenueCat). **#2** Bundle ID recomendado y a falta de
veto. **#6/#7** decididos por mí aplicando la regla #8.

**Único dato menor que aún ayudaría (no bloqueante):** chip + RAM del Mac que dedicará a
Xcode (para confirmar que corre el Xcode más reciente con holgura). Recomendación por
defecto: usar el **MacBook Pro** si es Apple Silicon (M1+) con ≥16 GB RAM y ≥60 GB libres.

---

## DECISIONES

### D-001 · Pago de la cuenta Apple Developer → ✅ PAGADO 2026-06-08
- **✅ PAGADO 2026-06-08.** Membership Apple Developer Program activada (€99/año).
- **Team ID: `XW9545NR8J`** · Titular legal completo: **Teodoro Francisco Mariscal Diaz**.
  ⚠️ Sin tarjeta en Apple Online Store → la membresía NO auto-renovará hasta añadir una
  ("Agregar tarjeta" en Account). Recomendado añadirla (auto-renew ON).
- **✅ CUENTA CONFIRMADA 2026-06-08:** la cuenta Apple Developer está en el Apple ID
  **`teomariscald@gmail.com`** (el Gmail con "d", el de infra Dogs Mind: Netlify/Railway),
  NO en `teomariscal@me.com`. Titular **TEODORO Mariscal**. **Enrollment ID `6ZYX4DM4WS`**.
  Membership: Apple Developer Program · €99/año · auto-renew ON. Factura a guardar en
  `~/Documents/Claude/Projects/Facturas TDM/2026-06-08_Apple_Apple-Developer-Program_99EUR.pdf`.
- **Fecha:** 2026-06-02
- **Decisión:** El founder paga la membresía Apple Developer Program ($99/año) **él mismo**
  al llegar a Madrid el domingo. Si algún preparativo lo bloquea antes, lo paga mañana.
- **Estado:** Acordado. Pago lo ejecuta el founder (regla de seguridad: el asistente NO
  introduce credenciales financieras ni hace pagos).
- **Razón:** Preferencia logística del founder. No es bloqueante para el trabajo de prep.
- **Implicaciones / qué se puede hacer SIN la cuenta paga (en paralelo desde ya):**
  - ✅ Auditoría compliance (hecha, `APPSTORE_COMPLIANCE.md`).
  - ✅ Scaffold del proyecto Capacitor en local (no requiere cuenta paga para `npx cap add ios` y abrir en Xcode con cuenta gratis en simulador).
  - ✅ Diseñar el catálogo de productos IAP (IDs, precios) en papel.
  - ✅ Preparar assets: screenshots, textos App Store, demo account, nutrition labels (borrador).
  - ✅ Implementar features nativas y `IS_IOS_NATIVE` flag (código local).
  - ✅ Verificación 4.1(c) del nombre "The Dogs' Mind" (búsqueda pública, no requiere cuenta).
- **Qué SÍ requiere la cuenta paga (esperan a domingo):**
  - App Store Connect: reservar App Name, crear App ID, crear productos IAP reales.
  - Certificados de distribución / provisioning profiles de distribución.
  - TestFlight (requiere build firmado con cuenta paga).
  - Sign in con App Store Server Notifications V2 (config de keys en App Store Connect).
- **Acción:** trabajar todo el bloque "sin cuenta paga" estas horas; congelar el bloque
  "con cuenta paga" hasta que el founder confirme pago.

### D-002 · Stripe completamente oculto en el binario iOS
- **Fecha:** 2026-06-02 · **✅ SCAFFOLD IMPLEMENTADO Y EN PROD 2026-06-04**
- **Decisión:** En el build iOS, ningún path de Stripe es accesible (ni botón, ni link,
  ni copy "más barato en la web"). Feature flag `IS_IOS_NATIVE` apaga todo Stripe en iOS.
- **Estado:** ✅ **Scaffold del flag implementado** en `frontend/index.html`. Falta solo
  cablear la compra IAP (RevenueCat) en los puntos ya marcados con `TODO Fase 2` (espera
  cuenta Apple paga). La detección + el apagado de Stripe en iOS YA están vivos.
- **Razón:** 3.1.1 + 3.1.3(b). Dirigir fuera del IAP dentro de la app iOS = rechazo seguro.
- **Implementación (verificada, `frontend/index.html`):**
  - `dmIsIosNative()` (~L13882): `true` solo si `window.Capacitor.getPlatform()==='ios'`.
    **Fail-closed**: try/catch + short-circuit → en web/Android `window.Capacitor` es
    `undefined` → devuelve `false` → flujo Stripe **intacto e INERTE**.
  - `dmApplyIosNativeUI()` (~L13893): en iOS oculta las 3 filas de packs de tokens
    (`#s-tokens [onclick^="recargar"]`), el bloque `tokens_secure_payment` y el copy
    `.ps-secure` ("Pago seguro vía Stripe"). No-op en web. Idempotente. Corre en
    DOMContentLoaded.
  - **3 entradas Stripe blindadas (fail-closed):** `recargar(pack)` (~L14659, packs de
    tokens → `/payments/checkout`), `psSubmit` rama Stripe (~L12906 → `/payments/pro-checkout`),
    `paGoToCheckout` (~L13086 → `/payments/pro-checkout`). El guard `if (dmIsIosNative())
    return` corta ANTES de crear sesión Stripe. Las ramas **promo/cortesía** (`/payments/
    pro-activate-promo`) van ANTES del guard → siguen funcionando en iOS (la promo NO es
    Stripe).
- **Verificación realizada 2026-06-04:** (a) inspección de código (fail-closed garantizado);
  (b) los 7 bloques `<script>` inline pasan `node --check` (sin error de sintaxis → no brickea
  prod); (c) empírico: ya está vivo en prod (`thedogsmind.net`) en SW v196 sin ninguna
  regresión en web. **Property "inerte en web" confirmada por las 3 vías.**
- **⚠️ Provenance (nota de honestidad):** el scaffold se commiteó y se desplegó a prod
  **mezclado** en los commits de training `65b4a52` (SW v195) / `4b1917d` (SW v196) de una
  sesión previa, NO en un commit propio etiquetado D-002. El código está bien y es inerte,
  pero la traza git no nombra D-002. Working tree limpio para `index.html` (HEAD == prod).
- **Implicaciones:** la web sigue vendiendo por Stripe (legítimo, en paralelo). Solo el
  binario iOS queda limpio. Los `TODO Fase 2 (IAP)` en esos 3 puntos son los anclajes donde
  se conecta la compra RevenueCat cuando haya cuenta Apple paga.

### D-003 · Tipo de producto para Pro → AUTO-RENEWABLE SUBSCRIPTION ✅ DECIDIDO
- **Fecha:** 2026-06-02
- **Decisión:** En iOS, la membresía Pro se modela como **Auto-Renewable Subscription**
  (€20/año, renueva automáticamente salvo cancelación). Tokens siguen siendo **consumibles**.
- **Estado:** ✅ DECIDIDO (aplicando regla del founder "siempre la mejor opción; el bug es
  el enemigo, no la comisión").
- **Razón (por qué es la mejor, no la más barata):**
  1. **RevenueCat está construido para auto-renewables** → es su caso de uso central →
     **mínimo código propio → mínima superficie de bug.** La alternativa (non-renewing)
     obliga a rastrear caducidad a mano en backend = más código = más riesgo de bug.
  2. Categoría limpia y estándar para los revisores Apple (la non-renewing los confunde).
  3. Mejor retención de ingresos (el usuario no tiene que re-comprar manualmente cada año).
- **Riesgo conocido y cómo se mitiga:** auto-renewable activa requisitos de 3.1.2 →
  copy obligatorio junto al botón (precio, periodo, "se renueva automáticamente salvo
  cancelación", links a Términos + Privacidad, cómo cancelar). Es un **checklist mecánico**;
  RevenueCat entrega ese copy en su doc. Riesgo bajo y conocido.
- **Implicación de modelo:** iOS Pro auto-renueva anualmente (el usuario cancela cuando
  quiera en Ajustes de iOS); la **web sigue siendo pago único anual** vía Stripe. Modelos
  por plataforma distintos = permitido y normal. El backend (`account_type='professional'`)
  es la fuente de verdad: si ya eres Pro por web, iOS NO te vuelve a cobrar (chequea
  entitlement en backend antes de ofrecer IAP).
- **Nota:** el caveat `[VERIFICAR]` sobre "non-renewing annual" queda DISUELTO — las
  auto-renewable existen y son el tipo más estándar, sin ambigüedad de nomenclatura.

### D-005 · Bundle ID → `net.thedogsmind.app` ✅ DECIDIDO (vetoable por founder)
- **Fecha:** 2026-06-02
- **Decisión:** `net.thedogsmind.app`. Corrige mi propuesta inicial `com.thedogsmind.app`.
- **Estado:** ✅ Recomendación firme. El founder puede vetar, pero hay que fijarlo UNA vez.
- **Razón:** El Bundle ID es reverse-DNS de un dominio que controlas. El founder controla
  `thedogsmind.net` (no `.com`), así que el reverse-DNS correcto empieza por `net.`. Apple
  NO verifica propiedad del dominio (el Bundle ID es solo un identificador único), pero usar
  el dominio real garantiza unicidad global y es lo técnicamente correcto.
- **⚠️ Regla dura:** el Bundle ID es **INMUTABLE para siempre** tras el primer envío.
  Cambiarlo = app nueva (se pierden reviews, usuarios, historial). Se elige UNA vez y nunca más.
- **Impacto en review:** CERO. `com.` o `net.` ambos pasan. Lo único que importa es que
  sea único y estable.

### D-006 · Device Family → iPhone-only en v1, NO comprar iPad ✅ DECIDIDO
- **Fecha:** 2026-06-02
- **Decisión:** v1 se publica como **app de iPhone únicamente** (Device Family = iPhone).
  **El founder NO necesita comprar iPad.**
- **Estado:** ✅ DECIDIDO.
- **Razón:** Apple NO exige soporte iPad. Una app iPhone-only corre igualmente en iPad
  (modo compatibilidad). Declarar iPhone-only evita: screenshots de iPad, QA de layout iPad,
  y un gasto innecesario. La app es portrait phone-first (`manifest.json` →
  `orientation: portrait-primary`). iPhone-only = camino limpio y rápido al App Store.
- **Implicación:** se testea en **iPhone 14 físico** (que ya tiene) + simulador. Soporte
  iPad se puede añadir en una versión futura si interesa.

### D-007 · Capa de IAP → RevenueCat ✅ DECIDIDO (founder, input #5)
- **Fecha:** 2026-06-02
- **Decisión:** `@revenuecat/purchases-capacitor` como capa de compras (abstrae StoreKit2
  en iOS y Google Play Billing en Android).
- **Estado:** ✅ DECIDIDO por el founder.
- **Razón:** menos código propio que StoreKit2 nativo → menos bugs; webhooks y validación
  de recibos gestionados; restore purchases y entitlements out-of-the-box; multiplataforma.
- **Coste:** RevenueCat es gratis hasta cierto MTR (monthly tracked revenue); por encima,
  comisión pequeña. El founder acepta el coste (dinero no es el criterio).

### D-008 · Capacitor Live Updates → NO en v1 ✅ DECIDIDO
- **Fecha:** 2026-06-02 (consolida D-004)
- **Decisión:** Live Updates / hot-code-push **desactivado** en v1.
- **Estado:** ✅ DECIDIDO (aplicando "la mejor opción = la más segura para pasar review").
- **Razón:** 2.5.2 (no descargar código que cambie features). Prioridad absoluta: pasar
  review sin fricción. Las actualizaciones van por el ciclo normal de App Store.

### D-009 · Push notifications → nativo vía @capacitor/push-notifications + APNs ✅ DECIDIDO
- **Fecha:** 2026-06-02
- **Decisión:** Push nativo con el plugin oficial `@capacitor/push-notifications` + APNs,
  para **recordatorios del seguimiento diario** (daily-followup). Opt-in del usuario.
- **Estado:** ✅ DECIDIDO. Requiere APNs Key creada en Apple Developer (espera cuenta paga).
- **Razón:** (a) es una de las ≥3 features nativas que cubren 4.2; (b) aporta valor real
  (el seguimiento diario vive o muere por la adherencia → un recordatorio la sube); (c)
  plugin oficial = bajo riesgo. RevenueCat no necesita push; son independientes.
- **Nota:** push es opt-in (iOS pide permiso); si el usuario lo rechaza, la app funciona igual.

### D-010 · "Las funciones son las que hay" — 4.2 sin features nuevas ✅ DECIDIDO (founder)
- **Fecha:** 2026-06-02
- **Decisión:** NO se añaden features de producto nuevas para iOS. La app ya es completa.
  La 4.2 se cubre con **capacidades nativas sobre funciones EXISTENTES** (IAP, push, picker
  nativo de vídeo de anamnesis, offline). Share Sheet / export PDF DESCARTADO (sería nuevo).
- **Estado:** ✅ DECIDIDO por el founder.
- **Razón:** menos superficie = menos bug = menos riesgo de rechazo. La app tiene
  funcionalidad genuina y profunda; no necesita inflarse para pasar 4.2.

### D-011 · Alcance v1 = el mínimo que pasa compliance, nada más ✅ DECIDIDO (founder)
- **Fecha:** 2026-06-02
- **Decisión:** La v1 contiene EXACTAMENTE lo necesario para pasar App Store review, ni un
  extra. Lo que no sea requisito de compliance NO entra en v1.
- **Alcance v1 BLOQUEADO:**
  - IAP (RevenueCat) + ocultar Stripe en iOS — req. 3.1.1.
  - Push nativo (founder lo quiere en v1) — refuerza 4.2.
  - Picker nativo de vídeo (función existente, plumbing nativo) — refuerza 4.2.
  - Offline vía Capacitor (gratis) — refuerza 4.2.
  - Refuerzo consent IA per-acción — req. 5.1.2(i).
  - Account deletion (ya existe), disclaimers (ya existen).
  - FUERA de v1: iPad, share sheet, cualquier feature nueva.
- **Estado:** ✅ DECIDIDO. Vetable solo si el founder ve algo mal; no se le pregunta.
- **Metáfora-regla del founder (ambulancia / camisa de marca):** ante una parada cardiaca,
  el médico rompe la camisa de marca y reanima; **no llama a la familia para pedir permiso
  por la camisa.** Traducción operativa: cuando el objetivo (compliance / no-rechazo) lo
  exige, EJECUTO. No delibero trivia, no la traigo al founder. El único criterio es App
  Store compliance. Solo acudo al founder para lo que SOLO él puede hacer (pagar, datos
  que únicamente él tiene), nunca para "camisas de marca" (coste, preferencias, micro-forks).

### D-012 · Logo / icono App Store → marca BESPOKE vía web especialista de pago ✅ DECIDIDO (founder)
- **Fecha:** 2026-06-03
- **Contexto:** El icono actual (`frontend/icons/*`, Jun 2 11:29) es una FOTO del border collie
  **de cuerpo entero** sobre bala de paja → la opción más débil para App Store (HIG desaconseja
  fotos; a 40 px es una mancha irreconocible). El founder pidió cambiar el logo y elegir el MEJOR
  para App Store, con dos reglas: (a) **NO diseños a mano alzada del agente** ("no te salen muy
  bien"); (b) si hay dudas, **recurrir juntos a una página especialista**.
- **Splash:** YA correcto y vivo en `index.html #s-splash` — eyebrow "The Dogs' Mind", título
  "AI for Canine Behavior", "by Teo Mariscal", dock flotante. NO tocar. (`splash-redesign-v2.html`
  fue el estudio de diseño detrás; es preview, no producción.)
- **Rondas descartadas:** monté candidatas con marcas open-source (Phosphor/Lucide/Tabler, MIT)
  sobre el campo esmeralda. **Founder: "ninguna llega a mi nivel".** Pipeline archivado FUERA de
  frontend en `./_logo-work-archive/` (no se despliega a prod).
- **DIRECTIVA DEFINITIVA DEL FOUNDER (2026-06-03, verbatim):** *"quiero un logo hecho en base a
  la foto del perro de calidad artista de top brands a cualquier coste"* + *"derívame a una web de
  pago, si es posible cara y de calidad, para que basados en el perro de la foto desarrollen una
  pieza única"* + *"no quiero opciones gratuitas, no quiero ahorrar si el resultado puede ser un
  1% peor, no quiero opciones entre malas y buenas, solo excelencia"* + *"no me preguntes tanto"*.
- **Decisión:** pieza **bespoke hecha por un ARTISTA HUMANO de primer nivel**, **derivada de la
  foto del border collie** (`frontend/assets/images/img-00.webp`). Coste no es restricción; la
  excelencia y la unicidad sí. El agente NO dibuja, NO ofrece menús, NO usa contests (sifting de
  opciones = lo que el founder NO quiere). Modelo 1-a-1 con top designer.
- **Sitio recomendado (1-a-1, sin contest):** **Dribbble → Hire Designers** (techo artístico más
  alto, los mejores ilustradores de marca del mundo, pieza única y 100% ownable). Alternativa
  turnkey premium: **99designs "Work 1:1 with a designer" (Platinum)**. NUNCA Looka/AI (descartado).
- **Foto fuente entregable:** exportada a `~/Downloads/the-dogs-mind-dog-source.jpg` y `.png`
  (1086×724, border collie B/N). Si el founder tiene el original en más resolución, mejor.
- **Spec de entrega para el agente (lo que el founder pedirá al artista):** el **símbolo/marca solo**
  (sin texto) en **SVG vectorial** + **PNG transparente ≥1024 px**; + el **lockup completo**
  (símbolo + wordmark "The Dogs' Mind" en Cormorant + tagline "AI for Canine Behavior" en Jost)
  para splash/marketing. Fondo TRANSPARENTE. **Transferencia de copyright total** incluida.
- **Icono App Store specs (las pone el agente):** 1024×1024 PNG, sRGB, **sin canal alpha**,
  **sin esquinas redondeadas** (Apple aplica la máscara), símbolo SIN texto, área segura ~80%,
  legible a 40 px. Set: 1024 + 180/192/152/144/128/96/72 + apple-touch-icon + favicon.ico.
- **Estado:** ⏳ esperando que el founder traiga el asset de la web especialista. Sin deploy a
  prod hasta aprobación visual (modo cautela). Backup de iconos actuales antes de sustituir.

- **Paso "esbozo" (founder, 2026-06-03):** antes de ir al artista top, el founder quiere llegar
  con un **logo esbozado** generado en la plataforma de IA-logos más prestigiosa. Decidido:
  **Recraft V4** (nº1 para logos en benchmarks, exporta **vector SVG real**, brand styles,
  acepta la foto como referencia). Midjourney solo como exploración de "mood" artístico (raster).
  Flujo: founder genera esbozo monocromo en Recraft con la foto del perro como referencia
  (prompts engineered entregados) → trae SVG/PNG → el agente monta el **mockup real** (icono
  40–1024px + splash en contexto) para que el founder lo VEA como app → ese esbozo+mockup es
  lo que se lleva a Bokhua/Toptal para la pieza bespoke final. Color lo compone el agente; el
  esbozo se evalúa en monocromo (forma). Pago siempre del founder (el agente no mete datos).
- **Dirección de estilo elegida (founder, 2026-06-03):** **línea continua única + retícula áurea
  visible**, la FIRMA de Bokhua (su serie "line art"). El perro = border collie en una sola línea.
  Bokhua figura "Available for work" en Dribbble con botón "Get in touch" → objetivo: que la haga
  ÉL. Esbozo Recraft/Midjourney solo para adjuntar dirección al encargo. Nota técnica: el line-art
  full-body es marca/splash; para el ICONO a 40px hará falta un derivado más bold/simplificado
  (lockup) — el artista entrega ambos y el agente hace el montaje. Foto mejor resolución que la
  actual fue compartida por el founder (pendiente que la guarde y dé ruta).

- **Esbozos Recraft generados (founder, 2026-06-03):** el founder generó 2 line-art del border
  collie en Recraft (línea continua + retícula áurea), guardados en `~/Downloads/bocalan_online_*`.
  El agente compuso el **wordmark "The Dogs' Mind" en Cormorant Garamond REAL** (variable font OFL,
  apóstrofo U+2019) sobre ambos, en 2 colocaciones: **A = pie/baseline** y **B = cruzando el cuerpo**.
  4 salidas + contact sheet en `_logo-work-archive/wordmark-out/` (v1/v2 × A/B). Script reproducible:
  `_logo-work-archive/add_wordmark.py`. Fuera de ruta de deploy.
- **VEREDICTO DEL CONSEJO (3 evaluadores independientes, 2026-06-03):** el founder pidió convocar
  consejo (diseño + psicología de compra + posicionamiento de marca). Resultado:
  - **Colocación: A (pie) gana por UNANIMIDAD 3/3.** La B (cruzando) rompe el concepto de "línea
    continua", choca con el line-art, pierde legibilidad y NO escala (no separable en icono). Los
    3 la descartan como identidad principal; sirve solo como sello/merch. (El founder prefería V2B
    → se le comunica honestamente el voto contrario.)
  - **Perro: 2 votos v2_A, 1 voto v1_A.** Diseño + Psicología eligen **v2** (línea más limpia y
    confiada, cara más calmada que "modela el resultado" que busca el dueño preocupado, y el único
    que sobrevive el shrink a 40px). Marca disiente → **v1** (su "chest-loop" es más ownable/
    memorable/registrable; v2 "es un dibujo, no un logo"). Tensión real: lo que Marca ama del v1
    (el bucle del pecho) es justo lo que Diseño llama "maraña que colapsa en mancha a 40px".
  - **Decisión del presidente (agente):** **v2_A como lockup primario.** Para el icono App Store
    pesa la legibilidad a 40px (2/3 + viabilidad icono) → v2 gana. Se incorpora la objeción de
    Marca: al encargar a Bokhua, pedirle que **empuje la línea de v2 a ser más distintiva/ownable**
    (un trazo-firma) manteniendo la anatomía limpia y la cara calmada de v2 = lo mejor de ambos.
  - **Retícula áurea: quitar del logo de producción y del icono (3/3).** Conservarla solo como
    recurso de "brand story" / animación de carga (refuerza el relato clínico/preciso).
  - **Refinos menores (crítico de diseño):** estrechar el bucle exterior de la cola de v2; abrir el
    tracking del wordmark ~2-3% para igualar la ligereza del line-art a tamaño pequeño.
  - **Icono = v2 perro SOLO** (sin texto, sin grid) sobre fondo gradiente esmeralda→cyan.
- **INTEGRACIÓN VIBRANT (founder "adelante", 2026-06-03):** aprobado v2_A → master guardado en
  `_logo-work-archive/decided/v2A_master_blackoncream.png`. Generada la versión de marca: perro
  como **línea de energía cyan luminosa** (glow #5ec8e6 + core casi-blanco) sobre **gradiente
  esmeralda** (`#0a1a14`→`#4a6741`) + **halo cyan** + **dot-grid técnico** sutil = el "punto AI".
  Script reproducible `_logo-work-archive/make_vibrant.py` (extrae el perro descartando la retícula
  por neutralidad de color; fuentes Cormorant + Jost OFL). Assets en `decided/`:
  `icon_1024_vibrant.png` (icono App Store, sin texto, sin alfa, square), `lockup_vibrant.png`
  (perro + wordmark Cormorant + tagline "AI FOR CANINE BEHAVIOR" Jost), `icon_sizes_strip.png`
  (prueba 1024→40px), `dog_glow_transparent.png`. Preview de app montado en
  `_logo-work-archive/logo-integration-preview.html` (home screen iOS + splash, NO desplegado).
  **Pendiente/known issue:** a 40px el trazo neón se afina → el arte bespoke final (Bokhua)
  engrosa la línea manteniendo glow. Sin tocar producción hasta aprobación visual del founder.
- **✅ LOGO APROBADO ("Me fascina", founder 2026-06-03):** tras iterar, el founder rechazó el
  neón fuerte ("menos neón mucho menos neón") y pidió **recolorear FIEL pixel-a-pixel** el lockup
  v2_A (perro v2 + retícula áurea COMPLETA + wordmark Cormorant), SIN redibujar trazos, a
  **cyan + blanco** y **conservando los trazos de fondo** (la retícula), **sin** tagline "AI for
  Canine Behavior". Mapa de color: **perro + "The Dogs' Mind" → BLANCO** (línea limpia, glow
  mínimo, nada de neón); **retícula áurea → CYAN claro #80d6ee bien visible** como blueprint
  técnico de fondo; **fondo → gradiente esmeralda oscuro** + halo cyan bajo. Corrección clave:
  primero recoloreé v1_A por error → founder "elige el logo correcto" → es **v2_A** (perro limpio,
  cara calmada). Script reproducible `_logo-work-archive/recolor_faithful.py` (keying por
  luminancia/croma/calidez para separar tinta vs retícula vs crema). **Masters definitivos** en
  `_logo-work-archive/decided/`: `MASTER_logo_vibrant_v2A_cyanwhite.png` (lockup completo
  2528×1778), `faithful_cyanwhite.png` (igual), `logo_transparent_cyanwhite.png` (líneas sobre
  fondo TRANSPARENTE para integrar en cualquier pantalla). Fuente del recolor:
  `wordmark-out/v2_A_footer.png`. Pendiente: derivar set de iconos iOS (perro solo, trazo
  engrosado para 40px) + integración en splash/icons SIN deploy hasta aprobación.
- **✅ SET DE ICONOS GENERADO E INSTALADO EN FRONTEND (founder "vamos con ese logo por si Bokhua
  no contesta / que salga ya en el icono para desktop", 2026-06-03):** se adopta el logo aprobado
  como **fallback de trabajo** mientras Bokhua responde. Script reproducible
  `_logo-work-archive/make_icon.py`: extrae SOLO el perro v2 (descarta la retícula por neutralidad
  de color), lo pinta como **línea blanca limpia + glow cyan mínimo** sobre el gradiente esmeralda
  (sin texto, sin grid = reglas App Store), y **engrosa el trazo con MaxFilter** escalado al tamaño
  para que sobreviva en pequeño. Genera 16 tamaños → staging en `decided/icons_new/`:
  `icon-{72,96,128,144,152,180,192,512}x*.png`, `apple-touch-icon.png` (180), `favicon.ico`
  (multi 16/32/48/64), `icon-1024x1024.png` (App Store, RGB sin alfa) + `_icon_review_strip.png`.
  - **Backup** del set anterior (foto cuerpo entero, Jun 2) en `frontend/icons_backup_2026-06-03/`
    (9 PNG + favicon.ico) ANTES de sustituir.
  - **Instalados** en `frontend/icons/` + `frontend/favicon.ico` (mismos nombres → sin tocar
    `index.html` ni `manifest.json`). Servido localmente en `http://127.0.0.1:8765` para revisión
    visual en desktop (favicon de pestaña + icono PWA instalado).
  - **Known issue (sin cambios):** el perro full-body line-art es nítido hasta ~120–180px (tamaño
    real del icono PWA/dock instalado) pero a 16–32px (favicon de pestaña) colapsa en mancha. Es
    inherente al dibujo; el arte bespoke de Bokhua engrosará/simplificará el trazo para 40px. El
    1024/512/192 (lo que se ve como "icono de desktop") lucen premium.
  - **✅ DESPLEGADO A PROD (founder: "deploy", 2026-06-03):** Netlify prod `thedogsmind.net`
    (deployId `6a204ff9b5a25ca47fb0e3cf`, 13 files). Causa de "no lo veo" = caché: assets
    same-origin son **cache-first** en el SW + el navegador cachea el favicon agresivamente.
    Fix idiomático del repo: **bump `CACHE_NAME` v193 → v194** (al activar el SW nuevo purga la
    caché vieja y re-descarga iconos/favicon) + **`?v=194`** en los links favicon/apple-touch de
    `index.html` (rompe la caché de favicon del navegador). Verificado en prod: favicon?v=194 200
    (10793 B nuevo), icon-512 72362 B nuevo, SW = `dogs-mind-v194`. App carga OK, banner "Nueva
    versión disponible · Actualizar" aparece correctamente (SKIP_WAITING → activa v194). Iconos
    viejos (foto cuerpo entero) respaldados en `frontend/icons_backup_2026-06-03/` → revertible.
  - **Pendiente menor:** commit a git de `frontend/icons/*`, `favicon.ico`, `index.html`,
    `service-worker.js` (cuando el founder lo pida; el deploy ya está vivo). Bokhua sigue siendo
    el objetivo para el arte bespoke final (este logo es el fallback de trabajo aprobado).

### D-004 · (Reemplazado por D-008)
- Live Updates OFF en v1. Ver D-008. Número conservado por trazabilidad histórica.

---

## CATÁLOGO DE PRODUCTOS IAP (para crear en App Store Connect)

Precios reales extraídos de `app/api/routes/payments.py` (2026-06-02). Los **Product IDs
son INMUTABLES** una vez creados (como el Bundle ID) → se eligen una sola vez.

| Producto | Tipo IAP | Precio web (real) | Product ID propuesto | Notas |
|---|---|---|---|---|
| 5 tokens | Consumable | €4,99 | `net.thedogsmind.tokens.5` | `amount_cents=499` |
| 20 tokens | Consumable | €16,00 | `net.thedogsmind.tokens.20` | `amount_cents=1600` |
| 60 tokens | Consumable | €42,00 | `net.thedogsmind.tokens.60` | `amount_cents=4200` |
| Pro (anual) | **Auto-Renewable Subscription** | €20,00/año | `net.thedogsmind.pro.yearly` | Grupo de suscripción: `net.thedogsmind.pro`. Ver D-003 |

**Decisiones de catálogo (regla #8/#9, decididas, no preguntadas):**
- **Precios iOS = precios web**, mapeados al *price point* de Apple más cercano (se confirma
  en App Store Connect; Apple no permite importe libre, se elige de su lista de price points).
  Se absorbe la comisión de Apple (el founder ya dijo: el dinero no es el criterio). Mantener
  el mismo precio evita confundir al usuario y simplifica.
- **Combo "Pro + 60 tokens" (€57,80) NO va a iOS** (D-011, minimal v1). En iOS, Pro y tokens
  se compran por separado. El combo sigue existiendo solo en web.
- **Tokens = consumibles** (no caducan; ToS §4). RevenueCat los gestiona y el backend acredita
  los tokens al validar el recibo (vía webhook App Store Server Notifications V2).
- **Pro:** el backend (`account_type='professional'`) es la fuente de verdad. Antes de ofrecer
  el IAP de Pro en iOS, comprobar entitlement en backend → si ya es Pro (p. ej. activado en
  web), NO ofrecer compra (evita doble cobro). Restore Purchases obligatorio (3.1.1).

**`[VERIFICAR]` al crear en App Store Connect:** (a) price point exacto por producto, (b) que
los Product IDs no se hayan usado antes (inmutables), (c) localización de nombres/descripción
de cada producto (ES + EN), (d) tax category correcta.

---

## PRINCIPIOS DE TRABAJO (acordados con el founder, vigentes)

1. **99% de certeza antes de cada paso.** Si no estoy seguro, lo digo o no lo hago.
2. **Cautela tipo nitroglicerina.** Hay usuarios de pago; prod es crítica. No batchear deploys.
3. **No preguntar por alternativas a App Store.** El objetivo es no-negociable.
4. **Honestidad > complacer.** Si necesito un ingeniero humano para algo, lo digo.
5. **Guardar TODO siempre** para próximas sesiones (este doc + COMPLIANCE + TRACKING).
6. **Plazos: dar tiempos APROXIMADOS para orientar, sin presión.** (matizado por el founder
   2026-06-08) El founder SÍ quiere estimaciones aproximadas ("me gusta trabajar sabiendo unos
   tiempos aproximados") y NO le importa que se alarguen. Lo que NO se hace: tratar los tiempos
   como fecha límite dura, meter prisa que arriesgue bugs, ni mandarlo a descansar. Dar rangos
   honestos por bloque + avisar al cerrar cada bloque cómo va el tiempo. La calidad/cautela va
   por delante del cronómetro. (Antes era "no hablar de plazos" a secas; queda matizado así.)
7. **Usar agentes para evitar fallos (directiva founder 2026-06-08).** Trabajar con paneles de
   agentes adversariales como práctica estándar anti-rechazo: (a) **auditoría multi-agente
   pre-submit** — varios agentes "revisor de Apple", cada uno con una guideline (3.1.1, 4.2,
   5.1.2, 4.7, metadatos…), buscando motivos de rechazo y tapándolos; (b) **code-review por
   agentes** en piezas de riesgo (IAP/RevenueCat, webhooks); (c) cada hallazgo **verificado por
   un segundo agente** antes de darlo por válido. El founder quiere esto integrado en el flujo.
   ⚠️ **Lección 2026-06-08:** en auditorías, lanzar los agentes en **SOLO-LECTURA** (agentType
   Explore o sin Edit/Write) — en el 1er audit un agente editó `Info.plist` por su cuenta
   ("ayudando"). El resultado fue correcto, pero un audit no debe mutar el repo. 1ª auditoría
   real (51 agentes) encontró 7 blockers reales (incl. un agujero en D-002: las pantallas de
   compra Pro NO se ocultaban en iOS) → ver `APPSTORE_AUDIT_FINDINGS.md`.
8. **SIEMPRE la mejor opción — yo decido, no pregunto disyuntivas técnicas.** (regla dura
   2026-06-02) El dinero, dentro de límites razonables, NO es el criterio. El criterio es
   **minimizar el riesgo de bug / rechazo**. Cuando hay una opción claramente superior,
   la tomo y la registro como decisión (vetoable), no como pregunta.
9. **Regla de la ambulancia (regla dura 2026-06-02).** Si un camino reduce el riesgo de
   rechazo, lo tomo SIN deliberarlo ni traérselo al founder. El médico rompe la camisa de
   marca y reanima; no llama a la familia por la camisa. **El único criterio es App Store
   compliance.** Solo acudo al founder para lo que SOLO él puede hacer (pagar, datos que
   únicamente él tiene). Nada de micro-forks, costes ni preferencias.
