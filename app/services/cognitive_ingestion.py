"""
Ingesta del corpus cognitivista italiano (RAG B — collection dogs_mind_cognitive_it).

Pipeline específico para CASOS REALES (aportados por Odette Abramovich, socia) y
bibliografía cognitiva:

  1. Parse PDF (pypdf) — mismo parser que la RAG A.
  2. ANONIMIZACIÓN (GDPR, fail-closed): los casos son reales → antes de indexar se
     eliminan los datos personales de los HUMANOS (propietarios): nombres y apellidos,
     teléfonos, emails, direcciones, DNI/CF. El nombre del perro y la raza se conservan.
     Doble capa: regex determinista (emails/teléfonos) + pasada LLM (clinical_model,
     con fallback). Si la pasada LLM falla o trunca → la ingesta ABORTA con error:
     NUNCA se indexa texto sin anonimizar.
  3. Chunking por caso: cada PDF se trata como UN caso (payload case_id=filename,
     corpus='cognitive_it'); chunks más largos que la RAG A para que la recuperación
     traiga bloques de redacción completos (molde de estilo, no fragmentos).
  4. Embedding Voyage + upsert a la collection B. JAMÁS a dogs_mind_knowledge.

La RAG B es corpus de EXPRESIÓN (cómo escribe un cognitivista), NO fuente diagnóstica:
la conclusión clínica sigue saliendo del motor ABA (pasada 1).
"""

import re
import time
import uuid

from qdrant_client.models import PointStruct, FilterSelector, Filter, FieldCondition, MatchValue

from app.config import get_settings
from app.core.anthropic_client import create_message_resilient
from app.core.qdrant_client import get_qdrant_client, ensure_cognitive_collection
from app.core.voyage_client import embed_documents
from app.services.document_ingestion import (
    _extract_pages,
    _split_into_chunks,
    _upsert_with_retry,
    EMBED_BATCH_SIZE,
    UPSERT_BATCH_SIZE,
)

# Chunks más largos que la RAG A (600/80): un caso clínico se recupera como bloque
# de redacción con contexto, no como fragmento suelto.
CASE_CHUNK_SIZE = 1000    # words
CASE_CHUNK_OVERLAP = 120  # words

# La pasada LLM de anonimización procesa el texto por segmentos para no acercarse
# a límites de output. ~2500 palabras ≈ ~3500 tokens de entrada.
ANON_SEGMENT_WORDS = 2500
ANON_MAX_TOKENS = 8000


class AnonymizationError(Exception):
    """La anonimización no pudo completarse → la ingesta debe abortar (fail-closed)."""


# ── Capa 1: regex determinista (backstop, corre ANTES y DESPUÉS del LLM) ─────────

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
# Secuencias de 9+ dígitos con separadores opcionales (teléfonos ES/IT).
# El mínimo de 9 evita comerse edades, dosis, fechas o medidas.
_PHONE_RE = re.compile(r"\+?\d(?:[ \-().]?\d){8,}")


def _regex_scrub(text: str) -> str:
    text = _EMAIL_RE.sub("[EMAIL]", text)
    text = _PHONE_RE.sub("[TELEFONO]", text)
    return text


# ── Capa 2: pasada LLM (nombres, apellidos, direcciones, identificadores) ────────

_ANON_SYSTEM_PROMPT = """Sei un sistema di anonimizzazione di documenti clinici veterinari/comportamentali.

Ricevi un testo (caso clinico reale). Devi restituire ESATTAMENTE lo stesso testo, parola
per parola, con UNA SOLA differenza: ogni dato personale riferito a ESSERI UMANI viene
sostituito da un segnaposto:

- Nomi e cognomi di persone (proprietari, familiari, colleghi) → [PROPRIETARIO]
- Indirizzi, vie, numeri civici, città se identificano il domicilio → [INDIRIZZO]
- Numeri di telefono → [TELEFONO]
- Email → [EMAIL]
- Codici fiscali, documenti d'identità, targhe → [ID]

REGOLE FERREE:
1. NON riassumere, NON riformulare, NON correggere, NON tradurre, NON omettere nulla.
   Il testo clinico resta INTATTO al 100%: solo i dati personali umani cambiano.
2. Il NOME DEL CANE e la RAZZA si CONSERVANO (non identificano una persona).
3. I nomi di autori scientifici citati in bibliografia si CONSERVANO (sono citazioni,
   non dati personali del caso).
4. Se non ci sono dati personali, restituisci il testo identico.
5. Restituisci SOLO il testo risultante, senza commenti né premesse."""


def _anonymize_segment(segment: str) -> str:
    settings = get_settings()
    response = create_message_resilient(
        model=settings.clinical_model,
        fallback_model=settings.clinical_fallback_model,
        max_tokens=ANON_MAX_TOKENS,
        system=[{"type": "text", "text": _ANON_SYSTEM_PROMPT}],
        messages=[{"role": "user", "content": segment}],
    )
    if getattr(response, "stop_reason", None) == "max_tokens":
        raise AnonymizationError("Anonymization output truncated (max_tokens).")
    out = ""
    for block in response.content:
        if block.type == "text":
            out += block.text
    out = out.strip()
    if not out:
        raise AnonymizationError("Anonymization returned empty text.")
    # Sanidad: si el LLM devolvió algo drásticamente más corto, algo se perdió →
    # fail-closed (mejor abortar que indexar un caso mutilado o sin anonimizar).
    if len(out) < len(segment) * 0.5:
        raise AnonymizationError(
            f"Anonymized segment suspiciously short ({len(out)} vs {len(segment)} chars)."
        )
    return out


def anonymize_case_text(text: str) -> str:
    """Anonimiza el texto completo de un caso. Lanza AnonymizationError si no puede
    garantizarse la anonimización (fail-closed: la ingesta aborta)."""
    text = _regex_scrub(text)

    words = text.split()
    segments = [
        " ".join(words[i : i + ANON_SEGMENT_WORDS])
        for i in range(0, len(words), ANON_SEGMENT_WORDS)
    ]

    try:
        anonymized = [_anonymize_segment(s) for s in segments]
    except AnonymizationError:
        raise
    except Exception as e:
        raise AnonymizationError(f"Anonymization LLM call failed: {e}") from e

    # Backstop determinista también sobre la salida del LLM.
    return _regex_scrub(" ".join(anonymized))


# ── Ingesta pública ──────────────────────────────────────────────────────────────

def ingest_cognitive_pdf(pdf_bytes: bytes, filename: str) -> int:
    """
    Ingesta un PDF al corpus cognitivista (RAG B). Returns chunks indexados.
    Reemplaza chunks previos del mismo filename. Fail-closed en anonimización.
    """
    settings = get_settings()
    ensure_cognitive_collection()
    qdrant = get_qdrant_client()
    collection = settings.qdrant_collection_cognitive

    # Reemplazo idempotente por filename (mismo patrón que la RAG A)
    qdrant.delete(
        collection_name=collection,
        points_selector=FilterSelector(
            filter=Filter(
                must=[FieldCondition(key="filename", match=MatchValue(value=filename))]
            )
        ),
        wait=True,
    )

    pages = _extract_pages(pdf_bytes)
    if not pages:
        return 0

    # ANONIMIZACIÓN antes de trocear: el texto completo del caso pasa por las dos
    # capas. Si falla → excepción → el job de ingesta termina en error y NADA se indexa.
    full_text = "\n\n".join(p["text"] for p in pages)
    clean_text = anonymize_case_text(full_text)

    # Un PDF = un caso. Chunking sobre el texto ya anonimizado.
    clean_pages = [{"page": 1, "text": clean_text}]
    chunks = _split_into_chunks(clean_pages, CASE_CHUNK_SIZE, CASE_CHUNK_OVERLAP)
    if not chunks:
        return 0

    texts = [c["text"] for c in chunks]
    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        all_embeddings.extend(embed_documents(texts[i : i + EMBED_BATCH_SIZE]))

    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=embedding,
            payload={
                "filename": filename,
                "case_id": filename,          # 1 PDF = 1 caso
                "corpus": "cognitive_it",     # marca inequívoca de RAG B
                "chunk_index": chunk["chunk_index"],
                "page_start": chunk["page_start"],
                "page_end": chunk["page_end"],
                "text": chunk["text"],
            },
        )
        for chunk, embedding in zip(chunks, all_embeddings)
    ]

    for i in range(0, len(points), UPSERT_BATCH_SIZE):
        _upsert_with_retry(qdrant, collection, points[i : i + UPSERT_BATCH_SIZE])

    return len(points)


def list_cognitive_documents() -> list[dict]:
    """Lista de documentos indexados en la RAG B (filename + chunk_count)."""
    settings = get_settings()
    qdrant = get_qdrant_client()

    # Si la collection aún no existe (RAG B vacía), lista vacía — no error.
    existing = {c.name for c in qdrant.get_collections().collections}
    if settings.qdrant_collection_cognitive not in existing:
        return []

    counts: dict[str, int] = {}
    offset = None
    while True:
        result, next_offset = qdrant.scroll(
            collection_name=settings.qdrant_collection_cognitive,
            with_payload=True,
            with_vectors=False,
            limit=500,
            offset=offset,
        )
        for point in result:
            fname = point.payload.get("filename", "unknown")
            counts[fname] = counts.get(fname, 0) + 1
        if next_offset is None:
            break
        offset = next_offset

    return [{"filename": k, "chunk_count": v} for k, v in sorted(counts.items())]
