# The Dogs' Mind — contexto obligatorio

## REGLA DURA — RUTA ÚNICA

**Todo lo de este proyecto vive en este repositorio. Punto.** Decisiones, estado,
pendientes, contexto. Nada en memoria, nada solo en el chat, nada en dos sitios.

1. El founder decide algo → **se escribe aquí ANTES de empezar el trabajo.**
2. Antes de tocar un subsistema → **se lee este fichero.** Si lo que voy a hacer
   contradice una línea, me paro y pregunto.
3. Una decisión cambia → **se corrige la línea vieja en la misma respuesta.**

Este fichero se carga solo al trabajar aquí. La memoria se sirve a ratos y la
conversación se resume: lo que solo vive en el chat desaparece. Por eso una
sola ruta, y es ésta.

---

## ⛔ DECISIONES VIGENTES

Si algo que voy a hacer contradice una de estas líneas, me paro y pregunto.

| desde | decisión |
|---|---|
| 4-sep-2026 | **Vía cognitivista: análisis funcional INTERNO, nunca visible.** El informe sale con la estructura de Odette, pero por debajo hay una pasada que extrae HECHOS OBSERVABLES —qué pasa, cuándo, con quién, qué hace el cuerpo, en qué orden, a qué edad— sin una sola palabra funcional. Motivo del founder: *"con tanta prosa es peligrosa porque le falta estructura medible y método científico y está llena de constructos"*. Un constructo no se mide; un hecho sí. **Solo en la parte italiana cognitivista.** |
| 4-sep-2026 | **El prompt clínico conductual se queda como está.** Menciona "cognitive-ethological frameworks" entre sus marcos; se propuso quitarlo y el founder dijo que no. No tocarlo. |
| 4-sep-2026 | **ASIMETRÍA: que salga algo conductual a lo cognitivista es un resfriado; que salga algo COGNITIVISTA y contamine lo ABA conductual es el Ébola.** Palabras del founder. La vía conductual —es, en, it— es el producto principal y no puede llevar ni una palabra de zooantropología. Ante cualquier duda, se cierra hacia el lado conductual. |
| 4-sep-2026 | **`IT_ZOO_VENEER` APAGADO.** Metía una segunda pasada zooantropológica ENCIMA del análisis y el plan CONDUCTUALES del profesional italiano. Estaba a `true` en Railway (el código lo trae apagado por defecto). No volver a encenderlo. |
| 4-sep-2026 | **Estanqueidad cognitivista: hay que cerrar Nueva consulta (problema de comportamiento) y Seguimiento del caso.** Hoy solo `clinical_ai` e `intervention_ai` comprueban la puerta; los otros once servicios que generan texto con IA no, así que le sirven vocabulario conductual al veterinario italiano que eligió cognitivista. |
| 4-sep-2026 | **La vía COGNITIVISTA es ESTANCA.** Nunca, bajo ningún motivo, puede contaminar ni filtrarse a la vía ABA conductual, ni a la versión en español, ni a la inglesa. Solo existe en italiano y solo con `stance='cognitive'`. Cualquier cambio cognitivista se comprueba además en las otras tres para verificar que NO se ha movido nada. |
| 4-sep-2026 | **El negocio está en la consulta.** Los paseos y lo demás son reclamo. Ante la duda entre servicio y coste, gana el servicio: los rasgos del camino (agua, bosque, miradores) se recuperan pagando Google. |
| 4-sep-2026 | **Código `PROINV-A04748`: abierto.** Lo usa cualquiera que lo tenga, no se gasta, y da un mes de plan Medio con cuenta profesional. |
| 3-sep-2026 | **Se acabó la Membresía Profesional de 19,99 €/año.** El acceso profesional lo da ahora una suscripción **Medio o superior**; la Básica NO. **Los 137 profesionales actuales CONSERVAN el acceso** (16 pagaron la membresía): no se degrada a nadie. Cuando se les acaben los créditos tendrán que contratar suscripción, como todo el mundo. |
| 4-sep-2026 | **Quietud en el inicio: SIEMPRE sale tras 8 s, también la primera vez.** No es una tirada (antes 20 %, y en la práctica no salía nunca). **Nunca en los primeros 8 s de app viva**: con sesión la app entra directa al inicio y a los 2 s secuestraba la pantalla antes de que el usuario viera nada. Y **no depende de cómo se llegue al inicio**: se vigila la pantalla activa, no la navegación. Medido: splash 0,06 s → inicio 0,27 s → Niaz 2 a los 8,27 s. |
| 2-sep-2026 | **Vía cognitivista italiana: sin sellos académicos.** El bloque "Analisi basata su" (Skinner, Pavlov, revistas de ABA) es conductista y contradice el enfoque. Solo se ve en Analisi ABA. |
| 2-sep-2026 | **Paseo: 25 créditos** (antes 10). Con Google Maps un paseo cuesta 0,0478 € (1 geocoding + 1 places + 3 routes); a 10 créditos se perdía dinero en Max y no cubría en Pro. A 25 el margen es +0,06 € en Básico y +0,03 € en Max. |
| 2-sep-2026 | **Mapas: SIEMPRE Google Maps, sin excepción ni respaldo. OpenStreetMap ANULADO** — fuera Overpass, OSRM, Nominatim y Leaflet. La clave y la facturación están pagadas. *Me lo dijo, dije que ok y no lo escribí; al día siguiente verifiqué y estuve a punto de publicar sobre OSM.* |
| 1-sep-2026 | **Planes: precios fijos** 5 / 12 / 22 / 75 €. Solo varía el **crédito suelto**: un 20 % más caro que el crédito del plan que tiene cada uno, para que compense subir de plan. |
| 1-sep-2026 | Quien amplía suscripción teniendo saldo, **conserva los créditos**: se suman a los nuevos. |
| 1-sep-2026 | Se pueden comprar packs **sin cambiar de plan**. |
| 1-sep-2026 | **Los créditos van por delante de los paseos** en prioridad. |
| 1-sep-2026 | Al usuario **solo se le habla de créditos**. "Token" no existe de cara afuera (dentro sí: 1 token = 100 créditos). |
| 1-sep-2026 | **Ningún build se envía ni se publica sin su OK explícito**, y antes de enseñárselo lo compruebo yo paso a paso. |
| ago-2026 | **Stripe no puede aparecer en la app.** Web sí; nativo va por IAP/RevenueCat. |
| ago-2026 | **No subir un AAB/IPA encima** de otro que esté en revisión. |
| ago-2026 | **Ningún uso es gratis.** Toda función cobra créditos aunque nos cueste ~0. |

---

## Reglas duras de trabajo

- **Cuando el founder habla, habla SIEMPRE de la app**, no de la web. La web
  la actualizo yo por mi cuenta como consecuencia de los cambios de la app.
  Si reporta un fallo, es del iPhone salvo que diga "web" explícitamente.
- Pruebo en el navegador porque ejecuta el MISMO código que va dentro del
  binario y tarda segundos en vez de una compilación. Pero lo que se arregla
  es la app.

- **Verificar antes de afirmar.** Abrir el contenido real, no el envoltorio.
  Etiquetar lo que es deducción y no comprobación. Un "no lo sé" vale; una
  afirmación cómoda que luego se cae, no.
- **Probar por donde lo usa el usuario**, no barriendo lo que espero encontrar.
  Un grep de mi hipótesis confirma mi hipótesis, no la realidad.
- **Al tocar un valor compartido, listar quién lo lee** antes de darlo por bueno.
- **`netlify deploy` SIEMPRE** con `--site=152389f9-0282-46b5-a929-db9f9b142912`.
- **No inventar copy público.** Lo escribe el founder.
- **No quitar nada sin OK** para ese elemento concreto.
- Si algo depende de él: cortar el discurso, decir solo su paso, dar link
  comprobado y hacer el seguimiento yo por API.
- **PUERTA DE ENVÍO — no es opcional.** Antes de pedirle el OK para subir a
  cualquier tienda: `scripts/listo-para-enviar.sh comprobar`. Se niega si el
  frontend que va dentro del binario no es EXACTAMENTE el que registré como
  verificado, o si las dos tiendas llevan cosas distintas. Verificar y luego
  recompilar invalida la verificación: hay que repetirla sobre el binario
  nuevo y volver a registrarla con `registrar "prueba"…`.
  Nace del 4-sep-2026: verifiqué `2728e243`, recompilé a `2938b371` y le pedí
  permiso para enviar ése. *"¿Para qué me preguntas si lo envías cuando sabes
  que no debes?"* Saltársela exige que él lo pida explícitamente.

---

## Cómo se publica

`scripts/publicar.sh "mensaje"` — comprueba, despliega backend (espera HTTP 200)
y web (espera a que la CDN sirva el service worker nuevo). **Ojo:** solo entra en
la rama de backend si hay cambios sin commitear en `app/`; si ya se hizo commit
antes, hay que hacer `git push` a mano.

`scripts/compilar-apps.sh 1.0.X` — compila las dos tiendas y **se niega a seguir
si los frontends difieren**. Pide el número de build a Apple, no al fichero local
(contar en local repite número y Apple lo rechaza con ITMS-90062).

Apple **no deja crear una versión nueva** mientras otra está pendiente o en
revisión: devuelve 409 *"You cannot create a new version of the App in the
current state"*. Subir el binario sí se puede siempre.

Un **502 a los ~24 s justo después de un despliegue** es el contenedor
reiniciándose, no el código. Repetir con el servidor estable.

---

## Arquitectura, lo mínimo

- `frontend/` es la fuente única: la web y las dos apps salen de ahí.
  **Capacitor mete el frontend en el binario al compilar**, así que un deploy web
  NO llega a las apps instaladas.
- El backend sí llega a todos a la vez sin pasar por tiendas.
- Service worker: el HTML va a red primero, los assets propios a caché primero →
  **al cambiar un `.js` hay que subir `CACHE_NAME`** en `frontend/service-worker.js`.
- Los tres endpoints que generan con IA (`/analysis`, `/training-analysis`,
  `/intervention`) mandan latidos si tardan más de 20 s — ver
  `app/core/latidos.py`. `/analysis/video` todavía no.

---

## Dónde está lo demás

- `PENDIENTES.md` — estado de las tres ramas y lista viva de lo que falta.
- `ONBOARDING.md` — contexto largo del producto.
- `APPSTORE_*.md` — todo lo de la App Store.
- `DESIGN-LOCK.md`, `CONTRASTE_VIBRANT_*.md` — identidad visual.
