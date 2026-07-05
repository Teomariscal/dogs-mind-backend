from functools import lru_cache
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PayloadSchemaType
from app.config import get_settings


@lru_cache
def get_qdrant_client() -> QdrantClient:
    settings = get_settings()
    kwargs = dict(url=settings.qdrant_url, timeout=120)
    if settings.qdrant_api_key:
        kwargs["api_key"] = settings.qdrant_api_key
    return QdrantClient(**kwargs)


def _ensure_named_collection(collection_name: str) -> None:
    """
    Create a collection (and its filename keyword index) if needed.
    Safe to call multiple times — fully idempotent.
    """
    settings = get_settings()
    client = get_qdrant_client()

    existing = {c.name for c in client.get_collections().collections}
    if collection_name not in existing:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=settings.embedding_dim,
                distance=Distance.COSINE,
            ),
        )

    # Create keyword index on 'filename' so we can filter/delete by it.
    # Qdrant ignores the call if the index already exists.
    try:
        client.create_payload_index(
            collection_name=collection_name,
            field_name="filename",
            field_schema=PayloadSchemaType.KEYWORD,
        )
    except Exception:
        pass  # index already exists — safe to ignore


def ensure_collection() -> None:
    """RAG A (dogs_mind_knowledge): create collection + index if needed."""
    _ensure_named_collection(get_settings().qdrant_collection)


def ensure_cognitive_collection() -> None:
    """RAG B (corpus cognitivista IT): create collection + index if needed.
    Collection separada — ver nota en config.py: NUNCA mezclar con la RAG A."""
    _ensure_named_collection(get_settings().qdrant_collection_cognitive)
