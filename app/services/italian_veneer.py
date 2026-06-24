"""
Two-pass: segunda pasada que añade el guiño zooantropológico a la versión ITALIANA.

Diseño (consejo 2026-06-24): el motor (pasada 1) genera el ABA puro en un entorno
SIN zooantropología y lo congela; esta función toma ese texto inmutable y SOLO puede
AÑADIR incisos atribuidos en la capa disposicional. Nunca toca ED/función/plan.

ADITIVO Y REVERSIBLE: si flag apagado, idioma != it o cuenta != professional,
devuelve el texto tal cual (cero cambio de comportamiento).
"""

from typing import Optional

from app.config import get_settings
from app.core.anthropic_client import create_message_resilient
from app.core.prompts.italian_zoo_veneer import ITALIAN_ZOO_VENEER_SYSTEM_PROMPT


def maybe_apply_italian_veneer(
    text: str,
    *,
    lang: Optional[str],
    account_type: Optional[str],
    kind: str = "analysis",
) -> str:
    """Aplica el guiño zooantropológico (segunda pasada) SOLO si se cumplen las
    tres puertas: flag IT_ZOO_VENEER on · lang=='it' · cuenta professional.
    En cualquier otro caso devuelve `text` sin tocar."""
    settings = get_settings()

    # ── Puertas (cualquiera que falle → texto idéntico) ─────────────────────
    if not getattr(settings, "it_zoo_veneer_enabled", False):
        return text
    if (lang or "").strip().lower() != "it":
        return text
    if (account_type or "").strip().lower() != "professional":
        return text
    if not text or not text.strip():
        return text

    user_message = (
        "TESTO CLINICO DA RIESPRIMERE (immutabile nel contenuto: ogni affermazione "
        "funzionale — stimolo discriminante, funzione, contingenza, fasi e passi del "
        "piano, criteri numerici — deve restare identica parola per parola):\n"
        '"""\n'
        f"{text}\n"
        '"""\n\n'
        "Restituisci lo STESSO testo aggiungendo SOLO, dove esiste un parallelismo ABA "
        "giustificabile e nel solo strato disposizionale/etologico, qualche breve inciso "
        'attribuito nella forma "...: ciò che in zooantropologia si chiama X". Rispetta la '
        "dose sottile (max 2-3 incisi, max 1 citazione facoltativa). Se non c'è parallelismo, "
        "restituisci il testo identico."
    )

    # El motor permite hasta 6000 (análisis) / 8000 (plan); la reexpresión re-emite
    # todo el texto, así que damos el mismo margen para que no se corte.
    max_tokens = 8000 if kind == "intervention" else 6000

    try:
        response = create_message_resilient(
            model=settings.clinical_model,
            fallback_model=settings.clinical_fallback_model,
            max_tokens=max_tokens,
            system=[
                {
                    "type": "text",
                    "text": ITALIAN_ZOO_VENEER_SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_message}],
        )
    except Exception:
        # Defensa en profundidad: si la segunda pasada falla por lo que sea, NUNCA
        # romper la respuesta clínica — devolvemos el ABA puro (pasada 1) intacto.
        return text

    veneered = ""
    for block in response.content:
        if block.type == "text":
            veneered += block.text

    # Salvaguarda anti-truncado: si la reexpresión tocó el tope, descartamos y
    # devolvemos el ABA puro (mejor el motor entero que un texto cortado).
    if getattr(response, "stop_reason", None) == "max_tokens":
        return text

    return veneered.strip() or text
