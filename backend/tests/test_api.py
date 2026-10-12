from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app, rag_service

client = TestClient(app)


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_query_rejects_empty_query():
    response = client.post("/query", json={"query": ""})

    assert response.status_code == 422


def test_query_rate_limit_error():  # type: ignore
    mock_response = type(
        "MockResponse",
        (),
        {
            "success": False,
            "error": "Provider rate limited",
            "error_kind": "rate_limit",
        },
    )()

    with patch.object(
        app.state.rag_service.llm,
        "generate",
        return_value=mock_response,
    ):
        response = client.post(
            "/query",
            json={"query": "What problem does the framework solve?"},
        )

    assert response.status_code == 429


def test_query_rate_limit_error():  # noqa: F811
    mock_response = type(
        "MockResponse",
        (),
        {
            "success": False,
            "error": "Provider rate limited",
            "error_kind": "rate_limit",
        },
    )()

    with patch.object(
        rag_service.llm,
        "generate",
        return_value=mock_response,
    ):
        response = client.post(
            "/query",
            json={"query": "What problem does the framework solve?"},
        )

    assert response.status_code == 429


def test_query_transient_error():
    mock_response = type(
        "MockResponse",
        (),
        {
            "success": False,
            "error": "Provider temporarily unavailable",
            "error_kind": "transient",
        },
    )()

    with patch.object(
        rag_service.llm,
        "generate",
        return_value=mock_response,
    ):
        response = client.post(
            "/query",
            json={"query": "What problem does the framework solve?"},
        )

    assert response.status_code == 503


def test_query_invalid_request_error():
    mock_response = type(
        "MockResponse",
        (),
        {
            "success": False,
            "error": "Invalid provider request",
            "error_kind": "invalid_request",
        },
    )()

    with patch.object(
        rag_service.llm,
        "generate",
        return_value=mock_response,
    ):
        response = client.post(
            "/query",
            json={"query": "What problem does the framework solve?"},
        )

    assert response.status_code == 400


def test_query_fatal_error():
    mock_response = type(
        "MockResponse",
        (),
        {
            "success": False,
            "error": "Provider rejected request",
            "error_kind": "fatal",
        },
    )()

    with patch.object(
        rag_service.llm,
        "generate",
        return_value=mock_response,
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
        rag_service.llm,
        "generate",
    ) as mock_generate:
        mock_generate.return_value = type(
            "MockResponse",
            (),
            {
                "success": False,
                "error": "Provider rate limited",
                "error_kind": "rate_limit",
            },
        )()

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
