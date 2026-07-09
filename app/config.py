from functools import lru_cache
from pydantic import field_validator, Field, AliasChoices
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
    # RAG B — corpus cognitivista italiano (casos reales + bibliografía cognitiva).
    # Collection FÍSICAMENTE SEPARADA de dogs_mind_knowledge: es corpus de EXPRESIÓN
    # (estilo/terminología para la 2ª pasada), NO fuente diagnóstica. Solo se consulta
    # en la vía cognitivista italiana (lang=='it' + stance=='cognitive'). NUNCA
    # ingestar material cognitivista en dogs_mind_knowledge (contaminaría es/en/it).
    qdrant_collection_cognitive: str = "dogs_mind_cognitive_it"
    # EJE de la RAG B: los documentos cuyo filename contenga alguno de estos patrones
    # (case-insensitive) son la CAPA NÚCLEO (obra "Vivir con el perro" = columna
    # vertebral); el resto (casos, papers, glosario) es COMPLEMENTO de segunda capa.
    # La recuperación cognitiva prioriza el núcleo y rellena con complemento.
    cognitive_core_patterns: list[str] = [
        "vivir con el perro",
        "vivere con il cane",
        "enfoque cognitivo",
        "approccio cognitivo",
    ]
    # Cuántos de los top_k se reservan al núcleo (si hay hits del eje sobre umbral).
    cognitive_core_quota: int = 4

    @field_validator("qdrant_url", "anthropic_api_key", "voyage_api_key", "qdrant_api_key", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip() if isinstance(v, str) else v

    # Models
    clinical_model: str = "claude-sonnet-4-6"
    # Fallback si el modelo clínico (Sonnet) está sobrecargado (529): sube a Opus
    # 4.8 (capacidad aparte + más capaz). Solo se usa en ese caso excepcional.
    clinical_fallback_model: str = "claude-opus-4-8"
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

    # Versión italiana — guiño zooantropológico (SIUA/Marchesini).
    # SOLO se activa con la env `IT_ZOO_VENEER=true` Y lang=='it' Y cuenta professional.
    # Arranca APAGADO: mientras esté en false el comportamiento es idéntico al actual.
    # (Acepta también IT_ZOO_VENEER_ENABLED por compatibilidad.)
    it_zoo_veneer_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("IT_ZOO_VENEER", "IT_ZOO_VENEER_ENABLED"),
    )

    # Vía COGNITIVISTA italiana (Deploy 2). Motor ABA intacto (pasada 1, invisible) +
    # pasada 2 que reescribe al marco cognitivo con la RAG B, con gate de lista negra.
    # Puertas: flag ON · lang=='it' · cuenta professional · stance=='cognitive'.
    # ACTIVO por defecto (founder 2026-07-08, para testeo de Odette). Solo afecta a la
    # versión italiana profesional cuando el veterinario pulsa "Analisi Cognitivista";
    # es/en y la vía conductual NO cambian. Kill-switch: IT_COGNITIVE=false en Railway.
    it_cognitive_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("IT_COGNITIVE", "IT_COGNITIVE_ENABLED"),
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
