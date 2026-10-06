# Pet Owner más amable — propuesta

Dos encargos del founder (6-oct-2026), en una sola pieza porque apuntan a lo
mismo: que el particular salga de la app con ganas de volver.

1. **Acortar lo que devuelve la app en formato Pet Owner.**
2. **Celebrar cada seguimiento diario** con Mario y su perro: el perro viene
   corriendo con música triunfal, Mario llega detrás, lo coge en brazos y dice
   *"¡Qué guay, amigo! Sigue así y conseguirás tus objetivos!!!"*.

Nada de esto está implementado todavía. Esto es la propuesta, para su OK.

---

## 1 · Lo que hoy recibe un particular

Medido en los prompts, no estimado:

| Pantalla | Presupuesto actual | Dónde |
|---|---|---|
| Análisis (QUÉ LA DISPARA · QUÉ HACE Y QUÉ CONSIGUE · EN RESUMEN) | **330 palabras tope**, objetivo 280 | `app/core/prompts/petowner_clinical.py:38` |
| Plan (OBJETIVO · LA IDEA · FASE 1 · FASE 2 · SEÑALES) | **450 palabras tope**, objetivo 400 | `app/core/prompts/petowner_intervention.py:36` |
| Seguimiento diario (coach) | **300-500 palabras** | `app/core/prompts/seguimiento.py:53` |

Una consulta entrega **hasta 780 palabras de un tirón**, y cada día de
seguimiento añade otras 300-500. En un móvil son cuatro o cinco pantallas de
texto seguidas antes de saber qué tiene que hacer hoy.

### La propuesta: no recortar el contenido, cambiar el orden

Recortar por recortar nos deja un análisis pobre, y el análisis es el producto.
Lo que sobra no es el contenido: es que **todo llega a la vez y en el mismo
tono**. Tres cambios, por orden de efecto:

**(a) Una primera línea que se lea de un vistazo.** El modelo entrega un campo
nuevo, `resumen`, de **máximo 40 palabras**, en segunda persona y sin jerga:
qué le pasa al perro y qué vamos a hacer. Es lo único que se ve al abrir. Debajo,
los bloques de siempre plegados, con **"Ver el análisis completo"**. Quien
quiera leerlo lo lee; quien no, ya se ha enterado.

**(b) Bajar los topes, que hoy están altos para un particular.**

| | hoy | propuesta |
|---|---|---|
| Análisis | 330 | **240** |
| Plan | 450 | **360** |
| Coach diario | 300-500 | **120-180** |

El coach diario es el que más sobra: es un check-in de treinta segundos y hoy
puede devolver media página. 120-180 palabras es un párrafo y dos indicaciones.

**(c) Quitar el muro de texto del plan.** FASE 1 y FASE 2 pasan a tarjetas de
ejercicio: título, una línea de para qué, pasos numerados y la cantidad concreta.
Es el mismo contenido con otra forma, y además es lo que ya hace la pantalla de
tareas del seguimiento.

**Lo que NO se toca:** la anamnesis no se recorta —sin datos amplios no hay
análisis—, el contenido clínico del profesional se queda como está, y la vía
cognitivista italiana no se roza.

---

## 2 · La celebración de Mario

### Lo que ya existe

- **Mario es un Aigent del elenco**, con su arte Pixar y su bulldog francés:
  `frontend/aig-mario-pixar.webp`, `aig-mario.webp`, `peek-mario.webp`.
  Color de marca `--aigent-mario: #06B6D4`.
- **La maquinaria de pantalla ya está hecha y probada**: la hoja de Aigent
  (`.ob-wrap` / `.ob-video` / `.ob-scroll`), con vídeo a pantalla, audio
  automático —Capacitor desactiva el gesto obligatorio dentro de la app—,
  subtítulo escrito a máquina y háptico. Es la misma que usan Niaz, Ale y
  Cecilia.
- **El punto exacto donde engancha**: `onSubmit()` del módulo de seguimiento
  diario, justo después del `POST /cases/{id}/daily-followup`, donde hoy ya se
  lanza el toast de medalla (`frontend/index.html:29280`). La respuesta trae
  `current_streak`, `gold_just_earned`, `silver_just_earned` y `current_badge`,
  así que la celebración puede saber si ese día es especial.

### Lo que falta: el clip

Es lo único que bloquea, y lo tiene que producir el founder (los assets
visuales no los fabrico yo).

| | |
|---|---|
| Duración | **6-8 s** |
| Formato | 9:16, 1080×1920, H.264 + AAC, ~1-2 MB |
| Guion visual | el bulldog entra corriendo de frente hacia cámara (0-2 s) · Mario aparece detrás y lo coge en brazos (2-4 s) · habla a cámara (4-7 s) |
| Música | triunfal, entra con el perro y baja cuando Mario habla |
| Frase, literal | **"¡Qué guay, amigo! Sigue así y conseguirás tus objetivos!!!"** |
| Idiomas | `celebra-mario-es.mp4` · `-en` · `-it`. Mientras falten EN e IT, cae al ES con el subtítulo traducido, que es lo que ya se hace con los relevos |

Referencia de tamaño de los que ya hay: `aigents-cecilia2.mp4` son 1080×1920 y
5,9 MB con 29,8 s; a 7 s esto sale por 1,5 MB.

### Cómo se comporta

1. El usuario pulsa **Guardar el día**.
2. El POST contesta. En vez del toast, se abre la hoja de Mario a pantalla
   completa, con el vídeo arrancando con sonido y un háptico de celebración en
   el momento en que lo coge en brazos.
3. Subtítulo con la frase, escrito a máquina, como en los demás Aigents.
4. Debajo, lo que el usuario se ha ganado ese día: **racha de N días** y, si
   toca, la medalla. Un botón grande, **"Seguir"**, que cierra y devuelve a la
   pantalla del seguimiento ya marcada como hecha.
5. Botón de silencio y de repetir, en la esquina, como en el resto.

### Una decisión que es suya

Dijo *"cada vez que realices el seguimiento diario"*, y así se implementa salvo
que diga otra cosa. Dejo escrita la alternativa porque es su terreno y él mismo
montó el programa de razón variable de los otros Aigents: **siempre los primeros
7 días** —que es cuando se construye el hábito— y a partir de ahí **razón
variable 3**, con el día de medalla y el de récord de racha siempre garantizados.
Un reforzador que aparece el 100 % de las veces deja de verse a la tercera
semana; intermitente aguanta.

---

## Orden de trabajo propuesto

| | qué | depende de |
|---|---|---|
| 1 | Topes nuevos de palabras y campo `resumen` en los tres prompts | nada; backend, llega a todos sin pasar por tiendas |
| 2 | Primera línea + bloques plegados en la pantalla de análisis y de plan | el paso 1 |
| 3 | Hoja de Mario montada con un clip provisional | nada |
| 4 | Clip definitivo en los tres idiomas | **del founder** |
| 5 | Tarjetas de ejercicio en el plan | el paso 1 |

Los pasos 1 y 2 se notan el mismo día en que se despliegan: son backend y web,
sin tienda de por medio. El 3 y el 5 entran en el siguiente build.
