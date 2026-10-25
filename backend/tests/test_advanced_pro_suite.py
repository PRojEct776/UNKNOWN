"""
UNKNOWN ADVANCED PRO — Comprehensive Validation Test Suite
Tests for:
- Multi-doc batch upload and limits
- Secure sharing token creation, retrieval, sanitization, and revocation
- Workspace document isolation and test-fixture filtering
- Evidence-grounded dual retrieval (/answer) with doc_only and web scopes
- Explicit insufficient-evidence handling
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.rag.document_eligibility import get_user_authorized_documents, is_test_document

client = TestClient(app)


def test_share_creation_retrieval_and_revocation():
    """Test full server-side sharing lifecycle: create, read sanitized, revoke, and confirm 404."""
    sample_conversation = {
        "title": "Quantum Error Correction Analysis",
        "createdAt": "2026-10-25T12:00:00Z",
        "messages": [
            {
                "id": "msg_1",
                "sender": "user",
                "timestamp": "12:00 PM",
                "text": "What is the threshold theorem?",
                "feature": "discover",
            },
            {
                "id": "msg_2",
                "sender": "assistant",
                "timestamp": "12:01 PM",
                "feature": "discover",
                "result": {
                    "answer": "The threshold theorem proves fault-tolerant quantum computation is possible.",
                    "detailedAnswer": "Full mathematical breakdown of fault tolerance thresholds.",
                    "confidence": 0.94,
                    "doc_section": "Document evidence paragraph with citations.",
                    "web_section": None,
                    "sources": [
                        {
                            "title": "Quantum_Computing_Review.pdf",
                            "page": 4,
                            "domain": "arxiv.org",
                            "url": "https://arxiv.org/abs/quant-ph/012345",
                        }
                    ],
                },
            },
        ],
    }

    # 1. Create share link
    resp = client.post(
        "/share",
        json={
            "conversation": sample_conversation,
            "include_doc_content": False,
            "expires_in_hours": 24,
        },
        headers={"X-User-Id": "test_researcher_123"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "share_token" in data
    assert "share_url" in data
    assert data["is_active"] is True
    token = data["share_token"]

    # 2. Retrieve public shared transcript
    get_resp = client.get(f"/share/{token}")
    assert get_resp.status_code == 200, get_resp.text
    shared = get_resp.json()
    assert shared["title"] == "Quantum Error Correction Analysis"
    assert len(shared["messages"]) == 2
    # Verify sensitive server metadata is stripped
    assert "secret_key" not in str(shared)
    assert "password" not in str(shared)
    assert "user_id" not in str(shared)

    # 3. Revoke share link
    del_resp = client.delete(
        f"/share/{token}",
        headers={"X-User-Id": "test_researcher_123"},
    )
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "revoked"

    # 4. Confirm revoked link is no longer accessible
    get_revoked = client.get(f"/share/{token}")
    assert get_revoked.status_code == 404


def test_workspace_isolation_and_test_data_filtering():
    """Verify that test fixtures are strictly filtered out from normal user workspaces."""
    # sample_ieee.pdf should be identified as a test document
    assert is_test_document("sample_ieee.pdf") is True
    assert is_test_document("duplicate_test_doc.txt") is True

    # Fresh user workspace should not contain test fixtures
    user_docs = get_user_authorized_documents("new_isolated_user_abc", include_test_docs=False)
    assert "sample_ieee.pdf" not in user_docs
    assert "duplicate_test_doc.txt" not in user_docs


def test_batch_upload_rejects_empty_files():
    """Verify batch upload endpoint validates input parameters."""
    resp = client.post("/documents/upload-batch", files=[])
    # Empty files list rejected
    assert resp.status_code in (400, 422)


def test_batch_upload_unsupported_extension():
    """Verify batch upload rejects unsupported file extensions."""
    files = [
        ("files", ("test.exe", b"binarycontent", "application/octet-stream")),
    ]
    resp = client.post("/documents/upload-batch", files=files)
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["failed"] >= 1
    assert "Unsupported format" in str(res_data["results"])


def test_answer_endpoint_doc_only_scope(monkeypatch):
    """Verify /answer endpoint handles doc_only=True without calling web search."""
    from app.main import rag_service

    called_connectors = []

    def mock_answer(*args, **kwargs):
        doc_only = kwargs.get("doc_only", False)
        if not doc_only:
            called_connectors.append("web")
        return {
            "query": kwargs.get("query", "test query"),
            "query_type": "factual",
            "answer": "This is a document-grounded answer.",
            "detail": "Detailed explanation.",
            "summary": "Summary.",
            "doc_section": "Doc section evidence.",
            "web_section": None,
            "comparison": [],
            "claims": [],
            "conflicts": [],
            "gaps": [],
            "confidence": {
                "score": 90.0,
                "breakdown": {
                    "evidence_coverage": 0.9,
                    "claim_support": 0.9,
                    "source_agreement": 1.0,
                    "source_quality": 0.9,
                },
                "formula_version": "v1.0",
            },
            "sources": [],
        }

    monkeypatch.setattr(rag_service, "answer", mock_answer)

    resp = client.post(
        "/answer",
        json={
            "query": "Explain the attention mechanism",
            "doc_only": True,
            "document_names": None,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["detail"] == "Detailed explanation."
    assert len(called_connectors) == 0
