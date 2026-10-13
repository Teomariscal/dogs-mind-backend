# Entrada por voz — bajar el coste de respuesta

Decidido con el founder el 13-oct-2026. **No implementado todavía.**

La frase que lo ordena, suya: *"el coste de respuesta no se refiere a dinero, se
refiere al gasto conductual que implica cualquier acción"*. Si la misma
consecuencia se puede conseguir con menos esfuerzo, el organismo elige el camino
barato. Siempre.

---

## Por qué no es una comodidad: es acceso

Dos poblaciones que el founder nombra, y una consecuencia que las une:

**Déficit de atención.** Ponerse a teclear en el móvil exige una ventana de
atención sostenida que mucha gente no tiene.

**Mayores de 40.** Escribir obliga a ponerse las gafas de cerca, y con esas gafas
no se ve de lejos: no se puede ir caminando, ni mirar al perro, ni al tráfico.
*"En vez de hacerte cinco consultas, te hago una."*

**Y lo que las une, que es lo importante:** el momento en que el problema de
conducta ocurre es exactamente el momento en que la app no se puede usar. El
perro tira, se lanza, se queda clavado — eso pasa en la calle, andando, con una
mano en la correa y sin gafas. Ahí teclear no es incómodo, es imposible. Y es
cuando el dato está fresco y la motivación alta.

---

## La regla de diseño

| tipo de respuesta | ¿sirve sin gafas? | qué se hace |
|---|---|---|
| Sí/no, chips, botones grandes | **Sí** — el blanco es grande y no hay que leer para acertar | se quedan como botones |
| Escribir texto | **No** — porque hay que releer lo escrito | **voz** |

**Y la consecuencia que hace que funcione: la transcripción NO se le enseña al
usuario para que la corrija.** Una pantalla de "revisa que te hayamos entendido"
devuelve el problema al principio — a releer con gafas. Quien lee la
transcripción es el motor, no la persona, y al motor le da igual una coma mal
puesta o un "eh" de más.

**Las dos opciones conviven y elige el usuario.** Micrófono y teclado, siempre
los dos. Nadie decide por él.

---

## Dónde se cobra coste de respuesta hoy

La anamnesis conductual tiene **19 campos de teclear**.

**8 de escribir largo** — aquí la voz es la ganancia grande:
describe la conducta problema · describe la evolución · qué has intentado ·
cuál crees que es la causa · otros problemas de conducta · qué te dificulta
aplicar las propuestas · escuela de educación canina · información extra.

**11 de una línea, y 8 de esos no deberían pedir teclear nada** (propuesta al
founder, las preguntas son suyas):

| pregunta | hoy | podría ser |
|---|---|---|
| ¿Convive con otros perros? | teclear | sí / no |
| ¿Tiene alguna dolencia crónica? | teclear | sí / no + cuál |
| ¿Con cuántos meses salió de la camada? | teclear | rueda de números |
| ¿Desde cuándo ocurre? | teclear | días / semanas / meses / +1 año |
| ¿Dónde ocurre? | teclear | casa · calle · parque · coche · otro |
| ¿Quién está presente? | teclear | yo · otra persona · otro perro · nadie |
| Si es adoptado, ¿cuánto lleva contigo? | teclear | rangos |
| ¿Ha visitado escuela de educación canina? | teclear | sí / no + cuál |

**No desaparece ninguna pregunta** — la anamnesis no se recorta, es regla del
founder. Solo deja de costar teclear. Y los chips, al contrario que el texto
libre, se pueden contar: "¿dónde ocurre?" en chips da mañana el porcentaje de
casos que pasan en la calle.

---

## Lo medido

**La gente ya elige pulsar sobre escribir, cuando puede.** En el seguimiento
diario: 447 respuestas dadas, **las 447 pulsando un botón, 0 escritas**. Y de
112 entradas con hueco de texto libre, 112 vacías.

**Y paga la cadena una vez y no vuelve:** 68 de 146 casos apuntaron exactamente
un día y nunca más. Hoy la cadena para apuntar un ejercicio es abrir → esperar →
casos → elegir caso → seguimiento → leer → pulsar → enviar. Siete u ocho
eslabones para una respuesta de dos segundos.

**Un dato que NO demuestra lo que parece:** entre los que sí terminaron el
formulario, quien escribió más siguió más (29,7 % con menos de 80 caracteres;
45,5 % entre 200 y 500). Eso **no** dice que escribir no eche a nadie: solo mira
a los supervivientes, y los que se habrían quedado si no hubiera que escribir no
están en la tabla por construcción. Es sesgo de selección, lo señaló el founder,
y es correcto. Desde dentro de esta app no se puede medir.

---

## Qué cuesta

Transcripción a 0,006 USD/minuto:

| | |
|---|---|
| Anamnesis entera dictada (8 min) | **0,044 €** |
| Feedback semanal hablado (2 min) | 0,011 € |
| Efecto en el margen del análisis | **95,7 % → 92,3 %** |

Tres puntos de margen. No hay discusión económica.

---

## Qué hace falta para montarlo

**Nivel 0 — gratis, hoy, sin pasar por tienda.** El teclado de iOS y de Android
ya traen dictado. Funciona en producción ahora mismo en todos los campos. Falta
que el usuario lo sepa: una línea bajo los campos largos. **Pero no resuelve el
caso del founder**, porque el dictado del teclado obliga igualmente a mirar la
pantalla y releer.

**Nivel 1 — micrófono propio, modo de voz sin leer.** Estado comprobado en el
repo el 13-oct:

| | |
|---|---|
| `NSMicrophoneUsageDescription` (iOS) | **ya está** — se puso para el vídeo |
| `NSSpeechRecognitionUsageDescription` | **falta** — Apple lo exige para dictar |
| Texto del permiso de micro | dice solo "al grabar un vídeo" — **hay que reescribirlo** o Apple puede marcarlo |
| `RECORD_AUDIO` en Android | **falta** — el manifiesto solo declara INTERNET |
| Plugin de reconocimiento | no instalado |
| Versión nueva en las dos tiendas | obligatoria |

**Sin verificar:** si el reconocimiento de voz del navegador funciona dentro del
WebView de iOS. *Creo* que no —en Safari sí, en WKWebView históricamente no— y
por eso haría falta plugin nativo o transcripción en servidor. Se comprueba en
una tarde con una página de prueba en el simulador. **No prometer hasta
comprobarlo.**

---

## La idea que sale de aquí y que decide el founder

Si la transcripción no se lee y las preguntas se pueden hacer en voz alta, la
anamnesis deja de ser un formulario y pasa a ser **una conversación con un
Aigent** — Cecilia preguntando, el usuario contestando mientras pasea. La
maquinaria de los Aigents ya existe. Es un salto de producto, no una mejora de
campo, y por eso no se decide aquí.
