"""
RAG retrieval service.

Given a query string, embeds it with Voyage AI and retrieves the top-k
most relevant chunks from Qdrant. Returns them as RetrievedChunk objects
ready to be injected into the clinical AI prompt.
"""

from __future__ import annotations

from typing import Optional

from app.config import get_settings
from app.core.qdrant_client import get_qdrant_client
from app.core.voyage_client import embed_query
from app.models.anamnesis import RetrievedChunk


def retrieve(query: str, top_k: Optional[int] = None) -> list[RetrievedChunk]:
    """
    Embed the query and return the top-k chunks from Qdrant.
    Returns an empty list if the collection is empty or unreachable.
    """
    settings = get_settings()
    k = top_k or settings.rag_top_k
    qdrant = get_qdrant_client()

    query_vector = embed_query(query)

    results = qdrant.search(
        collection_name=settings.qdrant_collection,
        query_vector=query_vector,
        limit=k,
        with_payload=True,
        score_threshold=0.35,   # discard low-relevance chunks
    )

    chunks: list[RetrievedChunk] = []
    for hit in results:
        payload = hit.payload or {}
        page = payload.get("page_start")
        chunks.append(
            RetrievedChunk(
                chunk_id=str(hit.id),
                text=payload.get("text", ""),
                source=payload.get("filename", "unknown"),
                page=page,
                score=round(hit.score, 4),
            )
        )

    return chunks


def build_rag_context_block(chunks: list[RetrievedChunk]) -> str:
    """
    Format retrieved chunks as a numbered reference block to inject
    into the user message sent to the clinical AI.
    """
    if not chunks:
        return ""

    lines = ["<retrieved_knowledge>"]
    for i, chunk in enumerate(chunks, start=1):
        source_info = chunk.source
        if chunk.page is not None:
            source_info += f", p. {chunk.page}"
        lines.append(f"[{i}] Source: {source_info}")
        lines.append(chunk.text.strip())
        lines.append("")
    lines.append("</retrieved_knowledge>")
    return "\n".join(lines)


_NOT_PROVIDED = "información no aportada / not provided"


def _walks_label(a: dict) -> str:
    """
    Render walks_per_day distinguiendo:
      None      → 'no aportado'
      0         → 'no walks (0)'
      1, 2      → 'N walks per day'
      3 or more → '3 or more walks per day'
    """
    wpd = a.get("walks_per_day")
    if wpd is None:
        # Fallback al campo legacy daily_walks si está presente, de lo contrario no aportado
        dw = a.get("daily_walks")
        if dw is True:
            return "Yes, but number per day not specified"
        if dw is False:
            return "No"
        return _NOT_PROVIDED
    if wpd == 0:
        return "0 (no walks)"
    if wpd >= 3:
        return "3 or more walks per day"
    return f"{wpd} walks per day"


def _bool_label(value, *, yes_text: str = "Yes", no_text: str = "No") -> str:
    """Render booleano nullable: None → 'no aportado', True → yes_text, False → no_text."""
    if value is None:
        return _NOT_PROVIDED
    return yes_text if value else no_text


def _str_label(value) -> str:
    """Render string optional: None / '' → 'no aportado'."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return _NOT_PROVIDED
    return str(value).strip()


_FAVORITE_REWARD_LABELS = {
    "food":    "Food (treats)",
    "ball":    "Ball / toy",
    "petting": "Petting / social attention",
    "none":    "Nothing motivates the dog (possible anhedonia / chronic stress signal)",
}


def build_anamnesis_block(anamnesis: dict) -> str:
    """
    Format the anamnesis dict as a structured text block for the clinical AI.

    Rendering principle (anti-fabrication):
    Cada campo distingue explícitamente entre "Sí", "No" e "información no
    aportada". El modelo lee literalmente; cualquier 'información no aportada'
    debe permanecer así en el output (ver Section 0 del system prompt clínico).
    """
    a = anamnesis

    # Campos del perro
    weaning = a.get("weaning_age_weeks")
    weaning_str = f"{weaning} weeks" if weaning is not None else _NOT_PROVIDED

    # Reforzador favorito
    fav_raw = a.get("favorite_reward")
    fav_str = _FAVORITE_REWARD_LABELS.get(fav_raw, _NOT_PROVIDED) if fav_raw else _NOT_PROVIDED

    # Escuela canina
    attended = a.get("attended_training_school")
    if attended is True:
        result = a.get("training_school_result")
        training_str = "Yes — Result: " + (result.strip() if result and result.strip() else _NOT_PROVIDED)
    elif attended is False:
        training_str = "No"
    else:
        training_str = _NOT_PROVIDED

    # Sexo del perro: 'male' | 'female' | None
    sex_raw = a.get("dog_sex")
    if sex_raw == "male":
        sex_str = "Male"
    elif sex_raw == "female":
        sex_str = "Female"
    else:
        sex_str = _NOT_PROVIDED

    lines = [
        "<anamnesis>",
        "## Dog profile",
        f"Dog: {a.get('dog_name') or _NOT_PROVIDED}, {a.get('breed') or _NOT_PROVIDED}, {a.get('dog_age') or _NOT_PROVIDED}",
        f"Sex: {sex_str}",
        f"Weaning age: {weaning_str}",
        f"Chronic disease: {'Yes — ' + (a.get('chronic_disease_detail') or _NOT_PROVIDED) if a.get('chronic_disease') else _bool_label(a.get('chronic_disease'))}",
        "",
        "## Living situation",
        f"Living environment: {a.get('living_environment') or _NOT_PROVIDED}",
        f"Urban/rural: {a.get('urban_rural') or _NOT_PROVIDED}",
        f"Household members: {a.get('household_members') if a.get('household_members') is not None else _NOT_PROVIDED}",
        f"Children present: {_bool_label(a.get('children_present'))}",
        f"Other dogs: {'Yes — ' + (a.get('other_dogs_detail') or _NOT_PROVIDED) if a.get('other_dogs') else _bool_label(a.get('other_dogs'))}",
        "",
        "## Routine & history",
        f"Walks per day: {_walks_label(a)}",
        f"Other behavior problems reported by owner: {_str_label(a.get('other_behavior_problems'))}",
        f"Has attended dog training school: {training_str}",
        f"Favorite reinforcer (motivator): {fav_str}",
        "",
        "## Behavior problem",
        f"Problem description: {_str_label(a.get('problem_description'))}",
        f"When it happens: {_str_label(a.get('when_it_happens'))}",
        f"Frequency: {a.get('frequency') or _NOT_PROVIDED}",
        f"Where: {_str_label(a.get('where_it_happens'))}",
        f"Who is present: {_str_label(a.get('who_is_present'))}",
        f"Involves aggression: {_bool_label(a.get('involves_aggression'))}",
    ]

    if a.get("involves_aggression") and a.get("aggression_distance_cm") is not None:
        lines.append(f"Aggression onset distance: {a['aggression_distance_cm']} cm")

    lines.append("")
    lines.append("## Owner-provided extra context")
    lines.append(f"Previous attempts: {_str_label(a.get('previous_attempts'))}")
    lines.append(f"Owner's theory: {_str_label(a.get('owner_theory'))}")
    lines.append(f"Major event/change before problem started: {_str_label(a.get('prior_event'))}")

    lines.append("</anamnesis>")
    return "\n".join(lines)
