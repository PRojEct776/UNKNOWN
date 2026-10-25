import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app, rag_service

client = TestClient(app)


# ---- helpers for error-path tests ----

def _make_rag_error(message: str, kind: str) -> RuntimeError:
    """Create a RuntimeError with an ``error_kind`` attribute.

    This mirrors what ``rag_service.query`` raises internally when the
    LLM provider returns an error response (see rag_service.py L519-523).
    """
    error = RuntimeError(message)
    error.error_kind = kind  # type: ignore[attr-defined]
    return error


# ---- tests ----


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_query_rejects_empty_query():
    response = client.post("/query", json={"query": ""})

    assert response.status_code == 422


def test_query_rate_limit_error():
    with patch.object(
        rag_service,
        "query",
        side_effect=_make_rag_error("Provider rate limited", "rate_limit"),
    ):
        response = client.post(
            "/query",
            json={"query": "What problem does the framework solve?"},
        )

    assert response.status_code == 429


def test_query_transient_error():
    with patch.object(
        rag_service,
        "query",
        side_effect=_make_rag_error("Provider temporarily unavailable", "transient"),
    ):
        response = client.post(
            "/query",
            json={"query": "What problem does the framework solve?"},
        )

    assert response.status_code == 503


def test_query_invalid_request_error():
    with patch.object(
        rag_service,
        "query",
        side_effect=_make_rag_error("Invalid provider request", "invalid_request"),
    ):
        response = client.post(
            "/query",
            json={"query": "What problem does the framework solve?"},
        )

    assert response.status_code == 400


def test_query_fatal_error():
    with patch.object(
        rag_service,
        "query",
        side_effect=_make_rag_error("Provider rejected request", "fatal"),
    ):
        response = client.post(
            "/query",
            json={"query": "What problem does the framework solve?"},
        )

    assert response.status_code == 502


def test_query_rejects_oversized_query():
    response = client.post(
        "/query",
        json={"query": "a" * 1001},
    )

    assert response.status_code == 422


def test_query_accepts_max_length_query():
    with patch.object(
        rag_service,
        "query",
        side_effect=_make_rag_error("Provider rate limited", "rate_limit"),
    ):
        response = client.post(
            "/query",
            json={"query": "a" * 1000},
        )

    assert response.status_code == 429


def test_adaptive_answer_comparison():
    response = client.post(
        "/adaptive-answer",
        json={"query": "Compare BM25 and FAISS"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "query": "Compare BM25 and FAISS",
        "mode": "COMPARATIVE",
    }


def test_adaptive_answer_technical():
    response = client.post(
        "/adaptive-answer",
        json={
            "query": "Explain the architecture and implementation of a REST API",
        },
    )

    assert response.status_code == 200
    assert response.json()["mode"] == "TECHNICAL"


def test_adaptive_answer_research():
    response = client.post(
        "/adaptive-answer",
        json={
            "query": "What are the limitations and findings of this research paper?",
        },
    )

    assert response.status_code == 200
    assert response.json()["mode"] == "RESEARCH"


def test_adaptive_answer_rejects_empty_query():
    response = client.post(
        "/adaptive-answer",
        json={"query": ""},
    )

    assert response.status_code == 422


def test_visual_answer_rejects_empty_query():
    response = client.post(
        "/visual-answer",
        json={"query": ""},
    )

    assert response.status_code == 422


def test_visual_answer_rejects_missing_query():
    response = client.post(
        "/visual-answer",
        json={},
    )

    assert response.status_code == 422


def test_verify_rejects_query_instead_of_claim():
    response = client.post("/verify", json={"query": "a claim"})

    assert response.status_code == 422


def test_discover_concept_rejects_query_instead_of_description():
    response = client.post("/discover-concept", json={"query": "a concept"})

    assert response.status_code == 422


def test_debate_rejects_query_without_positions():
    response = client.post("/debate", json={"query": "a debate topic"})

    assert response.status_code == 422


def test_knowledge_mind_map_empty_graph():
    mock_response = type(
        "MockResponse",
        (),
        {
            "success": True,
            "answer": '{"query": "unknown topic", "research_area": "unknown topic", "nodes": [], "edges": [], "sources": []}',
            "error": None,
            "error_kind": None,
        },
    )()

    with patch.object(
        rag_service.llm,
        "generate_structured",
        return_value=mock_response,
    ):
        response = client.post(
            "/knowledge-mind-map",
            json={"query": "unknown topic"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "unknown topic"
    assert data["nodes"] == []
    assert data["edges"] == []
    assert data["sources"] == []


def test_upload_rejects_unsupported_extension():
    response = client.post(
        "/documents/upload",
        files={"file": ("malicious.exe", b"binary", "application/octet-stream")},
    )
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]


def test_upload_rejects_empty_file():
    response = client.post(
        "/documents/upload",
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_list_documents():
    response = client.get("/documents")
    assert response.status_code == 200
    assert "documents" in response.json()
    # Ensure sample_ieee is excluded by default
    docs = [d.get("document", "") for d in response.json()["documents"]]
    assert not any("sample_ieee" in d.lower() for d in docs)


def test_reason_endpoint():
    with patch.object(
        rag_service,
        "reason",
        return_value={
            "query": "How does context compression work?",
            "subquestions": ["What is compression?", "How is fidelity preserved?"],
            "answer": "Context compression reduces tokens while retaining key evidence.",
            "sources": [
                {
                    "rank": 1,
                    "document": "paper1.pdf",
                    "page": 2,
                    "chunk_id": "chunk_1",
                    "hybrid_score": 0.88,
                    "bm25_score": 0.75,
                    "faiss_score": 0.92,
                }
            ],
        },
    ):
        response = client.post("/reason", json={"query": "How does context compression work?"})
        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "How does context compression work?"
        assert len(data["subquestions"]) == 2
        assert "Context compression" in data["answer"]
        assert len(data["sources"]) == 1
        assert data["sources"][0]["document"] == "paper1.pdf"


def test_query_assistant_endpoint():
    with patch.object(
        rag_service,
        "query_assistant",
        return_value={
            "original_query": "compare adaptive vs static",
            "refined_query": "Comparative analysis between adaptive retrieval and static top-k RAG",
            "suggested_task": "Compare Research",
            "explanation": "Detected comparative intent.",
            "alternative_queries": ["Adaptive vs static RAG benchmark"],
            "tips": ["Specify benchmark dataset."],
        },
    ):
        response = client.post("/query-assistant", json={"query": "compare adaptive vs static"})
        assert response.status_code == 200
        data = response.json()
        assert data["suggested_task"] == "Compare Research"
        assert "Comparative analysis" in data["refined_query"]
        assert len(data["alternative_queries"]) == 1


def test_compare_rejects_more_than_ten_documents():
    too_many_docs = [f"doc_{i}.pdf" for i in range(11)]
    response = client.post(
        "/compare",
        json={
            "query": "Compare these architectures",
            "documents": too_many_docs,
        },
    )
    assert response.status_code == 400
    assert "10 documents" in response.json()["detail"]


def test_upload_rejects_duplicate_document():
    # Attempting to upload content matching sample_ieee metadata hash should be rejected
    from app.rag.config import settings

    sample_metadata = settings.METADATA_DIR / "sample_ieee_metadata.json"
    if sample_metadata.exists():
        with open(sample_metadata, "r", encoding="utf-8") as f:
            meta = json.load(f)
            # Create content that produces same hash or upload with same filename if present
            # We test that duplicate rejection works by uploading a test file twice
            test_content = b"Unique content for duplicate upload verification in test suite."
            try:
                res1 = client.post(
                    "/documents/upload",
                    files={"file": ("duplicate_test_doc.txt", test_content, "text/plain")},
                )
                if res1.status_code == 200:
                    # Second upload with identical content must be rejected
                    res2 = client.post(
                        "/documents/upload",
                        files={"file": ("duplicate_test_doc_copy.txt", test_content, "text/plain")},
                    )
                    assert res2.status_code == 400
                    assert "duplicate" in res2.json()["detail"].lower()
            finally:
                for base in ["duplicate_test_doc", "duplicate_test_doc_copy"]:
                    for p in [
                        settings.PAPERS_DIR / f"{base}.txt",
                        settings.JSON_DIR / f"{base}.json",
                        settings.METADATA_DIR / f"{base}_metadata.json",
                    ]:
                        if p.exists():
                            p.unlink()
                from app.rag.chunker import DocumentChunker
                from app.rag.bm25_index_builder import BM25IndexBuilder
                from app.rag.faiss_index_builder import FAISSIndexBuilder
                DocumentChunker().create_chunks()
                BM25IndexBuilder().build_index()
                FAISSIndexBuilder().build_index()
