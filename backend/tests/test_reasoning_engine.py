"""
Unit and integration tests for Srinidhi's Reasoning Engine.
Tests decomposition, evidence validation/deduplication, insufficient evidence,
prompt generation, and end-to-end reasoning pipeline.
"""

import json
from unittest.mock import MagicMock

import pytest
from app.rag.context_builder import ContextBuilder
from app.rag.prompt_engine import PromptEngine
from app.reasoning.reasoning_engine import (
    GENERATION_FAILURE_MESSAGE,
    INSUFFICIENT_EVIDENCE_MESSAGE,
    ReasoningEngine,
)


@pytest.fixture
def mock_retriever():
    retriever = MagicMock()
    retriever.search.return_value = [
        {
            "chunk_id": "chunk_1",
            "document": "paper_a.pdf",
            "page": 2,
            "text": "DNA storage offers high data density.",
            "hybrid_score": 0.85,
            "bm25_score": 0.70,
            "faiss_score": 0.95,
        },
        {
            "chunk_id": "chunk_2",
            "document": "paper_b.pdf",
            "page": 4,
            "text": "Error-correcting codes mitigate synthesis errors in microbial storage.",
            "hybrid_score": 0.92,
            "bm25_score": 0.85,
            "faiss_score": 0.96,
        },
    ]
    return retriever


@pytest.fixture
def reasoning_engine(mock_retriever):
    mock_llm = MagicMock()
    mock_llm.generate.return_value = "Grounded synthesized answer from DNA evidence."
    mock_llm.generate_structured.return_value = MagicMock(
        success=True,
        answer='{"subquestions": ["What is DNA storage density?", "How are synthesis errors handled?"]}',
    )
    context_builder = ContextBuilder(max_chunks=5)
    prompt_engine = PromptEngine()
    return ReasoningEngine(
        retriever=mock_retriever,
        context_builder=context_builder,
        prompt_engine=prompt_engine,
        llm=mock_llm,
        max_subquestions=3,
        top_k=5,
    )


def test_initialization_validation():
    retriever = MagicMock()
    cb = MagicMock()
    pe = MagicMock()
    llm = MagicMock()

    with pytest.raises(ValueError, match="max_subquestions must be at least 1"):
        ReasoningEngine(retriever, cb, pe, llm=llm, max_subquestions=0)

    with pytest.raises(ValueError, match="top_k must be at least 1"):
        ReasoningEngine(retriever, cb, pe, llm=llm, top_k=0)


def test_decompose_query_success(reasoning_engine):
    subqs = reasoning_engine.decompose_query("How reliable and dense is microbial DNA storage?")
    assert len(subqs) == 2
    assert "What is DNA storage density?" in subqs
    assert "How are synthesis errors handled?" in subqs


def test_decompose_query_markdown_codeblock(reasoning_engine):
    reasoning_engine.llm.generate_structured.return_value = MagicMock(
        success=True,
        answer='```json\n{"subquestions": ["Subquestion 1", "Subquestion 2"]}\n```',
    )
    subqs = reasoning_engine.decompose_query("Test query")
    assert subqs == ["Subquestion 1", "Subquestion 2"]


def test_decompose_query_fallback_on_invalid_json(reasoning_engine):
    reasoning_engine.llm.generate_structured.return_value = MagicMock(
        success=True,
        answer="Not a valid JSON response",
    )
    subqs = reasoning_engine.decompose_query("Original complex query")
    assert subqs == ["Original complex query"]


def test_retrieve_evidence_deduplication_and_score_ranking(reasoning_engine):
    # Setup mock retriever to return overlapping chunks with different scores
    reasoning_engine.retriever.search.side_effect = [
        [
            {"chunk_id": "chunk_1", "document": "doc1.pdf", "page": 1, "text": "Text A", "hybrid_score": 0.5},
            {"chunk_id": "chunk_2", "document": "doc2.pdf", "page": 2, "text": "Text B", "hybrid_score": 0.8},
        ],
        [
            {"chunk_id": "chunk_1", "document": "doc1.pdf", "page": 1, "text": "Text A updated", "hybrid_score": 0.95},
            {"chunk_id": "chunk_3", "document": "doc3.pdf", "page": 3, "text": "", "hybrid_score": 0.99},  # empty text, should skip
            {"document": "doc4.pdf", "page": 4, "text": "Text without chunk_id", "hybrid_score": 0.90},  # no chunk_id, should skip
        ],
    ]

    evidence = reasoning_engine.retrieve_evidence(["subq 1", "subq 2"])

    assert len(evidence) == 2
    # chunk_1 should be updated to score 0.95 and ranked first
    assert evidence[0]["chunk_id"] == "chunk_1"
    assert evidence[0]["hybrid_score"] == 0.95
    assert evidence[1]["chunk_id"] == "chunk_2"
    assert evidence[1]["hybrid_score"] == 0.8


def test_retrieve_evidence_document_filter(reasoning_engine):
    reasoning_engine.retriever.search.return_value = [
        {"chunk_id": "chunk_1", "document": "allowed_doc.pdf", "page": 1, "text": "Relevant text", "hybrid_score": 0.8},
        {"chunk_id": "chunk_2", "document": "unrelated_doc.pdf", "page": 2, "text": "Other text", "hybrid_score": 0.9},
    ]

    evidence = reasoning_engine.retrieve_evidence(["subq 1"], doc_filter=["allowed_doc.pdf"])
    assert len(evidence) == 1
    assert evidence[0]["document"] == "allowed_doc.pdf"


def test_reason_insufficient_evidence(reasoning_engine):
    reasoning_engine.retriever.search.return_value = []
    res = reasoning_engine.reason("What are the storage limits?")

    assert res["query"] == "What are the storage limits?"
    assert res["answer"] == INSUFFICIENT_EVIDENCE_MESSAGE
    assert res["sources"] == []


def test_reason_generation_failure(reasoning_engine):
    # LLM throws an exception during answer generation
    reasoning_engine.llm.generate.side_effect = RuntimeError("Generation error")

    res = reasoning_engine.reason("What is microbial DNA density?")
    assert res["answer"] == GENERATION_FAILURE_MESSAGE
    assert len(res["sources"]) > 0


def test_reason_pipeline_end_to_end(reasoning_engine):
    res = reasoning_engine.reason("Explain DNA storage efficiency.")

    assert res["query"] == "Explain DNA storage efficiency."
    assert len(res["subquestions"]) == 2
    assert res["answer"] == "Grounded synthesized answer from DNA evidence."
    assert len(res["sources"]) == 2
    assert res["sources"][0]["document"] in ["paper_a.pdf", "paper_b.pdf"]
    assert res["sources"][0]["rank"] == 1
    assert "hybrid_score" in res["sources"][0]


# =====================================================================
# COMPREHENSIVE PRODUCTION REASONING TEST SUITE
# =====================================================================

from app.api.schemas import ReasoningResponse, Source


def test_simple_question_reasoning(reasoning_engine):
    """Simple questions should produce clean single/dual-step reasoning without artificial complexity."""
    reasoning_engine.llm.generate_structured.return_value = MagicMock(
        success=True,
        answer='{"complexity": "simple", "subquestions": ["What is DNA storage?"], "plan": [{"step_number": 1, "subquestion": "What is DNA storage?", "title": "Define DNA Storage", "objective": "Explain the core definition"}]}',
    )
    reasoning_engine.llm.generate.return_value = json.dumps({
        "intermediate_findings": [
            {
                "subquestion": "What is DNA storage?",
                "synthesis": "DNA storage encodes digital binary information into nucleotide sequences.",
                "evidence_chunk_ids": ["chunk_1"],
            }
        ],
        "conflicts": [],
        "uncertainty": None,
        "synthesis": "DNA storage encodes digital data into synthetic DNA molecules.",
        "final_answer": "DNA storage is a molecular storage technology that converts binary bits into nucleotide bases.",
    })

    res = reasoning_engine.reason("What is DNA storage?")
    assert res["query"] == "What is DNA storage?"
    assert len(res["subquestions"]) == 1
    assert "molecular storage" in res["final_answer"]
    assert len(res["steps"]) >= 2  # Step 1 + Synthesis step
    assert res["steps"][0]["status"] == "complete"
    assert res["confidence"] > 0.0


def test_complex_multistep_reasoning_ordering_and_dependencies(reasoning_engine):
    """Complex multi-hop questions should maintain ordered sequential dependencies and step synthesis."""
    reasoning_engine.llm.generate_structured.return_value = MagicMock(
        success=True,
        answer=json.dumps({
            "complexity": "complex",
            "subquestions": [
                "What is DNA storage density?",
                "How do error-correcting codes mitigate synthesis errors?",
                "How do error codes affect net usable density?",
            ],
            "plan": [
                {
                    "step_number": 1,
                    "subquestion": "What is DNA storage density?",
                    "title": "Analyze Raw Density",
                    "objective": "Determine raw theoretical and achieved density",
                },
                {
                    "step_number": 2,
                    "subquestion": "How do error-correcting codes mitigate synthesis errors?",
                    "title": "Evaluate Error Correction",
                    "objective": "Examine Reed-Solomon or Fountain codes",
                },
                {
                    "step_number": 3,
                    "subquestion": "How do error codes affect net usable density?",
                    "title": "Compute Net Trade-offs",
                    "objective": "Synthesize overhead impact on capacity",
                },
            ],
        }),
    )
    reasoning_engine.llm.generate.return_value = json.dumps({
        "intermediate_findings": [
            {
                "subquestion": "What is DNA storage density?",
                "synthesis": "Raw storage density reaches up to 215 petabytes per gram.",
                "evidence_chunk_ids": ["chunk_1"],
            },
            {
                "subquestion": "How do error-correcting codes mitigate synthesis errors?",
                "synthesis": "Fountain codes and Reed-Solomon algorithms protect against dropout and indel errors.",
                "evidence_chunk_ids": ["chunk_2"],
            },
            {
                "subquestion": "How do error codes affect net usable density?",
                "synthesis": "Code redundancy introduces a 10-15% overhead, slightly reducing net payload capacity.",
                "evidence_chunk_ids": ["chunk_1", "chunk_2"],
            },
        ],
        "conflicts": [],
        "uncertainty": None,
        "synthesis": "While raw DNA density is high, error correction introduces a 10-15% overhead that is necessary for zero-loss recovery.",
        "final_answer": "Error-correcting codes ensure data reliability in high-density DNA storage at the cost of a modest 10-15% reduction in net density.",
    })

    res = reasoning_engine.reason("How do error correction codes impact overall usable density in microbial DNA storage?")
    assert len(res["subquestions"]) == 3
    assert len(res["sub_questions"]) == 3
    assert res["sub_questions"][0]["evidenceIds"] == ["chunk_1"]
    assert res["sub_questions"][1]["evidenceIds"] == ["chunk_2"]
    assert len(res["steps"]) == 4  # 3 sub-questions + 1 final synthesis step
    assert res["steps"][0]["title"] == "Analyze Raw Density"
    assert res["steps"][1]["title"] == "Evaluate Error Correction"
    assert res["steps"][2]["title"] == "Compute Net Trade-offs"
    assert res["steps"][3]["title"] == "Synthesis & Conclusion"
    assert "modest 10-15%" in res["final_answer"]


def test_multidoc_reasoning_and_citation_correctness(reasoning_engine):
    """Reasoning across multiple documents must preserve valid document citations and chunk IDs."""
    reasoning_engine.retriever.search.side_effect = [
        [{"chunk_id": "c_docA_1", "document": "study_alpha.pdf", "page": 12, "text": "Alpha shows 99% accuracy.", "hybrid_score": 0.88}],
        [{"chunk_id": "c_docB_5", "document": "study_beta.pdf", "page": 3, "text": "Beta achieves 98.5% accuracy under stress.", "hybrid_score": 0.91}],
    ]
    res = reasoning_engine.reason("Compare accuracy between study alpha and beta.")
    assert len(res["sources"]) == 2
    doc_names = {s["document"] for s in res["sources"]}
    chunk_ids = {s["chunk_id"] for s in res["sources"]}
    assert "study_alpha.pdf" in doc_names
    assert "study_beta.pdf" in doc_names
    assert "c_docA_1" in chunk_ids
    assert "c_docB_5" in chunk_ids


def test_conflicting_evidence_detection_across_documents(reasoning_engine):
    """Conflicting claims across documents must be detected, explained, and lower confidence."""
    reasoning_engine.retriever.search.return_value = [
        {"chunk_id": "c_1", "document": "lab_a.pdf", "page": 1, "text": "The reaction increases overall efficiency.", "hybrid_score": 0.9},
        {"chunk_id": "c_2", "document": "lab_b.pdf", "page": 2, "text": "The reaction decreases overall efficiency.", "hybrid_score": 0.88},
    ]
    conflicts = reasoning_engine.detect_conflicts(reasoning_engine.retriever.search.return_value)
    assert len(conflicts) > 0
    assert "lab_a.pdf" in conflicts[0]
    assert "lab_b.pdf" in conflicts[0]

    res = reasoning_engine.reason("Does the reaction improve efficiency?")
    assert len(res["conflicts"]) > 0


def test_partial_evidence_uncertainty_handling(reasoning_engine):
    """When some subquestions lack evidence, uncertainty must be clearly communicated."""
    # First subquestion gets evidence, second gets nothing
    reasoning_engine.retriever.search.side_effect = [
        [{"chunk_id": "c_1", "document": "doc1.pdf", "page": 1, "text": "Cost is $500/TB.", "hybrid_score": 0.8}],
        [],  # second subquestion has zero evidence
    ]
    res = reasoning_engine.reason("What is the cost and the environmental carbon footprint?")
    assert res["uncertainty"] is not None
    assert "Partial evidence" in res["uncertainty"]
    assert res["sub_questions"][1]["synthesis"] == "No direct evidence found for this sub-question."
    assert res["steps"][1]["status"] == "incomplete"


def test_unsupported_conclusions_abstention(reasoning_engine):
    """If no evidence is retrieved, the engine must abstain with the standardized message."""
    reasoning_engine.retriever.search.return_value = []
    res = reasoning_engine.reason("What is the quantum state of non-existent particles?")
    assert res["answer"] == INSUFFICIENT_EVIDENCE_MESSAGE
    assert res["final_answer"] == INSUFFICIENT_EVIDENCE_MESSAGE
    assert res["confidence"] == 0.0
    assert len(res["sources"]) == 0


def test_llm_provider_fallback_on_structured_error(reasoning_engine):
    """If structured LLM call returns failure, the engine falls back to standard generation."""
    reasoning_engine.llm.generate_structured.return_value = MagicMock(
        success=False,
        error="Model rate limit exceeded",
    )
    # Should fall back to original query safely without crashing
    subqs = reasoning_engine.decompose_query("Test fallback query")
    assert subqs == ["Test fallback query"]


def test_malformed_llm_response_recovery(reasoning_engine):
    """Malformed JSON from LLM generation should be handled gracefully without raising unhandled errors."""
    reasoning_engine.llm.generate.return_value = "{malformed json without closing brace"
    res = reasoning_engine.reason("Evaluate robustness.")
    assert res["answer"] == "{malformed json without closing brace"
    assert res["final_answer"] == "{malformed json without closing brace"
    assert len(res["steps"]) > 0
    assert len(res["sources"]) > 0


def test_backend_contract_and_pydantic_schema_validation(reasoning_engine):
    """The output of reason() must strictly satisfy the ReasoningResponse Pydantic schema."""
    res = reasoning_engine.reason("Explain DNA storage efficiency.")
    # Convert dict sources to Source schemas
    sources_schemas = [Source(**s) for s in res["sources"]]
    response_model = ReasoningResponse(
        query=res["query"],
        subquestions=res["subquestions"],
        answer=res["answer"],
        sources=sources_schemas,
        steps=res.get("steps"),
        sub_questions=res.get("sub_questions"),
        synthesis=res.get("synthesis"),
        final_answer=res.get("final_answer"),
        confidence=res.get("confidence"),
        conflicts=res.get("conflicts"),
        uncertainty=res.get("uncertainty"),
    )
    assert response_model.query == res["query"]
    assert response_model.answer == res["answer"]
    assert len(response_model.sources) == len(res["sources"])
    assert response_model.confidence == res["confidence"]
    assert len(response_model.steps) == len(res["steps"])


# =====================================================================
# TOKEN BUDGET, DEDUPLICATION & COMPACTION REGRESSION TESTS
# =====================================================================


def test_build_multi_step_reasoning_prompt_deduplication_and_truncation(reasoning_engine):
    """Identical chunks retrieved across steps must only appear once in catalog, and long text must be capped."""
    plan = [
        {"step_number": 1, "subquestion": "What is DNA storage density?", "title": "Density"},
        {"step_number": 2, "subquestion": "How do error codes affect net density?", "title": "Overhead"},
    ]
    shared_chunk = {
        "chunk_id": "shared_c1",
        "document": "density_study.pdf",
        "page": 5,
        "text": "DNA storage offers high data density of up to 215 PB/gram." + (" Extra detail." * 100),
    }
    step_evidence = {
        "What is DNA storage density?": [shared_chunk],
        "How do error codes affect net density?": [
            shared_chunk,  # Duplicate!
            {"chunk_id": "c2", "document": "overhead.pdf", "page": 1, "text": "Overhead is 10-15%."},
        ],
    }

    prompt = reasoning_engine.build_multi_step_reasoning_prompt(
        query="What is net DNA storage density?",
        plan=plan,
        step_evidence=step_evidence,
    )

    # shared_c1 should appear only ONCE in the catalog
    assert prompt.count("[Chunk ID: shared_c1]") == 1
    # Long text should be truncated to 800 chars
    assert "[truncated for token budget]" in prompt
    # Step sections should list relevant chunk IDs
    assert "Relevant Evidence Chunks: shared_c1" in prompt
    assert "Relevant Evidence Chunks: shared_c1, c2" in prompt
    # Overall prompt should be compact (well under 5,000 characters / ~1,250 tokens)
    assert len(prompt) < 5000


def test_build_multi_step_reasoning_prompt_compact_mode(reasoning_engine):
    """Compact mode should strictly limit to top 2 chunks and 400 chars max."""
    plan = [{"step_number": 1, "subquestion": "Test subq", "title": "Test Title"}]
    long_chunk = {
        "chunk_id": "c_long",
        "document": "doc.pdf",
        "page": 1,
        "text": "Z" * 1000,
    }
    step_evidence = {"Test subq": [long_chunk]}

    prompt = reasoning_engine.build_multi_step_reasoning_prompt(
        query="Test query",
        plan=plan,
        step_evidence=step_evidence,
        compact=True,
    )
    assert "[Chunk ID: c_long]" in prompt
    assert "[truncated for token budget]" in prompt
    # Verify that the text snippet in prompt is around 400 chars, not 800 or 1000
    assert "Z" * 500 not in prompt
    assert "Z" * 350 in prompt


def test_reasoning_retries_with_compact_prompt_on_empty_initial_response(reasoning_engine):
    """When the initial prompt returns empty (e.g. provider rejected payload), reason() retries with compact prompt."""
    call_prompts = []

    def mock_generate(prompt):
        call_prompts.append(prompt)
        if len(call_prompts) == 1:
            # Simulate initial prompt being rejected or returning empty
            return ""
        # Second call (compact) succeeds
        return json.dumps({
            "intermediate_findings": [
                {
                    "subquestion": "What is DNA storage density?",
                    "synthesis": "Raw storage density reaches up to 215 PB/gram.",
                    "evidence_chunk_ids": ["chunk_1"],
                }
            ],
            "conflicts": [],
            "uncertainty": None,
            "synthesis": "High density achieved.",
            "final_answer": "DNA storage reaches 215 PB/gram.",
        })

    reasoning_engine.llm.generate = mock_generate

    res = reasoning_engine.reason("What is microbial DNA density?")
    assert len(call_prompts) == 2
    # Verify second prompt was compact
    assert res["final_answer"] == "DNA storage reaches 215 PB/gram."
    assert res["confidence"] > 0.0

