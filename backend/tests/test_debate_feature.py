"""
Comprehensive focused test suite for DEBATE feature.
Tests:
- Debate API and schemas
- Pro/Con argument generation
- Rebuttal generation
- Citation and page attribution
- Single-paper and multi-paper support
- Missing evidence and uncertainty
- Malformed/truncated LLM responses
- Provider failure and deterministic fallback
"""

import pytest
from unittest.mock import MagicMock, patch

from app.api.schemas import DebateRequest, DebateResponse
from app.main import rag_service
from app.rag.debate_engine import (
    DebateArgument,
    DebateEngine,
    DebateOpeningStatements,
    DebateRebuttal,
    DebateReport,
    DebateSide,
    EvidenceStrength,
    EvidenceType,
)


# ==============================================================================
# 1. SCHEMAS & REQUEST/RESPONSE VALIDATION
# ==============================================================================

def test_debate_request_and_response_schemas():
    """Verify DebateRequest and DebateResponse validation and field serialization."""
    req = DebateRequest(
        query="Should LLMs use retrieval augmented generation?",
        position_a="RAG improves factual grounding",
        position_b="RAG introduces retrieval latency and complexity",
        document_names=["paper1.pdf"],
    )
    assert req.query == "Should LLMs use retrieval augmented generation?"
    assert req.position_a == "RAG improves factual grounding"
    assert req.position_b == "RAG introduces retrieval latency and complexity"
    assert req.document_names == ["paper1.pdf"]

    resp = DebateResponse(
        query=req.query,
        topic="RAG factual grounding vs complexity",
        position_a=req.position_a,
        position_b=req.position_b,
        arguments=[
            {
                "side": "POSITION_A",
                "title": "Improved Grounding",
                "argument": "Retrieval supplies external evidence.",
                "evidence_type": "DIRECT_EVIDENCE",
                "evidence": ["Factual accuracy increases by 25%."],
                "confidence": 0.92,
                "evidence_strength": "STRONG",
                "document": "paper1.pdf",
                "page": 3,
                "chunk_id": "chunk_01",
            }
        ],
        rebuttals=[
            {
                "side": "POSITION_B",
                "target_argument": "Improved Grounding",
                "rebuttal": "Latency overhead degrades real-time user experience.",
                "evidence": ["Retrieval adds 450ms latency."],
                "confidence": 0.85,
                "document": "paper1.pdf",
                "page": 4,
                "chunk_id": "chunk_02",
            }
        ],
        final_verdict="RAG enhances precision but requires engineering for latency.",
        verdict_confidence=0.88,
        sources=[{"document": "paper1.pdf", "page": 3, "chunk_id": "chunk_01"}],
        proposition="LLMs should adopt retrieval augmented generation in production.",
        agreements=["Both sides acknowledge retrieval introduces architectural trade-offs."],
        disagreements=["Disagreement persists regarding tolerable latency thresholds."],
        unresolved_questions=["Can hybrid caching eliminate the 450ms retrieval overhead?"],
        neutral_assessment="Empirical evidence heavily supports accuracy gains over baseline LLMs.",
        conclusion="Evidence supports RAG effectiveness, though latency considerations remain non-trivial.",
    )
    dumped = resp.model_dump()
    assert dumped["proposition"] == "LLMs should adopt retrieval augmented generation in production."
    assert len(dumped["arguments"]) == 1
    assert len(dumped["rebuttals"]) == 1
    assert dumped["final_verdict"] == "RAG enhances precision but requires engineering for latency."
    assert dumped["sources"][0]["chunk_id"] == "chunk_01"


# ==============================================================================
# 2. PRO/CON ARGUMENT & REBUTTAL GENERATION
# ==============================================================================

def test_pro_con_argument_and_rebuttal_generation():
    """Verify parser correctly extracts Pro and Con arguments, rebuttals, and metadata."""
    engine = DebateEngine()
    sample_json = """{
      "query": "Is microservice architecture superior to monolith?",
      "proposition": "Microservices offer greater scalability than monolithic architectures.",
      "topic": "Microservices vs Monolith Architecture",
      "position_a": "Microservices enhance scalability and modularity",
      "position_b": "Microservices introduce distributed system complexity",
      "opening_statements": {
        "pro": "Microservices enable autonomous team deployment and elastic scaling.",
        "con": "Microservices incur severe network overhead and distributed transaction challenges."
      },
      "arguments": [
        {
          "side": "PRO",
          "title": "Elastic Scaling",
          "argument": "Services scale independently based on demand.",
          "evidence_type": "DIRECT_EVIDENCE",
          "evidence": ["CPU utilization was optimized by 40%."],
          "confidence": 0.90,
          "evidence_strength": "STRONG",
          "document": "arch_study.pdf",
          "page": 12,
          "chunk_id": "chunk_12"
        },
        {
          "side": "CON",
          "title": "Network Latency",
          "argument": "Inter-service RPC calls increase p99 response times.",
          "evidence_type": "DIRECT_EVIDENCE",
          "evidence": ["Distributed tracing showed 35ms RPC overhead."],
          "confidence": 0.87,
          "evidence_strength": "STRONG",
          "document": "arch_study.pdf",
          "page": 15,
          "chunk_id": "chunk_15"
        }
      ],
      "rebuttals": [
        {
          "side": "CON",
          "target_argument": "Elastic Scaling",
          "rebuttal": "Independent scaling comes at the cost of operational infrastructure overhead.",
          "evidence": ["Kubernetes cluster management required dedicated staff."],
          "confidence": 0.83,
          "document": "arch_study.pdf",
          "page": 16,
          "chunk_id": "chunk_16"
        }
      ],
      "agreements": ["Both architectures require disciplined boundary management."],
      "disagreements": ["Dispute over whether organizational autonomy justifies network complexity."],
      "unresolved_questions": ["What team size is the tipping point where microservices become cost-effective?"],
      "neutral_assessment": "Both sides possess strong empirical backing depending on team scale.",
      "conclusion": "Evidence indicates microservices excel for large teams with high scale, but fail small teams.",
      "final_verdict": "Monoliths remain preferable below specific throughput thresholds.",
      "verdict_confidence": 0.86,
      "sources": [{"document": "arch_study.pdf", "page": 12, "chunk_id": "chunk_12"}]
    }"""

    report = engine.parse_response(
        query="Is microservice architecture superior to monolith?",
        position_a="Microservices enhance scalability",
        position_b="Microservices introduce complexity",
        response_text=sample_json,
    )

    assert len(report.arguments) == 2
    assert report.arguments[0].side == DebateSide.POSITION_A
    assert report.arguments[0].evidence_strength == "STRONG"
    assert report.arguments[1].side == DebateSide.POSITION_B
    assert len(report.rebuttals) == 1
    assert report.rebuttals[0].target_argument == "Elastic Scaling"
    assert report.opening_statements.pro != ""
    assert report.opening_statements.con != ""
    assert len(report.agreements) == 1
    assert len(report.disagreements) == 1
    assert len(report.unresolved_questions) == 1


# ==============================================================================
# 3. CITATIONS & ATTRIBUTION (SINGLE & MULTI-PAPER)
# ==============================================================================

def test_single_paper_deterministic_debate():
    """Verify deterministic debate handles a single paper correctly."""
    engine = DebateEngine()
    evidence = [
        {
            "chunk_id": "c1",
            "document": "single_paper.pdf",
            "page": 2,
            "text": "The framework demonstrates superior throughput and achieves 95% accuracy in production environments.",
        },
        {
            "chunk_id": "c2",
            "document": "single_paper.pdf",
            "page": 5,
            "text": "A notable limitation is the high computational cost and memory overhead required during training.",
        },
    ]

    report = engine.build_no_llm_debate(
        query="Does the framework perform well in production?",
        position_a="Framework is highly efficient",
        position_b="Framework has severe resource limitations",
        evidence=evidence,
        document_names=["single_paper.pdf"],
    )

    assert report.partial is True
    assert len(report.arguments) >= 2
    # Check single-paper attribution
    for arg in report.arguments:
        assert arg.document == "single_paper.pdf"
        assert arg.chunk_id in ("c1", "c2")

    # Rebuttals generated
    assert len(report.rebuttals) >= 1
    assert report.neutral_assessment != ""
    assert report.conclusion != ""


def test_multi_paper_deterministic_debate():
    """Verify deterministic debate balances and cites multiple papers."""
    engine = DebateEngine()
    evidence = [
        {
            "chunk_id": "c_alpha",
            "document": "paper_alpha.pdf",
            "page": 4,
            "text": "Our algorithm achieves significant improvement and demonstrates superior convergence rates.",
        },
        {
            "chunk_id": "c_beta",
            "document": "paper_beta.pdf",
            "page": 8,
            "text": "The primary drawback is high memory footprint; the method fails when batch sizes exceed hardware capacity.",
        },
    ]

    report = engine.build_no_llm_debate(
        query="Evaluate algorithm convergence vs memory footprint.",
        position_a="Convergence is superior",
        position_b="Memory footprint causes failures",
        evidence=evidence,
        document_names=["paper_alpha.pdf", "paper_beta.pdf"],
    )

    docs_in_args = {arg.document for arg in report.arguments}
    assert "paper_alpha.pdf" in docs_in_args
    assert "paper_beta.pdf" in docs_in_args
    assert report.partial is True


# ==============================================================================
# 4. MISSING EVIDENCE & UNCERTAINTY HANDLING
# ==============================================================================

def test_missing_evidence_returns_proper_uncertainty():
    """Verify empty evidence results in explicit 'Not found in available sources' and zero confidence."""
    engine = DebateEngine()
    report = engine.build_no_llm_debate(
        query="Are quantum computers replacing classical databases?",
        position_a="Quantum databases are replacing classical",
        position_b="Quantum databases cannot replace classical",
        evidence=[],
    )

    assert "Not found in available sources" in report.final_verdict
    assert report.verdict_confidence == 0.0
    assert len(report.arguments) == 0
    assert report.partial is False


def test_one_sided_evidence_states_unsupported():
    """Verify when evidence only supports one position, the other side is explicitly marked UNSUPPORTED."""
    engine = DebateEngine()
    # Evidence only contains positive findings, zero critical or limitation words
    evidence = [
        {
            "chunk_id": "c_only_pro",
            "document": "sunshine.pdf",
            "page": 1,
            "text": "The model demonstrates optimal accuracy and proves superior across all benchmarks.",
        }
    ]

    report = engine.build_no_llm_debate(
        query="Is the model optimal?",
        position_a="Model is optimal",
        position_b="Model is sub-optimal",
        evidence=evidence,
    )

    # Con position should be explicitly created with UNSUPPORTED / NONE evidence strength
    con_args = [a for a in report.arguments if a.side == DebateSide.POSITION_B]
    assert len(con_args) >= 1
    assert con_args[0].evidence_strength == "NONE"
    assert con_args[0].evidence_type == "UNSUPPORTED"
    assert "do not report explicit limitations" in con_args[0].argument


# ==============================================================================
# 5. MALFORMED / TRUNCATED LLM RESPONSE & REPAIR
# ==============================================================================

def test_malformed_or_truncated_llm_raises_value_error():
    """Verify malformed and incomplete JSON strings raise ValueError cleanly."""
    engine = DebateEngine()

    with pytest.raises(ValueError, match="empty response"):
        engine.parse_response(
            query="test",
            position_a="a",
            position_b="b",
            response_text="",
        )

    with pytest.raises(ValueError, match="invalid JSON"):
        engine.parse_response(
            query="test",
            position_a="a",
            position_b="b",
            response_text="Not a json { broken text",
        )


# ==============================================================================
# 6. RAG SERVICE DEBATE ORCHESTRATION & FALLBACK
# ==============================================================================

def test_rag_service_debate_fallback_on_provider_error():
    """Verify rag_service.run_debate falls back to build_no_llm_debate when LLM fails."""
    from app.llm.base_provider import LLMResponse

    fake_resp = LLMResponse(
        answer="",
        provider="groq",
        model="llama3",
        latency_ms=120.0,
        success=False,
        error="finish_reason=length (token limit hit)",
    )
    sample_ev = [
        {
            "chunk_id": "test_chk",
            "document": "test_doc.pdf",
            "page": 1,
            "text": "The algorithm achieves superior throughput while facing a memory overhead limitation.",
        }
    ]

    with patch.object(rag_service, "_search", return_value=sample_ev), \
         patch.object(rag_service.llm, "generate_structured", return_value=fake_resp):
        report = rag_service.run_debate(
            query="Does the algorithm scale efficiently?",
            position_a="Algorithm scales efficiently",
            position_b="Algorithm does not scale efficiently",
            document_names=["test_doc.pdf"],
        )

    assert report.partial is True
    assert "generated deterministically" in (report.notice or "")
    assert len(report.arguments) >= 2
    assert report.arguments[0].document == "test_doc.pdf"
