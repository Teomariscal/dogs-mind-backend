from functools import lru_cache
import voyageai
from app.config import get_settings


@lru_cache
def get_voyage_client() -> voyageai.Client:
    settings = get_settings()
    return voyageai.Client(api_key=settings.voyage_api_key)


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed a batch of document chunks (ingestion)."""
    settings = get_settings()
    client = get_voyage_client()
    result = client.embed(texts, model=settings.embedding_model, input_type="document")
    return result.embeddings


def embed_query(text: str) -> list[float]:
    """Embed a single query string (retrieval)."""
    settings = get_settings()
    client = get_voyage_client()
    result = client.embed([text], model=settings.embedding_model, input_type="query")
    return result.embeddings[0]
