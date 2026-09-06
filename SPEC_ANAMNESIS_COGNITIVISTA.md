# Anamnesis cognitivista italiana — modelo Odette Abramovich

**Estado (7-sep-2026): MONTADO, sin desplegar ni compilar.**

| pieza | estado |
|---|---|
| Modelo `AnamnesiCognitivaInput` (29 campos de Odette) | hecho |
| Prompt del informe, 8 secciones | hecho |
| Motor `cognitive_odette.py` (ABA oculto → RAG B → auditoría) | hecho |
| Endpoint `POST /analysis/cognitiva`, con la puerta delante | hecho |
| Pantalla `s-anamnesi-cognitiva`, italiano a fuego | hecha |
| Canal estanco (entrar, salir, cambio de idioma) | hecho y probado |
| Detectores de fuga, estático y en vivo | hechos |
| **Desplegar backend** | **pendiente de su OK** |
| **Compilar y enviar app** | **pendiente de su OK** |
| Informe en PDF con la plantilla de Odette | pendiente |
| Cerrar los 13 servicios sin puerta (el "resfriado") | pendiente |

Origen: *Scheda anamnestica* de la **Dott.ssa Odette Abramovich**, médico
veterinario experta en comportamiento animal. PDF de 9 páginas entregado por el
founder el 4-sep-2026 (ejemplar relleno: Yuki, maltipoo de 8 meses). El founder
lo subirá también a la RAG B.

---

## Por qué no es un cambio de etiquetas

La anamnesis actual es **ABC**: antecedente, conducta, consecuencia. Campos
discretos alrededor de un problema, pensados para alimentar un análisis
funcional.

La de Odette es **biográfica**. Pregunta de dónde viene el perro, por qué lo
adoptaste, cómo es un día entero con sus horarios, qué le gusta hacer, qué
emociones predominan en él, cómo se relaciona, y qué quieres aprender tú en la
visita. El perro como sujeto con historia, no como un conjunto de contingencias.

Adaptar una a otra **no es traducir campos**: es cambiar qué se le pregunta al
dueño y, por tanto, con qué materia prima trabaja el motor.

---

## Las preguntas, en su orden

### Identificación
1. Email
2. Nombre y apellidos de quien rellena, dirección, código postal, ciudad, código
   fiscal y email *(necesario para factura — **de la consulta privada de Odette,
   probablemente NO aplica en la app**)*
3. ¿Qué animal traes a la visita?
4. ¿Cómo se llama?
5. ¿Qué edad tiene?
6. ¿Está castrado/esterilizado y a qué edad?

### Motivo
7. Describe brevemente el motivo de la visita
8. ¿Cuáles de estos comportamientos has notado? *(casillas múltiples)*
   Vocalización excesiva · Deyección en lugar inadecuado · Destrucciones ·
   Agresividad · Ansiedad · Ataques de pánico · Estereotipias · Problemas con
   correa o en libertad · Impetuosidad · Hiperactividad · Inactividad

### Historia y contexto
9. ¿De quién se compone el núcleo familiar? ¿Convive con otros animales o niños?
10. ¿Cuál fue el motivo de la adopción?
11. ¿Qué sabes de su vida antes de la adopción? Procedencia, padres…
12. ¿Qué come, cuándo y cómo? *(marcas y cantidades)*

### Cómo afronta el mundo
13. ¿Cómo afronta los viajes?
14. ¿Cómo afronta las separaciones?
15. ¿Cómo afronta las visitas al veterinario?
16. ¿Cómo se comporta en lugares públicos (bares, restaurantes)?
17. ¿Cómo son las relaciones con otros animales?
18. ¿Ha sufrido traumas alguna vez?

### Salud
19. ¿Qué patologías o síntomas tiene o ha tenido? *(casillas múltiples)*
    Dermatológicos · Gastroentéricos · Vías urinarias · Neurológicos · Pica ·
    Intervenciones quirúrgicas · Otro
20. ¿Qué fármacos toma?

### Vida cotidiana
21. ¿Qué ambientes tiene permitidos o a su disposición? *(casillas)*
    Zona de día · Zona de noche · Jardín · Balcón · Otro
22. **¿Cuáles son las emociones predominantes en tu animal?** *(casillas)*
    Alegría · Miedo · Rabia · Aburrimiento · Nostalgia · Tristeza · Ansiedad ·
    Otro
23. ¿Qué le gusta hacer a tu animal?
24. ¿Qué sabe hacer en términos de ejercicios?
25. ¿Qué te gusta hacer a ti con tu animal?
26. ¿Qué juegos sabe hacer contigo o en autonomía?
27. ¿Qué ejercicios o actividad física realiza? *(opción única)*
    Paseo · Juegos con otros animales · Juegos contigo · Actividad en casa ·
    Actividad en libertad · Deporte · Otro
28. **Describe un día tipo con todos los detalles (horarios y tiempos)**

### Cierre
29. ¿Cómo conseguiste mi contacto? *(de la consulta privada — probablemente no
    aplica)*
30. ¿Has visto ya a otros profesionales antes que a mí?
31. **¿Qué quieres aprender en la visita?**
32. ¿Tu animal ha agredido alguna vez a alguien o ha sido notificado a la ASL?
33. Consentimiento de datos *(la app ya tiene el suyo — no duplicar)*
34. *Espacio para que lo rellene el veterinario experto en comportamiento*

---

## Lo que hay que decidir antes de montarlo

- **Campos que no aplican en la app**: datos de facturación y código fiscal (2),
  cómo consiguió el contacto (29) y el consentimiento (33) son de la consulta
  privada de Odette. Confirmar con el founder.
- **¿Sustituye o convive?** ¿La vía cognitivista usa SOLO esta anamnesis, o la
  actual más estas preguntas? Afecta al motor: el ABC de la pasada 1 necesita
  antecedente y consecuencia, y aquí no se preguntan como tales.
- **Las tres preguntas con más peso cognitivista** —emociones predominantes (22),
  el día tipo con horarios (28) y qué quiere aprender el dueño (31)— no tienen
  equivalente en la anamnesis actual. Son las que más cambian el análisis.
- **Estanqueidad**: esta anamnesis es SOLO para `stance='cognitive'` en italiano.
  No puede aparecer en la vía conductual ni en español o inglés. Ver la regla del
  Ébola en `CLAUDE.md`.

---

# El INFORME cognitivista — modelo Odette

Dos casos reales entregados por el founder el 4-sep-2026: **Yuki** (cachorra de
8 meses, "Progetto Educativo", 10 páginas) y **Viola** (adulta de 4 años,
"Percorso Rieducativo", 14 páginas). Los dos siguen el MISMO esqueleto, así que
es una plantilla, no dos redacciones sueltas.

## Esqueleto

**Título**: `CASO [Nombre]: PROGETTO EDUCATIVO` (cachorro / educación) o
`PERCORSO RIEDUCATIVO` (adulto / reeducación). Subtítulo: *Relazione Clinica
Comportamentale e Pianificazione dell'Intervento*.

**Encuadre anagráfico y clínico** — tabla de dos columnas: nombre, especie y
raza, edad y peso, sexo y estado reproductivo, microchip, convivientes y núcleo,
residencia, alimentación (marca, gramos, número de comidas, si el cuenco queda a
disposición), estado clínico.

**1. ANAMNESI CLINICA ED EVOLUTIVA**
 · *Origine e Inserimento*: de dónde viene, camada, cuánto tiempo con la madre,
   por qué lo adoptaron, qué hueco venía a llenar.
 · *Evoluzione del Comportamento e Segnalazioni*: la historia en orden temporal,
   con edades. "A los 2 meses… a los 5 meses… en el último viaje…".

**2. OSSERVAZIONE DIRETTA E INDIRETTA**
 · *Indiretta*: análisis de los vídeos que aporta la familia.
 · *Diretta*: lo visto en la visita, en casa y en exterior.

**3. STUDIO DELLE COMPONENTI MENTALI (TASSONOMIA CZ)** — recuadro verde
 · **A) Componenti posizionali**: motivaciones prevalentes (hiper-polarizadas),
   motivaciones **negligidas** (sub-expresadas), emociones prevalentes, arousal.
 · **B) Componenti elaborative**: representaciones, funciones cognitivas
   (funciones lógicas y metacomponentes: atención, memoria, detour, tolerancia
   a la frustración).

**4. APPRAISAL, NUOVE STRATEGIE E POSIZIONAMENTO**
 · *Appraisal* según el modelo de **Roberto Marchesini**.
 · *Nuove strategie (coping)*.
 · *Posizionamento sociale*: rango como función situacional —NO dominancia—,
   los **4 indicadores CZ** (gestión de recursos, de relaciones, de iniciativas,
   de espacios) y la sistémica familiar.

**5. PROGETTO / PERCORSO EDUCATIVO**
 · Teoría de las motivaciones: disciplinar las hiper-expresadas, desarrollar las
   negligidas.
 · **Tabla de encuentros**: `Incontro 1…7` × (Focus operativo y objetivos CZ ·
   Protocolos prácticos aplicados, numerados `[1]…[21]`).

**6. LEGENDA TECNICA DEGLI ESERCIZI**
 Cada ejercicio numerado con cuatro apartados fijos:
 *Obiettivo Pedagogico* · *Esecuzione Pratica* · *Criteri di Adeguatezza* ·
 **Controindicazioni**.

**7. DIARIO / MONITOREO** — tabla semanal con escalas 1-5 (calma en casa, mirada
 espontánea, autonomía, nuevas estrategias) y anotaciones.

**Recuadro de ATENCIÓN MÉDICA** cuando aplica (en Yuki: celo y pseudogestación,
 con qué vigilar y cuándo volver a la clínica).

**8. CONCLUSIONI E PROGNOSI** — revaluación y seguimiento con fecha concreta
 (60 días), y pronóstico. Firma: *Dott.ssa Odette Abramovich Terol, Esperta in
 Comportamento Animale, Studiosa di Zooantropologia Applicata*.

## Vocabulario propio que hay que respetar

Motivaciones: affiliativa, et-epimeletica, epimeletica, comunicativa,
somestesica, cinestesica, esplorativa, perlustrativa, collaborativa, protettiva,
possessiva, competitiva, sillectica, di solitaria autogestione.
Otros: appraisal, coping, arousal, cooling-down, referenzialità, prossemica,
detour cognitivo, iper-polarizzazione, motivazioni neglette, i 4 indicatori CZ,
sistemica familiare.


---

# Cómo se genera: hechos debajo, prosa CZ encima

**Decidido el 4-sep-2026.** El founder sobre los informes de Odette: *"la respeto
obviamente pero me pone de los nervios porque con tanta prosa es peligrosa porque
le falta estructura medible y método científico y está llena de constructos"*.

Y sin embargo la estructura se respeta entera, porque es la que entiende y firma
el veterinario italiano. Lo que cambia es lo que hay debajo.

## Las dos pasadas

**Pasada 1 — HECHOS (interna, nunca se enseña).**
No es un análisis ABA con su vocabulario, como hoy. Es una extracción de hechos
observables a partir de la anamnesis: qué ocurre, cuándo, con quién, qué hace el
cuerpo, en qué orden, a qué edad, con qué frecuencia, qué lo precede y qué viene
después. **Cero terminología funcional.** Es el ancla contra la invención: sin
ella el modelo escribe prosa cognitivista preciosa sacada del relato del dueño, y
eso en un informe clínico que un veterinario firma es peligroso.

Que Odette hace exactamente esto se ve en sus propios informes: *"irrigidimento
posturale completo che culmina in un abbaio"*, *"arousal basale costantemente
elevato"*, *"cooling-down lento"*, *"si attiva tra le 5:00 e le 6:00"*. Observa
primero, interpreta después. La taxonomía CZ es la lectura, no la prueba.

**Pasada 2 — INFORME CZ (lo que se entrega).**
Construye las 8 secciones sobre esos hechos, con el vocabulario y el orden de
Odette.

## Por qué así y no como está hoy

Hoy la pasada 1 genera un análisis ABA **con su vocabulario**, y la 2 lo reescribe
mientras una lista negra frota las palabras conductuales. Es trabajo doble y
frágil: basta que a la lista se le escape un término para que el veterinario vea
ABA. Extrayendo hechos sin vocabulario funcional no hay nada que borrar.

Se gana: el ancla contra la invención · cero vocabulario que limpiar · una sola
redacción en vez de escribir y reescribir.

## Límite

**Solo la vía italiana cognitivista.** La conductual —es, en, it— no se toca. Ver
la regla del Ébola en `CLAUDE.md`.
