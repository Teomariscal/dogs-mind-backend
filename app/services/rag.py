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


def _is_core_cognitive(filename: str) -> bool:
    """True si el documento pertenece a la CAPA NÚCLEO (eje) de la RAG B."""
    settings = get_settings()
    fn = (filename or "").lower()
    return any(p.lower() in fn for p in settings.cognitive_core_patterns)


def retrieve_cognitive(query: str, top_k: Optional[int] = None) -> list[RetrievedChunk]:
    """
    Recuperación de la RAG B (corpus cognitivista IT) con JERARQUÍA DE CAPAS:
      • EJE (núcleo): la obra "Vivir con el perro" — columna vertebral del estilo.
      • COMPLEMENTO: casos (Referto*), glosario, papers y demás.
    Reserva una cuota del top_k al eje (si hay hits sobre umbral) y rellena el
    resto con el mejor complemento, preservando el orden por score dentro de cada capa.
    Devuelve lista vacía si la collection está vacía o es inalcanzable.
    """
    settings = get_settings()
    k = top_k or settings.rag_top_k
    qdrant = get_qdrant_client()

    # Si la RAG B aún no existe (vacía), no romper: sin contexto cognitivo.
    try:
        existing = {c.name for c in qdrant.get_collections().collections}
        if settings.qdrant_collection_cognitive not in existing:
            return []
    except Exception:
        return []

    query_vector = embed_query(query)

    # Pedimos un pool mayor que k para poder separar capas y elegir con criterio.
    pool = qdrant.search(
        collection_name=settings.qdrant_collection_cognitive,
        query_vector=query_vector,
        limit=max(k * 4, 20),
        with_payload=True,
        score_threshold=0.30,
    )

    def _to_chunk(hit) -> RetrievedChunk:
        payload = hit.payload or {}
        return RetrievedChunk(
            chunk_id=str(hit.id),
            text=payload.get("text", ""),
            source=payload.get("filename", "unknown"),
            page=payload.get("page_start"),
            score=round(hit.score, 4),
        )

    core = [_to_chunk(h) for h in pool if _is_core_cognitive((h.payload or {}).get("filename", ""))]
    complement = [_to_chunk(h) for h in pool if not _is_core_cognitive((h.payload or {}).get("filename", ""))]

    # El eje encabeza, con una cuota reservada; el complemento rellena hasta k.
    quota = min(settings.cognitive_core_quota, k)
    selected = core[:quota]
    for c in complement:
        if len(selected) >= k:
            break
        selected.append(c)
    # Si sobran huecos y quedan hits del eje, se añaden.
    if len(selected) < k:
        for c in core[quota:]:
            if len(selected) >= k:
                break
            selected.append(c)

    return selected[:k]


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
    # #1 (feedback tester): solo se añade cuando el tutor aporta el dato (perro adoptado).
    # NO mutar el prompt de los casos no adoptados (~95%): se omite por completo si está vacío.
    _adopted = a.get("adopted_time_with_tutor")
    if isinstance(_adopted, str):
        _adopted = _adopted.strip()
    if _adopted:
        lines.append(
            f"Adopted — time living with current tutor: {_adopted}. "
            "(Interpret the problem's duration/history relative to THIS time with the "
            "tutor, not the dog's total age.)"
        )

    lines.append("</anamnesis>")
    return "\n".join(lines)
