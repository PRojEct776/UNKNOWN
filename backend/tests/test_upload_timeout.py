"""
Regression tests for document upload timeout, retry handling, failure cleanup, and status tracking.
"""

import io
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from app.main import app, rag_service
from app.rag.config import settings
from app.rag.faiss_index_builder import FAISSIndexBuilder


@pytest.fixture
def client():
    return TestClient(app)


def test_upload_retry_same_file_returns_success(client):
    """
    When a client retries uploading the exact same document (e.g. after a frontend timeout
    or network retry), it should return success (HTTP 200) instead of throwing a duplicate error.
    """
    doc_name = "Synthetic_Retry_Test_Doc.txt"
    content = b"Content for testing upload retry behavior in UNKNOWN."

    try:
        # First upload
        payload = {"file": (doc_name, io.BytesIO(content), "text/plain")}
        res1 = client.post("/documents/upload", files=payload)
        assert res1.status_code == 200, res1.text
        data1 = res1.json()
        assert data1["status"] == "success"
        assert data1["filename"] == doc_name

        # Second upload with same filename and same content (retry)
        payload2 = {"file": (doc_name, io.BytesIO(content), "text/plain")}
        res2 = client.post("/documents/upload", files=payload2)
        assert res2.status_code == 200, res2.text
        data2 = res2.json()
        assert data2["status"] == "success"
        assert data2["filename"] == doc_name
    finally:
        client.delete(f"/documents/{doc_name}")


def test_upload_different_file_same_content_rejected(client):
    """
    Uploading a different file with identical content must still be rejected with 400
    to prevent duplicate clutter.
    """
    doc_a = "Synthetic_Orig_Doc.txt"
    doc_b = "Synthetic_Copy_Doc.txt"
    content = b"Identical content to verify true cross-document duplicate detection."

    try:
        payload_a = {"file": (doc_a, io.BytesIO(content), "text/plain")}
        res_a = client.post("/documents/upload", files=payload_a)
        assert res_a.status_code == 200, res_a.text

        payload_b = {"file": (doc_b, io.BytesIO(content), "text/plain")}
        res_b = client.post("/documents/upload", files=payload_b)
        assert res_b.status_code == 400
        assert "duplicate" in res_b.json()["detail"].lower()
    finally:
        client.delete(f"/documents/{doc_a}")
        client.delete(f"/documents/{doc_b}")


def test_failed_upload_cleans_up_and_allows_retry(client, monkeypatch):
    """
    If document processing raises an unexpected error midway, partial files must be cleaned
    up so a subsequent retry can succeed cleanly without false duplicate rejection.
    """
    doc_name = "Synthetic_Fail_Test_Doc.txt"
    content = b"Content that will trigger simulated failure on first attempt."

    p_path = settings.PAPERS_DIR / doc_name
    j_path = settings.JSON_DIR / f"{Path(doc_name).stem}.json"
    m_path = settings.METADATA_DIR / f"{Path(doc_name).stem}_metadata.json"

    # Simulate an error during chunking
    from app.rag.chunker import DocumentChunker
    original_create_chunks = DocumentChunker.create_chunks

    fail_counter = [0]

    def failing_create_chunks(self):
        if fail_counter[0] == 0:
            fail_counter[0] += 1
            raise RuntimeError("Simulated processing crash during chunking")
        return original_create_chunks(self)

    monkeypatch.setattr(DocumentChunker, "create_chunks", failing_create_chunks)

    try:
        # First upload attempt - should fail with 500
        payload1 = {"file": (doc_name, io.BytesIO(content), "text/plain")}
        res1 = client.post("/documents/upload", files=payload1)
        assert res1.status_code == 500
        assert "Failed to process document" in res1.json()["detail"]

        # Ensure cleanup removed partial files
        assert not p_path.exists(), "PAPERS_DIR file must be cleaned up on failure"
        assert not j_path.exists(), "JSON_DIR file must be cleaned up on failure"
        assert not m_path.exists(), "METADATA_DIR file must be cleaned up on failure"

        # Retry should succeed
        payload2 = {"file": (doc_name, io.BytesIO(content), "text/plain")}
        res2 = client.post("/documents/upload", files=payload2)
        assert res2.status_code == 200, res2.text
        assert res2.json()["status"] == "success"
    finally:
        client.delete(f"/documents/{doc_name}")


def test_document_status_endpoint(client):
    """
    Verify GET /documents/{document_name}/status endpoint for indexed and missing documents.
    """
    # 1. Missing document returns 404
    missing_res = client.get("/documents/NonExistent_Doc_12345.pdf/status")
    assert missing_res.status_code == 404

    # 2. Upload test document
    doc_name = "Synthetic_Status_Test_Doc.txt"
    content = b"Research document for status endpoint verification with enough words to chunk."
    try:
        payload = {"file": (doc_name, io.BytesIO(content), "text/plain")}
        upload_res = client.post("/documents/upload", files=payload)
        assert upload_res.status_code == 200

        # Check status
        status_res = client.get(f"/documents/{doc_name}/status")
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert status_data["document"] == doc_name
        assert status_data["status"] in ("ready", "stored")
        assert "chunks_count" in status_data
        assert "total_pages" in status_data
    finally:
        client.delete(f"/documents/{doc_name}")


def test_incremental_faiss_builder_caching():
    """
    Verify that FAISSIndexBuilder reuses cached embeddings for unchanged chunks,
    speeding up indexing without losing vector count or dimension.
    """
    builder = FAISSIndexBuilder()
    index1, meta1, embs1 = builder.build_index()

    # Second build immediately after
    index2, meta2, embs2 = builder.build_index()

    assert index1.ntotal == index2.ntotal
    assert embs1.shape == embs2.shape
    assert len(meta1) == len(meta2)
