"""
Daily Follow-up AI service — wizard ampliado 2026-05-09.

Sustituye al servicio batch del commit A (`daily_tasks_ai.py`, deprecado).
Nuevo flujo on-demand:

  1. classify_diagnosis(plan) → diagnosis_type (Haiku, ~$0.0001).
  2. generate_daily_checkin(case, history, ...) → DailyCheckin (Sonnet, ~$0.008).
     - Devuelve 2-5 ejercicios (último wellness) + 1 pregunta del día.
     - Lee histórico para decidir progresión / variación / regresión / cambio.
  3. La pregunta del día puede venir de la caché `theory_questions` filtrada
     por diagnosis_type (probabilidad ≥0.7 si hay ≥5 disponibles no servidas
     a este caso). Si no, se usa la generada por el coach y se persiste en
     caché para futuros casos del mismo diagnóstico.

Spec: ~/.claude/projects/.../memory/project_dogs_mind_daily_followup.md.
"""

from __future__ import annotations
import json
import logging
import random
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.config import get_settings
from app.core.anthropic_client import get_anthropic_client
from app.core.prompts.daily_followup_coach import (
    DAILY_FOLLOWUP_COACH_PROMPT_ES,
    DAILY_FOLLOWUP_COACH_PROMPT_EN,
    DIAGNOSIS_CLASSIFIER_PROMPT,
)


logger = logging.getLogger(__name__)


# Tipos de diagnóstico permitidos. Mantener en sync con DIAGNOSIS_CLASSIFIER_PROMPT.
ALLOWED_DIAGNOSES = {
    "leash_reactivity", "separation_anxiety", "recall_training",
    "resource_guarding", "fear_phobia", "aggression_dogs",
    "aggression_humans", "pulling_leash", "jumping_greeting",
    "hyperactivity_arousal", "destructive_chewing", "housetraining",
    "general_obedience", "stereotypies", "other",
}

# Cuántos días de histórico inyectar al coach. Suficiente para detectar
# tendencias y decidir progresión/regresión sin saturar contexto.
HISTORY_DAYS_TO_FEED = 5

# Probabilidad de servir pregunta desde caché si hay candidatas suficientes.
CACHE_HIT_PROBABILITY = 0.7
CACHE_MIN_CANDIDATES = 5

MAX_OUTPUT_TOKENS_COACH = 2200
MAX_OUTPUT_TOKENS_DIAGNOSIS = 16


@dataclass
class ExerciseSpec:
    title: str
    instruction: str
    result_type: str          # "chips" | "text"
    result_chips: list[str] | None
    is_wellness: bool


@dataclass
class TheoryQuestionSpec:
    question_type: str        # "theory" | "compliance"
    question: str
    options: list[str]
    correct_index: int        # 0..2
    explanation: str


@dataclass
class DailyCheckin:
    exercises: list[ExerciseSpec]
    theory_question: TheoryQuestionSpec
    theory_question_from_cache: bool
    theory_question_cache_id: str | None  # UUID si vino de caché
    input_tokens: int
    output_tokens: int


# ── Diagnosis classifier (Haiku) ─────────────────────────────────────────
def classify_diagnosis(intervention_plan_text: str) -> str:
    """Clasifica el plan en uno de ALLOWED_DIAGNOSES. Devuelve 'other' si
    el modelo no acierta una clave válida."""
    settings = get_settings()
    client = get_anthropic_client()

    text = (intervention_plan_text or "").strip()
    if not text:
        return "other"

    response = client.messages.create(
        model=settings.avatar_model,  # Haiku 4.5
        max_tokens=MAX_OUTPUT_TOKENS_DIAGNOSIS,
        system=DIAGNOSIS_CLASSIFIER_PROMPT,
        messages=[{"role": "user", "content": text[:4000]}],
    )

    raw = ""
    for block in response.content:
        if getattr(block, "type", None) == "text":
            raw += block.text
    token = (raw or "").strip().lower()
    # Limpia comillas, puntos, espacios
    token = re.sub(r"[^a-z_]", "", token)
    if token in ALLOWED_DIAGNOSES:
        return token
    return "other"


# ── Daily checkin generator (Sonnet) ─────────────────────────────────────
def generate_daily_checkin(
    *,
    db: Session,
    case_id,
    plan_text: str,
    dog_name: str,
    diagnosis_type: str,
    day_index: int,
    history: list[dict[str, Any]],
    lang: str = "es",
) -> DailyCheckin:
    """
    Genera el check-in del día N para un caso concreto.

    Args:
      db: sesión SQLAlchemy para mirar caché de preguntas.
      case_id: UUID del caso (para anti-repetir preguntas dentro del mismo caso).
      plan_text: plan de intervención completo.
      dog_name: nombre del perro (para personalizar).
      diagnosis_type: clave de caché de preguntas.
      day_index: día 1-N actual del check-in.
      history: lista cronológica con los últimos days, cada uno con
               {day_n, exercises_generated, exercises_results, observation?}.
      lang: 'es' | 'en'.

    Returns: DailyCheckin con N ejercicios + pregunta del día.
    """
    settings = get_settings()
    client = get_anthropic_client()

    lang_norm = (lang or "es").lower()
    system_prompt = (
        DAILY_FOLLOWUP_COACH_PROMPT_EN if lang_norm == "en"
        else DAILY_FOLLOWUP_COACH_PROMPT_ES
    )

    # Construir el mensaje de usuario con plan + histórico + día actual.
    history_block = _format_history(history, lang_norm)
    if lang_norm == "en":
        user_msg = (
            f"CRITICAL LANGUAGE INSTRUCTION: All your output (exercise titles, "
            f"descriptions, instructions, theory question, options and "
            f"explanation) MUST be in ENGLISH. The intervention plan below may "
            f"be in Spanish — translate the concepts but output everything in "
            f"English.\n\n"
            f"Dog's name: {dog_name}\n"
            f"Diagnosis type: {diagnosis_type}\n"
            f"Today is day {day_index} of the follow-up.\n\n"
            f"INTERVENTION PLAN:\n\n{plan_text.strip()}\n\n"
            f"PREVIOUS DAYS HISTORY:\n\n{history_block}\n\n"
            f"Generate today's check-in (day {day_index}) as JSON, ALL FIELDS IN ENGLISH."
        )
    else:
        user_msg = (
            f"INSTRUCCIÓN DE IDIOMA CRÍTICA: Toda tu salida (títulos, "
            f"descripciones, instrucciones, pregunta teórica, opciones y "
            f"explicación) DEBE estar en ESPAÑOL.\n\n"
            f"Nombre del perro: {dog_name}\n"
            f"Tipo de diagnóstico: {diagnosis_type}\n"
            f"Hoy es el día {day_index} del seguimiento.\n\n"
            f"PLAN DE INTERVENCIÓN:\n\n{plan_text.strip()}\n\n"
            f"HISTÓRICO DE DÍAS ANTERIORES:\n\n{history_block}\n\n"
            f"Genera el check-in de hoy (día {day_index}) en JSON, TODO EN ESPAÑOL."
        )

    response = client.messages.create(
        model=settings.clinical_model,  # Sonnet 4.6
        max_tokens=MAX_OUTPUT_TOKENS_COACH,
        system=system_prompt,
        messages=[{"role": "user", "content": user_msg}],
    )

    raw = ""
    for block in response.content:
        if getattr(block, "type", None) == "text":
            raw += block.text

    parsed = _parse_coach_json(raw)
    exercises_raw = parsed.get("exercises", [])
    theory_raw = parsed.get("theory_question", {})

    exercises = _validate_exercises(exercises_raw)
    theory_from_coach = _validate_theory(theory_raw)

    # Decidir si servimos pregunta de caché o usamos la del coach.
    theory_final, from_cache, cache_id = _maybe_use_cached_theory(
        db=db,
        case_id=case_id,
        diagnosis_type=diagnosis_type,
        lang=lang_norm,
        coach_theory=theory_from_coach,
    )

    return DailyCheckin(
        exercises=exercises,
        theory_question=theory_final,
        theory_question_from_cache=from_cache,
        theory_question_cache_id=cache_id,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )


# ── Helpers ──────────────────────────────────────────────────────────────
def _format_history(history: list[dict[str, Any]], lang: str) -> str:
    if not history:
        return ("(no previous days)" if lang == "en" else "(no hay días previos)")
    lines = []
    for h in history[-HISTORY_DAYS_TO_FEED:]:
        day_n = h.get("day_n", "?")
        gen = h.get("exercises_generated") or []
        res = h.get("exercises_results") or []
        lines.append(f"--- Día {day_n} ---" if lang != "en" else f"--- Day {day_n} ---")
        for i, ex in enumerate(gen):
            title = ex.get("title", "(sin título)")
            r = res[i] if i < len(res) else None
            r_text = ""
            if r:
                if "result_chip_index" in r and r["result_chip_index"] is not None:
                    chips = ex.get("result_chips") or []
                    idx = r["result_chip_index"]
                    if 0 <= idx < len(chips):
                        r_text = chips[idx]
                elif "result_text" in r and r["result_text"]:
                    r_text = r["result_text"]
            lines.append(f"  {i+1}. {title} → {r_text or '(sin reportar)'}")
    return "\n".join(lines)


def _parse_coach_json(text: str) -> dict[str, Any]:
    """Parsea JSON con tolerancia a fences accidentales o texto antes/después."""
    if not text:
        return {}
    # Quitar fences de markdown si los hubiera
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```\s*$", "", cleaned)
    # Localizar primera { y última } para tolerar texto extra
    first = cleaned.find("{")
    last = cleaned.rfind("}")
    if first == -1 or last == -1 or last <= first:
        return {}
    candidate = cleaned[first:last + 1]
    try:
        return json.loads(candidate)
    except Exception as e:
        logger.warning(f"[daily-followup] coach JSON parse failed: {e}; raw={text[:300]}")
        return {}


def _validate_exercises(raw: Any) -> list[ExerciseSpec]:
    """Valida el array de ejercicios. Garantiza:
    - 2 a 5 ejercicios.
    - Último siempre is_wellness=True (forzado si el modelo lo olvidó).
    - result_type ∈ {chips, text}; chips → 3 strings; text → None.
    Si parsing falla, lanza ValueError (el endpoint manejará el 502)."""
    if not isinstance(raw, list) or not raw:
        raise ValueError("exercises array vacío o no-lista")

    cleaned: list[ExerciseSpec] = []
    for ex in raw:
        if not isinstance(ex, dict):
            continue
        title = str(ex.get("title", "")).strip()
        instruction = str(ex.get("instruction", "")).strip()
        if not title or not instruction:
            continue
        rtype = str(ex.get("result_type", "chips")).lower().strip()
        if rtype not in ("chips", "text"):
            rtype = "chips"
        chips: list[str] | None = None
        if rtype == "chips":
            raw_chips = ex.get("result_chips") or []
            if isinstance(raw_chips, list):
                chips = [str(c).strip() for c in raw_chips if str(c).strip()]
            if not chips or len(chips) != 3:
                # Si chips inválidos, degradar a text para no inventar opciones
                rtype = "text"
                chips = None
        is_wellness = bool(ex.get("is_wellness", False))
        cleaned.append(ExerciseSpec(
            title=title[:100],
            instruction=instruction[:600],
            result_type=rtype,
            result_chips=chips,
            is_wellness=is_wellness,
        ))

    if len(cleaned) < 2:
        raise ValueError(f"too few exercises: {len(cleaned)}")
    cleaned = cleaned[:5]

    # Forzar el último = wellness (si el modelo no lo marcó, lo marcamos).
    for i in range(len(cleaned) - 1):
        cleaned[i].is_wellness = False
    cleaned[-1].is_wellness = True
    return cleaned


def _validate_theory(raw: Any) -> TheoryQuestionSpec:
    if not isinstance(raw, dict):
        raise ValueError("theory_question no es objeto")
    qtype = str(raw.get("question_type", "theory")).lower().strip()
    if qtype not in ("theory", "compliance"):
        qtype = "theory"
    question = str(raw.get("question", "")).strip()
    options_raw = raw.get("options") or []
    correct_index = raw.get("correct_index")
    explanation = str(raw.get("explanation", "")).strip()

    if not question or not explanation:
        raise ValueError("theory_question incompleta (question o explanation vacías)")
    if not isinstance(options_raw, list) or len(options_raw) != 3:
        raise ValueError("theory_question.options no es lista de 3")
    options = [str(o).strip() for o in options_raw]
    if any(not o for o in options):
        raise ValueError("theory_question.options con string vacío")
    try:
        ci = int(correct_index)
    except (TypeError, ValueError):
        raise ValueError("theory_question.correct_index no es entero") from None
    if ci not in (0, 1, 2):
        raise ValueError(f"theory_question.correct_index fuera de rango: {ci}")

    return TheoryQuestionSpec(
        question_type=qtype,
        question=question[:500],
        options=[o[:300] for o in options],
        correct_index=ci,
        explanation=explanation[:1000],
    )


def _maybe_use_cached_theory(
    *,
    db: Session,
    case_id,
    diagnosis_type: str,
    lang: str,
    coach_theory: TheoryQuestionSpec,
) -> tuple[TheoryQuestionSpec, bool, str | None]:
    """
    Decide entre servir una pregunta de caché o usar la generada por el coach.
    Si usamos la del coach, también la persistimos en caché para futuros casos.
    Devuelve (TheoryQuestionSpec, from_cache_bool, cache_id_uuid_str).
    """
    from app.models.case import TheoryQuestion, DailyFollowupEntry

    # Subquery: IDs de preguntas ya servidas a este caso (no repetir).
    used_ids_q = db.query(DailyFollowupEntry.theory_question_id).filter(
        DailyFollowupEntry.case_id == case_id,
        DailyFollowupEntry.theory_question_id.isnot(None),
    ).subquery()

    candidates_q = db.query(TheoryQuestion).filter(
        TheoryQuestion.diagnosis_type == diagnosis_type,
        TheoryQuestion.lang == lang,
        ~TheoryQuestion.id.in_(used_ids_q),
    )
    candidates_count = candidates_q.with_entities(func.count(TheoryQuestion.id)).scalar() or 0

    if (
        candidates_count >= CACHE_MIN_CANDIDATES
        and random.random() < CACHE_HIT_PROBABILITY
    ):
        # Servir pregunta de caché — la menos usada (round-robin equilibrado).
        cached = candidates_q.order_by(TheoryQuestion.usage_count.asc()).first()
        if cached:
            cached.usage_count = (cached.usage_count or 0) + 1
            db.commit()
            return (
                TheoryQuestionSpec(
                    question_type=cached.question_type,
                    question=cached.question_text,
                    options=list(cached.options) if cached.options else [],
                    correct_index=cached.correct_index,
                    explanation=cached.explanation,
                ),
                True,
                str(cached.id),
            )

    # No usamos caché: persistir la del coach y devolverla.
    new_q = TheoryQuestion(
        diagnosis_type=diagnosis_type,
        question_type=coach_theory.question_type,
        lang=lang,
        question_text=coach_theory.question,
        options=coach_theory.options,
        correct_index=coach_theory.correct_index,
        explanation=coach_theory.explanation,
        usage_count=1,
    )
    db.add(new_q)
    db.commit()
    db.refresh(new_q)
    return (coach_theory, False, str(new_q.id))
