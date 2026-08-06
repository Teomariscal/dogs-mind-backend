# Dogs Mind — Bugs encontrados en pruebas de TestFlight (hardware real)

Lista de incidencias detectadas probando el build de TestFlight en iPhone. Build actual:
**v1.0 (3)** — subido 2026-06-10. Fixes: teclado (resize:'native' + JS gated en iOS, tras
auditoría Opus) + texto blanco modo oscuro (color-scheme:light) + bug CSS título login.
Builds 1/2 obsoletos. Build 3 = el que va a interno + externo (enlace público) + beta review.
**#1–#4 VERIFICADOS OK en dispositivo por el founder (2026-06-10).** Teclado + modo oscuro bien.

> #1 y #2 eran BLOQUEANTES de testing (no se podía ni registrar/loguear) → se arreglaron y
> resubió build 2 de inmediato (`@capacitor/keyboard` resize:'body'). Pendiente: founder
> actualiza en TestFlight y verifica.

Estado: 🔴 abierto · 🟡 fix listo (sin rebuild) · ✅ verificado en nuevo build.

---

## #1 ✅ (build 3: resize native) — Login profesional: el footer salta al abrir el teclado
- **Pantalla:** `s-pro-login` ("Área Profesional · Inicia sesión").
- **Síntoma:** al tocar el campo Contraseña y abrir el teclado, el botón "Iniciar sesión" +
  "¿No tienes cuenta?" saltan ARRIBA y se solapan con la cabecera; la pantalla se descuadra.
- **Causa:** footer fijo (padding-bottom reservado 132px) + WKWebView redimensiona mal al
  abrir el teclado (`contentInset:'always'` + sin `@capacitor/keyboard` → resize por defecto).
- **Fix (iOS-only, no toca web):** `npm i @capacitor/keyboard` + en `capacitor.config.ts`
  `plugins: { Keyboard: { resize: 'none' } }` (probar 'none'; si el footer queda tapado por el
  teclado de forma molesta, probar 'body'). `npx cap sync ios`.
- **Riesgo:** bajo, solo afecta al binario iOS.

---

## #2 ✅ (build 3: resize native) — Al escribir, el campo queda tapado por el teclado (registro/login)
- **Pantalla:** login/registro profesional (y probablemente cualquier formulario con campos
  en la mitad inferior).
- **Síntoma:** al escribir en un campo, el teclado lo tapa y la vista NO sube para mostrarlo.
- **Causa:** misma raíz que #1 — manejo del teclado en WKWebView sin `@capacitor/keyboard`.
- **Fix (CUBRE #1 y #2 a la vez):** `@capacitor/keyboard` con **`resize: 'body'`** en
  `capacitor.config.ts` → el body se encoge al área sobre el teclado: el campo enfocado sube a
  la vista Y el footer fijo se reposiciona encima del teclado. (Si 'body' diera reflow raro,
  alternativa 'ionic'/'native'; se calibra en device.) iOS-only, no toca web.

> NOTA: #1 y #2 son el MISMO arreglo (config de teclado). Se resuelven en una sola intervención.

---

## #3 ✅ (build 3: color-scheme light) — Texto de inputs INVISIBLE (blanco) en modo oscuro iOS
- **Síntoma:** al escribir en Email/Contraseña (y cualquier input), el texto sale blanco sobre
  campo blanco → no se ve. Pasa con el iPhone en **modo oscuro**.
- **Causa:** la web NO declaraba `color-scheme` → WKWebView en dark mode invierte los inputs.
- **Fix:** `<meta name="color-scheme" content="light">` + `:root{color-scheme:light}` en
  `frontend/index.html`. Fuerza render claro en TODA la app (es light-themed; las pantallas
  vibrant usan colores CSS explícitos, no se ven afectadas). Additive, web-safe.

## #4 ✅ RESUELTO — la causa del salto era resize:'body' inerte contra .phone fijo; build 3 usa resize:'native'
- La última captura del founder aún muestra el footer "Iniciar sesión" arriba con el teclado
  abierto. PENDIENTE confirmar si estaba en build 1 o si `resize:'body'` no bastó. Si no bastó,
  probar otro modo (`native`/`ionic`) o fix CSS, en el próximo build.

## FEEDBACK CARTA TESTER (profesional) — implementado 2026-06-10 (STAGED, sin deploy)

Selección del founder: **#1, #2, #3, #4, #8, #9** (fuera #6, #7). #5 solo respuesta.
Tocan `frontend/index.html` (web+iOS) + backend (núcleo de análisis) → additive, bajo riesgo.

- **#1 Perro adoptado / tiempo con el tutor** ✅ — input `inp-adopted-time` (anamnesis) + i18n ES/EN + payload `adopted_time_with_tutor`. Backend: campo en `AnamnesisInput` + `rag.py build_anamnesis_block` lo renderiza con nota al modelo: interpretar la duración del problema relativa al tiempo con el tutor (no a la edad).
- **#2 Describir el vídeo** ✅ — textarea `inp-video-caption` (aparece al adjuntar) + i18n + `fd.append('video_caption')`. Backend: `/analysis/video` acepta `video_caption` Form → `run_clinical_analysis(..., video_caption)` → inyectado en el mensaje multimodal.
- **#3 Spinner "pensando"** ✅ — spinner claro y ARRIBA en `s-loading-analysis` (lo usan Analizar IA + Ver plan) + imagen reducida 46vh→38vh para que el indicador no quede bajo el corte en iPhone.
- **#4 PDF completo (análisis + plan)** ✅ — YA existía `build_case_pdf` (endpoint `/export.pdf`). Añadido alias `/cases/{id}/full/pdf` + botón "Descargar PDF completo (análisis + plan)" en la pantalla del plan sencillo + i18n. Era problema de descubribilidad.
- **#8 Vídeo más fiable** ✅ — `video_processor` activa `CAP_PROP_ORIENTATION_AUTO` (corrige vídeo girado, causa del "salta un muro") + prompt en `clinical_ai` ahora es PRUDENTE (solo describe lo claramente visible, juzga por contenido no orientación, admite incertidumbre) + usa la descripción del usuario como guía.
- **#9 PDF plan sencillo "incompleto"** ✅ (aclarado) — NO era bug: el plan sencillo es la versión simplificada por diseño. Solución: botón de **PDF completo** (#4) + relabel ("plan sencillo" vs "completo") para que se entienda.
- **#5 Privacidad** → respondido: confirmado en `cases.py`, todo filtra por `user_id`; nadie ve casos de otro.

**Verificación:** Python `py_compile` OK + JS `node --check` OK (7/7 bloques). Pendiente: preview visual (frontend) + decisión de deploy (web Netlify + Railway backend + nuevo build TestFlight, coordinados). Opción: code-review por agente del diff backend antes de desplegar (núcleo de pago).

## REVISIÓN ANTI-BUG (agentes, 2026-06-11) — 9 confirmados (0 blockers), CORREGIDOS

Panel de 7 revisores read-only sobre el diff de los fixes del tester. 0 blockers, 3 high.
Cazó 3 regresiones reales que yo había introducido → **todas corregidas (staged)**:
- 🔴→✅ `rag.py`: la línea de "perro adoptado" se añadía a TODOS los análisis (mutaba el prompt
  del 95% no adoptados) → ahora **condicional** (`if _adopted:`), solo si el tutor aporta el dato.
- 🔴→✅ `clinical_ai.py` (vídeo): el prompt "conservador" suprimía señales sutiles reales y la
  descripción del tutor anulaba los frames → **reequilibrado**: describir señales observables
  (tensión, orejas, peso, mirada) + caption tratado como contexto NO fiable que NO anula el vídeo.
- 🔴→✅ Botón PDF en `s-plan-simple`: puse "completo" como primario en la pantalla accesible →
  **revertido** (plan sencillo primario, completo secundario).
- 🟡→✅ `video_caption` sin cap → recortado a **300 chars** en la ruta (anti prompt-injection/abuso).
- 🟢→✅ `removeVideo()` no limpiaba la descripción → ahora la limpia.
- (LOW dejado a propósito) `video_processor` try/except amplio: está correctamente acotado a la
  única línea `cap.set(ORIENTATION_AUTO)` → solo silencia esa línea opcional, es el comportamiento
  deseado (nunca romper la extracción). No se toca.
- 3 falsos positivos descartados (el alias `/full/pdf` "innecesario" → SÍ se necesita para el helper).

**Estado:** todos los cambios (6 fixes + 5 correcciones) **staged, sintaxis OK, sin desplegar.**
Pendiente: decisión de deploy coordinado (Netlify + Railway + nuevo build TestFlight).

## DEPLOY COORDINADO — HECHO Y VERIFICADO (2026-06-12)

Pase final de confirmación (1 agente read-only) → **SAFE TO DEPLOY** (6/6 PASS, 0 regresiones nuevas).
Deploy con cautela, backend-first, verificando cada paso:
- **Commit** `35755ba` (rebaseado limpio sobre `f3b097e` smoke-tests remoto, sin conflictos — solo mis 9 archivos). `mobile/` + docs fuera del commit (stash temporal durante rebase).
- **Backend Railway** (auto-deploy on push a main): LIVE. health 200; OpenAPI servido por la app expone `/cases/{id}/full/pdf` + param `video_caption` → código nuevo corriendo (autoritativo, sin race).
- **Frontend Netlify** site `thedogsmind-prod` (152389f9): draft `6a2c372a…` verificado (SW v197 + marcadores) → promovido a prod `6a2c3749…`. thedogsmind.net sirve `CACHE_NAME='dogs-mind-v197'`, campos nuevos presentes, header `cache-control: no-cache,must-revalidate` en index.html (refresh inmediato).
- **SW** v196 → **v197** (CACHE_NAME + header). netlify.toml: fix publish path + headers seguridad/cache.

⚠️ PENDIENTE: nuevo build TestFlight (cap sync + archive + upload) para que Cecilia/Niaz reciban los fixes en la app nativa. Interacciona con el estado de beta review del build 3 → evaluar antes de subir build 4.

## (añadir más a medida que el founder pruebe)
