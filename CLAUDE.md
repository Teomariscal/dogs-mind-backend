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
