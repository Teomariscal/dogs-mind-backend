"""
ABC Explained / Cecilia te explica — Haiku 4.5.

Toma un análisis funcional ABC técnico ya generado y lo traduce a un texto
de 4 párrafos en lenguaje cotidiano para el dueño común.

Pricing: 0,1 tokens/llamada, margen 96% (CFO 2026-05-04, mismo patrón Plan
Sencillo). Persistencia obligatoria como CaseEntry.type='abc_explained'.
"""

from __future__ import annotations
from dataclasses import dataclass

from app.config import get_settings
from app.core.anthropic_client import get_anthropic_client
from app.core.prompts.abc_explained import (
    ABC_EXPLAINED_SYSTEM_PROMPT_ES,
    ABC_EXPLAINED_SYSTEM_PROMPT_EN,
)


# Output cap: 4 párrafos × ~90 palabras × ~1.6 tokens/palabra ≈ 580 tokens.
# Subido a 850 tras detectar que con 600 el modelo a veces se cortaba a
# media frase (Teo audit 2026-05-09). Margen para inglés y para que el
# modelo cierre con punto final cómodo, sin permitir desbordes.
MAX_OUTPUT_TOKENS = 850


@dataclass
class AbcExplainedResult:
    text: str
    input_tokens: int
    output_tokens: int


def run_abc_explained(*, original_abc_text: str, lang: str = "es") -> AbcExplainedResult:
    """
    Traduce un análisis ABC técnico a 4 párrafos accesibles para el dueño.

    Args:
        original_abc_text: texto markdown del análisis ABC ya generado por
                           Sonnet (CaseEntry.type='abc' del caso).
        lang: 'es' (default) o 'en'. El idioma del output.
    """
    if not original_abc_text or not original_abc_text.strip():
        raise ValueError("original_abc_text vacío — no se puede explicar.")

    settings = get_settings()
    client = get_anthropic_client()

    lang_norm = (lang or "es").lower()
    system_prompt = (
        ABC_EXPLAINED_SYSTEM_PROMPT_EN if lang_norm == "en" else ABC_EXPLAINED_SYSTEM_PROMPT_ES
    )

    user_message = (
        ("Here is the technical ABC analysis to translate to plain language for the dog's owner. "
         "Apply your strict rules and the 4-paragraph structure:\n\n"
         if lang_norm == "en"
         else "Aquí tienes el análisis ABC técnico que debes traducir a lenguaje sencillo para el dueño del perro. "
              "Aplica tus reglas duras y la estructura de 4 párrafos:\n\n"
        )
        + original_abc_text.strip()
    )

    response = client.messages.create(
        model=settings.avatar_model,  # Haiku 4.5 (mismo modelo que Plan Sencillo y Aigents)
        max_tokens=MAX_OUTPUT_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    text = ""
    for block in response.content:
        if getattr(block, "type", None) == "text":
            text += block.text

    # Defensa contra cortes a media frase: si el modelo se aproximó al
    # max_tokens y dejó la última frase incompleta, recortamos al último
    # cierre limpio (., !, ?, …) preservando los párrafos previos.
    text = _trim_to_clean_close(text.strip())

    return AbcExplainedResult(
        text=text,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )


def _trim_to_clean_close(text: str) -> str:
    """Si el texto termina sin signo de cierre, recortar a la última frase
    completa. Preserva todos los párrafos que estaban bien cerrados."""
    if not text:
        return text
    # ya termina bien
    if text.rstrip().endswith((".", "!", "?", "…", "»", '"', ":", ")")):
        return text
    # buscar el último signo de cierre fuerte
    closers = (".", "!", "?", "…")
    cut = max(text.rfind(c) for c in closers)
    if cut <= 0:
        return text  # no hay un buen sitio para cortar; devolver tal cual
    return text[: cut + 1].rstrip()
