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
| Google Play | **1.0.15 (32)** | publicada en producción el 6-sep |
| App Store | **1.0.15 (build 50)** | en revisión; sale sola al aprobarse (AFTER_APPROVAL) |
| App Store | 1.0.14 (build 49) | en venta. Salió sola, sin pulsar Publicar |
| Backend | vía cognitivista de Odette | **DESPLEGADO** el 7-sep |
| Web | pantalla y canal estanco | **EN VIVO** el 7-sep, comprobado en thedogsmind.net |

## 1.0.19 — dónde está cada tienda (9-sep-2026)

| tienda | qué | estado |
|---|---|---|
| App Store | **1.0.19 (build 54)** | **WAITING_FOR_REVIEW**, con `releaseType: AFTER_APPROVAL` — sale sola al aprobarse. También asignado al grupo Internal → visible en TestFlight |
| Google Play | **versionCode 37** | **PUBLICADO en producción al 100 %**. Medido con `tracks().list`: `production completed vc=['37']`. Sustituye a la vc 33 |

Lo que lleva: el subtítulo de Ale traducido, Ale entera con su perra, y los 26
textos que se quedaban en español fuera del español. Verificado sobre el IPA
(md5 `6ab9661072927e0d3de6b294f3469bac`, idéntico en las dos tiendas), no sobre
la copia de trabajo.

### CÓMO SE SUBE A GOOGLE PLAY — estaba solo en mi cabeza

Es lo que faltaba por escribir y me costó media hora encontrarlo. La credencial
vive **fuera del repositorio**, como la `.p8` de Apple:

    /Users/teomariscal/Desktop/PLAY-STORE-subir/CREDENCIAL-REVENUECAT.json
    cuenta de servicio: tdm-play-billing@tdm-play-billing.iam.gserviceaccount.com
    paquete:            net.thedogsmind.app

El nombre del fichero engaña: pone REVENUECAT, pero esa cuenta tiene permisos de
publicación en Play Console. Se usa con `googleapiclient` (ya instalado), y el
camino es siempre el mismo: `edits().insert` → `bundles().upload` (el AAB de
`mobile/android/app/build/outputs/bundle/release/`) → `tracks().update` con
`track='production'` → `edits().commit`.

**El `status` del release decide si sale o no**: `'draft'` lo deja subido y
guardado sin tocar a nadie; `'completed'` lo publica a todos. Subir y publicar
son dos cosas distintas y en Play se separan con esa palabra.

Y para mirar sin tocar: `edits().insert` → `tracks().list` → `edits().delete`.
Un edit sin commit no cambia nada.

## 9-sep — 1.0.18 (build 53) COMPROBADA POR EL FOUNDER EN EL IPHONE

Primer build que él prueba de verdad desde el 31-ago, porque es el segundo que
se asigna al grupo `Internal` (el 52 fue el primero). Sus palabras: *"en test
flight esta bien"* y *"todo ok"*. Confirmado por él, en el teléfono, no por mí
contra el repositorio:

| qué | estado |
|---|---|
| Selector **Analisi ABA / Analisi Cognitivista** en italiano | SALE |
| El inicio se ve unos segundos tras el vídeo del perro en la playa | SÍ — el `intro-overlay` ya no deja contar la quietud |
| El botón pequeño pone **"Don't show"** | SÍ |

Con esto se cierran los tres fallos abiertos de la semana: la vía cognitivista
que rompí el 7-sep con el `dm_account_type` (revertida), Niaz 2 saltando detrás
del vídeo de bienvenida, y el silencio sin marcha atrás.

**8-sep: la vía de Odette YA VA EN LAS APPS.** Apple aprobó la 1.0.15 y eso
desbloqueó la 1.0.16: **Google Play publicada (vc 33)** y **App Store build 51
en revisión**, con salida automática al aprobarse. Verificada sobre el binario:
36 combinaciones en vivo con cero fugas, el canal estanco cerrado por los tres
lados (entrar, salir y cambiar de idioma) y la puerta del servidor con 11/11.

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

## Medio plazo — NO activo

- [ ] **Red profesional: círculos de clientes alrededor de un profesional.**
  Diseñado y acordado el 7-sep-2026, **sin construir y sin publicar** (founder:
  *"no lo publiques, es un trabajo a medio plazo"*). El profesional paga una
  licencia, cada cliente paga su suscripción, y el cliente entra con un código
  aceptando compartir un perro concreto. Diseño completo en
  `SPEC_RED_PROFESIONAL.md`. Quedan tres decisiones suyas anotadas ahí, y obliga
  a actualizar las fichas de privacidad de Apple y Google.

## Cecilia en la quietud — falta su vídeo

**Guion del founder, 8-sep-2026. Va LITERAL, no se toca una coma:**

> Estás en una app sustentada por principios científicos. Tu herramienta perfecta
> para solucionar un problema de conducta de tu perro, establecer una estrategia
> para enseñarle un ejercicio, o crear un plan de educación temprana. A veces los
> términos pueden abrumar, especialmente si no eres profesional; no te preocupes,
> para eso estoy yo durante todo el análisis. Si tienes la más mínima duda,
> consúltame durante el proceso y te explicaré todo de la forma más sencilla
> posible. Quiero felicitarte porque has elegido una magnífica herramienta.
> Entra en nueva consulta y compruébalo.

**Version recortada a 25-30 s (founder, 8-sep-2026: "reduce texto y dejalo en
25-30 seg"). MEDIDA con sintesis de voz, no estimada: 78 palabras, 25,5 s.
El original eran 90 palabras y 30,5 s. PENDIENTE DE SU VISTO BUENO:**

> Estás en una app sustentada por principios científicos. Tu herramienta perfecta
> para solucionar un problema de conducta de tu perro, enseñarle un ejercicio o
> crear un plan de educación temprana. A veces los términos pueden abrumar, sobre
> todo si no eres profesional; no te preocupes, para eso estoy yo durante todo el
> análisis. Consúltame en cualquier momento y te lo explicaré de la forma más
> sencilla posible. Has elegido una magnífica herramienta. Entra en nueva consulta
> y compruébalo.

Lo quitado: "establecer una estrategia para" (queda "enseñarle un ejercicio"),
"Si tienes la más mínima duda ... durante el proceso" (queda "en cualquier
momento") y "Quiero felicitarte porque" (queda "Has elegido").

**La imagen:** NO es un vídeo nuevo desde cero. Es **el mismo de onboarding**
(`onboarding-cecilia.mp4`) con dos cambios: **fuera la fusta** —que lleva en la
mano DERECHA— y **el shih tzu en esa mano**. El casco de la izquierda se queda.
Es una edicion generativa, no un recorte: la lanza el founder.
Referencias entregadas el 8-sep: el frame base 1080x1920 y el recorte del shih
tzu de `aigents-final.webp`.
Formato de salida, el de sus hermanos: 1080x1920 o 576x1024, H.264 + AAC.

### Estado al 8-sep-2026, 19:30

**HECHO:** el avatar nuevo está creado en HeyGen — "Cecilia TDM with her puppy",
sin fusta, con el shih tzu de Los Aigents en el brazo derecho, el casco en el
izquierdo, misma cara y mismo fondo dorado. Hay seis variantes guardadas del
look. Aprobado por el founder: *"está fenomenal con el perro"*.

**Guion final, 29,2 s** según la línea de tiempo de HeyGen (73 palabras).
Es la versión de arriba menos "perfecta", "pueden" y "no te preocupes,".

**Voz elegida: `Catalina - Warm`** — la ÚNICA femenina chilena de la biblioteca
de HeyGen (*Youth, Explainer, Ads, E-learning*, motor Azure). El founder pidió
chilena, ~30 años, profesional y amable; encaja salvo que HeyGen la etiqueta
como *Youth*, así que puede sonar más joven. OJO: existe también
`Catalina - Professional`, que es ESTADOUNIDENSE, no chilena.

**BLOQUEADO POR HEYGEN.** El render final devuelve siempre *"Idioma no
compatible — Tu guion está en Spanish, y el motor de esta voz no lo admite"*.
Probadas SEIS combinaciones, todas fallan:

| motor | voz | look |
|---|---|---|
| Avatar III | Lucia (Google, ES) | inglés |
| Avatar IV | Lucia | inglés |
| Avatar V | Lucia | inglés |
| Avatar V | Catalina (Azure, CL) | inglés |
| Avatar IV | Catalina | inglés |
| Avatar IV | Catalina | **español** |

Cambiar motor, proveedor de voz e idioma del prompt no cambia nada, así que el
mensaje no dice la verdad sobre la causa. Lo que lo delata: **la vista previa
gratuita SÍ se genera**, con imagen y sincronía labial. Solo cae el render.
Ticket abierto con su soporte el 8-sep. **ESCALADO a su equipo tecnico** ese
mismo dia, con el proyecto, el grupo del avatar, el look, la prueba en incognito
y la confirmacion de que falla en los dos editores. Su soporte pidio
expresamente **no abrir mas tickets** por lo mismo, que solo retrasa la
respuesta. Identificadores, por si hacen falta otra vez:

    Proyecto (AI Studio) : 75d6908bb0b34886ac0974bfa1f7bddf
    Avatar Cecilia TDM   : a466c76c02cd42ff9a3f4079749c4c0f
    Look usado           : e781fa51d4c54be0b3279ed2469bea57

Su primera respuesta decia que el espanol si esta admitido y que la vista previa
funciona: eso ya lo sabiamos y es justo lo que hace sospechoso el fallo. Lo que
tienen que mirar es el render final.

- [ ] Vídeo `aigents-cecilia2.mp4` — **esperando a que HeyGen desbloquee el render**
- [ ] Guion en inglés e italiano — **lo escribe el founder** (no se inventa copy)
- [ ] Pantalla `s-cecilia2` y su entrada en el sorteo a 1/3 — se enciende el día
      que el vídeo esté en `frontend/`

## Menor / arrastrado

- [ ] **La app no enseña su versión por ningún lado.** Es lo que nos ha costado
  dos diagnósticos fallidos esta semana (muro de pago el 6-sep, quietud el
  8-sep). Poner el número de versión y de build visibles, p. ej. al pie de la
  cuenta. Va en el próximo build.
- [x] **"No volver a mostrar" ya tiene marcha atrás** (founder, 8-sep-2026).
  El silencio dura **5 días** y el botón pasa a llamarse "Don't show". La llave
  guarda la FECHA en vez de un `1`, y las llaves viejas (`'1'`, sin fecha) se dan
  por caducadas, así que quien llevaba semanas silenciado la recupera.
  Probado: 7 casos de la función y 3 ciclos completos.

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
- [x] **Los textos que se quedaban en español en inglés y en italiano: CERRADO
  el 9-sep-2026.** Salieron al auditar el fallo de Ale: eran claves pedidas con
  `_i18nText` que no existían en NINGUNO de los tres diccionarios, así que caía
  siempre el literal castellano escrito dentro de la función. Añadidas las 26 en
  los tres idiomas: los **20 errores de validación del formulario de cachorro**,
  `pup_saving`, `pup_saved`, el título del plan, `rec_lang_badge_title`, los 3
  del código de invitación y `ps_invite_label` / `ps_invite_hint`; más
  `ps_forgot_link`, que solo faltaba en inglés e italiano.
  Dos cosas que hubo que desenredar, no es solo traducir:
  · `pupr_title` servía A LA VEZ al `<h1>` genérico (por `data-i18n`) y al
    título con el nombre del perro (por JS). Metiéndola en el diccionario,
    cambiar de idioma con el plan abierto habría borrado el nombre. Ahora son
    tres claves: `pupr_title_h1`, `pupr_title_dog` y `pupr_title_abc_dog`, y las
    dos últimas llevan hueco `{dog}`.
  · `ps_err_invite_unexpected` se pedía desde dos sitios con literales distintos
    ('la cuenta' y 'la cuenta cortesía'). Con una sola clave los dos dicen lo
    mismo; si hace falta distinguirlos, hay que partir la clave en dos.
  `abc_intro_petowner` y `desc_` son falsos positivos: la primera ya trae sus
  tres idiomas dentro de la llamada y la segunda es un prefijo dinámico.
  **Auditoría reproducible**, y conviene repetirla al añadir textos: extraer las
  claves de `_i18nText('...')` y de `data-i18n` y cruzarlas con los tres
  diccionarios de `TRANSLATIONS`. Ahora mismo: 987 claves usadas, 0 huecos.
- [ ] **Un "resfriado" ABA en el inicio italiano cognitivista.** `sin-fugas-vivo`
  sobre el binario de la 1.0.19 da 30 casos y **0 fugas CZ** (la dirección que
  importa), pero anota una en sentido contrario: con `it + cognitive`, la
  pantalla de inicio enseña *"Revisione esperta e analisi funzionale"*
  (`home_teo_sub`). Es previo, no lo trae ningún cambio del 9-sep, y por la
  asimetría del 4-sep es resfriado y no Ébola. `rinforzo`, que sale en el mismo
  aviso, **está permitido** desde el 7-sep. No se toca sin OK: es copy.
- [ ] Mensajes 402 del backend solo en español (la app pone los suyos traducidos,
  así que hoy no se ven).
- [ ] Vídeos por idioma de Cecilia y Niaz (EN/IT) servidos desde nuestro dominio.
- [ ] Vibración en Inicio, al enviar anamnesis y en los botones de vídeo.
- [ ] Ale al 20 % cuando exista su vídeo.
- [ ] Italiano en la ficha de la App Store (texto promocional ya traducido y
  aprobado).
