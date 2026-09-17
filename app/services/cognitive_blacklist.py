"""
Lista negra léxica de la vía cognitivista italiana.

Blindaje anti-censura (Colegio de Veterinarios italiano): en la vía cognitivista
NINGÚN término de la escuela conductual puede aparecer en superficie. El motor
sigue siendo ABA (pasada 1, invisible); la pasada 2 re-expresa. Este escáner es
un GATE MECÁNICO en código, no una súplica al prompt: si un término prohibido
sobrevive, la salida se rechaza y se regenera; agotados los reintentos, error.

Se aplica al análisis, plan, y a cualquier texto que el veterinario italiano vea.

Nota de diseño: solo entran aquí los términos que son FIRMA de la escuela
conductual. Palabras ambiguas que un cognitivista también usa (p. ej. "punizione"
a secas, al condenarla) NO se prohíben en bruto — solo sus formas técnicas
("punizione positiva/negativa").
"""

import re

# ─────────────────────────────────────────────────────────────────────────────
# REGLA DEL FOUNDER, 11-sep-2026, aplicada por fin el 17-sep:
#
#   "No hay palabras prohibidas en cognitivismo si no hay traducción a lenguaje
#    cognitivista, y todas las palabras cognitivistas de la RAG B están
#    prohibidas en el análisis ABA."
#
# Hasta hoy esta lista vetaba EN BLOQUE, sin mirar si el término tenía
# equivalente. Eso hacía justo el daño que el founder quería evitar: el modelo
# no podía nombrar el concepto, no se le ofrecía con qué sustituirlo, y acababa
# escribiendo vaguedades — mutilando el informe que lee el veterinario.
#
# Ahora cada entrada lleva SU EQUIVALENTE, sacado de la tabla §1 de
# ITALIAN_COGNITIVE_MAPPING_DRAFT.md (yo no invento terminología clínica
# italiana; la tabla es la que hay).
#
#   · equivalente = str  → prohibido, y al regenerar SE LE DICE qué usar.
#   · equivalente = None → NO se persigue. Antes que quedarse vago, que use el
#                          término llano (palabras del founder).
#   · marca = True       → prohibido SIEMPRE, tenga o no equivalente. No son
#                          conceptos que traducir: son el nombre de la escuela
#                          (ABA, ABC, comportamentismo). Que aparezcan delata
#                          el motor de debajo, que es justo lo que el canal
#                          estanco existe para esconder.
# ─────────────────────────────────────────────────────────────────────────────
# (patrón, etiqueta, equivalente cognitivista, es_marca)
# (sin anotacion de union: el repo tiene que correr igual en 3.9 y en 3.11)
_BLACKLIST_PATTERNS = [
    # "rinforzo" SI se puede usar (founder, 7-sep-2026): no es exclusiva del
    # marco conductual, en italiano corriente y en cognitivismo se usa igual.
    # Núcleo operante — todos con equivalente validado en la tabla
    (r"\bestinzion\w*", "estinzione",
     "riduzione della condotta per venir meno del vantaggio", False),
    (r"\bcondizionament\w*", "condizionamento (operante/classico)",
     "associazione appresa tra situazione, condotta ed esito", False),
    (r"\bcontingenz\w*", "contingenza",
     "relazione tra situazione, condotta e conseguenza", False),
    (r"\boperant[ei]\b", "operante/operanti",
     "descrivi la relazione situazione–condotta–esito senza nominare il meccanismo", False),
    (r"\brispondent[ei]\b", "rispondente (condizionamento)",
     "associazione appresa tra stimoli", False),
    # Estímulo discriminativo
    (r"\bstimolo\s+discriminant\w*", "stimolo discriminante",
     "attivatore / contesto-innesco / situazione che orienta la condotta", False),
    (r"\bdiscriminativ\w*", "discriminativo",
     "attivatore / contesto-innesco", False),
    # "stimolo delta" no figura en la tabla validada. Sin equivalente, no se
    # persigue: regla del founder.
    (r"\bstimolo\s+delta\b", "stimolo delta", None, False),
    # MARCAS DE ESCUELA — prohibidas siempre
    (r"\bABA\b", "ABA", None, True),
    (r"\bABC\b", "ABC (analisi a tre termini)", None, True),
    (r"\banalisi\s+funzional\w*", "analisi funzionale",
     "lettura del comportamento / analisi etologico-cognitiva", True),
    (r"\bcomportamentism\w*", "comportamentismo", None, True),
    (r"\bcomportamentist\w*", "comportamentista", None, True),
    (r"\bbehavior\s*analysis\b", "behavior analysis", None, True),
    # Procedimientos operantes
    (r"\bDR[AIO]\b", "DRA/DRI/DRO",
     "costruzione di una condotta alternativa o incompatibile", False),
    (r"\bcontrollo\s+dello\s+stimolo\b", "controllo dello stimolo",
     "gestione del contesto e degli attivatori", False),
    (r"\boperazione\s+(motivante|stabilente)\b", "operazione motivante",
     "stato motivazionale / predisposizione del momento", False),
    # Sin equivalente en la tabla, pero LIMA prohibe el aversivo: no es una
    # cuestion de lexico, no puede aparecer en ningun caso.
    (r"\bpunizione\s+(positiva|negativa)\b", "punizione positiva/negativa", None, True),
    # Sin equivalente validado: antes que quedarse vago, termino llano.
    (r"\bmodellaggio\b", "modellaggio (shaping)", None, False),
    (r"\bshaping\b", "shaping", None, False),
    (r"\bconcatenamento\b", "concatenamento (chaining)", None, False),
    (r"\bchaining\b", "chaining", None, False),
    (r"\btoken\s+economy\b", "token economy", None, False),
]

# Solo se persigue lo que tiene equivalente, o lo que es marca de escuela.
_COMPILED = [(re.compile(p, re.IGNORECASE), label, eq)
             for p, label, eq, marca in _BLACKLIST_PATTERNS
             if (eq is not None or marca)]

# Lo que se deja pasar a proposito, para poder auditarlo de un vistazo.
SE_PERMITEN = [label for _p, label, eq, marca in _BLACKLIST_PATTERNS
               if eq is None and not marca]



def find_blacklisted(text: str) -> list[str]:
    """Devuelve las etiquetas de los términos prohibidos hallados (sin duplicar)."""
    if not text:
        return []
    hits: list[str] = []
    for rx, label, _eq in _COMPILED:
        if rx.search(text) and label not in hits:
            hits.append(label)
    return hits


def is_clean(text: str) -> bool:
    """True si el texto NO contiene ningún término conductual prohibido."""
    return not find_blacklisted(text)


# ─────────────────────────────────────────────────────────────────────────────
# DETECTOR DE CASTELLANO (15-sep-2026)
#
# Hasta hoy esta lista negra solo perseguía JERGA CONDUCTUAL, y de castellano
# solo tres palabras — y las tres porque eran términos conductuales, no por
# estar en español. Resultado: "il proprietario riferisce che el perro se queda
# solo" pasaba el filtro entero sin que saltara nada.
#
# El motor razona por dentro en español/inglés y re-expresa en italiano. Cuando
# la re-expresión se queda corta, lo que llega al veterinario italiano es
# castellano. Esto lo detecta.
#
# CRITERIO: solo marcadores que NO PUEDEN ser italianos. Las dos lenguas se
# parecen demasiado como para permitirse un falso positivo: cada falso positivo
# obliga a regenerar un informe de 40.000 caracteres y cuesta dinero y minutos.
# Por eso no entran aquí ni "normale", ni "totale", ni "piano", ni "animale".
# ─────────────────────────────────────────────────────────────────────────────
_SPAGNOLO_PATTERNS: list[tuple[str, str]] = [
    # Signos y letras que el italiano no usa jamás
    (r"ñ", "ñ (letra española)"),
    (r"[¿¡]", "¿ o ¡ (signos españoles)"),
    # Sufijos: el italiano hace -zione / -tà, nunca -ción / -dad
    (r"\b\w{3,}ci[oó]n(?:es)?\b", "-ción (el italiano hace -zione)"),
    (r"\b\w{4,}dad(?:es)?\b", "-dad (el italiano hace -tà)"),
    # Artículos y pronombres que no existen en italiano
    (r"\blos\b", "los"),
    (r"\blas\b", "las"),
    # Conectores inequívocos
    (r"\bsin\s+embargo\b", "sin embargo"),
    (r"\badem[aá]s\b", "además"),
    (r"\btambi[eé]n\b", "también"),
    (r"\bporque\b", "porque (it: perché)"),
    (r"\bcuando\b", "cuando (it: quando)"),
    (r"\bsiempre\b", "siempre (it: sempre)"),
    (r"\bentonces\b", "entonces"),
    (r"\bdesde\b", "desde"),
    (r"\bhasta\b", "hasta"),
    (r"\bhacia\b", "hacia"),
    (r"\bmuy\b", "muy"),
    # Léxico del dominio: las palabras que más veces se cuelan
    (r"\bperr[oa]s?\b", "perro/perra"),
    (r"\bdue[nñ]os?\b", "dueño"),
    (r"\bpropietari[oa]s?\b", "propietario (it: proprietario)"),
    (r"\bconduct[ao]s?\b", "conducta"),
    (r"\bejercicios?\b", "ejercicio (it: esercizio)"),
    (r"\badiestramiento\b", "adiestramiento"),
    (r"\bse[nñ]ales?\b", "señal"),
]

_SPAGNOLO = [(re.compile(p, re.IGNORECASE), label) for p, label in _SPAGNOLO_PATTERNS]


def find_spanish(text: str) -> list[str]:
    """Devuelve las etiquetas de los marcadores de castellano hallados.

    Pensado para el bucle de reintentos de la pasada 2: si devuelve algo, el
    informe lleva español dentro y hay que regenerarlo.
    """
    if not text:
        return []
    hits: list[str] = []
    for rx, label in _SPAGNOLO:
        if rx.search(text) and label not in hits:
            hits.append(label)
    return hits


def find_blacklisted_con_equivalente(text: str):
    """Como find_blacklisted, pero devuelve (término, equivalente).

    Sirve para que el reintento no diga solo "quita esto", sino "usa esto otro".
    Esa era la mitad que faltaba de la regla del founder: vetar sin ofrecer
    alternativa es lo que empujaba al modelo a la vaguedad.
    """
    if not text:
        return []
    out = []
    vistos = set()
    for rx, label, eq in _COMPILED:
        if rx.search(text) and label not in vistos:
            vistos.add(label)
            out.append((label, eq))
    return out


# ─────────────────────────────────────────────────────────────────────────────
# LA SEGUNDA MITAD DE LA REGLA (founder, 11-sep-2026):
#   "todas las palabras cognitivistas de la RAG B están prohibidas en el
#    análisis ABA"
#
# Esta dirección NO EXISTÍA. La lista de arriba solo auditaba el lado
# cognitivista; el lado conductual no se miraba, y es el que más importa según
# la asimetría del 4-sep: que se cuele algo conductual en lo cognitivista es un
# resfriado; que se cuele vocabulario cognitivista en el análisis ABA —el
# producto principal, en tres idiomas— es el Ébola.
#
# CRITERIO, el mismo que con el castellano: solo lo INEQUÍVOCO. Un falso
# positivo aquí obliga a regenerar el análisis del producto principal, que es
# caro y lento. Por eso NO entran términos que la etología y la psicología
# comparada usan con normalidad y que aparecen legítimamente en un análisis
# conductual: `arousal`, `neotenia`, `motivazione sociale`, `motivazione
# predatoria` — comprobado que `arousal` sale en análisis ABA reales.
#
# Lo que sí entra es lo que solo se dice desde el marco cognitivo-zooantropológico,
# tomado del §3 de ITALIAN_COGNITIVE_MAPPING_DRAFT.md.
# ─────────────────────────────────────────────────────────────────────────────
_COGNITIVISTA_PATTERNS: list = [
    (r"\bzooantropolog\w*", "zooantropologia / zooantropologico"),
    (r"\bzoo-?antropolog\w*", "zoo-antropologico"),
    (r"\bcognitivo-?zooantropolog\w*", "cognitivo-zooantropologico"),
    (r"\bUmwelt\b", "Umwelt (von Uexküll)"),
    (r"\bmondo\s+percettivo\s+di\s+specie\b", "mondo percettivo di specie"),
    (r"\b(et-?)?epimeletic\w*", "comportamento epimeletico"),
    (r"\bpedomorfos\w*", "pedomorfosi"),
    (r"\bmotivazione\s+perlustrativ\w*", "motivazione perlustrativa"),
    (r"\bperlustrativ\w*", "perlustrativo"),
    (r"\breferenza\s+sociale\b", "referenza sociale"),
]

_COGNITIVISTA = [(re.compile(p, re.IGNORECASE), label)
                 for p, label in _COGNITIVISTA_PATTERNS]


def find_cognitive(text: str) -> list:
    """Términos cognitivistas hallados en un texto que NO debería llevarlos.

    Se usa sobre la salida de la vía CONDUCTUAL (los tres idiomas). Si devuelve
    algo, el corpus cognitivista se ha filtrado al lado que no toca.
    """
    if not text:
        return []
    hits = []
    for rx, label in _COGNITIVISTA:
        if rx.search(text) and label not in hits:
            hits.append(label)
    return hits


def aba_is_clean(text: str) -> bool:
    """True si el análisis conductual NO lleva vocabulario cognitivista."""
    return not find_cognitive(text)
