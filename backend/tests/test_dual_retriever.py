"""
Tests for Dual Retriever with Comparison Layer (Task A8)

Acceptance Criteria:
- a document statement contradicting a fixture Wikipedia passage -> disagree with both quotes
- scope "document only" never calls connectors
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from app.api.schemas import AnswerRequest, AnswerResponse, ComparisonPair
from app.connectors.wikipedia import _summary_to_chunk
from app.rag.dual_retriever import (
    ComparisonPair as DualComparisonPair,
    DualResult,
    DualRetriever,
    _build_doc_section,
    _build_summary,
    _build_web_section,
    classify_nli_pair,
    web_chunk_to_source_dict,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def wikipedia_fixture_chunk() -> dict:
    """Load the Wikipedia summary fixture and convert to a chunk dict."""
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "wikipedia_summary.json"
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    chunk = _summary_to_chunk(data)
    assert chunk is not None
    return chunk.to_dict()


class MockRetriever:
    """Mock document retriever returning caller-specified chunks."""

    def __init__(self, doc_chunks: list[dict] | None = None) -> None:
        self.doc_chunks = doc_chunks or []
        self.last_query = None
        self.last_kwargs = None

    def search(self, query: str, **kwargs) -> list[dict]:
        self.last_query = query
        self.last_kwargs = kwargs
        return self.doc_chunks


# ---------------------------------------------------------------------------
# 1. Acceptance Criterion: Contradicting document statement -> disagree with both quotes
# ---------------------------------------------------------------------------

class TestContradictionWithWikipediaFixture:
    def test_document_contradicting_wikipedia_fixture_yields_disagree_with_both_quotes(
        self, wikipedia_fixture_chunk: dict
    ):
        """
        Document statement asserts that transformers are strictly sequential RNNs
        and do not use multi-head attention.
        Wikipedia fixture states transformers use multi-head attention and process
        sequences simultaneously unlike RNNs.
        Must produce label='disagree' and contain both verbatim quotes.
        """
        # Contradicting document passage
        doc_passage = {
            "document": "rnn_paper.pdf",
            "page": 2,
            "chunk_id": "chunk_rnn_01",
            "text": (
                "Transformers do not process entire sequences simultaneously and are not "
                "based on the multi-head attention mechanism. In contrast to modern claims, "
                "transformers are strictly sequential recurrent neural networks that fail to "
                "enable parallelizable training."
            ),
            "hybrid_score": 0.95,
        }

        mock_retriever = MockRetriever(doc_chunks=[doc_passage])
        dr = DualRetriever(retriever=mock_retriever)

        # Patch _fetch_web_chunks to return the Wikipedia fixture chunk
        with patch(
            "app.rag.dual_retriever._fetch_web_chunks",
            return_value=(
                [wikipedia_fixture_chunk],
                [{"connector": "wikipedia", "outcome": "ok", "count": 1, "detail": ""}],
            ),
        ):
            result = dr.dual_retrieve(
                query="How do transformers process sequence data?",
            )

        assert isinstance(result, DualResult)
        assert len(result.comparison) >= 1

        pair = result.comparison[0]
        assert pair.label == "disagree"
        assert len(pair.doc_quote.strip()) > 0
        assert len(pair.web_quote.strip()) > 0

        # Quotes must come verbatim from the passages
        assert pair.doc_quote in doc_passage["text"]
        assert pair.web_quote in wikipedia_fixture_chunk["text"]

        # Citations must reflect sources
        assert "rnn_paper.pdf" in pair.doc_source
        assert "p.2" in pair.doc_source
        assert "chunk_rnn_01" in pair.doc_source
        assert "https://en.wikipedia.org/wiki/" in pair.web_source

    def test_agreeing_document_statement_yields_agree(
        self, wikipedia_fixture_chunk: dict
    ):
        """Document statement agreeing with Wikipedia fixture yields 'agree'."""
        doc_passage = {
            "document": "attention_paper.pdf",
            "page": 1,
            "chunk_id": "c1",
            "text": (
                "A transformer is a deep learning architecture based on the multi-head attention "
                "mechanism. Similar to the original work, transformers process entire sequences "
                "simultaneously using self-attention, making them highly parallelizable and efficient."
            ),
        }

        mock_retriever = MockRetriever(doc_chunks=[doc_passage])
        dr = DualRetriever(retriever=mock_retriever)

        with patch(
            "app.rag.dual_retriever._fetch_web_chunks",
            return_value=(
                [wikipedia_fixture_chunk],
                [{"connector": "wikipedia", "outcome": "ok", "count": 1, "detail": ""}],
            ),
        ):
            result = dr.dual_retrieve(query="What is a transformer architecture?")

        assert len(result.comparison) >= 1
        assert result.comparison[0].label == "agree"


# ---------------------------------------------------------------------------
# 2. Acceptance Criterion: Scope "document only" never calls connectors
# ---------------------------------------------------------------------------

class TestScopeEnforcement:
    def test_scope_document_only_string_never_calls_connectors(self):
        """When scope='document only', connectors are never called."""
        doc_passage = {
            "document": "doc1.pdf",
            "page": 1,
            "chunk_id": "c1",
            "text": "Internal document evidence about system architecture.",
        }
        mock_retriever = MockRetriever(doc_chunks=[doc_passage])
        dr = DualRetriever(retriever=mock_retriever)

        with patch("app.rag.dual_retriever._fetch_web_chunks") as mock_web_fetch:
            result = dr.dual_retrieve(
                query="What is the system architecture?",
                scope="document only",
            )
            mock_web_fetch.assert_not_called()

        assert result.web_section is None
        assert result.web_sources == []
        assert result.doc_section is not None
        assert "doc1.pdf" in result.doc_section

    def test_doc_only_flag_never_calls_connectors(self):
        """When doc_only=True, connectors are never called."""
        mock_retriever = MockRetriever(doc_chunks=[{"document": "d.pdf", "text": "Some text"}])
        dr = DualRetriever(retriever=mock_retriever)

        with patch("app.rag.dual_retriever._fetch_web_chunks") as mock_web_fetch:
            result = dr.dual_retrieve(
                query="Some query",
                doc_only=True,
            )
            mock_web_fetch.assert_not_called()

        assert result.web_section is None
        assert result.web_sources == []

    def test_case_insensitive_scope_document_only(self):
        """Scope matching handles case-insensitivity ('DOCUMENT ONLY', 'Document Only')."""
        mock_retriever = MockRetriever(doc_chunks=[{"document": "d.pdf", "text": "Text"}])
        dr = DualRetriever(retriever=mock_retriever)

        with patch("app.rag.dual_retriever._fetch_web_chunks") as mock_web_fetch:
            dr.dual_retrieve(query="Q", scope="DOCUMENT ONLY")
            dr.dual_retrieve(query="Q", scope="Document Only")
            mock_web_fetch.assert_not_called()


# ---------------------------------------------------------------------------
# 3. Section and citation formatting
# ---------------------------------------------------------------------------

class TestSectionAndCitationFormatting:
    def test_doc_section_contains_page_and_chunk(self):
        chunks = [
            {
                "document": "neurips_2024.pdf",
                "page": 5,
                "chunk_id": "chunk_88",
                "text": "Empirical results show a 2.5x speedup across benchmarks.",
            }
        ]
        doc_sec = _build_doc_section(chunks)
        assert "[Source: neurips_2024.pdf, p.5, §chunk_88]" in doc_sec
        assert "2.5x speedup" in doc_sec

    def test_web_section_contains_url_and_retrieved_at(self):
        chunks = [
            {
                "title": "Wikipedia: Quantum Computing",
                "url": "https://en.wikipedia.org/wiki/Quantum_computing",
                "text": "Quantum computing is a rapidly-emerging technology.",
                "retrieved_at": "2026-10-24T23:00:00Z",
            }
        ]
        web_sec = _build_web_section(chunks)
        assert "[Wikipedia: Quantum Computing](https://en.wikipedia.org/wiki/Quantum_computing)" in web_sec
        assert "(fetched 2026-10-24)" in web_sec

    def test_summary_max_three_sentences_and_expandable_detail(self):
        doc_sec = (
            "Sentence one about transformers. Sentence two about attention. "
            "Sentence three about scalability. Sentence four about pretraining. "
            "Sentence five about fine-tuning."
        )
        web_sec = (
            "Sentence six from web source. Sentence seven about open-source models."
        )
        summary = _build_summary(doc_sec, web_sec)
        # Summary must contain at most 3 sentences
        sentences = [s for s in summary.split(".") if s.strip()]
        assert len(sentences) <= 3

        dr_result = DualResult(
            query="Q",
            doc_section=doc_sec,
            web_section=web_sec,
            summary=summary,
            detail=f"{doc_sec}\n\n{web_sec}",
        )
        assert len(dr_result.detail) > len(dr_result.summary)
        assert "Sentence one" in dr_result.detail
        assert "Sentence seven" in dr_result.detail


# ---------------------------------------------------------------------------
# 4. Live fetch timestamp verification
# ---------------------------------------------------------------------------

class TestLiveFetchTimestamp:
    def test_web_text_retrieved_at_is_set_live(self):
        """Verify that web chunks are stamped with a live UTC ISO 8601 timestamp."""
        before = datetime.now(timezone.utc)

        # Mock connector that returns chunks without retrieved_at
        class FakeConnector:
            @staticmethod
            def search(query, n):
                from app.connectors._base import Chunk
                return [
                    Chunk(
                        id="fake:1",
                        text="Some web text.",
                        title="Fake Web",
                        authors=[],
                        year=2024,
                        venue="Web",
                        doi=None,
                        url="https://example.com/fake",
                        origin="web",
                        retrieved_at="2000-01-01T00:00:00Z",  # Stale timestamp
                        content_hash="abc",
                    )
                ]

        from app.rag.dual_retriever import _fetch_web_chunks
        with patch("app.rag.dual_retriever._load_connectors", return_value=[FakeConnector]):
            chunks, _statuses = _fetch_web_chunks("query", n_per=1)

        after = datetime.now(timezone.utc)

        assert len(chunks) == 1
        retrieved_at_str = chunks[0]["retrieved_at"]
        assert retrieved_at_str is not None
        # Parse timestamp and verify it is strictly current
        retrieved_dt = datetime.fromisoformat(retrieved_at_str)
        assert before <= retrieved_dt <= after


# ---------------------------------------------------------------------------
# 5. Schema and endpoint compatibility
# ---------------------------------------------------------------------------

class TestSchemaCompatibility:
    def test_answer_response_schema_validation(self):
        pair = ComparisonPair(
            sub_question="Does X work?",
            label="disagree",
            doc_quote="Doc says no.",
            web_quote="Web says yes.",
            doc_source="doc.pdf p.1 §c1",
            web_source="https://wiki.org/x",
            nli_entail=0.05,
            nli_contra=0.92,
        )
        resp = AnswerResponse(
            summary="Brief summary.",
            detail="Full detail.",
            doc_section="Doc section.",
            web_section="Web section.",
            comparison=[pair],
            sources=[],
        )
        dump = resp.model_dump()
        assert dump["summary"] == "Brief summary."
        assert len(dump["comparison"]) == 1
        assert dump["comparison"][0]["label"] == "disagree"
        assert dump["comparison"][0]["doc_quote"] == "Doc says no."
        assert dump["comparison"][0]["web_quote"] == "Web says yes."

    def test_answer_request_schema(self):
        req = AnswerRequest(
            query="Tell me about transformers",
            document_names=["paper1.pdf"],
            scope="document only",
        )
        assert req.query == "Tell me about transformers"
        assert req.document_names == ["paper1.pdf"]
        assert req.scope == "document only"
