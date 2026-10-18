"""
Unit and integration tests for Srinidhi's Reasoning Engine.
Tests decomposition, evidence validation/deduplication, insufficient evidence,
prompt generation, and end-to-end reasoning pipeline.
"""

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
