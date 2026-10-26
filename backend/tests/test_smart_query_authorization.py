"""/smart-query must only act on documents the user may access."""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app, rag_service

client = TestClient(app)

AUTH_TARGET = "app.rag.document_eligibility.get_user_authorized_documents"
LIST_TARGET = "app.rag.utils.list_supported_documents"
DETECT_TARGET = "app.services.smart_router_service.detect_feature"
GRAPH_TARGET = "app.services.smart_router_service.extract_concept_graph"


def _files(*names):
    files = []
    for name in names:
        f = MagicMock()
        f.name = name
        files.append(f)
    return files


@pytest.fixture(autouse=True)
def _fake_workspace(monkeypatch):
    monkeypatch.setattr(
        "app.main.resolve_authenticated_workspace",
        lambda *args, **kwargs: ("test-user", None),
    )


def test_unauthorized_document_id_returns_404():
    with patch(LIST_TARGET, return_value=_files("mine.pdf")), patch(
        AUTH_TARGET, return_value={"mine.pdf"}
    ), patch(GRAPH_TARGET) as graph:
        response = client.post(
            "/smart-query",
            json={"text": "mind map", "document_ids": ["not_mine.pdf"]},
        )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
    graph.assert_not_called()


def test_fuzzy_matching_ignores_documents_the_user_cannot_access():
    payload = {"document": "report.pdf", "nodes": [], "edges": []}
    with patch(
        LIST_TARGET, return_value=_files("report.pdf", "secret_plan.pdf")
    ), patch(AUTH_TARGET, return_value={"report.pdf"}), patch(
        GRAPH_TARGET, return_value=payload
    ) as graph:
        response = client.post("/smart-query", json={"text": "secret_plan.pdf mind map"})

    assert response.status_code == 200
    assert "secret_plan.pdf" not in response.json()["matched_documents"]
    graph.assert_called_once()
    assert graph.call_args.args[0] != "secret_plan.pdf"


def test_qa_with_no_accessible_documents_does_not_query(monkeypatch):
    query_mock = MagicMock(return_value={"answer": "x"})
    monkeypatch.setattr(rag_service, "query", query_mock)
    with patch(LIST_TARGET, return_value=_files("theirs.pdf")), patch(
        AUTH_TARGET, return_value=set()
    ), patch(DETECT_TARGET, return_value="qa"):
        response = client.post("/smart-query", json={"text": "what is attention"})

    assert response.status_code == 200
    assert "error" in response.json()["result"]
    query_mock.assert_not_called()


def test_qa_is_scoped_to_authorized_documents(monkeypatch):
    query_mock = MagicMock(return_value={"answer": "x"})
    monkeypatch.setattr(rag_service, "query", query_mock)
    with patch(LIST_TARGET, return_value=_files("report.pdf", "theirs.pdf")), patch(
        AUTH_TARGET, return_value={"report.pdf"}
    ), patch(DETECT_TARGET, return_value="qa"):
        response = client.post("/smart-query", json={"text": "what is attention"})

    assert response.status_code == 200
    assert query_mock.call_args.kwargs["document_names"] == ["report.pdf"]