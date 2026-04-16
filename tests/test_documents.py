"""
Integration tests for the /documents endpoints.
Run with: pytest tests/test_documents.py -v
"""

import io
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _minimal_pdf_bytes() -> bytes:
    """Create a minimal valid PDF in memory (no external file needed)."""
    content = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj
4 0 obj<</Length 44>>stream
BT /F1 12 Tf 100 700 Td (Test dog behavior text.) Tj ET
endstream
endobj
5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000274 00000 n
0000000370 00000 n
trailer<</Size 6/Root 1 0 R>>
startxref
441
%%EOF"""
    return content


def test_upload_pdf():
    pdf = _minimal_pdf_bytes()
    response = client.post(
        "/documents/upload",
        files={"file": ("test_behavior.pdf", io.BytesIO(pdf), "application/pdf")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "test_behavior.pdf"
    assert "chunks_indexed" in data


def test_upload_non_pdf_rejected():
    response = client.post(
        "/documents/upload",
        files={"file": ("data.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code == 415


def test_list_documents():
    response = client.get("/documents")
    assert response.status_code == 200
    data = response.json()
    assert "documents" in data
    assert "total_chunks" in data


def test_delete_document():
    response = client.delete("/documents/test_behavior.pdf")
    assert response.status_code == 200
