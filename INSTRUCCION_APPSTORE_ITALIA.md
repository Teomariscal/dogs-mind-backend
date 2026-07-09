# Instrucción para Code — Build iOS con cambios Italia + App Store

**Objetivo:** empaquetar en un **build iOS nuevo** todos los cambios de idioma + diseño + heros que YA están en `frontend/index.html` (y en git `main`) y subirlo a App Store Connect. Los cambios están LIVE en web (thedogsmind.net) pero el binario iOS empaqueta su propia copia del frontend → hay que reconstruir para que la app los tenga.

## Contexto (leer primero)
- Lee la memoria `project_dogs_mind_italia_cognitivista.md` y `project_dogs_mind_appstore_submit_state.md` (pipeline exacto + gotchas + credenciales ASC).
- Repo: `~/Downloads/dogs-mind-backend`. Frontend empaquetado: `frontend/index.html` (Capacitor `webDir: '../frontend'`).
- **Backend YA desplegado en Railway** (git push): `plan_simple_ai.py` + `abc_explained_ai.py` con rama italiana, vía cognitivista (`IT_COGNITIVE` default ON, gateado a it+professional+stance=cognitive). NO hay que tocar backend.
- El frontend vivo (web, SW v213) = git `main` HEAD (`e363d9f`). Están commiteados. El working tree debe estar limpio.

## Qué cambios entran en el build (todos ya en git main)
1. **Vía cognitivista italiana**: selector "Analisi ABA / Analisi Cognitivista" al inicio de `s-anamnesis` (solo `lang=='it'`), envía `stance` en `/analysis`, `/analysis/video`, `/intervention`. Cognitivo salta la pantalla ABC → directo a `s-full-analysis`; reabrir caso cognitivo también (deduce postura del texto). Commits `a708f18`, `b6c70bf`, `f1bc801`, `0123493`, `f69af21`.
2. **Hero visual** `frontend/full-analysis-hero.jpg` (1600×1066) al inicio de todos los análisis completos, alto 210px. Commit `7d4a9a1`. **Verificar que el jpg está trackeado en git** (`git ls-files | grep full-analysis-hero`).
3. **Idioma es→it**: plan-simple/spiega italiano (backend), strings de carga/vacío del plan (`interv_loading`/`interv_empty_*` data-i18n it), título de carga JS. Commit `f69af21`. ⚠️ Quedan ~27 ternarios en pantallas secundarias que aún caen a español — NO bloquean el build.
4. **Diseño encabezados premium**: `markdownToHtml` con h1/h2 en Cormorant (`--ff-serif`) esmeralda + underline cyan #5ec8e6, h3 teal #2a7a9a; guiones markdown eliminados (strip decorativo ampliado). Commit `f98569e`.
5. **Fix layout botones** piano semplice/abc-translated (footer ya no tapa texto). Commit `e363d9f`.

## Pipeline de build (de la memoria appstore — verificar antes de ejecutar)
Estado ASC actual: **1.0.2 build 22** (verificar por API en qué estado está: si 1.0.1/1.0.2 sin publicar, decidir con el founder si se crea versión nueva o se reemplaza el build). `CURRENT_PROJECT_VERSION = 22` en pbxproj → **subir a 23** para el build nuevo.

1. `git pull origin main` (asegurar HEAD = `e363d9f` o posterior). Working tree limpio.
2. Verificar JS: extraer bloques `<script>` no-src de `frontend/index.html` y `node --check` cada uno (ya validado en cada commit, re-confirmar).
3. Bump `CURRENT_PROJECT_VERSION = 22;` → `23;` (2 ocurrencias) en `mobile/ios/App/App.xcodeproj/project.pbxproj`. Decidir con founder si `MARKETING_VERSION` sube (1.0.2→1.0.3 o 1.1) según si 1.0.2 ya está publicada.
4. `cd mobile && npx cap sync ios` (dangerouslyDisableSandbox).
5. Archive + export + upload con las auth keys (ver comando exacto en `project_dogs_mind_appstore_submit_state.md` sección "PIPELINE DE BUILD"). Todo `dangerouslyDisableSandbox`.
6. Poll build por ASC API hasta VALID → asignar a TestFlight beta group → adjuntar a la versión.
7. Verificar los **4 IAP** siguen adjuntos (API da falsos 404; comprobar en UI).
8. `PRO_PROMO_FREE=false` confirmado (Pro de pago) antes de enviar.
9. Capturas/metadata: si el founder quiere capturas nuevas mostrando la vía cognitivista italiana, es paso aparte (decisión suya).
10. **El clic final "Añadir a revisión" lo da el FOUNDER**, no la sesión.

## Reglas duras
- Prod con usuarios de pago: no romper nada. Backend ya live, no re-tocar.
- Verificar cada paso; si algo falla, parar y reportar.
- No inventar copy ni assets; los aporta el founder.
- Rechazo estimado 15-25% (comodines 4.7 IA / 4.2 web-wrapper). Si rechazan → Resolution Center.
