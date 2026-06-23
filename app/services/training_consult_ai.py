"""
Servicio del flujo "Entrenamiento específico" — análisis funcional ABA + plan
operante por fases con ejercicios varios para UNA habilidad concreta.

Pipeline (igual patrón que clinical_ai.py / /analysis ABC):
  1. RAG retrieval contra `dogs_mind_knowledge` con query construida desde
     los 9 campos de la plantilla.
  2. Build user message = bloque RAG + bloque entrada estructurada.
  3. Llamar Sonnet 4.6 con system prompt cacheado (prompt caching activo).
  4. Devolver TrainingConsultResult con markdown + sources + tokens.

Decisión founder 2026-05-29 (segunda iteración): anclar a RAG clínica
compartida, estructura ABA formal, tono técnico puro, plan por fases con
ejercicios principal + complementarios. Heredando blindaje LIMA literal.

Coste por consulta (con RAG): ~$0.025 (Sonnet 4.6 + chunks RAG en input).
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Optional

from app.config import get_settings
from app.core.anthropic_client import get_anthropic_client, create_message_resilient
from app.core.prompts.training_consult import (
    TRAINING_CONSULT_PROMPT_ES,
    TRAINING_CONSULT_PROMPT_EN,
)
from app.services.rag import retrieve, build_rag_context_block
from app.models.anamnesis import RetrievedChunk


logger = logging.getLogger(__name__)

MAX_OUTPUT_TOKENS = 2000  # Plan profesional denso, sin padding. Prompt impone
                          # ≤700 palabras ES / ≤600 EN (~1100 tokens). 2000 deja
                          # margen suficiente sin invitar al modelo a rellenar.
                          # Founder 2026-06-02 ronda 2: "es demasiado y aburre,
                          # el lector es profesional, evita redundancias".
TEMPERATURE = 0.4

# Top-K chunks RAG. La RAG clínica está alimentada con literatura de
# modificación de conducta y aprendizaje operante; para entrenamiento
# específico recuperamos algunos menos que para análisis ABC porque el
# foco es más estrecho (una habilidad concreta).
RAG_TOP_K = 5


# Etiquetas localizadas (mismo enfoque que training_ai.py).
_LEVEL_LABELS = {
    "es": {"basico": "Básico", "medio": "Medio", "avanzado": "Avanzado"},
    "en": {"basico": "Basic", "medio": "Intermediate", "avanzado": "Advanced"},
}
_CONTEXT_LABELS = {
    "es": {"pista": "Pista", "interior": "Interior", "calle": "Calle"},
    "en": {"pista": "Training field", "interior": "Indoor", "calle": "Street"},
}


@dataclass
class TrainingConsultResult:
    """Resultado ligero del servicio."""
    analysis_markdown: str
    sources: list[RetrievedChunk] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cache_hit: bool = False


def _build_rag_query(
    *,
    goal: str,
    context: str,
    dog_level: str,
    breed: str,
    reinforcers: list[str],
    lang: str,
) -> str:
    """Construye una query densa para Qdrant que abarca: habilidad objetivo,
    raza/tipología (para etología comparada), contexto, nivel actual y
    reforzadores. Mezcla términos técnicos para mejorar recall semántico."""
    ctx_map = _CONTEXT_LABELS.get(lang, _CONTEXT_LABELS["es"])
    ctx = ctx_map.get(context.lower(), context)
    reinforcers_str = ", ".join(reinforcers) if reinforcers else ""

    if lang == "en":
        parts = [
            f"Operant training of specific skill: {goal}.",
            f"Functional analysis ABA, discriminative stimulus, target behavior, reinforcement schedule.",
            f"DRI, DRA, DRO, shaping, capture, luring, stimulus control, generalization, proofing.",
            f"Subject profile: {breed}, training level {dog_level}.",
            f"Training context: {ctx}.",
        ]
        if reinforcers_str:
            parts.append(f"Available reinforcers: {reinforcers_str}.")
    else:
        parts = [
            f"Adiestramiento operante de habilidad específica: {goal}.",
            f"Análisis funcional ABA, estímulo discriminativo, conducta meta, programa de reforzamiento.",
            f"DRI, DRA, DRO, shaping, captura, luring, control de estímulo, generalización, proofing.",
            f"Perfil del sujeto: {breed}, nivel de entrenamiento {dog_level}.",
            f"Contexto de entrenamiento: {ctx}.",
        ]
        if reinforcers_str:
            parts.append(f"Reforzadores disponibles: {reinforcers_str}.")

    return " ".join(parts)


def _build_input_block(
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
    """Bloque estructurado con los 9 campos de la plantilla, equivalente al
    `build_anamnesis_block` del flujo clínico. Formato técnico."""
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
        return (
            "<consultation_input>\n"
            "SUBJECT:\n"
            f"  - Name: {dog_name}\n"
            f"  - Breed type: {breed}\n"
            f"  - Age: {age}\n"
            "\n"
            "PROFILE:\n"
            f"  - Subject training level: {dlvl}\n"
            f"  - Handler level: {hlvl}\n"
            f"  - Reported preferred reinforcers: {reinforcers_str}\n"
            f"  - Clicker installed and used regularly: {clicker_str}\n"
            "\n"
            "TARGET EXERCISE:\n"
            f"  - Skill / behavior to teach: {goal}\n"
            f"  - Main training context: {ctx}\n"
            "</consultation_input>"
        )
    else:
        return (
            "<consultation_input>\n"
            "SUJETO:\n"
            f"  - Nombre: {dog_name}\n"
            f"  - Tipología racial: {breed}\n"
            f"  - Edad: {age}\n"
            "\n"
            "PERFIL:\n"
            f"  - Nivel de entrenamiento del sujeto: {dlvl}\n"
            f"  - Nivel del guía: {hlvl}\n"
            f"  - Reforzadores preferidos reportados: {reinforcers_str}\n"
            f"  - Clicker instalado y de uso habitual: {clicker_str}\n"
            "\n"
            "EJERCICIO OBJETIVO:\n"
            f"  - Habilidad / conducta a enseñar: {goal}\n"
            f"  - Contexto principal de entrenamiento: {ctx}\n"
            "</consultation_input>"
        )


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
    Pipeline:
      1. RAG retrieval contra dogs_mind_knowledge.
      2. Build user message = bloque RAG + bloque entrada + instrucciones.
      3. Sonnet 4.6 con prompt caching.
      4. Devuelve markdown + sources + tokens.

    Lanza Exception si Anthropic falla. El caller (router) hace refund_token
    + log de error.
    """
    lang_norm = (lang or "es").lower()
    if lang_norm not in ("es", "en"):
        lang_norm = "es"

    system_prompt = (
        TRAINING_CONSULT_PROMPT_EN if lang_norm == "en"
        else TRAINING_CONSULT_PROMPT_ES
    )

    # ── 1. RAG retrieval ────────────────────────────────────────────────────
    query = _build_rag_query(
        goal=goal,
        context=context,
        dog_level=dog_level,
        breed=breed,
        reinforcers=reinforcers,
        lang=lang_norm,
    )
    retrieved_chunks: list[RetrievedChunk] = retrieve(query, top_k=RAG_TOP_K)
    rag_block = build_rag_context_block(retrieved_chunks)

    # ── 2. Build user message ───────────────────────────────────────────────
    input_block = _build_input_block(
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

    if lang_norm == "en":
        lang_instruction = (
            "CRITICAL LANGUAGE: Write the ENTIRE response in ENGLISH. "
            "Headings, bullets and inline text in English only."
        )
        closing = (
            "Use the retrieved knowledge above (cited [1], [2], …) to anchor "
            "the analysis and plan. Follow the response structure defined in "
            "your system prompt exactly. Strict technical tone."
        )
    else:
        lang_instruction = (
            "INSTRUCCIÓN DE IDIOMA: Toda la respuesta en ESPAÑOL. "
            "Encabezados, viñetas y texto en español únicamente."
        )
        closing = (
            "Usa la literatura recuperada arriba (citada [1], [2], …) para "
            "anclar el análisis y el plan. Sigue exactamente la estructura "
            "definida en tu system prompt. Tono técnico estricto."
        )

    user_text = (
        f"{lang_instruction}\n\n"
        f"{rag_block}\n\n"
        f"{input_block}\n\n"
        f"{closing}"
    )

    # ── 3. Call Claude Sonnet 4.6 with prompt caching ───────────────────────
    settings = get_settings()
    client = get_anthropic_client()

    response = create_message_resilient(
        model=settings.clinical_model,  # Sonnet 4.6
        fallback_model=settings.clinical_fallback_model,  # sube a Opus si Sonnet está 529 (temperature se quita en el helper)
        max_tokens=MAX_OUTPUT_TOKENS,
        temperature=TEMPERATURE,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_text}],
    )

    # ── 4. Parse response ───────────────────────────────────────────────────
    raw = ""
    for block in response.content:
        if getattr(block, "type", None) == "text":
            raw += block.text

    analysis = raw.strip()
    cache_hit = (response.usage.cache_read_input_tokens or 0) > 0

    return TrainingConsultResult(
        analysis_markdown=analysis,
        sources=retrieved_chunks,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        cache_hit=cache_hit,
    )
