# Spec — Katja en el seguimiento diario

**Estado: PENDIENTE DE IMPLEMENTAR.** Encargado por el founder el 2026-08-08,
después de cerrar el trabajo de contraste.

## Qué pide el founder (literal)

> "En seguimiento del día, al final, me gustaría que hubiera debajo de la
> pregunta del día un slot donde puedas meter comentarios con una imagen del
> Aigent Katja y que ella responda con feedback a los comentarios, dudas o
> problemas con los que se ha enfrentado. Katja sería ideal que tuviese toda la
> info que el propietario ha introducido."

## Precio — decidido por el founder

**0,3 tokens por consulta** (revisado a la baja desde 0,5).

- 30 créditos · ~0,25 € de ingreso · ~0,0063 € de coste (0,021 €/token)
- Margen ~97%, en línea con el resto del modelo
- Es la mitad de un check-in (1,5 tk), coherente con un uso diario

Regla de la casa: ninguna función es gratis. 0,3 cumple el mínimo simbólico.
Ver [[feedback-ningun-uso-es-gratis]].

## Lo que YA existe (no hay que crearlo)

- **Katja como Aigent**, con ilustración: `aig-katja-pixar.webp`. Es una de las
  ocho (Ale, Borja, Cecilia, Iris, Katja, Leo, Mario, Niaz).
- **El motor de seguimiento diario**: `app/services/daily_followup_ai.py` +
  `app/core/prompts/daily_followup_coach.py`. Ya inyecta el plan del caso.
- **El patrón de chat** con Cecilia, reutilizable para el hilo.

## Lo que hay que construir

1. **UI**: slot de comentario bajo la pregunta del día, con la imagen de Katja
   y su respuesta. Vibrant, respetando la paleta ya verificada
   (`CONTRASTE_VIBRANT_ESTADO.md`).
2. **Endpoint**: recibe el comentario y devuelve la respuesta de Katja.
   Cobra 0,3 tk vía `deduct_token`.
3. **Contexto**: el founder pide "toda la info que el propietario ha
   introducido" — anamnesis, análisis, plan e histórico de check-ins.
   **Cuidado con el tamaño**: más contexto es más coste por respuesta; a 0,3 tk
   el margen aguanta, pero conviene medir el consumo real antes de abrirlo.

## Decisiones que siguen abiertas (del founder)

- **Katja vs Cecilia.** Cecilia es hoy quien explica y acompaña. Si Katja hace
  lo mismo en otra pantalla hay solape. Hay que definir qué hace cada una.
- **Idioma/tono de Katja**: no inventar. El copy lo da el founder
  ([[feedback-no-inventar-copy-publico]]).

## Nota relacionada: la pantalla de espera por pasos

El founder pidió también llevar a la app la pantalla de carga que describe el
proceso. **Ya está hecha**: `dmLoadingSteps()` (commit `cde2271`, 25-jul-2026),
dos modos (`analysis` y `plan`), cinco pasos, en el archivo compartido y sin
puerta de web. La app la mostrará en cuanto salga la **build 27**; el bundle
instalado es anterior. No hay trabajo pendiente ahí, solo verificar en la 27.
