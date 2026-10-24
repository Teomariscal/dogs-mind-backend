# Notificaciones push de reactivación

## ESTADO REAL, 23-oct-2026 — LOS CUATRO ESLABONES

Founder: *"metelo en el siguiente build y lo ponemos en cola y meto mis
credenciales en firebase pero operar tu con el"*.

Medido, no supuesto. `scripts/push-vivo.sh` comprueba los cuatro en cada envio
y la puerta de `listo-para-enviar.sh` se niega mientras alguno falle.

| # | eslabon | estado | de quien |
|---|---|---|---|
| 1 | la app pide permiso y registra el token | **CODIGO HECHO**, falta build | mio |
| 2 | los tokens llegan (`push_devices`) | 0 filas, sera consecuencia del 1 | — |
| 3 | el servidor habla con Apple/Google | **FALTAN CREDENCIALES** | **founder** |
| 4 | alguien ejecuta la pasada cada hora | no existe | mio |

### Lo hecho el 23-oct

- `@capacitor/push-notifications@8.1.3` instalado. **Android compila con el
  plugin dentro** — probado, no supuesto: `google-services.json` hace falta en
  ejecucion, no al compilar, asi que la cadena de build no se rompe mientras
  llegan las credenciales.
- `window.dmPush` en el frontend: `pedir()` y `refrescar()`.
- **El permiso se pide al ACEPTAR UN PLAN**, no al arrancar la app. Pedirlo al
  abrir es la forma mas rapida de que digan que no para siempre: en iOS la
  negativa solo se revierte en Ajustes, donde no entra nadie. Al aceptar un
  plan el usuario acaba de comprometerse a hacer ejercicios cada dia, que es
  justo lo que el aviso recuerda.
- `refrescar()` al abrir con sesion y permiso ya dado: **el token de FCM rota
  solo** (reinstalacion, restauracion desde copia, decision de Google) y un
  token muerto es un movil al que creemos estar avisando y no lo estamos. El
  envio no falla de forma visible, asi que nadie se entera: es la misma familia
  de fallo que todo esto.
- **PUSH_NOTIFICATIONS activado en el App ID** `net.thedogsmind.app`
  (`M98KSFJUJU`) por API. Sin esto, añadir el entitlement habria roto el build
  de iOS. Confirmado leyendo de Apple: `['IN_APP_PURCHASE','PUSH_NOTIFICATIONS']`.
  Ojo: `GET /bundleIdCapabilities` devuelve lista VACIA aunque esten activadas;
  hay que leerlo con `?include=bundleIdCapabilities`.

### Lo que falta, y en este orden

1. **Founder** — en Firebase, con `net.thedogsmind.app` en las dos:
   `google-services.json` (Android) · `GoogleService-Info.plist` (iOS) · la
   clave APNs `.p8` subida en Cloud Messaging · el JSON de cuenta de servicio.
2. **Yo** — `FCM_PROJECT_ID` y `FCM_CREDENTIALS_JSON` en Railway, el
   entitlement `aps-environment` en iOS, y el disparador horario (eslabon 4).
3. **Build** con todo dentro. En cola a proposito: sin el 1 no hay nada que
   probar de verdad.

### Y los textos

Los de reactivacion los escribio el founder (abajo). Los de **"se te acabo la
invitacion, contrata un plan"** NO existen todavia y **los pone el**: no se
inventan.



Encargo del founder, 10-oct-2026: que quien lleva tres días sin usar la app
reciba un aviso en el móvil que le recuerde volver.

---

## ⛔ LOS TEXTOS SON DEL FOUNDER — APROBADOS 10-oct-2026

**No se tocan, no se "mejoran" y no se añaden variantes nuevas sin que las
escriba él.** Las versiones en inglés e italiano son traducción en intención,
con los términos que la app ya usa: *seguimiento* → `follow-up` / `monitoraggio`,
*adiestramiento* → `training` / `addestramento`.

Van partidos en **título + cuerpo** porque en la pantalla bloqueada el cuerpo se
corta sobre los 110 caracteres, y el texto 1 entero son 148: sin partir, la
frase que remata quedaba escondida.

### 1 · `con_casos` — tiene uno o más casos guardados

| | título | cuerpo |
|---|---|---|
| ES | No me creo que vayas a aflojar el ritmo | Un problema de conducta exige constancia. Tú eres una persona constante. Tienes seguimientos esperándote. |
| EN | I don't buy that you'll ease off now | A behaviour problem demands consistency. And you are a consistent person. You have follow-ups waiting. |
| IT | Non ci credo che adesso molli | Un problema di comportamento richiede costanza. E tu sei una persona costante. Hai dei monitoraggi che ti aspettano. |

### 2 · `nunca_probo` — se registró y nunca generó nada

| | título | cuerpo |
|---|---|---|
| ES | ¿Has probado la app? | Échale un vistazo, porque te vas a sorprender. |
| EN | Have you tried the app? | Take a look — it is going to surprise you. |
| IT | Hai provato l'app? | Dacci un'occhiata: ti sorprenderà. |

### 3 · `probo_y_no_siguio` — generó algo y no volvió

| | título | cuerpo |
|---|---|---|
| ES | Hace días que no te vemos | Asómate de nuevo a The Dogs' Mind: soluciona cualquier problema de conducta canina o diseña el mejor plan de adiestramiento. |
| EN | We haven't seen you in days | Come back to The Dogs' Mind: solve any dog behaviour problem or design the best training plan. |
| IT | Non ti vediamo da giorni | Rifatti vivo su The Dogs' Mind: risolvi qualsiasi problema di comportamento del cane o progetta il miglior piano di addestramento. |

**Sin nombre del perro.** Se le ofreció y no lo pidió: el texto 1 habla de la
persona, no del perro. Si algún día quiere una variante con `{perro}`, la
escribe él.

---

## Reglas de producto (del encargo)

| | |
|---|---|
| Frecuencia | Un envío cada **3 días** como máximo por usuario |
| Tope | **2 por semana** (7 días naturales) |
| Hora | Hora **local** del usuario, ventana **10:00–20:00**. Nunca de madrugada |
| Interruptor | Desactivables desde ajustes. Apple lo exige |
| Rotación | El texto depende del segmento; dentro del segmento no se repite el mismo dos veces seguidas si hubiera varias variantes |
| Permiso | Explícito. Si lo deniega, la app funciona igual. Android 13+ pide `POST_NOTIFICATIONS` |

---

## Idioma: resuelto, y sale gratis

El idioma **no** está en `users`: viaja en cada petición y solo se guarda en
`cases.lang`. De los 434 usuarios reales del 10-oct-2026, 141 tienen idioma
conocido por su último caso (120 es · 12 en · 9 it) y 293 no.

No importa. Una notificación solo llega a quien tenga **token de dispositivo**, y
el token solo existe desde la versión que lo registra — y en esa misma llamada
va el idioma de la interfaz. De todo el que pueda recibir push sabemos el idioma
al 100 %. Se guarda en `push_devices.lang` y se refresca en cada registro, por si
cambia la interfaz.

Mismo razonamiento para la **zona horaria**: la manda el dispositivo al
registrarse (IANA, `Intl.DateTimeFormat().resolvedOptions().timeZone`). Sin ella
no se puede respetar la hora local, y deducirla del país de la delegación sería
adivinar.

---

## Reparto del trabajo

**Backend — llega a todos sin pasar por tiendas:**

| | qué | estado |
|---|---|---|
| 1 | `users.last_seen_at` + `users.push_enabled` | hecho |
| 2 | Tabla `push_devices` (user, token, plataforma, lang, tz, estado) | hecho |
| 3 | Alta y baja de token, e interruptor | hecho |
| 4 | Selección de segmentos y topes de frecuencia | hecho |
| 5 | Envío contra FCM (sirve para Android **y** para iOS vía APNs) | hecho, a la espera de credencial |
| 6 | `POST /push/run`, protegido. **En seco por defecto** | hecho |
| 7 | **El disparo horario NO está montado.** Se decide cuando haya credencial de FCM: hasta entonces no hay nada que disparar | pendiente |

Comprobado en producción el 10-oct-2026, no deducido: `last_seen_at` llega NULL
al registrarse y queda sellado tras la primera petición autenticada; el alta de
dispositivo guarda plataforma, idioma y zona; el interruptor se lee y se cambia;
las tres guardas contestan 401/401/403 sin credenciales. Y contra la base real:
los tres segmentos se detectan bien, quien entró hace un día no sale, quien no
tiene zona horaria tampoco, la segunda pasada seguida da cero por el tope de 3
días, y apagar el interruptor baja la cuenta.

**App — exige versión nueva en las dos tiendas:**

| | qué | depende de |
|---|---|---|
| 8 | `@capacitor/push-notifications`, capacidad en Xcode | — |
| 9 | **Clave APNs** en Apple Developer | **founder** |
| 10 | **Proyecto Firebase + `google-services.json`** | **founder** |
| 11 | Pedir permiso, coger token y mandarlo al backend | 8, 9, 10 |
| 12 | Interruptor en ajustes | — |

Dos variables de entorno en Railway cuando lleguen las credenciales:
`FCM_PROJECT_ID`, `FCM_CREDENTIALS_JSON` (el JSON entero de la cuenta de
servicio). Y `PUSH_CRON_KEY` para que el disparo horario pueda llamar a
`/push/run` sin sesión de usuario.

`last_seen_at` es lo que distingue «entró» de «consultó»: `usage_log` solo
registra llamadas facturables, así que quien abre la app a mirar su plan no
aparece ahí. Se actualiza en `get_current_user`, que es por donde pasa toda
petición autenticada.
