# Red profesional — círculos de clientes alrededor de un profesional

**Estado: SPEC, trabajo a MEDIO PLAZO. No se publica.**
Founder, 7-sep-2026: *"no lo publiques, es un trabajo a medio plazo"*. Nada de
esto está construido: no hay tablas, ni endpoints, ni pantalla. Este documento
es el diseño acordado para cuando toque, no un pendiente activo.

Origen: founder, 7-sep-2026. *"Los profesionales se dan de alta con un número de
licencias y sus clientes pueden descargarse la app y meter un código del
profesional aceptando compartir los datos de su perro. De esa manera todos sus
clientes estarán en su red y él tendrá acceso a ver las fichas de todos los
perros a su cargo y ver si sus clientes han hecho los ejercicios diarios."*
Y la forma: *"serían círculos de clientes alrededor de un profesional"*.

---

## La decisión comercial, que ya está tomada

> *"Lo más sencillo es que el profesional pague una licencia y los usuarios una
> suscripción y se genere una estructura"* (founder, 7-sep-2026).

- El **profesional paga una licencia**. Le da el círculo y el centro de control.
- **Cada cliente paga su propia suscripción** y consume sus propios créditos.
- **No hay bolsa común.** Esto es lo que separa esta figura de la cuenta
  corporativa que ya existe: allí la universidad pone los créditos de sus
  alumnos; aquí el profesional no paga el consumo de nadie.

Consecuencia directa: **no se reutiliza `Corporate` tal cual**. Se le parece en
el código de afiliación y en el tope de altas, pero su razón de ser —repartir
una bolsa de créditos pactada— aquí no aplica.

---

## Qué hay ya construido, y qué no

| pieza | estado |
|---|---|
| Código de afiliación + tope de altas + caducidad | **existe**, en `Corporate` (`code`, `max_members`, `expires_at`) |
| Alta del cliente con un código | **existe**, `POST /corporate/join` |
| Ejercicios diarios del cliente | **existen**: `CaseDailyTask` (días 1-30) y `DailyFollowupEntry` (`day_local_date`, `task_completed`, `execution_quality`, `dog_state`) |
| Ficha del perro | **existe**, `Dog`, con **un solo dueño** (`user_id`) |
| Vínculo perro ↔ profesional | **no existe** |
| Registro de consentimiento | **no existe** |
| Camino de lectura para el profesional | **no existe**: los 47 filtros de las rutas son por "el usuario que pregunta" |
| Alta de licencia por el propio profesional | **no existe**: hoy los acuerdos los crea un admin |

La buena noticia: **el dato que quiere ver ya se está recogiendo**. No hay que
instrumentar nada nuevo para saber si el cliente hizo el ejercicio del día.

---

## El modelo: círculos

Un **círculo** es el conjunto de clientes de un profesional.

Un cliente **puede estar en más de un círculo** a la vez: un perro puede tener
veterinario y adiestrador. Por eso la relación es de muchos a muchos, y **cada
pertenencia lleva su propio consentimiento**: aceptar compartir con el
veterinario no comparte nada con el adiestrador.

### Tablas nuevas

**`professional_licenses`** — la licencia que compra el profesional
```
id · owner_user_id → users.id · code (único, el que reparte a sus clientes)
seats (licencias contratadas) · seats_used
status (active | past_due | canceled) · store (apple|google|stripe)
expires_at · created_at · revoked_at
```

**`circle_members`** — cada cliente dentro del círculo, con su consentimiento
```
id · license_id → professional_licenses.id · client_user_id → users.id
dog_id → dogs.id            (se comparte UN perro, no la cuenta entera)
scope (ver abajo)
consent_given_at · consent_text_version   ← qué aceptó exactamente y cuándo
revoked_at · revoked_by (client | professional)
status (pending | active | revoked | expired)
```

Índice único por `(license_id, client_user_id, dog_id)` para que no haya
duplicados, y **`revoked_at` nunca se borra**: la revocación es historia, no un
borrado. Si el cliente vuelve a aceptar, es una fila nueva.

### El alcance (`scope`) — qué ve el profesional

Tres niveles. **El que hay que confirmar contigo es cuál se pone por defecto**;
mi propuesta es el nivel 2, porque es exactamente lo que pediste y ni un dato
más.

| nivel | qué abre |
|---|---|
| 1 · seguimiento | Solo la adherencia: si hizo el ejercicio del día, con qué calidad, y la racha. Sin texto libre. |
| **2 · ficha + seguimiento** *(propuesto)* | Lo anterior más la **ficha del perro**: nombre, raza, edad, peso, notas de salud. |
| 3 · caso completo | Lo anterior más las anamnesis, los análisis y los planes. Es historia clínica: solo con un consentimiento explícito y aparte. |

El nivel se guarda **por pertenencia**, no por licencia: un cliente puede darle
el nivel 3 a su etólogo y el 1 a su adiestrador.

---

## Los caminos

### El profesional
1. Compra la licencia (N asientos) desde su área. Se le genera un **código**.
2. Ve su **centro de control**: la lista de sus círculos con, por cada perro,
   el nombre, el cliente, la adherencia de los últimos 7 y 30 días y la fecha
   del último registro.
3. Puede **retirar** a un cliente de su círculo, lo que libera un asiento.
4. **No** puede añadir a nadie por su cuenta: el alta la hace siempre el cliente.

### El cliente
1. Se descarga la app y **paga su suscripción**, como cualquiera.
2. Mete el **código del profesional** y elige **qué perro** comparte.
3. Ve, con todas las letras, **qué se va a compartir** y con quién. Acepta.
4. En su cuenta tiene siempre a la vista con quién comparte, y un botón para
   **dejar de compartir** que surte efecto al instante.

### Endpoints nuevos
```
POST   /professional/license            comprar/activar licencia
GET    /professional/license            mis asientos y mi código
GET    /professional/circle             mis clientes, con adherencia
DELETE /professional/circle/{member_id} retirar a un cliente

POST   /circle/join                     el cliente entra con código + perro + alcance
GET    /circle/mine                     con quién comparto y qué
DELETE /circle/mine/{member_id}         dejar de compartir, ahora
```

---

## Cómo se protege esto

**La frontera actual no se toca.** Los 47 sitios que filtran por el usuario que
pregunta se quedan como están. Lo que se añade es **una segunda vía explícita**,
que para cada lectura exige encontrar una fila en `circle_members` con:
licencia activa y no caducada · `status = 'active'` · `revoked_at` nulo · y un
`scope` que cubra lo que se está pidiendo. Si falta cualquiera de las cuatro,
no se abre nada. Falla cerrado, como la puerta cognitivista.

Ese chequeo vive en **un solo sitio**, y todas las rutas del profesional pasan
por él. Un permiso repartido por cinco ficheros se rompe solo.

**Lo que hay que decidir y no puedo decidir yo:**
- Si el profesional pierde la licencia (impago, cancelación), ¿deja de ver a sus
  clientes de inmediato, o hay un periodo de gracia?
- Si el cliente deja de pagar su suscripción, ¿sigue siendo visible para su
  profesional?
- ¿Puede el profesional **escribir** algo (una nota, un ejercicio), o solo leer?
  La spec de arriba es de solo lectura.

---

## Lo que esto obliga fuera del código

Pasas a **compartir datos personales entre usuarios**, y eso no es un detalle:

- **Apple y Google**: hay que actualizar la ficha de privacidad de las dos
  tiendas. Es la clase de cambio que un revisor mira.
- **Textos legales**: `privacy.html` y `terms.html` tienen que decir qué se
  comparte, con quién y cómo se revoca. Ese copy **lo escribes tú**.
- **El texto del consentimiento** se versiona (`consent_text_version`): si
  mañana cambia lo que se comparte, hay que saber qué aceptó cada cliente.
- Si un cliente **borra su cuenta**, su pertenencia se va con ella.

---

## Por fases

**Fase 1 — la estructura.** Las dos tablas, el chequeo único de permiso, y los
caminos de alta y de revocación. Sin centro de control todavía: se comprueba con
llamadas directas.

**Fase 2 — el centro de control.** La pantalla del profesional con la lista de
perros y la adherencia. Es lo que hace la licencia vendible.

**Fase 3 — la licencia de pago.** Producto en las tiendas y asientos.
Va la última a propósito: hasta que la estructura no esté probada, no se cobra
por ella.
