"""
Motor IA del módulo "Inspiración Profesional" / Adiestramiento Avanzado.

Genera EXACTAMENTE 5 ejercicios de ADIESTRAMIENTO (enseñar habilidades)
a partir de un objetivo del día y ajustes opcionales (nivel del perro,
nivel de los guías, tiempo, dónde, recursos, reforzadores).

Llama a Claude Haiku 4.5 (settings.avatar_model) y devuelve una lista de
objetos {instruccion, explicacion}:
  - instruccion: el ejercicio concreto a hacer hoy.
  - explicacion: BREVE (1 frase) — el porqué/para qué.

Reglas de dominio (importantes, vienen de la spec de Teo):
  - MARCADOR POR DEFECTO = CLICKER. La IA NO debe usar "bien" ni "sí"
    como marcador por defecto; usa clicker (salvo que el guía indique que
    no dispone de clicker, en cuyo caso adapta el marcador).
  - Vocabulario de ADIESTRAMIENTO: criterio, aproximación, shaping,
    generalización, proofing, tasa de éxito, etc.
  - NADA de léxico clínico: NO ABC, NO LIMA, NO ED/EC, NO "conducta problema".
  - Respeta recursos/reforzadores marcados.

Salida JSON estricta de Haiku, parseada de forma robusta.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from app.config import get_settings
from app.core.anthropic_client import get_anthropic_client

logger = logging.getLogger(__name__)


# ── System prompts ────────────────────────────────────────────────────────────
_SYSTEM_ES = """Eres un adiestrador canino profesional experto en enseñanza de habilidades \
mediante adiestramiento moderno basado en refuerzo positivo.

Tu tarea: diseñar EXACTAMENTE 5 ejercicios de ADIESTRAMIENTO (enseñar habilidades) para la \
sesión de hoy, adaptados al OBJETIVO indicado y a los ajustes opcionales del guía.

REGLAS DURAS:
- MARCADOR POR DEFECTO = CLICKER. Usa el clicker como marcador en los ejercicios. NUNCA uses \
"bien" ni "sí" como marcador por defecto. Solo si el guía indica explícitamente que NO dispone \
de clicker, adapta el marcador (p. ej. marcador verbal corto o lengua).
- Usa vocabulario propio de adiestramiento: criterio, aproximación, shaping/moldeado, \
generalización, proofing, tasa de éxito, capturar, luring, manejo del entorno, etc.
- Progresión lógica entre los 5 ejercicios: del más sencillo al más exigente, subiendo criterio \
de forma gradual (distancia, distracción, duración, velocidad…).
- Respeta los recursos y reforzadores marcados por el guía. Si hay comida, úsala; si hay pelota \
o juguete, intégralos como reforzador cuando aporte; si NO hay clicker disponible, adáptate.
- NUNCA uses léxico clínico ni de modificación de conducta: NADA de ABC, LIMA, ED/EC, \
contracondicionamiento, "conducta problema", "estímulo discriminativo". Esto es ADIESTRAMIENTO, \
no terapia conductual.
- Cada ejercicio: una instrucción concreta y accionable HOY (qué hacer, repeticiones o criterio \
de éxito cuando proceda) y una explicación BREVE de 1 frase (el porqué/para qué).
- No uses emojis. No uses markdown.

FORMATO DE SALIDA — OBLIGATORIO:
Devuelve SOLO un array JSON válido con EXACTAMENTE 5 objetos, sin texto antes ni después:
[
  {"instruccion": "...", "explicacion": "..."},
  ... (5 en total)
]"""

_SYSTEM_EN = """You are a professional dog trainer, expert in teaching skills through modern \
reinforcement-based training.

Your task: design EXACTLY 5 TRAINING exercises (teaching skills) for today's session, adapted \
to the given GOAL and the handler's optional settings.

HARD RULES:
- DEFAULT MARKER = CLICKER. Use the clicker as the marker in the exercises. NEVER use "good" or \
"yes" as the default marker. Only if the handler explicitly states there is NO clicker available, \
adapt the marker (e.g. a short verbal marker or tongue click).
- Use training vocabulary: criterion, approximation, shaping, generalization, proofing, success \
rate, capturing, luring, environment management, etc.
- Logical progression across the 5 exercises: from easiest to most demanding, raising criterion \
gradually (distance, distraction, duration, speed…).
- Respect the resources and reinforcers the handler marked. If there is food, use it; if there is \
a ball or toy, integrate them as reinforcers when useful; if there is NO clicker available, adapt.
- NEVER use clinical or behavior-modification jargon: NO ABC, LIMA, antecedent/consequence, \
counterconditioning, "problem behavior", "discriminative stimulus". This is TRAINING, not \
behavioral therapy.
- Each exercise: one concrete, actionable instruction for TODAY (what to do, reps or success \
criterion where relevant) and a SHORT one-sentence explanation (the why/what for).
- No emojis. No markdown.

OUTPUT FORMAT — MANDATORY:
Return ONLY a valid JSON array with EXACTLY 5 objects, no text before or after:
[
  {"instruccion": "...", "explicacion": "..."},
  ... (5 total)
]"""


_LEVEL_LABELS = {
    "es": {"basico": "básico", "medio": "medio", "avanzado": "avanzado"},
    "en": {"basico": "basic", "medio": "intermediate", "avanzado": "advanced"},
}


def _build_user_prompt(
    objetivo: str,
    nivel_perro: str,
    nivel_guias: str,
    tiempo: Optional[int],
    donde: Optional[str],
    recursos: Optional[list[str]],
    reforzadores: Optional[list[str]],
    lang: str,
) -> str:
    """Construye el mensaje de usuario con objetivo + ajustes."""
    lvl = _LEVEL_LABELS.get(lang, _LEVEL_LABELS["es"])
    np_ = lvl.get(nivel_perro, nivel_perro)
    ng_ = lvl.get(nivel_guias, nivel_guias)

    recursos = [r for r in (recursos or []) if r and str(r).strip()]
    reforzadores = [r for r in (reforzadores or []) if r and str(r).strip()]
    clicker_disponible = any("clicker" in str(r).lower() for r in recursos)

    if lang == "en":
        lines = [
            f"GOAL FOR TODAY: {objetivo}",
            "",
            "SETTINGS:",
            f"- Dog level: {np_}",
            f"- Handlers level: {ng_}",
        ]
        if tiempo:
            lines.append(f"- Available time: {tiempo} min")
        if donde:
            lines.append(f"- Location: {donde}")
        lines.append(
            f"- Available resources: {', '.join(recursos) if recursos else 'not specified'}"
        )
        lines.append(
            f"- Most valuable reinforcers for the dog: "
            f"{', '.join(reforzadores) if reforzadores else 'not specified'}"
        )
        if recursos:
            if clicker_disponible:
                lines.append("- Clicker IS available: use it as the default marker.")
            else:
                lines.append(
                    "- Clicker is NOT in the resource list: adapt the marker "
                    "(short verbal marker), do not assume a clicker."
                )
        lines.append("")
        lines.append("Generate the 5 training exercises now as a strict JSON array.")
    else:
        lines = [
            f"OBJETIVO DE HOY: {objetivo}",
            "",
            "AJUSTES:",
            f"- Nivel del perro: {np_}",
            f"- Nivel de los guías: {ng_}",
        ]
        if tiempo:
            lines.append(f"- Tiempo disponible: {tiempo} min")
        if donde:
            lines.append(f"- Dónde: {donde}")
        lines.append(
            f"- Recursos disponibles: {', '.join(recursos) if recursos else 'no especificado'}"
        )
        lines.append(
            f"- Reforzadores más válidos para el perro: "
            f"{', '.join(reforzadores) if reforzadores else 'no especificado'}"
        )
        if recursos:
            if clicker_disponible:
                lines.append("- SÍ hay clicker disponible: úsalo como marcador por defecto.")
            else:
                lines.append(
                    "- El clicker NO está en la lista de recursos: adapta el marcador "
                    "(marcador verbal corto), no des por hecho que hay clicker."
                )
        lines.append("")
        lines.append("Genera ahora los 5 ejercicios de adiestramiento como array JSON estricto.")

    return "\n".join(lines)


def _parse_exercises(raw: str) -> list[dict]:
    """
    Parsea de forma robusta la respuesta de Haiku a una lista de exactamente
    5 dicts {instruccion, explicacion}. Lanza ValueError si no se puede.
    """
    text = (raw or "").strip()

    # 1) Quitar fences markdown si Haiku los añade pese al prompt.
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()

    # 2) Intentar parse directo; si falla, extraer el primer array [...] del texto.
    data = None
    try:
        data = json.loads(text)
    except Exception:
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except Exception:
                data = None

    if not isinstance(data, list):
        raise ValueError("La IA no devolvió un array JSON de ejercicios.")

    exercises: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        instruccion = str(item.get("instruccion") or item.get("instruction") or "").strip()
        explicacion = str(
            item.get("explicacion") or item.get("explanation") or item.get("why") or ""
        ).strip()
        if instruccion:
            exercises.append({"instruccion": instruccion, "explicacion": explicacion})

    if len(exercises) < 5:
        raise ValueError(
            f"La IA devolvió {len(exercises)} ejercicios válidos (se esperaban 5)."
        )

    # Garantizar exactamente 5 (recortar si vinieran de más).
    return exercises[:5]


def generate_training_session(
    objetivo: str,
    nivel_perro: str = "medio",
    nivel_guias: str = "medio",
    tiempo: Optional[int] = None,
    donde: Optional[str] = None,
    recursos: Optional[list[str]] = None,
    reforzadores: Optional[list[str]] = None,
    lang: str = "es",
):
    """
    Genera 5 ejercicios de adiestramiento via Haiku 4.5.

    Devuelve un objeto ligero con:
      - exercises: list[{instruccion, explicacion}] (exactamente 5)
      - input_tokens / output_tokens (para logueo de coste)

    Lanza Exception si Anthropic falla o si la salida no se puede parsear —
    el caller (router) debe hacer refund + log de error.
    """
    lang = (lang or "es").lower()
    if lang not in ("es", "en"):
        lang = "es"

    system = _SYSTEM_ES if lang == "es" else _SYSTEM_EN
    user_prompt = _build_user_prompt(
        objetivo=objetivo,
        nivel_perro=nivel_perro,
        nivel_guias=nivel_guias,
        tiempo=tiempo,
        donde=donde,
        recursos=recursos,
        reforzadores=reforzadores,
        lang=lang,
    )

    client = get_anthropic_client()
    settings = get_settings()

    response = client.messages.create(
        model=settings.avatar_model,  # Haiku 4.5
        max_tokens=1200,
        temperature=0.8,
        system=system,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw_text = ""
    for block in response.content:
        if getattr(block, "type", None) == "text":
            raw_text += block.text

    exercises = _parse_exercises(raw_text)

    return _TrainingResult(
        exercises=exercises,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )


class _TrainingResult:
    """Resultado ligero del servicio (no es un modelo de respuesta de API;
    el router construye el response Pydantic a partir de esto)."""

    def __init__(self, exercises: list[dict], input_tokens: int, output_tokens: int):
        self.exercises = exercises
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
