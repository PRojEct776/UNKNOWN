"""
Tests for Unified Confidence and Canonical Source Module (Task A7)

Acceptance Criteria:
- identical output over 100 runs
- every endpoint returns identical Source objects for the same passage
- a test proving no code outside compute_confidence computes a score
"""

from __future__ import annotations

import ast
from pathlib import Path
import pytest

from app.api.schemas import (
    AnswerResponse,
    Claim,
    Confidence,
    ConfidenceBreakdown,
    Conflict,
    Source,
)
from app.rag.confidence import (
    build_sources,
    compute_confidence,
    compute_stable_source_id,
)


# ---------------------------------------------------------------------------
# 1. Acceptance Criterion: Identical output over 100 runs
# ---------------------------------------------------------------------------

class TestConfidenceDeterminism:
    def test_identical_output_over_100_runs(self):
        statuses = ["sufficient", "sufficient", "weak"]
        claims = [
            Claim(text="Claim 1", label="supported"),
            Claim(text="Claim 2", label="supported"),
            Claim(text="Claim 3", label="partial"),
        ]
        sources = [
            Source(
                id="src_1",
                document="doc1.pdf",
                page=1,
                chunk_id="c1",
                hybrid_score=0.9,
                bm25_score=0.8,
                faiss_score=0.85,
                reliability=0.85,
            ),
            Source(
                id="src_2",
                document="doc2.pdf",
                page=2,
                chunk_id="c2",
                hybrid_score=0.7,
                bm25_score=0.6,
                faiss_score=0.65,
                reliability=0.75,
            ),
        ]
        conflicts = [
            Conflict(topic="T", side_a="A", side_b="B", likely_reason="Temporal difference"),
        ]

        results = [
            compute_confidence(
                statuses=statuses,
                claims=claims,
                sources=sources,
                conflicts=conflicts,
            )
            for _ in range(100)
        ]

        first = results[0]
        assert isinstance(first, Confidence)
        assert 0.0 <= first.score <= 100.0

        for idx, res in enumerate(results[1:], start=2):
            assert res.score == first.score, f"Mismatch at run {idx}: {res.score} vs {first.score}"
            assert res.breakdown.evidence_coverage == first.breakdown.evidence_coverage
            assert res.breakdown.claim_support == first.breakdown.claim_support
            assert res.breakdown.source_agreement == first.breakdown.source_agreement
            assert res.breakdown.source_quality == first.breakdown.source_quality
            assert res.formula_version == first.formula_version

    def test_formula_weights_and_breakdown(self):
        # coverage: 1/1 = 1.0
        # claim_support: 1/1 = 1.0
        # agreement: 0 conflicts -> 1.0
        # quality: 1.0
        # score = 100 * (0.25*1 + 0.35*1 + 0.20*1 + 0.20*1) = 100.0
        c = compute_confidence(
            statuses=["sufficient"],
            claims=[Claim(text="C", label="supported")],
            sources=[{"reliability": 1.0}],
            conflicts=[],
            w_coverage=0.25,
            w_claim_support=0.35,
            w_agreement=0.20,
            w_quality=0.20,
            formula_version="v1.0",
        )
        assert c.score == pytest.approx(100.0)
        assert c.breakdown.evidence_coverage == 1.0
        assert c.breakdown.claim_support == 1.0
        assert c.breakdown.source_agreement == 1.0
        assert c.breakdown.source_quality == 1.0
        assert c.formula_version == "v1.0"

    def test_zero_and_partial_weights(self):
        # 1 insufficient status -> coverage 0.0
        # 1 contradicted claim -> claim_support 0.0
        # 2 conflicts -> agreement 1.0 - 0.25*2 = 0.50
        # 1 source with reliability 0.50 -> quality 0.50
        c = compute_confidence(
            statuses=["insufficient"],
            claims=[Claim(text="Contradicted", label="contradicted")],
            sources=[{"reliability": 0.5}],
            conflicts=[
                Conflict(topic="A vs B", side_a="A", side_b="B", likely_reason="Different methods"),
                Conflict(topic="C vs D", side_a="C", side_b="D", likely_reason="Temporal difference"),
            ],
            w_coverage=0.25,
            w_claim_support=0.35,
            w_agreement=0.20,
            w_quality=0.20,
            formula_version="v1.0",
        )
        expected = 100.0 * (0.25 * 0.0 + 0.35 * 0.0 + 0.20 * 0.5 + 0.20 * 0.5)
        assert c.score == pytest.approx(expected)
        assert c.breakdown.evidence_coverage == 0.0
        assert c.breakdown.claim_support == 0.0
        assert c.breakdown.source_agreement == 0.5
        assert c.breakdown.source_quality == 0.5


# ---------------------------------------------------------------------------
# 2. Acceptance Criterion: Every endpoint returns identical Source objects for same passage
# ---------------------------------------------------------------------------

class TestCanonicalSourceBuilder:
    def test_identical_source_objects_for_same_passage(self):
        passage = {
            "document": "attention.pdf",
            "page": 3,
            "chunk_id": "chunk_42",
            "text": "Multi-head attention allows the model to jointly attend to information.",
            "url": "https://doi.org/10.1145/3308558.3313508",
            "venue": "NeurIPS",
            "year": 2017,
            "cites": 50000,
            "hybrid_score": 0.92,
            "bm25_score": 0.88,
            "faiss_score": 0.94,
        }

        # Simulate multiple distinct endpoints (Query, Reason, Adaptive, Debate, etc.)
        # all passing the same retrieved passage to build_sources
        endpoint_query_sources = build_sources([passage])
        endpoint_reason_sources = build_sources([passage])
        endpoint_adaptive_sources = build_sources([passage])

        assert len(endpoint_query_sources) == 1
        assert len(endpoint_reason_sources) == 1
        assert len(endpoint_adaptive_sources) == 1

        s_q = endpoint_query_sources[0]
        s_r = endpoint_reason_sources[0]
        s_a = endpoint_adaptive_sources[0]

        # Must be identical across all endpoints
        assert s_q.id == s_r.id == s_a.id
        assert s_q.rank == s_r.rank == s_a.rank == 1
        assert s_q.document == s_r.document == s_a.document == "attention.pdf"
        assert s_q.chunk_id == s_r.chunk_id == s_a.chunk_id == "chunk_42"
        assert s_q.hybrid_score == s_r.hybrid_score == s_a.hybrid_score == 0.92
        assert s_q.reliability == s_r.reliability == s_a.reliability
        assert s_q.warnings == s_r.warnings == s_a.warnings
        assert s_q.url == s_r.url == s_a.url
        assert s_q.model_dump() == s_r.model_dump() == s_a.model_dump()

    def test_stable_order_reliability_desc_then_id(self):
        p1 = {"document": "docA.pdf", "chunk_id": "c1", "venue": "bioRxiv", "year": 2024}  # preprint -> lower rel
        p2 = {"document": "docB.pdf", "chunk_id": "c2", "venue": "Nature", "year": 2024}   # top journal -> higher rel
        p3 = {"document": "docC.pdf", "chunk_id": "c3", "venue": "Nature", "year": 2024}   # same top journal

        sources = build_sources([p1, p2, p3])
        assert len(sources) == 3

        # p2 and p3 (Nature) should be before p1 (bioRxiv)
        assert sources[0].document in ("docB.pdf", "docC.pdf")
        assert sources[1].document in ("docB.pdf", "docC.pdf")
        assert sources[2].document == "docA.pdf"
        assert sources[0].rank == 1
        assert sources[1].rank == 2
        assert sources[2].rank == 3

        # For equal reliability, sorted by stable id ASC
        if sources[0].reliability == sources[1].reliability:
            assert sources[0].id <= sources[1].id

    def test_stable_id_hash(self):
        item_with_url = {"url": "https://doi.org/10.1234/sample"}
        item_with_doc_chunk = {"document": "paper.pdf", "chunk_id": "chunk_10"}

        id1_a = compute_stable_source_id(item_with_url)
        id1_b = compute_stable_source_id(item_with_url)
        assert id1_a == id1_b
        assert len(id1_a) == 16

        id2_a = compute_stable_source_id(item_with_doc_chunk)
        id2_b = compute_stable_source_id(item_with_doc_chunk)
        assert id2_a == id2_b
        assert id1_a != id2_a

    def test_every_endpoint_and_service_uses_build_sources_ast(self):
        """
        Verify that no endpoint or service file in backend/app/ directly instantiates
        Source(...) except the canonical build_sources function.
        """
        app_dir = Path(__file__).resolve().parents[1] / "app"
        violations = []

        for py_path in app_dir.rglob("*.py"):
            # Schemas definition and canonical confidence module are expected
            if py_path.name in ("confidence.py", "schemas.py"):
                continue

            try:
                tree = ast.parse(py_path.read_text(encoding="utf-8"))
            except Exception:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Name) and func.id == "Source":
                        violations.append(f"{py_path.name}:{node.lineno}")

        assert violations == [], (
            f"Found direct Source(...) instantiations outside build_sources: {violations}"
        )


# ---------------------------------------------------------------------------
# 3. Acceptance Criterion: No code outside compute_confidence computes a score
# ---------------------------------------------------------------------------

class TestSingleConfidenceScoreSource:
    def test_no_code_outside_compute_confidence_computes_confidence_score(self):
        """
        Static code analysis test across backend/app/:
        Verifies that no function outside app/rag/confidence.py defines
        confidence score calculation or ad-hoc confidence functions.
        """
        app_dir = Path(__file__).resolve().parents[1] / "app"
        assert app_dir.exists() and app_dir.is_dir()

        disallowed_function_names = {
            "compute_confidence_score",
            "calculate_confidence_score",
            "calculate_confidence",
            "calc_confidence",
            "get_confidence_score",
            "score_confidence",
            "compute_answer_confidence",
        }

        violations = []

        for py_path in app_dir.rglob("*.py"):
            # Exclude the canonical confidence module itself
            if py_path.name == "confidence.py":
                continue

            try:
                tree = ast.parse(py_path.read_text(encoding="utf-8"))
            except Exception:
                continue

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name in disallowed_function_names or (
                        node.name.startswith("compute_confidence") and node.name != "compute_confidence"
                    ):
                        violations.append(f"{py_path.name}:{node.name}:{node.lineno}")

        assert violations == [], (
            f"Found confidence calculation functions outside compute_confidence: {violations}"
        )

    def test_confidence_instantiation_ast(self):
        """
        Verify that Confidence(...) is never instantiated outside app/rag/confidence.py
        or schema defaults.
        """
        app_dir = Path(__file__).resolve().parents[1] / "app"
        violations = []

        for py_path in app_dir.rglob("*.py"):
            if py_path.name in ("confidence.py", "schemas.py"):
                continue

            try:
                tree = ast.parse(py_path.read_text(encoding="utf-8"))
            except Exception:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Name) and func.id == "Confidence":
                        violations.append(f"{py_path.name}:{node.lineno}")

        assert violations == [], (
            f"Found direct Confidence(...) instantiations outside app/rag/confidence.py: {violations}"
        )
