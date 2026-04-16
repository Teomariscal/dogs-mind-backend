from fastapi import APIRouter
from app.core.qdrant_client import get_qdrant_client
from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    settings = get_settings()
    qdrant_ok = False
    try:
        get_qdrant_client().get_collections()
        qdrant_ok = True
    except Exception:
        pass

    return {
        "status": "ok",
        "env": settings.app_env,
        "clinical_model": settings.clinical_model,
        "avatar_model": settings.avatar_model,
        "embedding_model": settings.embedding_model,
        "qdrant": "connected" if qdrant_ok else "unreachable",
    }
