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


# Cap output: 30 tasks × ~18 palabras × ~1.6 tok = 870 tok. 2200 deja margen
# generoso para inglés (más palabras por idea) y para que el modelo cierre el
# día 30 con punto final cómodo. Con 1500 anteriores el modelo se quedaba
# sin tokens en los días 26-30 (audit Teo 2026-05-09).
MAX_OUTPUT_TOKENS = 2200


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

    # Descartar la última task si está claramente truncada (sin puntuación de
    # cierre). Mejor 29 tasks limpias que 30 con la última cortada.
    if tasks and not tasks[-1].rstrip().endswith((".", "!", "?", "…", "»", '"', ":", ")")):
        tasks.pop()

    # Si faltan tasks, segunda llamada solo para las que falten (más caro
    # solo cuando el LLM se queda corto, sin propagar texto truncado).
    if len(tasks) < 30:
        try:
            missing_count = 30 - len(tasks)
            existing = "\n".join(f"{i+1}. {t}" for i, t in enumerate(tasks))
            patch_user_msg = (
                (f"Dog's name: {dog_name.strip()}\n\n"
                 f"You generated the following tasks already:\n\n{existing}\n\n"
                 f"Now produce ONLY tasks {len(tasks)+1} through 30, "
                 f"keeping the same numbered format ({len(tasks)+1}. ... {30}. ...). "
                 f"Same intervention plan applies (already in your system prompt context).\n\n"
                 f"Plan reminder:\n{intervention_plan_text.strip()[:1500]}")
                if lang_norm == "en"
                else
                (f"Nombre del perro: {dog_name.strip()}\n\n"
                 f"Ya has generado estas tareas:\n\n{existing}\n\n"
                 f"Ahora produce SOLO las tareas {len(tasks)+1} a la 30, "
                 f"manteniendo el formato numerado ({len(tasks)+1}. ... 30. ...). "
                 f"Aplica el mismo plan de intervención.\n\n"
                 f"Resumen del plan:\n{intervention_plan_text.strip()[:1500]}")
            )
            patch_resp = client.messages.create(
                model=settings.clinical_model,
                max_tokens=MAX_OUTPUT_TOKENS,
                system=system_prompt,
                messages=[{"role": "user", "content": patch_user_msg}],
            )
            patch_text = "".join(
                getattr(b, "text", "") for b in patch_resp.content
                if getattr(b, "type", None) == "text"
            )
            patch_tasks = _parse_numbered_tasks(patch_text)
            # Filter again truncadas
            if patch_tasks and not patch_tasks[-1].rstrip().endswith(
                (".", "!", "?", "…", "»", '"', ":", ")")
            ):
                patch_tasks.pop()
            # patch_tasks tiene índices 1-based correctos para los slots faltantes.
            # Tomar solo las que vienen con índice > len(tasks) actual.
            tasks_combined = list(tasks)
            for idx, t in enumerate(patch_tasks, start=1):
                target_idx = len(tasks) + idx
                if target_idx <= 30 and t and t not in tasks_combined:
                    tasks_combined.append(t)
            tasks = tasks_combined
        except Exception:
            # Si la segunda llamada también falla, completamos con un fallback
            # genérico clínicamente sano (no propagamos truncados).
            pass

    # Último fallback: si tras patch sigue habiendo huecos, rellenar con un
    # task genérico del plan (NO truncado, NO repetido del último).
    fallback = (
        "Practica el ejercicio principal del plan en un contexto distinto al de los días anteriores y anota cómo respondió tu perro."
        if lang_norm != "en"
        else "Practice the main exercise of the plan in a context different from previous days and note how your dog responded."
    )
    while len(tasks) < 30:
        tasks.append(fallback)

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
