import logging
from fastapi import APIRouter, Request
from app.core.qdrant_client import get_qdrant_client
from app.config import get_settings

router = APIRouter(tags=["health"])
_log = logging.getLogger("frontend.errors")


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


@router.post("/health/log-error")
async def log_frontend_error(request: Request):
    """Receive and log JS errors from the frontend."""
    try:
        body = await request.json()
        _log.error(
            "[FE-ERROR] type=%s msg=%s file=%s line=%s ua=%s ts=%s",
            body.get("type", "?"),
            body.get("msg", "?")[:200],
            body.get("file", "?"),
            body.get("line", "?"),
            body.get("ua", "?")[:80],
            body.get("ts", "?"),
        )
    except Exception:
        pass
    return {"ok": True}
