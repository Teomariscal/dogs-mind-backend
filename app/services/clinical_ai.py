"""
Clinical AI service — Claude Sonnet 4.6 with RAG + prompt caching.

Caching strategy:
  • The large clinical system prompt is sent as a system block with
    cache_control = {"type": "ephemeral"} (5-min TTL).
  • The user message contains the retrieved RAG context + anamnesis data
    and is NOT cached (it changes per request).
  • This means we pay the cache-write premium once and then ~0.1× on
    subsequent requests that share the same system prompt prefix.

The minimum cacheable prefix for claude-sonnet-4-6 is 2 048 tokens.
Our clinical system prompt is intentionally long enough to exceed that.
"""

import anthropic
from typing import Optional

from app.config import get_settings
from app.core.anthropic_client import get_anthropic_client
from app.core.prompts.clinical import CLINICAL_SYSTEM_PROMPT
from app.models.anamnesis import AnamnesisInput, AnalysisResponse, RetrievedChunk
from app.services.rag import retrieve, build_rag_context_block, build_anamnesis_block


def _build_query_from_anamnesis(anamnesis: AnamnesisInput) -> str:
    """Derive a concise retrieval query from the anamnesis fields."""
    parts = [
        anamnesis.problem_description,
        anamnesis.when_it_happens,
        anamnesis.where_it_happens,
        anamnesis.owner_theory or "",
        anamnesis.breed,
    ]
    return " ".join(p for p in parts if p).strip()


def _build_user_message_content(
    user_text: str,
    video_frames: Optional[list] = None,
) -> object:
    """
    Build the user message content for the Claude API call.

    • Without video  → plain string (unchanged behaviour).
    • With video     → list of content blocks: intro text + image frames +
                       full anamnesis/RAG text. Claude sees the frames as part
                       of the consultation material.
    """
    if not video_frames:
        return user_text

    blocks: list[dict] = [
        {
            "type": "text",
            "text": (
                "The owner has submitted a video recording of the dog's behavior. "
                "The following frames (sampled evenly across the video) show the "
                "dog in context. Observe body language, posture, ear/tail position, "
                "spatial relationships and any visible triggers before reading the "
                "written anamnesis below.\n"
            ),
        }
    ]

    for i, frame_b64 in enumerate(video_frames, start=1):
        blocks.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": frame_b64,
                },
            }
        )

    blocks.append({"type": "text", "text": user_text})
    return blocks


def run_clinical_analysis(
    anamnesis: AnamnesisInput,
    video_frames: Optional[list] = None,
) -> AnalysisResponse:
    """
    Full pipeline:
      1. Retrieve relevant knowledge chunks from Qdrant.
      2. Build user message = RAG context + anamnesis (+ optional video frames).
      3. Call Claude Sonnet 4.6 with cached system prompt.
      4. Return structured AnalysisResponse.

    When *video_frames* is provided the user message becomes a multi-modal
    content list (text + JPEG image blocks).
    """
    settings = get_settings()
    client = get_anthropic_client()

    # ── 1. RAG retrieval ────────────────────────────────────────────────────
    query = _build_query_from_anamnesis(anamnesis)
    retrieved_chunks: list[RetrievedChunk] = retrieve(query)

    rag_block = build_rag_context_block(retrieved_chunks)
    anamnesis_block = build_anamnesis_block(anamnesis.model_dump())

    video_note = (
        "\nNOTE: Video frames of the dog's behavior have been provided above. "
        "Integrate your visual observations into the ABC analysis — describe "
        "observable body language signals as part of BLOQUE A and BLOQUE B.\n"
        if video_frames
        else ""
    )

    lang = (anamnesis.lang or "es").lower()
    if lang == "en":
        lang_instruction = (
            "\nCRITICAL LANGUAGE INSTRUCTION: Write the ENTIRE analysis in ENGLISH. "
            "Every heading, bullet point, label and sentence must be in English. "
            "Do NOT use Spanish at any point in the output.\n"
        )
    else:
        lang_instruction = (
            "\nINSTRUCCIÓN DE IDIOMA: Escribe el análisis completo en ESPAÑOL. "
            "Todos los encabezados, puntos y frases deben estar en español.\n"
        )

    user_text = f"""Please produce a Functional Behavioral Analysis for the following case.{video_note}{lang_instruction}

{rag_block}

{anamnesis_block}

Use the retrieved knowledge above (cited as [1], [2], etc.) to ground your
analysis. Follow the output format defined in your instructions exactly.
"""

    content = _build_user_message_content(user_text, video_frames)

    # ── 2. Call Claude Sonnet 4.6 with prompt caching ───────────────────────
    response = client.messages.create(
        model=settings.clinical_model,
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": CLINICAL_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": content}],
    )

    # ── 3. Parse response ────────────────────────────────────────────────────
    analysis_text = ""
    for block in response.content:
        if block.type == "text":
            analysis_text += block.text

    cache_hit = (response.usage.cache_read_input_tokens or 0) > 0

    return AnalysisResponse(
        analysis=analysis_text,
        sources=retrieved_chunks,
        cache_hit=cache_hit,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )
