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


def ensure_collection() -> None:
    """
    Create the knowledge collection and filename keyword index if needed.
    Safe to call multiple times — fully idempotent.
    """
    settings = get_settings()
    client = get_qdrant_client()

    existing = {c.name for c in client.get_collections().collections}
    if settings.qdrant_collection not in existing:
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(
                size=settings.embedding_dim,
                distance=Distance.COSINE,
            ),
        )

    # Create keyword index on 'filename' so we can filter/delete by it.
    # Qdrant ignores the call if the index already exists.
    try:
        client.create_payload_index(
            collection_name=settings.qdrant_collection,
            field_name="filename",
            field_schema=PayloadSchemaType.KEYWORD,
        )
    except Exception:
        pass  # index already exists — safe to ignore
