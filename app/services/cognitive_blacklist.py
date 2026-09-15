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

# Cada patrón es regex case-insensitive con límites de palabra.
_BLACKLIST_PATTERNS: list[tuple[str, str]] = [
    # Núcleo operante
    # "rinforzo" SI se puede usar (founder, 7-sep-2026). No es exclusiva del
    # marco conductual: en italiano corriente y en el cognitivismo se usa
    # igual. Estaba prohibida y sobrevivia a los tres intentos, obligando a
    # entregar el informe con un aviso de resto. Ya no se persigue.
    # (r"\brinforz\w*", "rinforzo/rinforzare"),
    (r"\bestinzion\w*", "estinzione"),
    (r"\bcondizionament\w*", "condizionamento (operante/classico)"),
    (r"\bcontingenz\w*", "contingenza"),
    (r"\boperant[ei]\b", "operante/operanti"),
    (r"\brispondent[ei]\b", "rispondente (condizionamento)"),
    # Estímulo discriminativo
    (r"\bstimolo\s+discriminant\w*", "stimolo discriminante"),
    (r"\bdiscriminativ\w*", "discriminativo"),
    (r"\bstimolo\s+delta\b", "stimolo delta"),
    # Marcas de escuela
    (r"\bABA\b", "ABA"),
    (r"\bABC\b", "ABC (analisi a tre termini)"),
    (r"\banalisi\s+funzional\w*", "analisi funzionale"),
    (r"\bcomportamentism\w*", "comportamentismo"),
    (r"\bcomportamentist\w*", "comportamentista"),
    (r"\bbehavior\s*analysis\b", "behavior analysis"),
    # Procedimientos operantes
    (r"\bDR[AIO]\b", "DRA/DRI/DRO"),
    (r"\bcontrollo\s+dello\s+stimolo\b", "controllo dello stimolo"),
    (r"\boperazione\s+(motivante|stabilente)\b", "operazione motivante"),
    (r"\bpunizione\s+(positiva|negativa)\b", "punizione positiva/negativa"),
    (r"\bmodellaggio\b", "modellaggio (shaping)"),
    (r"\bshaping\b", "shaping"),
    (r"\bconcatenamento\b", "concatenamento (chaining)"),
    (r"\bchaining\b", "chaining"),
    (r"\btoken\s+economy\b", "token economy"),
    # Fugas del castellano (el motor razona en es/en por dentro)
    (r"\brefuerzo\w*", "refuerzo (ES)"),
    (r"\bextinci[oó]n\b", "extinción (ES)"),
    (r"\best[ií]mulo\s+discriminativo\b", "estímulo discriminativo (ES)"),
]

_COMPILED = [(re.compile(p, re.IGNORECASE), label) for p, label in _BLACKLIST_PATTERNS]


def find_blacklisted(text: str) -> list[str]:
    """Devuelve las etiquetas de los términos prohibidos hallados (sin duplicar)."""
    if not text:
        return []
    hits: list[str] = []
    for rx, label in _COMPILED:
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
