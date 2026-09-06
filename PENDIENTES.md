# Pendientes — The Dogs' Mind

## ⛔ DECISIONES VIGENTES — leer ANTES de tocar nada

Cada linea es una decision del founder con su fecha. Si algo que voy a hacer la
contradice, me paro y pregunto. **Se escribe aqui EN EL MOMENTO en que la dice,
antes de empezar el trabajo**, no despues: una decision que solo vive en el chat
desaparece cuando la conversacion se resume.

| desde | decision |
|---|---|
| 2-sep-2026 | **Mapas: SOLO Google Maps. OpenStreetMap queda anulado** (Overpass, OSRM, Nominatim y Leaflet fuera). La clave y la facturacion ya estan pagadas. Me lo dijo, dije que ok y NO lo escribi: al dia siguiente verifique y publique sobre OSM. |
| 1-sep-2026 | Los planes mantienen sus precios (5/12/22/75 €). Solo varia el credito suelto: un 20 % mas caro que el del plan de cada uno, para que compense subir de plan. |
| 1-sep-2026 | Los creditos van por delante de los paseos. |
| 1-sep-2026 | Ningun build se envia ni se publica sin su OK explicito, y antes de enseñarselo lo compruebo yo paso a paso. |
| 1-sep-2026 | Al usuario solo se le habla de **creditos**. Los tokens no existen como concepto de cara afuera. |


Lista viva. Se actualiza en cuanto algo entra o sale. Última revisión: 1-sep-2026, 23:05.

## Estado de las ramas — 5-sep-2026

| rama | versión | estado |
|---|---|---|
| Web | v295 | en vivo, con Ale, el área profesional y el ajuste de escritorio |
| Backend | Google Maps + latidos | desplegado, Railway SUCCESS |
| Google Play | **1.0.14 (30)** | publicada en producción |
| App Store | **1.0.14 (build 49)** | **APROBADA Y EN VENTA.** Salió sola, sin pulsar Publicar |

## 6-sep — "el muro de pago vuelve a salir vacío": era un build viejo

**Síntoma:** captura de TestFlight, pantalla Elige tu plan con el saldo en guion,
sin un solo plan y **sin mensaje de error**.

**No es una regresión.** El arreglo está intacto en lo que hay publicado. La
fecha lo cierra:

| | |
|---|---|
| builds 47 y 48 subidos a Apple (= **1.0.12**) | 1-sep 08:22 y 08:55 |
| commit `a4d55ba` que arregla el muro | **1-sep 17:41** — nueve horas después |
| build 49 (= 1.0.14), primero que lo lleva | 4-sep |

Comprobado, no deducido: `git show a4d55ba^:frontend/index.html` tiene **cero**
apariciones del gancho y el commit las deja en una. Y el gancho **sí** está
dentro del IPA del build 49. Con sesión real en producción (cuenta de revisión,
22.395 créditos) la pantalla pinta los 4 planes y el saldo correcto.

**Por qué no deja ni rastro de error:** en ≤48 nadie llama a `dmCargarPlanes()`
al entrar por la píldora del saldo, así que la función no llega a ejecutarse.
No hay "Cargando planes…" ni error porque no corre nada: el HTML se queda como
nació. Por eso la captura enseña el guion original.

**Qué hace falta:** actualizar la app del teléfono. TestFlight **no se actualiza
solo**.

**La lección, que es la parte que se repite:** un fallo reportado desde el móvil
no se diagnostica contra el repositorio, sino contra **el binario que tiene él
instalado**. Ver la regla en `CLAUDE.md`.

Cerrado desde la última revisión: créditos, muro de pago vacío, corte de conexión
en los análisis, paseos migrados a Google Maps, italiano colándose en español,
sellos fuera de la vía cognitivista, membresía de 19,99 retirada, acceso
profesional por suscripción Medio+, clasificación por edades respondida, área
profesional con su tarjeta, y Ale en la quietud del inicio.

Pendiente de compilar en la 1.0.15: **Ale** (solo está en web).

## Cerrado hoy — el usuario de pago que no podia analizar

**Sintoma:** "Error de conexion. El analisis puede haberse completado igualmente"
al pulsar Analizar con IA en la web de escritorio. NO era la etiqueta de creditos.

**Causa, medida contra produccion:** el analisis tarda 66,6 s y la respuesta
llegaba entera al final, asi que la conexion pasaba mas de un minuto sin enviar
un solo byte. Los proxies que cortan por inactividad a los 60 s la mataban. Por
eso le pasaba a el y no a otros: depende de su red.

**Arreglado** (`app/core/latidos.py`, aplicado a los TRES endpoints que generan
con IA): si tarda mas de 20 s se mandan
espacios cada 5 s. Un JSON admite espacios delante, asi que el cliente sigue
haciendo `res.json()` y no hay que tocar la app — cubre iOS, Android y web a la
vez, incluidas las versiones ya instaladas, sin pasar por tienda.
Medido en produccion, primer byte:

| endpoint | antes | ahora |
|---|---|---|
| `/analysis` (Problema de conducta) | 66,6 s | 20,1 s |
| `/training-analysis` (Educacion y entrenamiento) | 45,2 s | 21,2 s |
| `/intervention` (plan) | — | envuelto igual |

El corte de jpcarmid estaba entre 45 y 66 s: por eso le funcionaba uno y el otro
no. A las 22:46, ya con el arreglo, su `/analysis` salio bien y se cobro una sola
vez (saldo 4450 -> 4150).

OJO al probar justo tras un despliegue: un 502 a los ~24 s es el contenedor
reiniciandose, no el codigo. Repetir con el servidor estable.

Comprobado en produccion: camino rapido intacto (cacheado 0,18 s, cero latidos),
422 y 401 intactos, y se cobra exactamente una vez.

**Al usuario:** que reintente con la MISMA anamnesis. La idempotencia le devuelve
lo ya generado al instante y sin cobrar (medido: 0,17 s, 0 creditos).

## Prioridad

**Los créditos van por delante de los paseos** (founder, 1-sep-2026): "los paseos
son poco importantes en comparación con los créditos". Por eso la 1.0.12 se deja
pasar en revisión aunque no lleve paseos, en vez de sacarla y rehacerla.

- [x] **Créditos**: saldo correcto, muro de pago que ya no sale vacío, banner de
  bienvenida, mensajes de saldo y páginas legales.
  Web v288 · Google Play 1.0.12 (26) publicada · App Store 1.0.12 en revisión.

- [ ] **Paseos: arreglado en web (v288), falta en las apps → va en la 1.0.13.**
  Causa real, medida el 1-sep: **los tres servidores de Overpass caídos a la vez**
  (el principal corta la conexión, los dos espejos dan 502). No cambió nada del
  código; se cayó el servicio público gratuito que busca parques. OSRM, que es
  quien calcula la ruta, estaba y está perfecto.
  Lo arreglado en `web-walk.js`:
  1. `generar()` ya no corta cuando no hay sitios. El plan B por rumbo existía
     desde hacía semanas pero era inalcanzable: había un `return` veinte líneas
     antes.
  2. Overpass pasa a tener plazo de 10 s en total. Antes eran 3 servidores × 2
     vueltas × 25 s, repetido para 3 radios: más de siete minutos en "buscando".
  3. Divisor del plan B de 3.2 a 5.0 — la desviación media baja del 57 % al 19 %,
     sin gastar ni una llamada más.
  Comprobado: 12 de 12 rutas con la lista de sitios VACÍA, en ciudad y en pueblo,
  en tres países.

## Decidido, montado a medias, esperando a la 1.0.12

- [ ] **Crédito suelto un 20 % más caro que el del plan.**
  Regla del founder (1-sep): "los planes mantienen los precios", solo varía el
  suelto, "a fin de que les compense subir de plan".
  Escrito y verificado en `app/core/subscriptions.py` (`valor_credito_plan`,
  `valor_credito_suelto`, `tokens_por_recarga`) pero **nadie lo llama todavía**.
  El pack cuesta lo mismo en la tienda y varían los créditos que entrega: así
  bastan los 3 productos que ya existen en vez de los 12 que harían falta si
  variase el precio.

  | plan | €/cr plan | €/cr suelto | pack de 4,99 € |
  |---|---|---|---|
  | Básico | 0,00625 | 0,00750 | 665 créditos |
  | Medio | 0,00556 | 0,00667 | 748 |
  | Pro | 0,00500 | 0,00600 | 832 |
  | Max | 0,00435 | 0,00522 | 956 |

  Falta: las tarjetas de packs del frontend llevan las cifras **a mano**
  (`index.html` ~8600). Si solo cambia el servidor, la app promete 500 y se
  entregan 665. Va de una pieza o no va.

- [ ] **La puerta a créditos sueltos está enterrada.** Vive al final de la
  pantalla de planes, después de los cuatro planes y del texto legal. Quien no
  quiere cambiar de plan tiene que entrar justo donde no quiere entrar.

## Acciones del founder

- [ ] **Clasificación por edades (redes sociales), Apple.** Límite 7-sep-2026, y
  ya se ha enviado una versión, así que puede exigirlo antes.
  https://appstoreconnect.apple.com/apps/6777848632/appinfo

- [ ] **Copy legal de fondo**: `terms.html` apartado 4 y `privacy.html` ya dicen
  "créditos", pero el texto es mío adaptado del suyo. Que lo revise.

## Menor / arrastrado

- [ ] `teo-mariscal-v3.html`: copia del 26-may que sigue publicándose, indexable,
  con 182 menciones a "tokens". Nadie la enlaza desde la app. No se borra sin OK.
- [ ] Código muerto `checkVideoTokens` (`index.html` ~12659): cadena entera
  inalcanzable; si alguien la engancha, muestra tokens en vez de créditos.
- [ ] `payments.py:881` dice "añadir tokens" a propósito: ese endpoint de admin
  suma **tokens** como unidad interna. Renombrarlo sin convertir haría meter 100
  veces de más.
- [ ] `cobrarPaseo()` falla en abierto: si la llamada de cobro cae por red, el
  paseo sale gratis (`catch { return true }`). Previo y parece deliberado.
- [ ] `/analysis/video` sin latidos: ya era async y maneja ficheros subidos, es
  otra estructura. Es el unico de los cuatro que genera con IA sin proteger.
- [ ] Mensajes 402 del backend solo en español (la app pone los suyos traducidos,
  así que hoy no se ven).
- [ ] Vídeos por idioma de Cecilia y Niaz (EN/IT) servidos desde nuestro dominio.
- [ ] Vibración en Inicio, al enviar anamnesis y en los botones de vídeo.
- [ ] Ale al 20 % cuando exista su vídeo.
- [ ] Italiano en la ficha de la App Store (texto promocional ya traducido y
  aprobado).
