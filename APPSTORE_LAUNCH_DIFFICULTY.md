# The Dogs' Mind — App Store: dificultad, riesgo de rechazo y tiempo estimado

Análisis multi-agente (3 agentes read-only: ritmo/tiempo, pasos+dificultad, revisor adversarial de Apple).
**Fecha: 2026-06-13.** Documento de trabajo, cero impacto en prod. Fuente de verdad de compliance: `APPSTORE_COMPLIANCE.md`.

Leyenda: **Dif** = esfuerzo/dificultad 1–10 · **Rech** = probabilidad de causar rechazo si se hace mal 1–10 (con guideline de Apple).

---

## 1. Tiempo estimado a "enviado y sin errores" (según ritmo real)

Ritmo observado: **6 sesiones en 6 días** (8→13 jun 2026), ~1 sesión sustancial cada ~1,2 días en activo.
Patrón: cada sesión cierra un bloque grande pero destapa un bloqueante nuevo dependiente del founder.

| Escenario | Sesiones | Días | Fecha submit |
|---|---|---|---|
| Optimista | 2 | ~3 | ~16 jun |
| **Realista** | **3–4** | **5–7** | **~18–20 jun** |
| Conservador | 5–6 | 9–12 | ~22–25 jun |

- **Review de Apple** (post-submit): 1–3 días. Posible 1er rechazo + reenvío: +2–4 días.
- **App LIVE estimada: última semana de junio (~23–28 jun 2026)**, escenario realista.
- Mayores retrasos probables: (a) test real de compra IAP en sandbox (nunca probado end-to-end), (b) disponibilidad del founder para pasos de dashboard (se serializan), (c) ciclo rechazo→reenvío.

---

## 2. Pasos restantes — dificultad + riesgo de rechazo

| Paso | Quién | Dif | Rech | Nota / guideline |
|---|---|---|---|---|
| Webhook backend desplegado | yo | — | — | ✅ HECHO 2026-06-13 (live + seguro, 401/200 verificado) |
| Configurar webhook en RevenueCat (dashboard) | founder | 2 | 1 | URL + header Authorization = secreto. La API de RC no lo permite |
| Precio €20/año suscripción (ASC UI) | founder | 3 | 3 (3.1.2) | API dio 409 2×; sin precio el IAP no queda "Ready to Submit" |
| IAP "Ready to Submit" + atado al build | ambos | 3 | **7** (3.1.1) | error clásico: submit con productos sin atar a la versión |
| `cap sync` + build 4 + upload | yo | 4 | 2 | el build 3 NO lleva el IAP; CFBundleVersion→4 |
| **Test real compra sandbox** (compra→webhook→tokens) | ambos | 6 | **8** (3.1.1/2.1) | nunca probado; mayor varianza; necesita sandbox tester + agreement Active |
| Verificar Restore Purchases en build | ambos | 3 | 6 (3.1.1) | obligatorio Apple; existe `dmRcRestore` pero sin probar; consumibles NO se restauran (solo Pro) |
| Cuenta demo revisor (password real) | founder | 2 | **7** (2.1) | sigue con `[FOUNDER FILLS THIS IN]` → rechazo seguro; probar login end-to-end |
| Screenshots 6.9" (1320×2868) | ambos | 4 | 5 (2.3.3) | app en uso, no splash/login; reflejar UI real |
| Verificar Stripe 100% oculto en build iOS | yo | 3 | **7** (3.1.1/3.1.3b) | el audit pilló fugas de "20€"/botones Stripe en pantallas Pro; revisar strings reescritos por JS en 1er paint |
| **Plugins nativos (push/cámara) para 4.2** | yo+founder | 6 | **7** (4.2) | ⚠️ HALLAZGO: solo `@capacitor/keyboard`+`purchases-capacitor` instalados; sin push ni picker → "esto es una web" |
| **Endurecer chat IA (4.7/edad)** | yo | 3 | **6** (4.7) | ⚠️ HALLAZGO: el chat se presenta como persona ("Niaz, mil ideas, cerebro a mil") sin aviso de ámbito en UI ni botón "reportar"; 4+ con chat libre = imán de rechazo |
| Apagar `PRO_PROMO_FREE` al submit | founder/yo | 3 | 4 (3.1.1) | simultáneo y coordinado; sin IAP working dejaría a usuarios sin Pro |
| Aceptar contrato Apple actualizado | founder | 1 | 6 (negocio) | sin "Active" bloquea submit; Paid Apps debe estar Active |
| **DSA trader status (UE)** | founder | 2 | **8** (DSA) | ⚠️ ya NO es opcional: bloquea PUBLICAR en UE; como autónomo publica dirección personal salvo empresa |
| Metadata / Description / Notes for Review | yo+founder | 2 | 6 (2.3.1) | no afirmar features ausentes; sin "Bocalán"; sin refs Google Play |
| Age rating 4+ + account deletion (5.1.1v) + consent IA en binario | ambos | 2 | 5 | confirmar que viven en el build iOS, no solo en web |
| Gate pre-submit adversarial (`APPSTORE_PRELAUNCH_GATE.md`) | yo | 4 | 3 | criterio: 0 blockers / 0 high antes de enviar |
| Submit (seleccionar build + atar IAP + enviar) | founder+yo | 2 | 3 | atar IAP + binario juntos |

---

## 3. Síntesis de riesgo

**Top 3 MAYOR riesgo de rechazo:**
1. **DSA trader status (8)** — gate UE en release; deferirlo choca con que Apple ya lo exige para publicar.
2. **Test real IAP sandbox (8)** — toda la cadena compra→webhook→tokens→Pro está construida pero NUNCA probada en device; si el revisor paga y no recibe nada = 3.1.1+2.1.
3. **Empate (7):** plugins nativos 4.2 (binario = WebView fino) / fuga Stripe en iOS / cuenta demo con password placeholder.

**Top 3 más DIFÍCILES:**
1. Plugins nativos 4.2 (6) — instalar plugins + APNs key + entitlement + permisos.
2. Test IAP sandbox (6) — loop multi-parte (device + sandbox tester + webhook + RC dashboard) simultáneo.
3. IAP "Ready" + atado al build (3 pero operacionalmente frágil) — precio+localización+screenshot+agreement en verde a la vez.

**Probabilidad de rechazo 1er intento** (si todo se hace bien): **~30–40%**, concentrado en 4.7 (chat persona/edad) y 4.2 (¿es solo una web?). Enviando el build 3 actual: **~95%**.

**Lo más subestimado:** el chat IA se juzga por la UI, no por el system prompt. Hoy la UI vende una personalidad abierta a 4+ sin aviso de ámbito ni botón de reporte → añadir aviso visible "solo conducta canina" + botón reportar (barato) baja mucho el riesgo 4.7.

---

## 4. Modelo: ¿Fable 5?

Recomendación: **Opus 4.8 para la ejecución mecánica** (config, build, deploy, sandbox test) — sin brecha de calidad ahí.
**Fable 5 para 2 momentos de juicio fino** (regla founder "máximos recursos anti-rechazo"):
1. El **gate adversarial pre-submit** (verificador final).
2. Las decisiones **4.2 (plugins nativos)** y **4.7 (enfoque del chat)** — donde está el grueso del ~35% de riesgo.

---

## 5. Estado a 2026-06-13 (lo ya HECHO)

RevenueCat ↔ Apple conectado (IAP key + ASC API key válidas), catálogo creado (4 productos + entitlement `pro` + offering `default`), webhook backend live+verificado, cliente IAP escrito (working tree, inerte web). Build 3 en TestFlight beta-aprobado. Detalle en `[[dogs-mind-appstore-phase2]]` (6ª sesión).
