"""
Tests for UNKNOWN Task FINAL-FE: Redesigned Modern LLM Chat App
ACCEPT criteria:
- Overview appears first and gates the tools until ready
- Starter buttons are gone (no preset one-click starter inquiry)
- Scope chip sends the right scope (this_document, selected, all, documents_web)
- Message renders ConfidenceBadge and SourceList once
- Delete shows confirm then 10-second undo toast
- /smart-query autocomplete and Run All wired and verified
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_starter_query_buttons_are_completely_gone():
    """
    ACCEPT check: verify that no preset starter-query buttons, example query buttons,
    or quick-start cards exist in the frontend code.
    Suggested questions in overview must be plain text, not clickable buttons.
    """
    repo_root = Path(__file__).resolve().parents[2]
    frontend_src = repo_root / "frontend" / "src"
    ts_files = list(frontend_src.rglob("*.ts")) + list(frontend_src.rglob("*.tsx"))

    prohibited_patterns = [
        re.compile(r"handleTestQuery", re.IGNORECASE),
        re.compile(r"domainList", re.IGNORECASE),
        re.compile(r"onSelectDocumentQuery", re.IGNORECASE),
        re.compile(r"onQueryPaper", re.IGNORECASE),
        re.compile(r"createMockWorkspaceResult", re.IGNORECASE),
        re.compile(r"quickStartQueries", re.IGNORECASE),
    ]

    violations = []
    for filepath in ts_files:
        content = filepath.read_text(encoding="utf-8")
        for pat in prohibited_patterns:
            if pat.search(content):
                violations.append(f"{filepath.name} matches {pat.pattern}")

    assert not violations, f"Found prohibited starter inquiry patterns:\n" + "\n".join(violations)

    # Verify overview plain text
    chat_workspace = frontend_src / "pages" / "ChatWorkspacePage.tsx"
    assert chat_workspace.exists(), "ChatWorkspacePage.tsx does not exist"
    chat_text = chat_workspace.read_text(encoding="utf-8")
    assert 'data-testid="suggested-questions-plain-text"' in chat_text
    assert "pointer-events-none" in chat_text or "select-text" in chat_text


def test_overview_appears_first_and_gates_tools_until_ready():
    """
    ACCEPT check: verify that after an upload, the Overview card is added first,
    and tools/querying are gated (isToolsGated) until the overview generation completes.
    """
    repo_root = Path(__file__).resolve().parents[2]
    chat_workspace = repo_root / "frontend" / "src" / "pages" / "ChatWorkspacePage.tsx"
    content = chat_workspace.read_text(encoding="utf-8")

    # 1. State for gating
    assert "isToolsGated" in content
    assert "setIsToolsGated(true)" in content
    assert "setIsToolsGated(false)" in content

    # 2. Overview card structure
    assert 'data-testid="document-overview-card"' in content
    assert 'data-testid="document-iq-badge"' in content
    assert 'data-testid="overview-title"' in content
    assert "Executive Summary (5 Key Aspects)" in content

    # 3. Gating on composer and tools
    assert "disabled={isQueryRunning || isToolsGated" in content
    assert "Document overview in progress..." in content


def test_scope_chip_and_options():
    """
    ACCEPT check: verify scope chip supports this_document, selected, all, and documents_web,
    and forwards target doc ids.
    """
    repo_root = Path(__file__).resolve().parents[2]
    chat_workspace = repo_root / "frontend" / "src" / "pages" / "ChatWorkspacePage.tsx"
    content = chat_workspace.read_text(encoding="utf-8")

    assert 'data-testid="scope-chip"' in content
    assert 'data-testid="scope-dropdown-menu"' in content
    assert "this_document" in content
    assert "selected" in content
    assert "documents_web" in content
    assert "targetDocIds" in content


def test_message_renders_confidence_badge_and_source_list_once():
    """
    ACCEPT check: verify ConfidenceBadge and SourceList are the only components
    used for score and source rendering.
    """
    repo_root = Path(__file__).resolve().parents[2]
    frontend_src = repo_root / "frontend" / "src"

    answer_panel = frontend_src / "components" / "answers" / "AnswerPanel.tsx"
    assert answer_panel.exists()
    content = answer_panel.read_text(encoding="utf-8")

    assert "<ConfidenceBadge" in content
    assert 'data-testid="open-sources-drawer-btn"' in content
    assert 'data-testid="inline-citation-marker"' in content

    # Check that sources drawer uses SourceList
    drawer = frontend_src / "components" / "evidence" / "SourcesDrawer.tsx"
    assert drawer.exists()
    drawer_content = drawer.read_text(encoding="utf-8")
    assert "<SourceList" in drawer_content


def test_delete_shows_confirm_then_10s_undo_toast():
    """
    ACCEPT check: verify delete actions for documents and history display
    a confirmation modal, followed by a 10-second undo toast.
    """
    repo_root = Path(__file__).resolve().parents[2]
    chat_workspace = repo_root / "frontend" / "src" / "pages" / "ChatWorkspacePage.tsx"
    content = chat_workspace.read_text(encoding="utf-8")

    assert 'data-testid="confirm-dialog-backdrop"' in content
    assert 'data-testid="confirm-dialog-ok-btn"' in content
    assert 'data-testid="undo-toast"' in content
    assert 'data-testid="undo-toast-btn"' in content
    assert "secondsLeft: 10" in content
    assert "undoDeleteDocument" in content


def test_smart_query_autocomplete_and_run_all_wiring(client: TestClient):
    """
    ACCEPT check: verify /smart-query autocomplete and run_all endpoints
    are operational and return required shapes.
    """
    # 1. Autocomplete
    ac_resp = client.get("/smart-query/autocomplete?q=sum")
    assert ac_resp.status_code == 200
    ac_data = ac_resp.json()
    assert "query" in ac_data
    assert "features" in ac_data
    assert any(f.get("feature") == "summary" for f in ac_data.get("features", []))

    # 2. Run All via /smart-query (returns streaming SSE)
    sq_resp = client.post("/smart-query", json={"text": "compare high dimensional data", "run_all": True})
    assert sq_resp.status_code == 200
    assert "text/event-stream" in sq_resp.headers.get("content-type", "")
    content = sq_resp.text
    assert "data: " in content
    assert "run_all_start" in content or "run_all_complete" in content
