from pydantic import BaseModel, Field


class DocumentUploadResponse(BaseModel):
    filename: str
    chunks_indexed: int
    message: str


class DocumentListItem(BaseModel):
    filename: str
    chunk_count: int


class DocumentListResponse(BaseModel):
    documents: list[DocumentListItem]
    total_chunks: int
