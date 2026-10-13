# El plan vivo — el caso deja de ser un documento

Decidido con el founder el 13-oct-2026. Sustituye a la forma actual de entregar
el plan de intervención al particular. **Nada de esto está implementado: esto es
el diseño acordado, para trabajar contra él.**

La frase que lo resume, suya: *"no te da un plan y adiós — es un plan vivo con el
que estás interactuando de forma constante"*. Es la queja que el founder oye
sobre los veterinarios comportamentalistas, y hoy la app hace exactamente eso.

**Maqueta viva:** https://tdm-mockups.netlify.app — el recorrido entero
(entrega → semana 1 → cuestionario → fase superada → fase 2), con la vibración y
el sonido funcionando de verdad. Sitio de maquetas, nunca producción.

---

## Los números que lo justifican

Medidos el 13-oct-2026 sobre la población entera, no sobre una muestra.

**Lo que se lee de una sentada.** Palabras reales contadas sobre el texto
guardado en `case_entries`:

| quién | pieza | mediana | p90 |
|---|---|---|---|
| Particular | análisis | 387 | 1.802 |
| Particular | **plan** | **717** | 1.535 |
| Profesional | análisis | 1.533 | 1.850 |

El plan del particular tiene un tope duro de 450 palabras en el prompt
(`petowner_intervention.py:36`) y la mediana real es 717: **se salta su propio
límite en un 60 %**.

**Por qué semanal y no diario.** De 145 casos con seguimiento:

| | |
|---|---|
| Récord de días SEGUIDOS en toda la historia de la app | **8, una sola persona** |
| Casos que siguen ahí 7+ días | 57 |
| Casos que siguen ahí 30+ días | 18 |
| **Casos que aparecieron en 2+ semanas distintas** | **63** |
| Casos que aparecieron en 4+ semanas distintas | 16 |

**63 frente a 1.** La gente aguanta semanas; lo que no hace es venir cada día.
Una puerta de racha diaria los cuenta a todos como fracasos. Una cadencia
semanal encaja con lo que ya hacen.

**Por días anotados, no seguidos.** Exigiendo días consecutivos, 2 casos
llegarían a 4-5 días. Contando días anotados sin exigir que sean seguidos,
llegan 28. Mismo esfuerzo del usuario, diez veces más gente que cruza — y es más
justo: quien trabaja lunes, miércoles y viernes está trabajando con su perro.

---

## Lo decidido

### 1 · El plan se entrega por semanas

10-12 semanas, una por bloque. **El motor hoy no produce semanas**: entrega
OBJETIVO · LA IDEA · FASE 1 · FASE 2 · SEÑALES. Hay que cambiar el prompt para
que salga con calendario, y poner el tope de palabras **por semana** (~120) en
vez de un tope global que ya se está ignorando.

### 2 · Dos lecturas, una sola generación

| | Modo guiado | Plan completo |
|---|---|---|
| Por defecto en | Particular | Profesional |
| Qué ve | Una semana cada vez | Todo, como hoy |
| Puede cambiar al otro | Sí | Sí |

El plan se genera **entero y de una vez**: mismo coste, un solo cobro,
imprimible desde el día uno. Lo que cambia es cómo se sirve.

La puerta es blanda a propósito —el plan es suyo y lo ha pagado— pero el modo
guiado manda en la pantalla y el plan entero vive en el menú y en el PDF.

### 3 · El caso pasa de documento a proceso

Hoy un caso es un archivador: `status` vale `open` en **384 de 385**, o sea que
no significa nada. Con semanas, el caso tiene una posición y **puede terminar**.

Hace falta un puntero en el caso: semana actual, total de semanas, cuándo
empezó. Lo demás ya existe (`daily_followup_enabled`, `current_streak`,
`longest_streak`, `last_filled_at`, `current_badge`, `in_recovery`, y la tabla
`case_daily_tasks` con las tareas pre-generadas — construida y usada en solo 4
casos, o sea lista y sin estrenar).

**Los 385 casos que ya existen llevan el puntero a NULL, y NULL significa "plan
completo, sin puerta", exactamente como hoy.** Nadie se encuentra la app
cambiada debajo.

Y sigue mandando la regla dura del 19-sep: un caso se abre con **lo que se
guardó**, nunca con lo que quedó en pantalla. La semana en que va se lee del
servidor, no del dispositivo, o abres en el iPhone y en el iPad y vas por sitios
distintos.

### 4 · La pantalla del caso

```
Rocky · Semana 3 de 12
▓▓▓░░░░░░░░░

Esta semana trabajamos
  (lo que marca el plan — los OBLIGATORIOS)
  [ Apuntar lo de hoy ]

Ejercicios extra
  (los diarios opcionales, para quien quiera más)

Leer el plan
  [ Ver el plan completo ]  [ Esta semana en detalle ]
  ─────────────────────────
  [ Contarle a Cecilia cómo va ]
```

El feedback va abajo a propósito: visible siempre, sin competir con lo que tiene
que hacer hoy.

### 5 · El feedback, y lo que hace

Al cerrar la semana —que es cuando tiene algo que contar y está mirando la
pantalla— y además disponible cuando él quiera.

> ¿Cómo ha ido la semana?
> · ¿Algún ejercicio que no te esté saliendo?
> · ¿Cómo ha reaccionado Rocky?
> · ¿Algo que quieras preguntarme?

Ese material sirve para **modificar la semana siguiente**. El agente sugiere, el
usuario acepta, y al aceptar se reescribe. Nunca se cambia sin que acepte.

**Cecilia ya es Sonnet** (`avatar_models_per_id: {"cecilia": "claude-sonnet-4-6"}`),
se subió porque con Haiku cedía al primer envite. No hace falta un avatar nuevo
por capacidad; si se hace uno, que sea por lo que representa.

### 6 · Qué cuesta

Economía verificada el 13-oct: precio por token leído de `subscriptions.py`
(0,625 € en Básico · 0,435 € en Max, siendo 1 token = 100 créditos), coste
comprobado a mano contra el precio oficial de Anthropic y cuadrado al céntimo
con `usage_log`.

| | coste real | se cobra | margen |
|---|---|---|---|
| Contar y preguntar | 0,0098 € | 0,1 tk ≈ 0,06 € | 84 % |
| **Aceptar el cambio** | 0,0431 € | 0,2 tk ≈ 0,125 € | **65 %** |

Quejarse es casi gratis; rehacer el plan se cobra. Rehacer un bloque cuesta lo
mismo que generar el plan entero hoy, así que el precio de 0,2 tokens que ya
existe sirve tal cual. Y cumple la regla dura del 13-oct: **nada cobra cero**.

### 7 · Consulta nueva sobre un perro con plan en marcha

El botón "+ Nueva consulta para X" pregunta antes:

> Rocky ya tiene un plan en marcha. Vas por la semana N de 12.
> Lo que me quieres contar, ¿es…?
> [ Algo nuevo y distinto ]  [ Lo mismo, quiero contarte cómo va ]

**Algo nuevo** → consulta nueva, como hoy. Dos casos vivos para el mismo perro es
legítimo: reactividad en la calle y destrozos en casa son dos cosas.

**Lo mismo** → entra en el caso que ya tiene. Hoy ese botón dispara un análisis
completo y cobra **3 tokens** por volver a contar el mismo problema; entrando al
caso, lo que necesita es el chat del plan, a **0,25**. Doce veces menos por la
misma intención, y evita acabar con tres casos abiertos de lo mismo y el
seguimiento repartido entre los tres.

La pregunta solo sale si hay plan en marcha.

### 8 · El push

El disparador deja de ser "3 días sin aparecer" y pasa a ser **"no has abierto la
semana"**. Infraestructura ya desplegada (ver `SPEC_PUSH_REACTIVACION.md`).

---

## Textos

**Los escribe el founder.** Los de las notificaciones ya están aprobados y viven
en `SPEC_PUSH_REACTIVACION.md`. Los de las pantallas de arriba son maqueta de
trabajo, no copy final.
