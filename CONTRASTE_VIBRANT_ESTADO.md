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
