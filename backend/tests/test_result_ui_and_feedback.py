"""
Tests for UNKNOWN Task P2-1: Result UI and Feedback
1. Grep verification: No confidence computation in frontend.
2. Component tests for panels (ConfidenceBadge, SourceList, AnswerPanel sections).
3. Deterministic source ordering: Same query twice renders the same sources in the same order.
4. /feedback endpoint stores and retrieves a record.
"""

from __future__ import annotations

import glob
import json
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.schemas import (
    Claim,
    Confidence,
    ConfidenceBreakdown,
    Conflict,
    ComparisonPair,
    Source,
)
from app.main import app
from app.rag.confidence import build_sources, compute_confidence
from app.services.feedback_service import record_feedback, get_feedback_records


@pytest.fixture
def client():
    return TestClient(app)


# ===========================================================================
# 1. Grep Check: Frontend never computes a confidence score
# ===========================================================================

def test_no_confidence_computation_in_frontend():
    """
    ACCEPT check: grep finds no other confidence computation in the frontend.
    The frontend must only display the API score directly and never calculate it.
    """
    repo_root = Path(__file__).resolve().parents[2]
    frontend_src = repo_root / "frontend" / "src"
    assert frontend_src.exists(), f"Frontend src not found at {frontend_src}"

    ts_files = list(frontend_src.rglob("*.ts")) + list(frontend_src.rglob("*.tsx"))
    assert len(ts_files) > 0, "No frontend TypeScript files found."

    arithmetic_pattern = re.compile(
        r"(\bconfidence\s*[\*\/+]|[\*\/+]\s*confidence\b|\bconfidence\s+-\s+[0-9a-zA-Z_]|\bcompute_confidence\b|\bcalc.*confidence\b)",
        re.IGNORECASE,
    )

    violations = []
    for filepath in ts_files:
        with open(filepath, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                clean_line = line.strip()
                if arithmetic_pattern.search(line):
                    if not clean_line.startswith(("//", "/*", "*")):
                        violations.append(f"{filepath.name}:{line_no}: {clean_line}")

    assert not violations, f"Found prohibited confidence computations in frontend:\n" + "\n".join(violations)


# ===========================================================================
# 2. Component Contract & Panel Tests
# ===========================================================================

def test_confidence_badge_component_contract():
    """
    Verify ConfidenceBadge component contract:
    - Displays API score directly
    - Exposes breakdown for evidence_coverage, source_agreement, source_quality, claim_support.
    """
    repo_root = Path(__file__).resolve().parents[2]
    badge_file = repo_root / "frontend" / "src" / "components" / "answers" / "ConfidenceBadge.tsx"
    assert badge_file.exists()

    content = badge_file.read_text(encoding="utf-8")

    # Must contain breakdown keys
    assert "evidence_coverage" in content
    assert "source_agreement" in content
    assert "source_quality" in content
    assert "claim_support" in content

    # Must have testids for interactive breakdown
    assert 'data-testid="confidence-badge"' in content
    assert 'data-testid="confidence-breakdown"' in content
    assert 'data-testid="breakdown-coverage"' in content
    assert 'data-testid="breakdown-agreement"' in content
    assert 'data-testid="breakdown-quality"' in content
    assert 'data-testid="breakdown-support"' in content


def test_source_list_component_contract():
    """
    Verify SourceList component contract:
    - Renders title, authors, year, link, passage, origin badge, reliability badge, retracted/preprint warning.
    - Replaces old single-score / evidence cards.
    """
    repo_root = Path(__file__).resolve().parents[2]
    source_list_file = repo_root / "frontend" / "src" / "components" / "evidence" / "SourceList.tsx"
    assert source_list_file.exists()

    content = source_list_file.read_text(encoding="utf-8")

    # Required fields & badges
    assert "source-title" in content
    assert "source-authors" in content
    assert "source-year" in content
    assert "source-link" in content
    assert "source-passage" in content
    assert "source-origin" in content
    assert "source-reliability" in content
    assert "source-warning" in content
    assert "retracted" in content.lower()
    assert "preprint" in content.lower()


def test_answer_panel_all_required_sections_present():
    """
    Verify AnswerPanel contains every required section and panel:
    - summary of at most 3 sentences
    - expandable detail
    - sections 'From your document', 'From the web', 'Agreement and differences'
    - claim chips (supported/partial/unsupported)
    - 'Conflicting sources' panel
    - 'What I could not find' panel
    - thumbs up/down and 'report wrong answer' (POST /feedback)
    """
    repo_root = Path(__file__).resolve().parents[2]
    panel_file = repo_root / "frontend" / "src" / "components" / "answers" / "AnswerPanel.tsx"
    assert panel_file.exists()

    content = panel_file.read_text(encoding="utf-8")

    # Summary of at most 3 sentences
    assert "extractSummaryAtMost3Sentences" in content
    assert "data-testid=\"answer-summary\"" in content
    assert "max 3 sentences" in content

    # Expandable detail
    assert "data-testid=\"detail-toggle\"" in content
    assert "data-testid=\"answer-detail\"" in content

    # Sections
    assert "From your document" in content
    assert "data-testid=\"section-document\"" in content
    assert "From the web" in content
    assert "data-testid=\"section-web\"" in content
    assert "Agreement and differences" in content
    assert "data-testid=\"section-agreement\"" in content

    # Claim chips
    assert "data-testid=\"claim-chips\"" in content
    assert "data-testid=\"claim-chip\"" in content

    # Panels
    assert "Conflicting sources" in content
    assert "data-testid=\"conflicting-sources-panel\"" in content
    assert "What I could not find" in content
    assert "data-testid=\"what-i-could-not-find-panel\"" in content

    # Feedback controls
    assert "data-testid=\"feedback-thumbs-up\"" in content
    assert "data-testid=\"feedback-thumbs-down\"" in content
    assert "data-testid=\"feedback-report-wrong\"" in content
    assert "submitFeedback" in content


# ===========================================================================
# 3. Deterministic Source Ordering Test
# ===========================================================================

def test_same_query_twice_renders_same_sources_in_same_order():
    """
    ACCEPT check: The same query twice renders the same sources in the same order.
    build_sources() must produce identical order and ranks deterministically.
    """
    raw_results = [
        {
            "document": "paper_b.pdf",
            "page": 4,
            "chunk_id": "chunk_b4",
            "text": "Passage regarding empirical benchmarks.",
            "reliability": 0.75,
            "year": 2023,
            "authors": ["Alice Smith"],
        },
        {
            "document": "paper_a.pdf",
            "page": 1,
            "chunk_id": "chunk_a1",
            "text": "Initial formulation of retrieval algorithm.",
            "reliability": 0.95,
            "year": 2024,
            "authors": ["Bob Jones", "Carol White"],
        },
        {
            "document": "paper_c.pdf",
            "page": 12,
            "chunk_id": "chunk_c12",
            "text": "Secondary review findings.",
            "reliability": 0.85,
            "year": 2022,
            "authors": ["David Miller"],
        },
    ]

    # First run
    sources_run1 = build_sources(raw_results)
    ids_run1 = [s.id for s in sources_run1]
    ranks_run1 = [s.rank for s in sources_run1]
    titles_run1 = [s.title or s.document for s in sources_run1]

    # Second run with same raw results
    sources_run2 = build_sources(raw_results)
    ids_run2 = [s.id for s in sources_run2]
    ranks_run2 = [s.rank for s in sources_run2]
    titles_run2 = [s.title or s.document for s in sources_run2]

    # Must be strictly equal in order and values across multiple runs
    assert ids_run1 == ids_run2
    assert ranks_run1 == ranks_run2
    assert titles_run1 == titles_run2
    assert [s.document for s in sources_run1] == [s.document for s in sources_run2]
    assert [s.reliability for s in sources_run1] == [s.reliability for s in sources_run2]

    # Ranks must be sequentially assigned starting from 1
    assert ranks_run1 == [1, 2, 3]


# ===========================================================================
# 4. /feedback Endpoint Stores a Record
# ===========================================================================

def test_feedback_endpoint_stores_record(client, tmp_path):
    """
    ACCEPT check: /feedback stores a record.
    POST /feedback logs query, answer, sources, feedback_type, and comment.
    GET /feedback returns the stored record.
    """
    test_feedback_file = tmp_path / "test_feedback.json"

    with patch("app.services.feedback_service.FEEDBACK_FILE", test_feedback_file):
        payload = {
            "query": "What is SAC-RAG?",
            "answer": "SAC-RAG is a selective, adaptive context RAG framework.",
            "sources": [
                {
                    "id": "src_1",
                    "title": "SAC-RAG Paper",
                    "document": "sac_rag.pdf",
                    "reliability": 0.95,
                }
            ],
            "feedback_type": "thumbs_up",
            "comment": "Accurate response with proper citations.",
            "user_id": "test_researcher",
        }

        # 1. POST /feedback
        resp = client.post("/feedback", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        assert data["status"] == "recorded"
        assert "id" in data
        assert data["feedback_type"] == "thumbs_up"
        assert "recorded_at" in data

        # 2. Check stored record on disk
        assert test_feedback_file.exists()
        records = json.loads(test_feedback_file.read_text(encoding="utf-8"))
        assert len(records) == 1
        stored = records[0]
        assert stored["query"] == payload["query"]
        assert stored["answer"] == payload["answer"]
        assert stored["feedback_type"] == "thumbs_up"
        assert stored["comment"] == payload["comment"]
        assert len(stored["sources"]) == 1
        assert stored["sources"][0]["document"] == "sac_rag.pdf"

        # 3. Test wrong_answer report feedback
        report_payload = {
            "query": "What is SAC-RAG?",
            "answer": "Hallucinated claim.",
            "sources": [],
            "feedback_type": "wrong_answer",
            "comment": "The statement about 99% accuracy is unsupported.",
            "user_id": "test_researcher",
        }
        resp2 = client.post("/feedback", json=report_payload)
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["feedback_type"] == "wrong_answer"

        # Check records now has 2 entries
        records = json.loads(test_feedback_file.read_text(encoding="utf-8"))
        assert len(records) == 2
        assert records[1]["feedback_type"] == "wrong_answer"
        assert records[1]["comment"] == "The statement about 99% accuracy is unsupported."
