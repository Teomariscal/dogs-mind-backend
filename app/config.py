from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_ignore_empty=True,   # shell empty vars don't override .env values
    )

    # Anthropic
    anthropic_api_key: str

    # Voyage AI
    voyage_api_key: str

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "dogs_mind_knowledge"

    # Models
    clinical_model: str = "claude-sonnet-4-6"
    avatar_model: str = "claude-haiku-4-5"
    embedding_model: str = "voyage-3-large"

    # RAG
    rag_top_k: int = 6
    chunk_size: int = 600      # words
    chunk_overlap: int = 80    # words

    # Embedding vector dimension for voyage-3-large
    embedding_dim: int = 1024

    # App
    app_env: str = "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
