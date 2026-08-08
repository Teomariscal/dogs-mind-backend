# Vibrant total + contraste cero — estado del trabajo

**Fecha:** 2026-08-06 · **Estado: EN CURSO, NO TERMINADO**

## El encargo del founder (literal)

> "no puede ninguna tarjeta en ninguna funcionalidad de todas las de la web
> (revisa todas sin excepción) puede volver a salir con problema de contraste"

> "y todas con este formato, fondo todo vibrant. Malla radar o no, depende del
> gusto de tu skill de diseño, pero no es aceptable otro tipo de fondo, ni
> parcial ni total"

> "dedícate a esto sin interrupciones de forma continua hasta cero resultados
> con iteración y double check total"

Referencia visual aprobada: tres capturas suyas (pantalla de Ale/paseos,
Nueva Consulta, Sesión de hoy). Fondo esmeralda profundo con malla tenue,
paneles translúcidos con borde cyan, texto claro, acentos cyan/verde/arena.

**Aviso del founder:** este trabajo se ha pedido varias veces y se ha dado por
completo sin estarlo. No declarar "hecho" sin que el medidor dé 0.

## El medidor (lo importante de esta sesión)

Se construyó un auditor de contraste que se inyecta en la página viva. Está en
el historial de la sesión; **hay que reconstruirlo si se pierde**. Qué hace:

- Recorre las 38 pantallas (`.screen`), activando cada una.
- Mide 732 elementos de texto hoja.
- Calcula el fondo efectivo atravesando ancestros y componiendo alfas.
- En degradados, extrae **cada parada de color** y se queda con el PEOR ratio.
- Umbral AA: 4.5 normal, 3.0 para texto grande (≥24px, o ≥18.66px en negrita).
- Se expone como `window.__audit2()` y devuelve `{medidos, fallos:[...]}`.

Ya ha pillado dos intentos míos que EMPEORABAN el resultado. Es la única
defensa contra volver a declarar esto terminado sin estarlo.

## Números

| momento | fallos |
|---|---|
| estado inicial (producción) | **173** |
| tras primer bloque CSS global | 242 (peor) |
| tras excluir controles claros | 234 (peor) |
| objetivo | **0** |

Las 173 se agrupan en 43 pares color/fondo; los 5 primeros explican 100:

| casos | texto | fondo | ratio |
|---|---|---|---|
| 32 | `#5ec8e6` cyan | `#4a6741` verde | 3.29 |
| 30 | `#6b6456` (--text2) | `#203a35` | 2.08 |
| 18 | `#a09688` (--text3) | `#faf8f4` | 2.74 |
| 11 | `rgba(255,250,240,.45)` | `#3b4133` | 3.44 |
| 9 | `#0891b2` | `#ffffff` | 3.68 |

## Causa raíz

El diseño original era **claro**. `--text2`, `--text3`, `--grey` y `--dark` son
tokens de tema claro. El vibrant se ha ido aplicando pantalla a pantalla, y
cada pantalla migrada sin tocar esos tokens reintroduce el mismo fallo.
Mientras convivan superficies claras y oscuras es **imposible** arreglarlo con
un remapeo: el mismo token tendría que ser oscuro aquí y claro allá.

Por eso la orden del founder (ninguna superficie clara) es justo lo que hace
el problema resoluble: sin fondos claros, los cuatro tokens se remapean UNA vez.

## Sistema de diseño (extraído de sus capturas, contrastes ya verificados)

```
página   #14302a  (degradado #0e1f1a -> #14302a, peor caso el de abajo)
panel    #1f3934  (blanco 4,5% sobre página)
tarjeta  #26403a  (blanco 7,5% sobre página)
```

| rol | color | alfa | s/panel | s/tarjeta |
|---|---|---|---|---|
| título / cuerpo primario | `#f3f1ea` | 1.0 | 10.95 | 9.96 |
| secundario | `#f3f1ea` | 0.78 | 7.33 | 6.78 |
| atenuado | `#f3f1ea` | 0.62 | 5.25 | 4.93 |
| cyan acento (serif itálica) | `#5ec8e6` | 1.0 | 6.41 | 5.83 |
| verde epígrafe | `#9ed48c` | 1.0 | 7.22 | 6.57 |
| arena etiquetas de campo | `#d8b98a` | 1.0 | 6.61 | 6.02 |
| placeholder | `#f3f1ea` | **0.62** | 5.25 | 4.93 |

(el placeholder se subió de 0,55 a 0,62 porque a 0,55 daba 4,48 y no llegaba)

Bordes: panel `1px rgba(94,200,230,0.14)`, radio 20–24px.
Tarjeta interior: `1px rgba(255,255,255,0.08)`, radio 16–18px.

## Lo que falta (el trabajo en sí)

En `frontend/index.html` hay **146 declaraciones de fondo claro, 21 colores
distintos**:

```
110x #fff     7x #f5f5ef   4x #ffffff   3x #f5f4ed   3x #dce6d8
  2x #e8f0e8  2x #fff5f5   2x #f7f9f5   1x #faf8f4   1x #fff0f0
  1x #c8cdd0  1x #c2d8e0   1x #ecebe2   1x #f3f1ea   1x #c8d8bf
  1x #f0f4ff  1x #e8eeff   1x #f8f9ff   1x #e8eee5   1x #fafafa
  1x #fdf0f0
```

Clasificadas ya en `CONTRASTE_VIBRANT_CHECKLIST.md` (146 entradas con línea,
color y selector):

| tipo | n | qué hacer |
|---|---|---|
| SUPERFICIE | 19 | a vibrant (panel `#1f3934` / tarjeta `#26403a`) |
| CAMPO | 4 | input translúcido `rgba(255,255,255,.06)` + borde cyan |
| CONTROL | 15 | se quedan claros, PERO deben conservar texto oscuro |
| INLINE | 108 | `style="..."` en el HTML — hay que revisarlas a mano |

Las 108 inline son el grueso y la razón de que los bloques CSS globales no
funcionen: el estilo en línea gana a cualquier hoja, así que un `.screen{...}`
no las toca. Hay que editarlas en el HTML.

Hay que convertirlas **una a una**, no en bloque (el bloque ya falló dos veces).
Distinguir:
- **Superficies** (pantallas, paneles, tarjetas, formularios) → van a vibrant.
- **Controles** (botones blancos tipo "Descargar PDF completo", nav, menús) →
  el founder los aprobó; se quedan claros, pero deben conservar texto oscuro.
  Si se les aplica el remapeo de tokens, heredan texto claro y se vuelven
  ilegibles: ese fue el fallo del primer intento (51 casos).

## Método obligatorio para continuar

1. **No desplegar a producción para probar.** Usar `netlify deploy` sin
   `--prod` (deploy de borrador) e inyectar el auditor ahí.
2. Iterar: cambio → medir → si sube, revertir ese cambio.
3. Solo promover a producción cuando `__audit2()` devuelva **0 fallos**.
4. Después, captura de cada pantalla y validación visual (el medidor mide
   contraste, no gusto).
5. Sitio: `--site=152389f9-0282-46b5-a929-db9f9b142912` (thedogsmind.net).
   SIEMPRE con `--site` explícito.
6. Al cambiar cualquier `.js` o `.css`, subir su `?v=` en index.html Y el
   `CACHE_NAME` del service worker, o el cambio no llega a nadie
   (ya pasó hoy: v245→v246→v247).

## Ya cerrado hoy (no volver a tocar)

- Barra fija de la web: `--w-bar` era literal 118px mientras la barra mide 162
  (el botón "Registros de conducta" salta de línea). Se comía 44px de la
  cabecera de todas las pantallas. Arreglado en `web-desktop.js`, escribiendo
  la variable en `body` (no en `:root`: la declara `body.dm-web`).
- Crema: 25 usos eliminados, conservando luminosidad exacta.
- Pantalla del análisis: tres tarjetas vacías para particulares (el prompt
  Pet Owner emite "QUÉ LA DISPARA/QUÉ HACE Y QUÉ CONSIGUE/EN RESUMEN", no
  "BLOQUE A/B/C") y tarjeta ED vacía para profesionales (`extractSubSection`
  compara subcadenas literales, no regex).

## Cuenta de prueba PARTICULAR (para ver el formato de particular)

Creada 2026-08-06 en producción. `account_type: particular`.

```
email:    prueba.lenguaje.83943@thedogsmind.net
password: PruebaLenguaje2026!
```

Sirve para ver la rama Pet Owner sin crear otra cuenta ni gastar créditos de
nadie. Login: `POST /auth/login` en
`https://dogs-mind-backend-production.up.railway.app` — la respuesta trae el
campo `token` (NO `access_token`, ese error costó una llamada).

Para verla en el navegador sin tocar la sesión del founder: **perfil de Chrome
aparte**, no incógnito (en incógnito la extensión suele estar desactivada y
otra sesión de Code no podría pilotar la pestaña).

## Capa web: gate de ancho eliminado (2026-08-07)

REGLA DURA DEL FOUNDER: "nunca nunca vuelvas en la web a ese modelo" (el
layout de la app con hamburguesa y barra inferior).

Causa: `web-desktop.css` y `web-desktop.js` se activaban con
`(min-width:700px) and (hover:hover) and (pointer:fine)`. Con un panel lateral
abierto en el navegador la ventana baja de 700px, la capa web se apagaba y
salía la maqueta antigua.

Arreglo: se quita SOLO el gate de ancho y se conserva el de puntero
(`(hover:hover) and (pointer:fine)`), para que un iPhone en el navegador siga
viendo la maqueta movil. La app nativa no se ve afectada: `dmInitWebLayer()`
(index.html:15224) sale antes de anadir `body.dm-web` y antes de inyectar los
dos archivos, asi que en la app ni se descargan.

Verificado en borrador a 560px: barra presente (86px) y `.phone` reservando 86.

---

# SESIÓN DEL 7-AGO (madrugada) — dónde se quedó

**PRODUCCIÓN ESTÁ EN SW v249 Y ES BUENA.** Todo lo del contraste vive en
deploys de BORRADOR y en el repo sin desplegar. Verificado: producción no
contiene el bloque "TOKENS DE TEMA CLARO SOBRE PANTALLAS OSCURAS".

## Números medidos

| momento | fallos |
|---|---|
| partida | 173 |
| bloque CSS global (intento 1) | 242 — peor, revertido |
| exclusión de controles (intento 2) | 234 — peor, revertido |
| superficies y campos en línea a vibrant | **184** |
| remapeo de tokens en pantallas oscuras | **SIN MEDIR** ← empezar aquí |

## Lección que costó dos intentos

Las 108 declaraciones de fondo claro que hay **en atributos `style=`** ganan a
cualquier hoja de estilos. Por eso los bloques CSS globales no bajaban los
fallos: se veía bien la pantalla que uno miraba y quedaban decenas de
superficies blancas intactas. Y al remapear los tokens de texto a claro sin
haber convertido esas superficies, el texto se volvía invisible sobre ellas
(51 casos nuevos de golpe).

**Regla:** fondo y texto se cambian SIEMPRE en el mismo sitio y a la vez.

## Los 5 pares que explican 97 de los 184

| casos | texto | fondo | ratio | estado |
|---|---|---|---|---|
| 32 | `#5ec8e6` cyan | `#4a6741` verde | 3.29 | **PENDIENTE** — usar `#ade3f2` (4,56) donde el cyan va sobre verde |
| 31 | `#6b6456` | `#203a35` | 2.08 | remapeado, **sin medir** |
| 18 | `#a09688` | `#faf8f4` | 2.74 | hecho → `#7a7061` (4,59) |
| 11 | `rgba(255,250,240,.45)` | oscuro | 3.32 | hecho → alfa 0,62 |
| 9 | `#0891b2` | blanco | 3.68 | hecho → `#07819e` (4,51) |

Otros pendientes: `#5ec8e6` sobre blanco (1,93), crema `#f4efe2` sobre el verde
claro `#7eb86a` de los CTA (2,04 — aquí lo correcto es **oscurecer el botón**,
no el texto, o saldría marrón), `#80d6ee` sobre `#5c7f52` (2,77).

## Al retomar, en este orden

1. Abrir el último borrador, reconstruir el auditor (`window.__audit`) y
   **medir**. Si el número no ha bajado de 184, revertir el remapeo antes de
   seguir: es señal de que alguna de esas cuatro pantallas conserva superficie
   clara.
2. Atacar el par del cyan sobre verde (32 casos, 6 pantallas).
3. Repetir: cambio → medir → si sube, revertir ese cambio.
4. Solo promover a producción con **0** y tras mirar capturas de las pantallas
   tocadas.

## Aviso sobre el navegador

El panel se quedó colgado dos veces al ejecutar el auditor completo (38
pantallas × ~730 elementos). Si vuelve a pasar: `preview_start` con la URL del
borrador para reiniciarlo, y definir los helpers y el auditor en **llamadas
separadas** en vez de en un solo bloque grande.

---

# AVANCE MEDIDO (7-ago, madrugada)

Producción sigue en **SW v249**. Nada de esto está desplegado.

## Por pantalla, medido en borrador

| pantalla | antes | después | |
|---|---|---|---|
| s-anamnesis | 37 | **6** | ✔ |
| s-anamnesis-puppy | 18 | **2** | ✔ |
| s-anamnesis-training | 13 | **3** | ✔ |
| s-seguimiento | 12 | **0** | ✔ |
| s-dog-profile | 6 | **0** | ✔ |
| s-tour-intro | 26 | **15** | parcial |
| s-abc | 6 | 6 | sin tocar |
| s-avatars | 8 | 8 | sin tocar |
| s-pro-signup | 15 | **31** | ✘ empeoró → corregido, SIN MEDIR |
| s-pro-login | 3 | **7** | ✘ empeoró → corregido, SIN MEDIR |

## Qué se hizo y por qué funcionó

1. **Superficies y campos en línea a vibrant** (24 + 18), cambiando fondo y
   texto en el MISMO atributo `style`. Esto por sí solo no bajó el total (173 →
   184), pero era el requisito para poder remapear tokens sin romper nada.
2. **Remapeo de tokens de tema claro** en s-anamnesis, s-anamnesis-puppy,
   s-anamnesis-training y s-tour-intro. Aquí está el salto grande: s-anamnesis
   pasó de 37 a 6.
3. **`--text3` #a09688 → #7a7061**, que se llevó s-seguimiento y s-dog-profile
   a cero de golpe.
4. **Cyan de texto unificado a `#ade3f2`** (32 usos). Antes `#5ec8e6` daba 3,29
   sobre verde. Para poder tener un solo cyan hubo que convertir las dos
   últimas pantallas claras (s-pro-login, s-pro-signup): mientras existieran,
   el cyan tenía que ser oscuro allí y claro en el resto.
5. Esa conversión **empeoró** esas dos pantallas (su paleta `--ps-*` era
   oscura-sobre-claro). Corregido invirtiendo las cuatro variables:
   `--ps-text` → `#f3f1ea` (10,82), `--ps-text-muted` → alfa 0,86 (8,45),
   `--ps-text-soft` → alfa 0,70 (6,18), `--ps-cyan` → `#ade3f2` (8,76).
   **Calculado, no medido en navegador.**

## Lo PRIMERO al retomar

Medir el último borrador. Si s-pro-signup y s-pro-login no han bajado de 31 y
7, revertir el punto 5 antes de seguir.

Pendientes conocidos después de eso:
- `s-tour-intro`: 15, casi todo ámbar `#c8a96e` sobre oliva (3,61–4,41).
  Subirlo a `#d8b98a` (6,61 sobre panel).
- `s-abc`: 6 · `s-avatars`: 8 · resto de pantallas sin revisar en esta tanda.
- Crema `#f4efe2` sobre el verde claro `#7eb86a` de los CTA (2,04): aquí lo
  correcto es **oscurecer el botón**, no aclarar el texto.

## Aviso: el panel del navegador se cuelga

Se colgó tres veces. Patrón observado: navegar con `location.href` y ejecutar
JS inmediatamente después lo mata. Método que sí aguantó: `preview_start` con
la URL del borrador, y definir helpers y auditor en **dos llamadas separadas y
cortas**, midiendo **pantalla a pantalla** con `__una(id)` en vez de las 38 de
golpe.


---

# PROGRESO MEDIDO (7-ago, continuación)

| momento | fallos | |
|---|---|---|
| partida | 173 | |
| tras superficies en línea | 184 | peor, pero necesario |
| tras remapeo de tokens + cyan unificado + paleta ps-* | **75** | medido |
| tras ámbar `#c8a96e`→`#d8b98a` y CTA verde oscurecido | **59** | medido |
| tras verdes oscurecidos y alfas subidos | ? | **SIN MEDIR** |

## Última tanda (sin medir)

- `--green2` `#5c7f52` → `#4a6642` (el cyan encima daba 3,26)
- `color: rgba(0,0,0,.55)` → `rgba(243,241,234,.72)` — 15 usos. Era **texto
  negro sobre fondo oscuro** (1,14): el descargo del análisis.
- Alfas subidos: blanco .55→.74 (12), crema .62→.74 (7), blanco .78→.88 (4),
  verde claro .55→.74 (6)
- `#5e8154` → `#5b7c51` (5) · `#6b9b62` → `#54803f` (2)

## Pendientes conocidos tras esa tanda

- `#5ec8e6` sobre blanco (1,93) en "Solo profesionales" y sobre `#e2e4e4`
  (1,51) en "Variables disposicionales": quedan superficies claras en
  s-pro-company y s-abc que hay que pasar a vibrant.
- `var(--green)` `#4a6741` como TEXTO sobre fondo profundo (2,21–2,23):
  los enlaces "Política de Privacidad". Aclarar a `#739e66` (4,58) solo donde
  va como color, no como fondo.
- Crema `#f4efe2` sobre el CTA ya oscurecido `#50833e`: 3,93. Pasar ese texto
  a blanco puro (4,52).

---

# CORRECCIÓN DEL MEDIDOR (importante)

`__S` extraía las paradas de los degradados **solo en formato `rgb()`**. Media
app los declara en **hexadecimal**, así que en esas pantallas el auditor no
encontraba fondo, caía al blanco por defecto e inventaba fallos.

Arreglado: ahora parsea `rgb()/rgba()` **y** `#rrggbb`/`#rgb`.

**Consecuencia: los números anteriores no eran fiables.** Con el medidor
corregido, el estado real es:

| | fallos |
|---|---|
| partida | **173** |
| estado actual (medido con el medidor corregido) | **40** |

Reducción del 77%. El "28" que llegué a anunciar era del medidor viejo.

## Tandas revertidas (empeoraban)

Tres bloques seguidos subieron a 47, 103 y 104. Se revirtieron con
`git checkout frontend/index.html`. Qué los rompía:
1. `color: var(--green)` cambiado en bloque (116 usos): metió 16 fallos en
   `s-privacy`/`s-terms`, donde esos enlaces van sobre blanco.
2. Convertir tarjetas cambiando solo `background` y `color` del contenedor:
   los hijos traen su color de los tokens y se quedaron oscuros sobre oscuro.
3. Aplanar `s-privacy`/`s-terms` con `* { background-color: transparent }`:
   el contenedor blanco está más adentro y la regla no llegó.

## Verificación visual hecha

- `s-anamnesis`: correcta y fiel a la referencia del founder — fondo esmeralda,
  epígrafes en arena, chips con borde cyan, campos y botones legibles.
- `s-abc`: la cabecera es una **foto real con fondo blanco** ("A – Antecedent /
  B – Behavior / C – Consequence"). El contraste ahí es correcto (texto oscuro
  sobre blanco) pero **es una superficie clara**, y además está en inglés.
  Decisión del founder: cambiar la imagen o superponerla. No la toco.
