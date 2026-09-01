# Pendientes — The Dogs' Mind

Lista viva. Se actualiza en cuanto algo entra o sale. Última revisión: 1-sep-2026.

## Estado de las ramas ahora mismo

| rama | versión | estado |
|---|---|---|
| Web | v287 | en vivo, con todo lo de hoy |
| Backend | `cd6a6c8` | desplegado, Railway SUCCESS |
| Google Play | 1.0.12 (vc26) | publicada en producción |
| App Store | 1.0.12 (build 48) | en revisión · 1.0.11 en venta |

## URGENTE — tiene que entrar en la próxima que salga

- [ ] **Paseos / mapas con rutas: no funcionan en la app.**
  Causa localizada (sin reproducir aún en simulador): `capacitor.config.ts` tiene
  `limitsNavigationsToAppBoundDomains: true`, pero **no existe la clave
  `WKAppBoundDomains` en `mobile/ios/App/App/Info.plist`** — comprobadas las 21
  claves. Con esa opción activa y sin lista declarada, iOS bloquea las llamadas a
  `overpass-api.de`, `nominatim.openstreetmap.org` y `routing.openstreetmap.de`,
  que es justo lo que necesitan las rutas. En web funciona porque ahí no hay
  restricción.
  Siguiente paso: reproducir en el simulador, y arreglar declarando los dominios
  o quitando la restricción.
  **La 1.0.12 que está en revisión NO lleva esto.**

- [ ] **Cobros**: pendiente de que el founder concrete qué falla exactamente.
  Lo que sí está arreglado y va en la 1.0.12: el muro de pago vacío y el saldo
  cien veces menor.

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
- [ ] Mensajes 402 del backend solo en español (la app pone los suyos traducidos,
  así que hoy no se ven).
- [ ] Vídeos por idioma de Cecilia y Niaz (EN/IT) servidos desde nuestro dominio.
- [ ] Vibración en Inicio, al enviar anamnesis y en los botones de vídeo.
- [ ] Ale al 20 % cuando exista su vídeo.
- [ ] Italiano en la ficha de la App Store (texto promocional ya traducido y
  aprobado).
