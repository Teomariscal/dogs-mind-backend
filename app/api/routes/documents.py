from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks
from app.models.documents import DocumentUploadResponse, DocumentListResponse, DocumentListItem
from app.services.document_ingestion import ingest_pdf, list_indexed_documents

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
