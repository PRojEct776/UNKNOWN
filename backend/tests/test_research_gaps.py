import faiss  # noqa: F401 - must be imported before other C-extensions on Windows
import json
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app, rag_service, research_gaps
from app.api.schemas import ResearchGapRequest
from app.rag.research_gap_finder import (
    GapCategory,
    GapOverview,
    GapPriority,
    GapType,
    OpportunityMap,
    ResearchGap,
    ResearchGapFinder,
    ResearchGapReport,
    FutureResearchRecommendation,
    GapConflict,
)

client = TestClient(app)

SAMPLE_EVIDENCE_DOC_A = [
    {
        "chunk_id": "doc_a_c1",
        "document": "paper_a.pdf",
        "page": 2,
        "text": "Paper A achieves 89.2% accuracy. However, our limitation is high inference latency on edge devices exceeding 450ms.",
        "rank": 1,
        "hybrid_score": 0.94,
    },
    {
        "chunk_id": "doc_a_c2",
        "document": "paper_a.pdf",
        "page": 4,
        "text": "We evaluate only on English Wikipedia; lack of multilingual benchmark datasets remains an unresolved challenge.",
        "rank": 2,
        "hybrid_score": 0.88,
    },
]

SAMPLE_EVIDENCE_DOC_B = [
    {
        "chunk_id": "doc_b_c1",
        "document": "paper_b.pdf",
        "page": 1,
        "text": "Paper B introduces low-latency pruning reaching 45ms. However, accuracy degrades by 12% on low-resource tasks.",
        "rank": 1,
        "hybrid_score": 0.92,
    },
    {
        "chunk_id": "doc_b_c2",
        "document": "paper_b.pdf",
        "page": 3,
        "text": "We leave formal theoretical convergence bounds for non-convex loss landscapes to future work.",
        "rank": 2,
        "hybrid_score": 0.85,
    },
]

MOCK_LLM_RESPONSE_JSON = json.dumps({
    "query": "What are the research gaps in model optimization?",
    "research_area": "Efficient Model Optimization",
    "existing_findings": [
        "Paper A achieves 89.2% accuracy on benchmark tasks.",
        "Paper B introduces low-latency pruning achieving 45ms runtime.",
    ],
    "reported_limitations": [
        "High inference latency on edge devices exceeding 450ms.",
        "Accuracy degrades significantly by 12% on low-resource tasks.",
    ],
    "gaps": [
        {
            "gap": "High Edge Latency Bottleneck",
            "category": "PERFORMANCE",
            "type": "EXPLICIT",
            "priority": "HIGH",
            "priority_reasoning": "High priority: Critical performance bottleneck directly stated by authors.",
            "confidence": 0.92,
            "rationale": "Inference latency exceeds 450ms, rendering edge deployment unfeasible.",
            "current_knowledge": "High accuracy achieved on desktop hardware.",
            "missing_unresolved": "Inference latency on edge devices under 100ms.",
            "limitation_evidence": "our limitation is high inference latency on edge devices exceeding 450ms.",
            "why_it_matters": "Prevents real-time on-device autonomous execution.",
            "potential_direction": "Apply structured sparse quantization and hardware-aware pruning.",
            "relevant_methods": ["Quantization-Aware Training", "Structured Pruning"],
            "document": "paper_a.pdf",
            "page": 2,
            "chunk_id": "doc_a_c1",
            "evidence": ["our limitation is high inference latency on edge devices exceeding 450ms."],
            "supporting_papers": ["paper_a.pdf"],
            "is_shared": False,
        },
        {
            "gap": "Multilingual Dataset Generalization",
            "category": "DATASET",
            "type": "DERIVED",
            "priority": "MEDIUM",
            "priority_reasoning": "Medium priority: Evaluation restricted to English Wikipedia with no multilingual benchmarks.",
            "confidence": 0.84,
            "rationale": "Evaluation is restricted solely to English Wikipedia corpora.",
            "current_knowledge": "Monolingual English benchmarks are well-established.",
            "missing_unresolved": "Multilingual cross-lingual transfer datasets and evaluations.",
            "limitation_evidence": "lack of multilingual benchmark datasets remains an unresolved challenge.",
            "why_it_matters": "Limits applicability across non-English global languages.",
            "potential_direction": "Construct curated multilingual benchmark corpora across low-resource dialects.",
            "relevant_methods": ["Zero-shot cross-lingual transfer", "Multilingual benchmarking"],
            "document": "paper_a.pdf",
            "page": 4,
            "chunk_id": "doc_a_c2",
            "evidence": ["lack of multilingual benchmark datasets remains an unresolved challenge."],
            "supporting_papers": ["paper_a.pdf", "paper_b.pdf"],
            "is_shared": True,
        },
    ],
    "recommendations": [
        {
            "gap_title": "High Edge Latency Bottleneck",
            "title": "Hardware-Aware Mixed-Precision Quantization Study",
            "research_question": "Can mixed-precision INT4/FP8 quantization reduce edge latency below 50ms without degrading accuracy?",
            "problem_to_investigate": "High edge latency exceeding 450ms on mobile hardware.",
            "suggested_approach": "Profile memory throughput on ARM cores with automated bit-width search.",
            "expected_contribution": "Provides sub-50ms latency Pareto frontier on edge processors.",
            "supporting_evidence": ["our limitation is high inference latency on edge devices exceeding 450ms."],
        }
    ],
    "conflicts": [
        {
            "topic": "Pruning Effect on Non-convex Loss",
            "paper_a": "paper_a.pdf",
            "finding_a": "Pruning preserves global optima stability.",
            "paper_b": "paper_b.pdf",
            "finding_b": "Pruning destabilizes non-convex gradient descent trajectories.",
            "explanation": "Conflicting findings on optimization trajectory stability under structured sparsity.",
            "evidence_chunks": ["doc_a_c1", "doc_b_c2"],
        }
    ],
})


# ==============================================================================
# TESTS
# ==============================================================================

def test_explicit_gap_extraction():
    """Verify explicit gaps directly acknowledged by authors are extracted with correct type and confidence."""
    finder = ResearchGapFinder()
    report = finder.parse_response(
        query="edge latency gaps",
        response_text=MOCK_LLM_RESPONSE_JSON,
    )

    explicit_gaps = [g for g in report.gaps if g.type == GapType.EXPLICIT]
    assert len(explicit_gaps) >= 1
    gap = explicit_gaps[0]
    assert gap.category == GapCategory.PERFORMANCE
    assert gap.confidence >= 0.90
    assert "latency" in gap.gap.lower()
    assert gap.document == "paper_a.pdf"
    assert gap.page == 2
    assert gap.chunk_id == "doc_a_c1"
    assert "our limitation is high inference latency" in gap.limitation_evidence


def test_derived_gap_identification():
    """Verify derived gaps synthesized across empirical findings are labeled DERIVED."""
    finder = ResearchGapFinder()
    report = finder.parse_response(
        query="dataset gaps",
        response_text=MOCK_LLM_RESPONSE_JSON,
    )

    derived_gaps = [g for g in report.gaps if g.type == GapType.DERIVED]
    assert len(derived_gaps) >= 1
    gap = derived_gaps[0]
    assert gap.category == GapCategory.DATASET
    assert gap.is_shared is True
    assert len(gap.supporting_papers) >= 2


def test_multi_document_gap_analysis():
    """Verify multi-document analysis tracks shared gaps, unique limitations, and multi-doc insights."""
    finder = ResearchGapFinder()
    report = finder.parse_response(
        query="multi-document gaps",
        response_text=MOCK_LLM_RESPONSE_JSON,
    )

    assert report.overview.supporting_papers_count == 2
    assert len(report.multi_doc_insights["shared_gaps"]) >= 1
    assert "Multilingual Dataset Generalization" in report.multi_doc_insights["shared_gaps"]
    assert "paper_a.pdf" in report.multi_doc_insights["unique_limitations"]


def test_contradiction_detection():
    """Verify genuine conflicting findings are extracted without treating missing info as contradiction."""
    finder = ResearchGapFinder()
    report = finder.parse_response(
        query="contradictions in pruning",
        response_text=MOCK_LLM_RESPONSE_JSON,
    )

    assert len(report.conflicts) == 1
    conflict = report.conflicts[0]
    assert conflict.paper_a == "paper_a.pdf"
    assert conflict.paper_b == "paper_b.pdf"
    assert "Pruning" in conflict.topic
    assert len(conflict.evidence_chunks) == 2


def test_gap_prioritization():
    """Verify prioritization calculates High, Medium, Low with detailed transparent reasoning."""
    finder = ResearchGapFinder()
    gap_high = ResearchGap(
        gap="High VRAM Bottleneck",
        category=GapCategory.PERFORMANCE,
        type=GapType.EXPLICIT,
        confidence=0.92,
        rationale="Requires 80GB VRAM.",
        limitation_evidence="Requires 80GB VRAM.",
        supporting_papers=["paper1.pdf", "paper2.pdf"],
        is_shared=True,
    )

    prio, reason = finder.calculate_gap_priority(gap_high, evidence_count=2, is_shared=True)
    assert prio == GapPriority.HIGH
    assert "High priority" in reason
    assert "directly acknowledged" in reason

    gap_low = ResearchGap(
        gap="Minor UI aesthetic variant",
        category=GapCategory.APPLICATION,
        type=GapType.POTENTIAL,
        confidence=0.60,
        rationale="Could consider dark mode color adjustments.",
    )
    prio_low, reason_low = finder.calculate_gap_priority(gap_low, evidence_count=1, is_shared=False)
    assert prio_low == GapPriority.LOW
    assert "Low priority" in reason_low


def test_citation_preservation():
    """Verify document name, page, and chunk IDs are preserved across gaps and sources."""
    finder = ResearchGapFinder()
    report = finder.parse_response(
        query="citations check",
        response_text=MOCK_LLM_RESPONSE_JSON,
    )

    for gap in report.gaps:
        assert gap.document != ""
        assert gap.chunk_id != ""
        assert len(gap.evidence) > 0

    assert len(report.sources) >= 2
    source_chunks = {s["chunk_id"] for s in report.sources}
    assert "doc_a_c1" in source_chunks
    assert "doc_a_c2" in source_chunks


def test_confidence_assignment():
    """Verify confidence score is between 0.0 and 1.0 grounded in evidence quality."""
    finder = ResearchGapFinder()
    report = finder.parse_response(
        query="confidence check",
        response_text=MOCK_LLM_RESPONSE_JSON,
    )

    for gap in report.gaps:
        assert 0.0 <= gap.confidence <= 1.0


def test_future_research_recommendations():
    """Verify recommendations are structured proposals with research question, problem, approach, and contribution."""
    finder = ResearchGapFinder()
    report = finder.parse_response(
        query="recommendations check",
        response_text=MOCK_LLM_RESPONSE_JSON,
    )

    assert len(report.recommendations) >= 1
    rec = report.recommendations[0]
    assert rec.is_proposal is True
    assert rec.research_question != ""
    assert rec.problem_to_investigate != ""
    assert rec.suggested_approach != ""
    assert rec.expected_contribution != ""


def test_no_llm_fallback():
    """Verify deterministic rule-based fallback extracts gaps directly from evidence without LLM."""
    finder = ResearchGapFinder()
    combined_evidence = SAMPLE_EVIDENCE_DOC_A + SAMPLE_EVIDENCE_DOC_B

    report = finder.build_no_llm_gaps(
        query="What are the research limitations in edge latency?",
        evidence=combined_evidence,
        document_names=["paper_a.pdf", "paper_b.pdf"],
    )

    assert report.partial is True
    assert report.notice is not None
    assert len(report.gaps) >= 2
    assert report.overview.total_gaps >= 2
    assert len(report.recommendations) >= 1
    assert len(report.opportunity_map.nodes) > 0

    # Ensure no hallucinations: all evidence quotes exist in input
    all_raw_text = " ".join([c["text"] for c in combined_evidence])
    for gap in report.gaps:
        assert gap.limitation_evidence in all_raw_text


def test_llm_quota_exhaustion_fallback():
    """Verify RAGService falls back gracefully to deterministic gaps on quota exhaustion (never HTTP 500)."""
    fake_resp = MagicMock()
    fake_resp.success = False
    fake_resp.error = "Resource has been exhausted (e.g. check quota)."

    with patch.object(rag_service, "_search", return_value=SAMPLE_EVIDENCE_DOC_A), \
         patch.object(rag_service.llm, "generate_structured", return_value=fake_resp):
        report = rag_service.find_research_gaps("optimization limitations", document_names=["paper_a.pdf"])

        assert report.partial is True
        assert "Notice: Research gap report generated directly" in (report.notice or "")
        assert len(report.gaps) >= 1
        assert report.gaps[0].document == "paper_a.pdf"


def test_malformed_response_fallback():
    """Verify RAGService recovers from truncated or corrupted provider response text."""
    fake_resp = MagicMock()
    fake_resp.success = True
    fake_resp.answer = "CORRUPTED_NON_JSON_OUTPUT_<<<502_BAD_GATEWAY>>>"

    with patch.object(rag_service, "_search", return_value=SAMPLE_EVIDENCE_DOC_A), \
         patch.object(rag_service.llm, "generate_structured", return_value=fake_resp):
        report = rag_service.find_research_gaps("corrupted response test", document_names=["paper_a.pdf"])

        # Fell back to deterministic extractor
        assert report.partial is True
        assert len(report.gaps) >= 1


def test_empty_retrieval_returns_not_found():
    """Verify empty retrieval returns notice with 'Not found in available sources' and zero gaps."""
    with patch.object(rag_service, "_search", return_value=[]):
        report = rag_service.find_research_gaps("quantum gravity unindexed", document_names=["nonexistent.pdf"])

        assert report.partial is False
        assert "Not found in available sources" in (report.notice or "")
        assert len(report.gaps) == 0
        assert report.overview.total_gaps == 0


def test_api_gaps_endpoint_success():
    """Verify POST /gaps endpoint logic returns complete response schema and status 200."""
    finder = ResearchGapFinder()
    mock_report = finder.parse_response(
        query="edge latency gaps",
        response_text=MOCK_LLM_RESPONSE_JSON,
    )

    with patch.object(rag_service, "find_research_gaps", return_value=mock_report):
        req = ResearchGapRequest(query="edge latency gaps", document_names=["paper_a.pdf"])
        resp = research_gaps(req)

        assert resp.query == "What are the research gaps in model optimization?"
        assert len(resp.gaps) == 2
        assert resp.overview["total_gaps"] == 2
        assert len(resp.recommendations) == 1
        assert len(resp.opportunity_map["nodes"]) > 0
        assert len(resp.conflicts) == 1


def test_api_gaps_endpoint_validation():
    """Verify research_gaps rejects empty queries or empty document arrays with HTTP 400."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc1:
        research_gaps(ResearchGapRequest(query="   "))
    assert exc1.value.status_code == 400

    with pytest.raises(HTTPException) as exc2:
        research_gaps(ResearchGapRequest(query="valid query", document_names=[]))
    assert exc2.value.status_code == 400
