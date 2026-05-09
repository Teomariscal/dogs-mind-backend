"""
Generación de las 30 micro-tareas diarias del seguimiento — Sonnet 4.6.

Llamada única por caso al aceptar el plan de intervención.
Coste estimado: ~$0.003 (200-300 input + 800-1000 output con cache hit).

Devuelve una lista ordenada de 30 strings (índice 0 = day_index 1).
Si el modelo devuelve menos de 30, rellena con re-prompt o trunca defensivamente.
"""

from __future__ import annotations
import re
from typing import List
from dataclasses import dataclass

from app.config import get_settings
from app.core.anthropic_client import get_anthropic_client
from app.core.prompts.daily_tasks import (
    DAILY_TASKS_SYSTEM_PROMPT_ES,
    DAILY_TASKS_SYSTEM_PROMPT_EN,
)


# Cap output: 30 tasks × ~25 palabras × ~1.6 tok = 1200 tok. 1500 deja margen.
MAX_OUTPUT_TOKENS = 1500


@dataclass
class DailyTasksResult:
    tasks: List[str]  # exactamente 30 strings
    input_tokens: int
    output_tokens: int


def generate_daily_tasks(
    *,
    intervention_plan_text: str,
    dog_name: str,
    lang: str = "es",
) -> DailyTasksResult:
    """Genera 30 micro-tareas a partir del plan de intervención y el nombre del perro."""
    if not intervention_plan_text or not intervention_plan_text.strip():
        raise ValueError("intervention_plan_text vacío.")
    if not dog_name or not dog_name.strip():
        dog_name = "tu perro" if lang == "es" else "your dog"

    settings = get_settings()
    client = get_anthropic_client()

    lang_norm = (lang or "es").lower()
    system_prompt = (
        DAILY_TASKS_SYSTEM_PROMPT_EN if lang_norm == "en"
        else DAILY_TASKS_SYSTEM_PROMPT_ES
    )

    if lang_norm == "en":
        user_msg = (
            f"Dog's name: {dog_name.strip()}\n\n"
            f"Intervention plan to convert into 30 daily micro-tasks:\n\n"
            f"{intervention_plan_text.strip()}"
        )
    else:
        user_msg = (
            f"Nombre del perro: {dog_name.strip()}\n\n"
            f"Plan de intervención a convertir en 30 micro-tareas diarias:\n\n"
            f"{intervention_plan_text.strip()}"
        )

    response = client.messages.create(
        model=settings.clinical_model,  # Sonnet 4.6
        max_tokens=MAX_OUTPUT_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_msg}],
    )

    text = ""
    for block in response.content:
        if getattr(block, "type", None) == "text":
            text += block.text

    tasks = _parse_numbered_tasks(text)

    # Defensa: si el modelo devuelve menos de 30, completar con genéricos
    # del último contexto (no abortar — el usuario no debe ver una pantalla
    # de error por una variación del LLM).
    while len(tasks) < 30:
        last = tasks[-1] if tasks else (
            "Pasea con tu perro durante 10 minutos en una zona tranquila y observa cómo reacciona."
            if lang_norm != "en"
            else "Walk your dog for 10 minutes in a quiet area and observe how it reacts."
        )
        tasks.append(last)

    # Truncar si llegan más de 30
    tasks = tasks[:30]

    return DailyTasksResult(
        tasks=tasks,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )


def _parse_numbered_tasks(text: str) -> List[str]:
    """Parsea output del LLM en formato '1. ... \\n 2. ... \\n ... \\n 30. ...'."""
    if not text:
        return []
    out: List[str] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        # Match "12. content" o "12) content"
        m = re.match(r"^(\d{1,2})[\.\)]\s+(.+)$", line)
        if m:
            idx = int(m.group(1))
            content = m.group(2).strip()
            if 1 <= idx <= 30 and content:
                # Asegurar slot correcto (alguna línea puede llegar fuera de orden)
                while len(out) < idx - 1:
                    out.append("")  # placeholder, se sobrescribe si llega
                if len(out) >= idx:
                    out[idx - 1] = content
                else:
                    out.append(content)
    # Quitar placeholders vacíos finales
    while out and not out[-1]:
        out.pop()
    return out
