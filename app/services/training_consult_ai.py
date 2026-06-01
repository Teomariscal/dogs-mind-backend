"""
Servicio del flujo "Entrenamiento específico" — análisis + plan operante por
fases para UNA habilidad concreta. Modelo: Sonnet 4.6 (clinical_model).

Llama al system prompt validado de app/core/prompts/training_consult.py y
construye el user prompt a partir de los 9 campos de la plantilla:
  1. Nombre del perro
  2. Tipología racial
  3. Edad
  4. Nivel de entrenamiento del perro (Básico / Medio / Avanzado)
  5. Nivel del guía (Básico / Medio / Avanzado)
  6. Reforzadores preferidos (lista)
  7. Habilidad o ejercicio (texto libre)
  8. Contexto (Pista / Interior / Calle)
  9. ¿Usa clicker habitualmente? (Sí / No)

Devuelve un objeto ligero con el markdown del análisis + plan + métricas de
tokens (para usage_log y refund_token si falla).

Validación previa al servicio (2026-05-29): 8 tests cruzados sobre Sonnet 4.6
con T=0.4, max_tokens=2200 sacaron media 9.75/10 (autores reales citados:
McDevitt LAT, Herrnstein matching law, Kamin overshadowing, Premack). 100% LIMA.
"""

from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import Optional

from app.config import get_settings
from app.core.anthropic_client import get_anthropic_client
from app.core.prompts.training_consult import (
    TRAINING_CONSULT_PROMPT_ES,
    TRAINING_CONSULT_PROMPT_EN,
)


logger = logging.getLogger(__name__)

MAX_OUTPUT_TOKENS = 2200
TEMPERATURE = 0.4  # precisión técnica > creatividad inventada


# Etiquetas de nivel localizadas (mismo enfoque que training_ai.py).
_LEVEL_LABELS = {
    "es": {"basico": "Básico", "medio": "Medio", "avanzado": "Avanzado"},
    "en": {"basico": "Basic", "medio": "Intermediate", "avanzado": "Advanced"},
}

# Etiquetas de contexto localizadas.
_CONTEXT_LABELS = {
    "es": {"pista": "Pista", "interior": "Interior", "calle": "Calle"},
    "en": {"pista": "Training field", "interior": "Indoor", "calle": "Street"},
}


@dataclass
class TrainingConsultResult:
    """Resultado ligero del servicio (no es modelo de respuesta de API)."""
    analysis_markdown: str
    input_tokens: int
    output_tokens: int


def _build_user_prompt(
    *,
    dog_name: str,
    breed: str,
    age: str,
    dog_level: str,
    handler_level: str,
    reinforcers: list[str],
    goal: str,
    context: str,
    uses_clicker: bool,
    lang: str,
) -> str:
    """Construye el user prompt con los 9 campos de la plantilla."""
    lvl = _LEVEL_LABELS.get(lang, _LEVEL_LABELS["es"])
    ctx_map = _CONTEXT_LABELS.get(lang, _CONTEXT_LABELS["es"])

    dlvl = lvl.get(dog_level.lower(), dog_level)
    hlvl = lvl.get(handler_level.lower(), handler_level)
    ctx = ctx_map.get(context.lower(), context)

    reinforcers_clean = [r for r in (reinforcers or []) if r and str(r).strip()]
    reinforcers_str = ", ".join(reinforcers_clean) if reinforcers_clean else (
        "no especificado" if lang == "es" else "not specified"
    )

    clicker_str = ("Sí" if uses_clicker else "No") if lang == "es" else ("Yes" if uses_clicker else "No")

    if lang == "en":
        lines = [
            "NEW CONSULTATION - SPECIFIC TRAINING",
            "",
            "DOG DATA:",
            f"- Name: {dog_name}",
            f"- Breed type: {breed}",
            f"- Age: {age}",
            "",
            "PROFILE:",
            f"- Dog training level: {dlvl}",
            f"- Handler level: {hlvl}",
            f"- Preferred reinforcers: {reinforcers_str}",
            f"- Uses clicker regularly?: {clicker_str}",
            "",
            "EXERCISE:",
            f"- Skill or exercise to improve: {goal}",
            f"- Main context: {ctx}",
            "",
            "Now generate the analysis and operant plan by phases for THIS specific exercise.",
        ]
    else:
        lines = [
            "NUEVA CONSULTA - ENTRENAMIENTO ESPECÍFICO",
            "",
            "DATOS DEL PERRO:",
            f"- Nombre: {dog_name}",
            f"- Tipología racial: {breed}",
            f"- Edad: {age}",
            "",
            "PERFIL:",
            f"- Nivel de entrenamiento del perro: {dlvl}",
            f"- Nivel del guía: {hlvl}",
            f"- Reforzadores preferidos: {reinforcers_str}",
            f"- ¿Usa clicker habitualmente?: {clicker_str}",
            "",
            "EJERCICIO:",
            f"- Habilidad o ejercicio a mejorar: {goal}",
            f"- Contexto principal: {ctx}",
            "",
            "Genera ahora el análisis y plan operante por fases para ESTE ejercicio específico.",
        ]

    return "\n".join(lines)


def generate_training_consult(
    *,
    dog_name: str,
    breed: str,
    age: str,
    dog_level: str,
    handler_level: str,
    reinforcers: list[str],
    goal: str,
    context: str,
    uses_clicker: bool,
    lang: str = "es",
) -> TrainingConsultResult:
    """
    Genera el análisis técnico + plan operante por fases para una habilidad
    específica que el guía quiere enseñar a su perro.

    Args:
      dog_name, breed, age: identidad del perro (texto libre).
      dog_level: "basico" | "medio" | "avanzado".
      handler_level: "basico" | "medio" | "avanzado".
      reinforcers: lista de reforzadores marcados (ej: ["comida", "pelota"]).
      goal: habilidad o ejercicio (texto libre del usuario).
      context: "pista" | "interior" | "calle".
      uses_clicker: bool.
      lang: "es" | "en".

    Returns:
      TrainingConsultResult con markdown del análisis + métricas tokens.

    Lanza Exception si Anthropic falla. El caller (router) debe hacer
    refund_token + log de error.
    """
    lang_norm = (lang or "es").lower()
    if lang_norm not in ("es", "en"):
        lang_norm = "es"

    system_prompt = (
        TRAINING_CONSULT_PROMPT_EN if lang_norm == "en"
        else TRAINING_CONSULT_PROMPT_ES
    )

    user_prompt = _build_user_prompt(
        dog_name=dog_name,
        breed=breed,
        age=age,
        dog_level=dog_level,
        handler_level=handler_level,
        reinforcers=reinforcers,
        goal=goal,
        context=context,
        uses_clicker=uses_clicker,
        lang=lang_norm,
    )

    settings = get_settings()
    client = get_anthropic_client()

    response = client.messages.create(
        model=settings.clinical_model,  # Sonnet 4.6
        max_tokens=MAX_OUTPUT_TOKENS,
        temperature=TEMPERATURE,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = ""
    for block in response.content:
        if getattr(block, "type", None) == "text":
            raw += block.text

    analysis = raw.strip()

    return TrainingConsultResult(
        analysis_markdown=analysis,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )
