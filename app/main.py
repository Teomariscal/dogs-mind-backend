import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api.routes import health, analysis, avatar, documents, intervention

# Path to the frontend HTML — override via FRONTEND_HTML env var
FRONTEND_HTML = os.environ.get(
    "FRONTEND_HTML",
    os.path.join(os.path.dirname(__file__), "..", "frontend", "teo-mariscal-v3.html"),
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure Qdrant collection exists (only when keys are available)
    from app.config import get_settings
    from app.core.qdrant_client import ensure_collection
    try:
        ensure_collection()
    except Exception as e:
        print(f"[startup] Could not initialise Qdrant collection: {e}")
    yield


app = FastAPI(
    title="Dogs Mind — Backend API",
    description=(
        "Clinical canine behavioral analysis powered by Claude Sonnet 4.6 "
        "(RAG + prompt caching) and a conversational avatar powered by Claude Haiku 4.5."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(analysis.router)
app.include_router(intervention.router)
app.include_router(avatar.router)
app.include_router(documents.router)


@app.get("/", include_in_schema=False)
def serve_frontend():
    """Serve the Dogs Mind single-page app."""
    if os.path.isfile(FRONTEND_HTML):
        return FileResponse(FRONTEND_HTML, media_type="text/html")
    return {"error": f"Frontend not found at {FRONTEND_HTML}. Set FRONTEND_HTML env var."}
