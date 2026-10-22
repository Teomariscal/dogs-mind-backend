"""
TERMINOLOGIA CONDUCTUAL EN ITALIANO — un solo sitio.

Founder, 22-oct-2026, visto en la app: *"error en italiano, en italiano castigo
es punizione"*. El analisis ABC de Mio salia en italiano correcto salvo una
palabra: *"Il castigo usato finora non ha cambiato questa logica"*. "Castigo"
es castellano; en italiano es **punizione**.

POR QUE PASA. Los prompts estan escritos en castellano, con la terminologia
tecnica en castellano. Cuando se le pide al modelo que responda en italiano,
traduce la prosa pero arrastra los terminos tecnicos tal cual, porque los ha
leido como nombres propios de un procedimiento. Es la misma raiz del fallo de
`modellamento` / `modellaggio` de septiembre.

POR QUE EN UN SOLO FICHERO. Hasta hoy cada prompt llevaba su terminologia
italiana suelta: `training_consult.py` la tenia completa, y los demas no tenian
nada. Asi es imposible que no se escape una. Aqui esta la lista, y cualquier
prompt que escriba en italiano la pega al final con `bloque()`.

En Italia esto no es cosmetico: la via conductual italiana la leen veterinarios,
y un termino en castellano dentro de un informe tecnico lo descalifica entero.
"""

# Castellano -> italiano. La izquierda es lo que el modelo tiende a colar.
EQUIVALENCIAS: dict[str, str] = {
    "castigo":                    "punizione",
    "castigo positivo":           "punizione positiva",
    "castigo negativo":           "punizione negativa",
    "refuerzo":                   "rinforzo",
    "reforzador":                 "rinforzatore",
    "refuerzo diferencial":       "rinforzo differenziale",
    "estimulo discriminativo":    "stimolo discriminativo",
    "contingencia":               "contingenza",
    "extincion":                  "estinzione",
    "desensibilizacion":          "desensibilizzazione",
    "contracondicionamiento":     "controcondizionamento",
    "moldeado":                   "modellamento",
    "moldeamiento":               "modellamento",
    "modelado":                   "modellaggio",
    "encadenamiento":             "concatenamento",
    "conducta":                   "comportamento",
    "umbral":                     "soglia",
    "manejo":                     "gestione",
    "destete":                    "svezzamento",
    "adiestramiento":             "addestramento",
    "guia":                       "conduttore",
    "correa":                     "guinzaglio",
    "premio":                     "rinforzo",
    "linea base":                 "linea di base",
    "ensayo":                     "prova",
    "tasa de respuesta":          "tasso di risposta",
    "saciedad":                   "sazieta",
    "privacion":                  "deprivazione",
    "generalizacion":             "generalizzazione",
}

# Dos que se confunden entre si, y la confusion cambia el procedimiento.
# Ya costo un fallo en septiembre.
AVISOS = (
    "- `modellamento` es MOLDEADO (reforzar aproximaciones sucesivas).\n"
    "  `modellaggio` es MODELADO (aprender por observacion de un modelo).\n"
    "  No son sinonimos y confundirlos cambia el ejercicio que hace el dueño.\n"
    "- `punizione` NUNCA se recomienda: aparece solo para explicar por que lo\n"
    "  que ya se intento no funciono. LIMA sigue siendo innegociable."
)


def bloque() -> str:
    """El bloque que se pega al prompt cuando la salida va en italiano."""
    pares = "\n".join(f"  {es}  ->  {it}" for es, it in EQUIVALENCIAS.items())
    return (
        "\n\nTERMINOLOGIA ITALIANA (OBBLIGATORIA, PRIORITARIA SU TUTTO IL RESTO)\n"
        "\nQuesto prompt e scritto in spagnolo. La prosa la traduci, ma i TERMINI\n"
        "TECNICI non si traducono da soli: tendi a lasciarli in spagnolo perche\n"
        "li leggi come nomi propri di una procedura. Non farlo. Un solo termine\n"
        "spagnolo dentro un testo italiano squalifica l'intero documento davanti\n"
        "a un veterinario italiano.\n"
        "\nUsa SEMPRE la forma di destra, MAI quella di sinistra:\n\n"
        f"{pares}\n\n"
        "ATTENZIONE:\n"
        f"{AVISOS}\n"
        "\nPrima di consegnare, rileggi il testo e cerca parole spagnole. Se ne\n"
        "trovi una, sostituiscila. Questo vale anche dentro le parentesi e nei\n"
        "titoli delle sezioni.\n"
    )


def colados(texto: str) -> list[str]:
    """Que terminos castellanos se han colado en un texto italiano.

    Para comprobar la salida de verdad, no para confiar en que el prompt
    bastara. Devuelve la lista de terminos encontrados.
    """
    import re
    if not texto:
        return []
    bajo = texto.lower()
    # Se quitan los acentos para que "estimulo" case con "estímulo".
    tabla = str.maketrans("áéíóúüñ", "aeiouun")
    bajo = bajo.translate(tabla)
    fuera = []
    for es in EQUIVALENCIAS:
        # Palabra entera: "conducta" no debe casar dentro de "conductas" ...
        # si debe: por eso \b al principio y sufijo opcional al final.
        if re.search(r"\b" + re.escape(es) + r"(s|es)?\b", bajo):
            fuera.append(es)
    return fuera
