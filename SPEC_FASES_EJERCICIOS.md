# Ejercicios diarios POR FASE — spec

Founder, 19-oct-2026, visto en TestFlight sobre el caso de Joss:

> *"los ejercicios diarios que planteaba antes la aplicación han desaparecido"*
>
> *"Antes se daban muy random, ahora queremos que primero se dividan varias
> fases y los ejercicios que se plantean sean de una fase, pues como en Duolingo
> o en Strava, donde hasta que no aprendes lo anterior no pasas. Entonces la
> fase 2 no puede llegar antes de terminar la fase 1, y es el seguimiento el que
> dicta los ejercicios a realizar."*
>
> *"cuando tome los datos y haga una consulta a Teo, utilice los datos del
> seguimiento de los ejercicios"*

---

## 1. LO QUE SE ROMPIÓ (19-oct, regresión mía)

`dmPF.aceptar()` —el botón **"Aceptar el plan"** de la pantalla de fases nueva—
hacía `goTo('s-tracking')` y nada más. La única función que guarda el caso en el
servidor y llama a **`POST /cases/{id}/daily-followup/init`** es
`acceptIntervention()`, y nadie la llamaba.

Consecuencia para el dueño: acepta el plan, ve los ejercicios **una sola vez**
dentro del texto del plan, y no vuelven a aparecer nunca. Si no los copió, los
perdió.

**Arreglado:** `dmPF.aceptar()` llama a `acceptIntervention()`.

Esto solo devuelve los ejercicios como estaban. Lo de las fases es lo de abajo.

---

## 2. EL MODELO: UNA FASE CADA VEZ, Y NO SE SALTA

El plan ya sale partido en cuatro fases con encabezado exacto
(`petowner_intervention.py`), y cada fase trae su **criterio de salida
observable y contable**:

    FASE 1 — SEMANA 1
    FASE 2 — SEMANAS 2-3
    FASE 3 — SEMANAS 4-7
    FASE 4 — SEMANAS 8-12

Reglas:

| regla | detalle |
|---|---|
| El caso tiene **una fase actual** | `Case.current_phase`, empieza en 1 |
| Los ejercicios del día salen **SOLO del texto de esa fase** | hoy se le pasa el plan entero al modelo, y por eso mezcla |
| La fase 2 **no existe** hasta cerrar la 1 | como Duolingo: no se desbloquea lo siguiente |
| Quien decide avanzar es **el dueño** | él dice que está listo, o lo consulta con Teo |
| Avanzar exige **haber trabajado** | el criterio de salida de la fase lo escribe el propio plan |
| La consulta a Teo **lee el historial de ejercicios** | no se le pregunta al dueño lo que la app ya sabe |

## 3. EL FLUJO CORRECTO (founder, literal, 19-oct-2026)

> *"introducir anamnesis, análisis funcional, plan de intervención y con plan
> sencillo o plan complejo. Luego aceptar la intervención, seguimiento,
> notificaciones push de seguimiento, cada día apretar el seguimiento diario y
> rellenar y hacer los ejercicios que te pide ese mismo día. No poder saltarte
> más de 3 días seguidos sin una advertencia de que la cosa no va a funcionar,
> si ya tienes constancia. Y luego tener la opción en la hoja de seguimiento
> diario de poder consultar el estado de tu perro y la evolución del mismo. Y
> luego, cuando has realizado todos los ejercicios y consideramos que ha
> terminado la fase 1, una consulta con Teo para ver si puedes pasar a fase 2. Y
> hay un cuestionario en el que busquemos que no haya ninguna bandera de
> regresión y que sean banderas de progreso suficientes como para pasar a fase
> 2, y así a fase 3 y a las fases que establezca el plan de intervención. Y
> luego al terminar, aceptar si el caso está cerrado y solucionado o no."*

| # | paso | estado hoy |
|---|---|---|
| 1 | Anamnesis | existe |
| 2 | Análisis funcional | existe |
| 3 | Plan de intervención, **sencillo (por fases) o complejo (entero)** | existe: `s-plan-fases` / `s-tracking` |
| 4 | **Aceptar la intervención** | arreglado hoy — vuelve a guardar y a activar el seguimiento |
| 5 | Seguimiento | existe |
| 6 | **Push de seguimiento** | motor montado; **faltan los textos del founder** |
| 7 | Cada día: abrir el seguimiento, rellenar y hacer **los ejercicios de ese día** | existe, pero salen del plan ENTERO → hay que atarlos a la fase |
| 8 | **Aviso al tercer día saltado seguido** — solo si ya hay constancia previa | no existe |
| 9 | En la hoja diaria: **consultar el estado y la evolución del perro** | existe como pantalla suelta; hay que meterla ahí |
| 10 | Al completar los ejercicios de la fase: **consulta con Teo para pasar de fase** | no existe |
| 11 | **Cuestionario de paso de fase**: cero banderas de regresión + banderas de progreso suficientes | no existe |
| 12 | Al terminar: **cerrar el caso** diciendo si quedó resuelto o no | no existe |

### La puerta de fase (paso 11)

No la decide el dueño a ojo ni la decide un contador de días. Se pide la
consulta a Teo y el cuestionario se evalúa con dos listas:

- **Banderas de regresión** — si aparece **una sola**, no se pasa de fase. Se
  explica cuál y qué hacer esta semana.
- **Banderas de progreso** — tienen que ser **suficientes**, no una.

El criterio concreto de cada fase lo escribe el propio plan de intervención
("cómo sabrás que puedes pasar a la siguiente", observable y contable).

### Orden dentro de la hoja diaria

Primero los ejercicios, después la consulta: los ejercicios son el material
sobre el que se consulta. Hoy el dueño entra y se encuentra el formulario de
consulta delante.

## 4. NOTIFICACIÓN

Push diaria de los ejercicios, como había antes. Se apoya en lo ya montado en
`app/core/push.py`. **Los textos los pone el founder**, no se inventan.

## 4-bis. ORDEN DE TRABAJO (founder, 19-oct-2026)

Primero **toda la parte conductual**, en los tres idiomas — español, inglés e
italiano. Cuando eso esté zanjado y bien hecho, y solo entonces, se replica
igual en la **parte cognitivista italiana**: ejercicios diarios cognitivistas y
**consulta a Odette** en lugar de la consulta a Teo.

> *"Con la puerta dura de que sea el lenguaje cognitivista en la sección
> cognitivista italiana. Pero escucha, en la italiana hay una parte conductual y
> una parte cognitivista. No se pueden mezclar. Acuérdate."*

Esto NO es una traducción: es la segunda vía, con su propio motor, su propio
vocabulario y su propia voz. El italiano tiene **las dos** vías, y el canal es
estanco en los dos sentidos (decisiones del 4-sep y 6-sep en `CLAUDE.md`). El
seguimiento por fases cognitivista tendrá que pasar por `sin-fugas` igual que
pasó la relazione.

| | conductual (es · en · it) | cognitivista (solo it) |
|---|---|---|
| Quien responde | Teo | **Odette** |
| Vocabulario | conductual | cognitivista, sin una palabra ABA |
| Cuándo se hace | **ahora** | después, replicando lo de al lado |

## 5. LO QUE NO SE TOCA

- El profesional sigue viendo el plan entero de una vez. Las fases son del
  particular.
- La vía cognitivista italiana es estanca: nada de esto entra ahí sin decidirlo
  aparte.
- Todo uso tiene coste: la generación diaria no puede cobrar 0.

---

## Estado

| pieza | estado |
|---|---|
| Regresión del aceptar (paso 4) | **ARREGLADA** 19-oct |
| `Case.current_phase` | pendiente |
| Parseo de fases en servidor | pendiente |
| `/daily-followup/today` por fase (paso 7) | pendiente |
| Aviso de 3 días saltados (paso 8) | pendiente |
| Consultar estado y evolución desde la hoja diaria (paso 9) | pendiente |
| Consulta de paso de fase (paso 10) | pendiente |
| Cuestionario con banderas (paso 11) | pendiente |
| Cierre del caso, resuelto o no (paso 12) | pendiente |
| Consulta a Teo alimentada con el historial de ejercicios | pendiente |
| Push diaria (paso 6) | motor listo; **faltan los textos del founder** |
