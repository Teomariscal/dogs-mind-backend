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


def build_anamnesis_block(anamnesis: dict) -> str:
    """
    Format the anamnesis dict as a structured text block for the clinical AI.
    """
    a = anamnesis
    lines = [
        "<anamnesis>",
        f"Dog: {a.get('dog_name', 'Unknown')}, {a.get('breed', '?')}, {a.get('dog_age', '?')}",
        f"Weaning age: {a.get('weaning_age_weeks', 'unknown')} weeks",
        f"Chronic disease: {'Yes — ' + a.get('chronic_disease_detail', '') if a.get('chronic_disease') else 'No'}",
        f"Living environment: {a.get('living_environment', '?')}",
        f"Household: {a.get('household_members', '?')} person(s)",
        f"Children present: {'Yes' if a.get('children_present') else 'No'}",
        f"Other dogs: {'Yes — ' + a.get('other_dogs_detail', '') if a.get('other_dogs') else 'No'}",
        f"Urban/rural: {a.get('urban_rural', 'unknown')}",
        f"Daily walks: {'Yes, ' + str(a.get('walks_per_day', '?')) + ' per day' if a.get('daily_walks') else 'No'}",
        "",
        f"Problem description: {a.get('problem_description', '')}",
        f"When it happens: {a.get('when_it_happens', '')}",
        f"Frequency: {a.get('frequency', '')}",
        f"Where: {a.get('where_it_happens', '')}",
        f"Who is present: {a.get('who_is_present', '')}",
        "",
        f"Involves aggression: {'Yes' if a.get('involves_aggression') else 'No'}",
    ]
    if a.get("involves_aggression") and a.get("aggression_distance_cm"):
        lines.append(f"Aggression onset distance: {a['aggression_distance_cm']} cm")

    if a.get("previous_attempts"):
        lines.append(f"Previous attempts: {a['previous_attempts']}")
    if a.get("owner_theory"):
        lines.append(f"Owner's theory: {a['owner_theory']}")

    lines.append("</anamnesis>")
    return "\n".join(lines)
