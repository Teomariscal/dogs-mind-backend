"""
Plan Sencillo / Pet Owners — Haiku 4.5.

Toma un plan de intervención técnico ya generado y lo reformula como guía
paso-a-paso accesible para el dueño común. Sin RAG, sin prompt cache (system
prompt < 2k tokens). One-shot, output corto formato receta.

Pricing congelado: 0,1 tokens/llamada (margen 96 % alineado con mensaje Aigent).
Validado por CFO 2026-05-04 (ver dogs-mind-state.md, invariantes 4 y 5).
"""

from __future__ import annotations
from dataclasses import dataclass

from app.config import get_settings
from app.core.anthropic_client import get_anthropic_client
from app.core.prompts.plan_simple import (
    PLAN_SIMPLE_SYSTEM_PROMPT_ES,
    PLAN_SIMPLE_SYSTEM_PROMPT_EN,
)


# Output cap duro (regla CFO): 800 tokens es suficiente para 5-15 pasos cortos.
MAX_OUTPUT_TOKENS = 800


@dataclass
class PlanSimpleResult:
    text: str
    input_tokens: int
    output_tokens: int


def run_plan_simple(*, original_plan_text: str, lang: str = "es") -> PlanSimpleResult:
    """
    Reformula un plan de intervención técnico en formato receta accesible.

    Args:
        original_plan_text: texto markdown del plan de intervención generado
                            previamente por Sonnet (CaseEntry.type='intervention').
        lang: 'es' (default) o 'en'.
    """
    if not original_plan_text or not original_plan_text.strip():
        raise ValueError("original_plan_text vacío — no se puede generar Plan Sencillo.")

    settings = get_settings()
    client = get_anthropic_client()

    lang_norm = (lang or "es").lower()
    system_prompt = (
        PLAN_SIMPLE_SYSTEM_PROMPT_EN if lang_norm == "en" else PLAN_SIMPLE_SYSTEM_PROMPT_ES
    )

    user_message = (
        ("Here is the technical intervention plan to reformulate as a step-by-step recipe "
         "for the dog's owner. Apply your strict rules:\n\n"
         if lang_norm == "en"
         else "Aquí tienes el plan de intervención técnico que debes reformular como guía paso-a-paso para el dueño del perro. Aplica tus reglas duras:\n\n"
        )
        + original_plan_text.strip()
    )

    response = client.messages.create(
        model=settings.avatar_model,  # Haiku 4.5 — mismo que avatares
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
    # cierre limpio (., !, ?, …) preservando los pasos previos. Mismo
    # patrón que abc_explained_ai (audit Teo 2026-05-09).
    text = _trim_to_clean_close(text.strip())

    return PlanSimpleResult(
        text=text,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )


def _trim_to_clean_close(text: str) -> str:
    """Si el texto termina sin signo de cierre, recortar a la última frase
    completa. Preserva todos los párrafos que estaban bien cerrados."""
    if not text:
        return text
    if text.rstrip().endswith((".", "!", "?", "…", "»", '"', ":", ")")):
        return text
    closers = (".", "!", "?", "…")
    cut = max(text.rfind(c) for c in closers)
    if cut <= 0:
        return text
    return text[: cut + 1].rstrip()
