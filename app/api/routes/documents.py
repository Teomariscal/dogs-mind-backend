from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks, Form
from app.models.documents import DocumentUploadResponse, DocumentListResponse, DocumentListItem
from app.services.document_ingestion import ingest_pdf, list_indexed_documents
from app.services.cognitive_ingestion import ingest_cognitive_pdf, list_cognitive_documents

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_CONTENT_TYPES = {"application/pdf"}
MAX_FILE_SIZE_MB = 100

# Simple in-memory job status (resets on server restart)
_jobs: dict[str, dict] = {}


def _run_ingestion(job_id: str, pdf_bytes: bytes, filename: str) -> None:
    """Background task: embed and index the PDF."""
    try:
        chunks = ingest_pdf(pdf_bytes, filename)
        _jobs[job_id] = {"status": "done", "filename": filename, "chunks_indexed": chunks}
    except Exception as e:
        _jobs[job_id] = {"status": "error", "filename": filename, "error": str(e)}


@router.post("/upload", status_code=202)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """
    Upload a PDF and index it into Qdrant in the background.

    Returns 202 immediately. Poll GET /documents/jobs/{job_id} for status.
    """
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Only PDF files are accepted. Got: {file.content_type}",
        )

    pdf_bytes = await file.read()
    size_mb = len(pdf_bytes) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {MAX_FILE_SIZE_MB} MB limit ({size_mb:.1f} MB).",
        )

    import uuid
    job_id = str(uuid.uuid4())
    filename = file.filename or "unknown.pdf"
    _jobs[job_id] = {"status": "processing", "filename": filename}

    background_tasks.add_task(_run_ingestion, job_id, pdf_bytes, filename)

    return {
        "job_id": job_id,
        "filename": filename,
        "status": "processing",
        "message": f"Indexing '{filename}' in background. Poll /documents/jobs/{job_id} for status.",
    }


@router.get("/jobs/{job_id}")
def get_job_status(job_id: str):
    """Check the status of a PDF ingestion job."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@router.get("", response_model=DocumentListResponse)
def list_documents():
    """List all documents currently indexed in the knowledge base."""
    try:
        docs = list_indexed_documents()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    items = [DocumentListItem(**d) for d in docs]
    total = sum(d.chunk_count for d in items)
    return DocumentListResponse(documents=items, total_chunks=total)


# ── RAG B: corpus cognitivista italiano (collection dogs_mind_cognitive_it) ─────
# Slot SEPARADO del principal: destino cableado en fijo a la collection B para que
# sea imposible contaminar dogs_mind_knowledge. La ingesta B lleva anonimización
# GDPR fail-closed (casos reales) + chunking por caso. Ver cognitive_ingestion.py.

def _run_cognitive_ingestion(job_id: str, pdf_bytes: bytes, filename: str, anonymize: bool) -> None:
    """Background task: (anonimizar si es caso +) indexar en la RAG B."""
    try:
        chunks = ingest_cognitive_pdf(pdf_bytes, filename, anonymize=anonymize)
        _jobs[job_id] = {"status": "done", "filename": filename, "chunks_indexed": chunks}
    except Exception as e:
        _jobs[job_id] = {"status": "error", "filename": filename, "error": str(e)}


@router.post("/cognitive/upload", status_code=202)
async def upload_cognitive_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    doc_type: str = Form("case"),
):
    """
    Upload a PDF to the ITALIAN COGNITIVE corpus (RAG B).

    doc_type='case' (default) → anonimiza (datos de cliente) antes de indexar.
    doc_type='book'           → libro/bibliografía: indexa directo, sin anonimizar.

    Returns 202 immediately. Poll GET /documents/jobs/{job_id} for status.
    """
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Only PDF files are accepted. Got: {file.content_type}",
        )

    pdf_bytes = await file.read()
    size_mb = len(pdf_bytes) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {MAX_FILE_SIZE_MB} MB limit ({size_mb:.1f} MB).",
        )

    import uuid
    job_id = str(uuid.uuid4())
    filename = file.filename or "unknown.pdf"
    anonymize = (doc_type or "case").strip().lower() != "book"
    _jobs[job_id] = {"status": "processing", "filename": filename}

    background_tasks.add_task(_run_cognitive_ingestion, job_id, pdf_bytes, filename, anonymize)

    action = "Anonymizing + indexing" if anonymize else "Indexing (no anonymization)"
    return {
        "job_id": job_id,
        "filename": filename,
        "status": "processing",
        "message": f"{action} '{filename}' into cognitive corpus (RAG B).",
    }


@router.get("/cognitive", response_model=DocumentListResponse)
def list_cognitive():
    """List documents indexed in the cognitive corpus (RAG B)."""
    try:
        docs = list_cognitive_documents()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    items = [DocumentListItem(**d) for d in docs]
    total = sum(d.chunk_count for d in items)
    return DocumentListResponse(documents=items, total_chunks=total)


@router.delete("/cognitive/{filename}")
def delete_cognitive_document(filename: str):
    """Remove all chunks for a filename from the cognitive corpus (RAG B)."""
    from app.config import get_settings
    from app.core.qdrant_client import get_qdrant_client
    from qdrant_client.models import FilterSelector, Filter, FieldCondition, MatchValue

    settings = get_settings()
    qdrant = get_qdrant_client()
    try:
        qdrant.delete(
            collection_name=settings.qdrant_collection_cognitive,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[FieldCondition(key="filename", match=MatchValue(value=filename))]
                )
            ),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"message": f"Deleted all chunks for '{filename}' from cognitive corpus."}


@router.delete("/{filename}")
def delete_document(filename: str):
    """Remove all chunks for a given filename from the knowledge base."""
    from app.config import get_settings
    from app.core.qdrant_client import get_qdrant_client
    from qdrant_client.models import FilterSelector, Filter, FieldCondition, MatchValue

    settings = get_settings()
    qdrant = get_qdrant_client()
    try:
        qdrant.delete(
            collection_name=settings.qdrant_collection,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[FieldCondition(key="filename", match=MatchValue(value=filename))]
                )
            ),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"message": f"Deleted all chunks for '{filename}'."}
