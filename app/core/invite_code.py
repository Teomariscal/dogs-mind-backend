"""Normalizacion de los codigos de invitacion.

24-sep-2026. El founder tecleo `PROINV-A04748.` —con el punto final que pone
cualquiera al terminar una frase— y la app le contesto "Codigo no reconocido".
El codigo era correcto. Lo mismo pasa al copiar y pegar desde WhatsApp o desde
un correo, que arrastra espacios, comillas tipograficas o un punto de cierre.

Cada uno de esos caracteres invisibles es un usuario que se queda fuera
creyendo que su codigo no vale, y de los 19 profesionales del grupo ya sabemos
lo que cuesta cada alta.

Lo que NO se toca: las mayusculas y minusculas. Los codigos de delegacion se
comparan tal cual a proposito, para que no colisionen entre si.
"""

import re

# Basura que la gente arrastra al pegar: espacios de todo tipo (incluido el
# no-separable que mete WhatsApp), comillas rectas y tipograficas, y los signos
# de puntuacion con los que se cierra una frase.
_BASURA = " \t\r\n ​.,;:!?\"'«»“”‘’()[]<>"


def normalizar(codigo):
    """Deja el codigo como el usuario queria escribirlo, sin tocar su caja."""
    if not codigo:
        return ""
    limpio = str(codigo).strip(_BASURA)
    # Un espacio en medio ("PROINV - A04748") tampoco puede invalidarlo.
    limpio = re.sub(r"\s+", "", limpio)
    return limpio
