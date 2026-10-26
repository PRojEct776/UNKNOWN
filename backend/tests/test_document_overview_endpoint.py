"""M1-08: GET /documents/{name}/overview must keep returning correct errors."""
import dataclasses
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import main as app_main
from app.main import app

client = TestClient(app)

AUTH_TARGET = "app.rag.document_eligibility.get_user_authorized_documents"
GENERATE_TARGET = "app.services.overview_service.generate_document_overview"


@pytest.fixture(autouse=True)
def _fake_workspace(monkeypatch):
    """Bypass real authentication; document authorization is patched per test."""
    monkeypatch.setattr(
        "app.main.resolve_authenticated_workspace",
        lambda *args, **kwargs: ("test-user", None),
    )


@pytest.fixture
def papers_dir(monkeypatch, tmp_path):
    """Point the route at a temp folder holding doc.pdf (Settings is frozen)."""
    (tmp_path / "doc.pdf").write_bytes(b"%PDF-1.4 test")
    patched = dataclasses.replace(app_main.settings, PAPERS_DIR=tmp_path)
    monkeypatch.setattr(app_main, "settings", patched)
    return tmp_path


def test_overview_unauthorized_document_returns_404():
    with patch(AUTH_TARGET, return_value=set()), patch(GENERATE_TARGET) as gen:
        response = client.get("/documents/not_mine.pdf/overview")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
    gen.assert_not_called()


def test_overview_authorized_but_missing_file_returns_404():
    name = "m1_08_missing_on_disk.pdf"
    with patch(AUTH_TARGET, return_value={name}), patch(GENERATE_TARGET) as gen:
        response = client.get(f"/documents/{name}/overview")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
    gen.assert_not_called()


def test_overview_value_error_returns_404(papers_dir):
    with patch(AUTH_TARGET, return_value={"doc.pdf"}), patch(
        GENERATE_TARGET, side_effect=ValueError("Document has no indexed content")
    ):
        response = client.get("/documents/doc.pdf/overview")

    assert response.status_code == 404
    assert response.json()["detail"] == "Document has no indexed content"


def test_overview_unexpected_error_returns_500(papers_dir):
    with patch(AUTH_TARGET, return_value={"doc.pdf"}), patch(
        GENERATE_TARGET, side_effect=RuntimeError("boom")
    ):
        response = client.get("/documents/doc.pdf/overview")

    assert response.status_code == 500
    assert response.json()["detail"].startswith("Overview generation failed")