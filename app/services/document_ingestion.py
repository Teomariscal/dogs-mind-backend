"""
PDF ingestion pipeline:
  1. Parse PDF pages with pypdf
  2. Split into overlapping word-based chunks
  3. Embed chunks with Voyage AI (voyage-3-large) in small batches
  4. Upsert into Qdrant in small batches with wait=False + retry
"""

import time
import uuid
from io import BytesIO

from pypdf import PdfReader
from qdrant_client.models import PointStruct, FilterSelector, Filter, FieldCondition, MatchValue

from app.config import get_settings
from app.core.qdrant_client import get_qdrant_client, ensure_collection
from app.core.voyage_client import embed_documents

# Voyage AI: max ~120 000 tokens per batch.
# voyage-3-large tokenises ~1.3 tokens/word.
# chunk_size=600 words → ~780 tokens/chunk → safe batch = 50 chunks (~39 000 tok)
EMBED_BATCH_SIZE = 50

# Qdrant Cloud free tier struggles with large single writes → keep small
UPSERT_BATCH_SIZE = 50

# Retry config for Qdrant timeouts
MAX_RETRIES = 4
RETRY_BACKOFF = 2.0   # seconds (doubles each retry)


# ── helpers ──────────────────────────────────────────────────────────────────

def _extract_pages(pdf_bytes: bytes) -> list[dict]:
    """Return [{page: int, text: str}] for every non-empty page."""
    reader = PdfReader(BytesIO(pdf_bytes))
    pages = []
    for i, page in enumerate(reader.pages):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append({"page": i + 1, "text": text})
    return pages


def _split_into_chunks(pages: list[dict], chunk_size: int, overlap: int) -> list[dict]:
    """
    Word-based sliding-window chunking across all pages.
    Guards against overlap >= chunk_size to prevent infinite loop.
    """
    step = max(chunk_size - overlap, 1)

    word_source: list[tuple[str, int]] = []
    for p in pages:
        for w in p["text"].split():
            word_source.append((w, p["page"]))

    if not word_source:
        return []

    chunks = []
    idx = 0
    chunk_index = 0
    total = len(word_source)

    while idx < total:
        end = min(idx + chunk_size, total)
        sl = word_source[idx:end]
        chunks.append({
            "chunk_index": chunk_index,
            "text": " ".join(w for w, _ in sl),
            "page_start": sl[0][1],
            "page_end": sl[-1][1],
        })
        chunk_index += 1
        idx += step

    return chunks


def _upsert_with_retry(qdrant, collection: str, points: list[PointStruct]) -> None:
    """Upsert a batch with exponential-backoff retry on timeout errors."""
    delay = RETRY_BACKOFF
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            qdrant.upsert(
                collection_name=collection,
                points=points,
                wait=False,   # don't block until Qdrant finishes indexing
            )
            return
        except Exception as e:
            msg = str(e).lower()
            is_timeout = "timed out" in msg or "timeout" in msg or "deadline" in msg
            if is_timeout and attempt < MAX_RETRIES:
                time.sleep(delay)
                delay *= 2
                continue
            raise


# ── public API ────────────────────────────────────────────────────────────────

def ingest_pdf(pdf_bytes: bytes, filename: str) -> int:
    """
    Full ingestion pipeline. Returns the number of chunks indexed.
    Replaces any previous chunks from the same filename.
    """
    settings = get_settings()
    ensure_collection()
    qdrant = get_qdrant_client()

    # Delete stale chunks for this file (uses the keyword index we created)
    qdrant.delete(
        collection_name=settings.qdrant_collection,
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

    chunks = _split_into_chunks(pages, settings.chunk_size, settings.chunk_overlap)
    if not chunks:
        return 0

    texts = [c["text"] for c in chunks]

    # Embed in small batches to stay under Voyage AI token limit
    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        batch_embeddings = embed_documents(texts[i : i + EMBED_BATCH_SIZE])
        all_embeddings.extend(batch_embeddings)

    # Build Qdrant point structs
    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=embedding,
            payload={
                "filename": filename,
                "chunk_index": chunk["chunk_index"],
                "page_start": chunk["page_start"],
                "page_end": chunk["page_end"],
                "text": chunk["text"],
            },
        )
        for chunk, embedding in zip(chunks, all_embeddings)
    ]

    # Upsert in small batches with retry
    for i in range(0, len(points), UPSERT_BATCH_SIZE):
        _upsert_with_retry(qdrant, settings.qdrant_collection, points[i : i + UPSERT_BATCH_SIZE])

    return len(points)


def list_indexed_documents() -> list[dict]:
    """Return aggregated list of indexed filenames and their chunk counts."""
    settings = get_settings()
    qdrant = get_qdrant_client()

    counts: dict[str, int] = {}
    offset = None
    while True:
        result, next_offset = qdrant.scroll(
            collection_name=settings.qdrant_collection,
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
