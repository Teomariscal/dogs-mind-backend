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
    (r"\brinforz\w*", "rinforzo/rinforzare (positivo, negativo, differenziale)"),
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
