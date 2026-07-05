# Mapeo ABA ↔ cognitivista (IT) + lista negra — BORRADOR para validación del founder

> **Diseño (Opción B, cerrado 2026-07-05):** un solo motor conductual. En la rama
> `lang=='it'` + `stance=='cognitive'`, la **pasada 1** corre el motor ABA puro (invisible,
> congelado — piso de seguridad clínica: ED real, plan ejecutable, LIMA); la **pasada 2**
> reescribe la superficie a marco cognitivo-etológico consultando la **RAG cognitivista
> separada**. El veterinario italiano **nunca ve una palabra ABA**. Los dos planes (conductual
> vs cognitivista) **pueden diferir** en marco, énfasis y extras, pero el cognitivista **no puede
> salir clínicamente más débil ni menos ejecutable** que el conductual.
>
> **Marchesini: APARCADO.** No entra como parte por ahora. Los anclajes de citas son
> **etología/ciencia cognitiva reales** (Coppinger, Scott, von Uexküll, Belyaev), no su obra.
>
> **Regla de oro:** nada de lo que aquí figure es definitivo. Yo no invento terminología clínica
> italiana; las filas **[VALIDAR]** esperan tu término canónico. Corta, cambia y añade lo que sea.

---

## 1) LISTA NEGRA — términos ABA PROHIBIDOS en superficie (it + cognitivo)

Gate mecánico en código: antes de devolver cualquier texto de la vía cognitivista (análisis,
plan, seguimiento, chat, cabeceras, **strings estáticos del frontend** y **PDF**), el backend
escanea contra esta lista. Si aparece **uno solo** → se rechaza y se regenera; si agota
reintentos → error + refund (NUNCA degradar a salida conductual).

| # | Término ABA prohibido (IT) | Por qué delata conductismo | Equivalente cognitivista canónico (superficie) | Estado |
|---|---|---|---|---|
| 1 | rinforzo / rinforzo positivo / negativo | núcleo operante | vantaggio / beneficio ottenuto · ciò che il cane ottiene o evita | **[VALIDAR]** |
| 2 | estinzione | operante | riduzione della condotta per venir meno del vantaggio | **[VALIDAR]** |
| 3 | stimolo discriminante (SD/ED) | operante | attivatore / contesto-innesco / situazione che orienta la condotta | **[VALIDAR]** |
| 4 | condizionamento operante / operante | nombra el mecanismo | (no se nombra el mecanismo; se describe la relazione situazione–condotta–esito) | propongo |
| 5 | contingenza / contingenza a tre termini | operante | relazione tra situazione, condotta e conseguenza | propongo |
| 6 | analisi funzionale del comportamento / ABC | marca de escuela | lettura / profilo del comportamento · analisi etologico-cognitiva | **[VALIDAR]** |
| 7 | rinforzo differenziale · DRA / DRI / DRO | jerga operante | costruzione di una condotta alternativa / incompatibile | propongo |
| 8 | controllo dello stimolo | operante | gestione del contesto e degli attivatori | propongo |
| 9 | operazione motivante / establishing operation | operante | stato motivazionale / predisposizione del momento | propongo |
| 10 | comportamento-problema (como término técnico) | frío/conductual | condotta / manifestazione comportamentale | propongo |
| 11 | punizione (positiva/negativa) | operante | — (LIMA prohíbe aversivos; no debe aparecer en ningún caso) | propongo |
| 12 | condizionamento classico / rispondente | escuela | associazione appresa tra stimoli | propongo |

> **Cobertura del gate:** la lista se aplica también a (a) las **cabeceras/plantilla** (p. ej. una
> cabecera "ANALISI ABC" delataría la escuela → debe ser "LETTURA DEL COMPORTAMENTO" o lo que fijes),
> (b) los **strings estáticos del frontend** italiano ANTES del build de App Store (es lo único
> que queda congelado en el binario), y (c) el **PDF** exportable (lo ve el cliente final).

---

## 2) MAPEO de re-expresión — cómo se traduce cada bloque del output

No es sustitución palabra-a-palabra: es reescribir el bloque manteniendo **la misma decisión clínica**.

| Bloque del análisis/plan | ABA interno (pasada 1, invisible) | Superficie cognitivista (pasada 2) |
|---|---|---|
| Antecedente / disparador | stimolo discriminante concreto | l'attivatore / la situazione che innesca la condotta |
| Función de la conducta | rinforzo positivo/negativo automatico/sociale | il vantaggio che il cane ne ricava (ottiene X / evita Y) |
| Conducta objetivo | comportamento-problema | la condotta di cui ci occupiamo |
| Mecanismo del plan | DRA/DRI + estinzione + controllo stimolo | costruire una condotta alternativa più conveniente e gestire il contesto |
| Criterios del plan | criterios numéricos, fases | **idénticos** — números y fases NO se tocan, solo su rótulo |
| Capa disposicional | disposición con historia de reforzamiento | motivazione di specie/razza (lente etológica, ver §3) |

> **Invariante que verifica el test de mapeo inverso:** deshacer esta traducción debe recuperar
> el ED, la función y los pasos numerados de la pasada 1. Si no los recupera → salida rechazada.
> (Los pasos y criterios numéricos son **zona cero-reescritura**: cambia el nombre del proceso,
> nunca el número ni el orden.)

---

## 3) CORPUS de la lente etológica útil (el "10%" real — extras genuinos, citables)

Estos SÍ aportan y son ciencia real. Se emiten solo si hay paralelismo conductual limpio
(gate de la regla dura) y solo en la capa disposicional/motivacional — nunca sobre el ED
concreto, la función ni los verbos del plan.

| Concepto (IT) | Anclaje real citable | Aporta (por qué no es humo) |
|---|---|---|
| motivazione predatoria (orientamento–fissazione–inseguimento–presa) | Coppinger & Coppinger, *Dogs* (2001) | identifica contra qué compite el plan y qué es reforzante para la raza |
| comportamento epimeletico / et-epimeletico | J. P. Scott (1958); Scott & Fuller (1965) | nombra la clase de conducta de cuidado/solicitud |
| neotenia / pedomorfosi | Coppinger; zorros de Belyaev (Trut) | contexto filogenético de la disposición |
| motivazione perlustrativa / esplorativa | etología clásica (open-field) | encuadra conducta exploratoria |
| motivazione sociale / collaborativa | cooperación intra/interespecífica | encuadra motivación social |
| Umwelt (mondo percettivo di specie) | von Uexküll (1934) | mundo perceptivo de la especie (NO para reetiquetar el ED del caso) |
| arousal / attivazione | psicología comparada | variable de estado como antecedente distal (no como función) |

> **Marchesini queda fuera** del corpus de citas por ahora. Si algún día vuelve, el corpus
> validado por ISBN sigue en `ITALIAN_SIUA_GLOSSARY_DRAFT.md`.

---

## 4) Decisiones que necesito de ti antes de cablear

1. **Términos [VALIDAR]** de la lista negra (§1, filas 1-3-6 sobre todo): dame el equivalente
   cognitivista canónico que usan de verdad los veterinarios italianos, o confirma mis propuestas.
2. **¿Cuánto pueden diferir los planes?** Confirmas Opción B: difieren en marco/énfasis/extras,
   nunca por debajo del piso ABA (ejecutabilidad + LIMA). ✔ ya acordado — solo lo dejo escrito.
3. **Copy de los dos botones** (pre-anamnesis, italiano): "Postura cognitivista" / "Postura
   comportamentale" — o el texto exacto que quieras. Me lo das tú (no invento copy público).
4. **Fallo de pasada 2 = error + refund** (el veterinario nunca ve ABA). ✔ acordado.
5. **Nombre de la cabecera** que sustituye a "SINTESI ABC" en la vía cognitivista.

Cuando valides §1 y me des §4.1/§4.3/§4.5, monto: RAG cognitivista (collection nueva) + gate
`stance` + pasada 2 de re-expresión + gate de lista negra + test de mapeo inverso. Todo detrás
de flag nuevo que arranca APAGADO, con es/en intactos.

---

## 5) RAG B — población (decidido 2026-07-05: ~200 casos cognitivistas REALES)

**Origen del corpus (2026-07-05):**
- **Casos (~200):** de **Odette Abramovich**, **SOCIA del proyecto**. Consentimiento de uso como
  corpus: RESUELTO por su condición de socia (aporte de la sociedad, no cesión de tercero).
  ⚠️ Pendiente independiente: **anonimizar a los clientes finales** (dueños de los perros) que
  aparezcan dentro de los casos — son terceros, GDPR aplica igualmente. Atribución a Odette si
  procede: copy lo da el founder.
- **Bibliografía cognitiva:** la selecciona y aporta el **founder** (además de los anclajes
  etológicos ya validados: Coppinger, Scott, von Uexküll, Belyaev).

**Rol de los casos:** corpus de **expresión** (estilo, marco, terminología, ejemplos de
redacción cognitivista), NO fuente diagnóstica. La conclusión (ED, función, plan) sigue saliendo
del motor ABA (pasada 1). Los 200 casos enseñan a la pasada 2 *cómo escribe un cognitivista*,
no *qué concluir*.

**Por qué encaja sin riesgo:** si la tesis del founder es correcta (cognitivismo = ABA con otras
palabras), estos 200 casos hacen ABA por debajo → no pueden contradecir al motor; solo aportan
el dialecto real. Son molde de oro.

**Prerrequisitos de ingesta (antes de meterlos en la RAG B):**
1. **Formato/origen:** ¿en qué están (PDF, texto, export de la app, base propia)? Define el trabajo de parseo.
2. **ANONIMIZACIÓN (requisito duro, GDPR/UE — Italia):** casos reales = datos de dueño/perro.
   Hay que **quitar toda PII** (nombres de propietario, teléfonos, direcciones, datos
   identificativos) antes de que entren al vector store. Nombre del perro y raza pueden quedar si
   no identifican a una persona; el resto se despersonaliza.
3. **Curación para el piso de calidad:** descartar/limpiar los casos que modelen el fallo que el
   propio founder critica —verbos grandilocuentes no ejecutables ("accompagnare il dialogo",
   "ripristinare la relazione")— para que la pasada 2 NO aprenda a diluir el plan. Se conserva el
   marco cognitivista, se exige que el molde sea de planes **ejecutables**.
4. **Idioma:** confirmar que están en italiano (o plan de traducción).

**Aislamiento:** entran SOLO a la collection RAG B; jamás a `dogs_mind_knowledge` (RAG A).
Recuperación gateada por `lang=='it'` + `stance=='cognitive'`.
