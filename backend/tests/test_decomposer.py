"""
Tests for Task A4 – Query Decomposer with Sufficiency Checking

All tests use fake LLMs and fake retrievers — no real API calls, no numpy.

Coverage:
  - decompose()   : happy path, LLM failure fallback, JSON parse fallback
  - _compute_n_r(): DOI dedup, title dedup, score extraction (all score types)
  - _classify_status(): sufficient / weak / insufficient boundaries
  - solve_sub_question(): each status path; max-round cap; reformulation called
  - run_decomposition(): gaps populated; trace round count; no sentence for gap
  - _extract_json(): fence stripping, embedded-JSON extraction
  - _reformulate(): success and failure paths
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Import module under test — pure Python, no numpy required
# ---------------------------------------------------------------------------
from app.rag.decomposer import (
    DecompositionTrace,
    RetrievalRound,
    SubQuestionResult,
    _classify_status,
    _compute_n_r,
    _extract_json,
    _reformulate,
    decompose,
    run_decomposition,
    solve_sub_question,
)


# ---------------------------------------------------------------------------
# Fake helpers
# ---------------------------------------------------------------------------

@dataclass
class FakeLLMResponse:
    answer: str
    success: bool = True
    error: str = ""
    provider: str = "fake"
    model: str = "fake-model"


class FakeLLM:
    """Configurable fake LLM — responds with fixed JSON strings."""

    def __init__(self, answers: list[str | None]):
        """
        answers: list consumed one-by-one per generate() call.
        None means the call fails (success=False).
        """
        self._answers = iter(answers)

    def generate(self, prompt: str, system: str | None = None) -> FakeLLMResponse:
        try:
            ans = next(self._answers)
        except StopIteration:
            ans = None
        if ans is None:
            return FakeLLMResponse(answer="", success=False, error="exhausted")
        return FakeLLMResponse(answer=ans, success=True)


class FakeRetriever:
    """Returns pre-set chunks for any query."""

    def __init__(self, chunks: list[dict]):
        self._chunks = chunks
        self.calls: list[str] = []   # queries received

    def search(self, query: str, top_k: int = 10) -> list[dict]:
        self.calls.append(query)
        return self._chunks[:top_k]


def _chunk(chunk_id: str, doi: str = "", title: str = "",
           reranker_score: float | None = None,
           hybrid_score: float | None = None,
           rank: int | None = None) -> dict:
    """Build a minimal chunk dict for testing."""
    c: dict = {"chunk_id": chunk_id, "text": f"Text for {chunk_id}.",
               "document": "doc.pdf", "page": 1}
    if doi:
        c["doi"] = doi
    if title:
        c["title"] = title
    if reranker_score is not None:
        c["reranker_score"] = reranker_score
    if hybrid_score is not None:
        c["hybrid_score"] = hybrid_score
    if rank is not None:
        c["rank"] = rank
    return c


# ---------------------------------------------------------------------------
# 1. decompose()
# ---------------------------------------------------------------------------

class TestDecompose:
    def test_happy_path_returns_sub_questions(self):
        llm = FakeLLM(['{"sub_questions": ["What is BERT?", "How does attention work?"]}'])
        result = decompose("Explain transformers.", llm)
        assert result == ["What is BERT?", "How does attention work?"]

    def test_capped_at_max_subqs(self, monkeypatch):
        monkeypatch.setattr("app.rag.decomposer.DECOMPOSE_MAX_SUBQS", 2)
        ans = '{"sub_questions": ["Q1", "Q2", "Q3", "Q4", "Q5"]}'
        llm = FakeLLM([ans])
        result = decompose("Big question.", llm)
        assert len(result) == 2

    def test_llm_failure_falls_back_to_original(self):
        llm = FakeLLM([None])   # simulate failure
        result = decompose("What is RAG?", llm)
        assert result == ["What is RAG?"]

    def test_malformed_json_falls_back(self):
        llm = FakeLLM(["this is not json at all"])
        result = decompose("My query.", llm)
        assert result == ["My query."]

    def test_empty_list_falls_back(self):
        llm = FakeLLM(['{"sub_questions": []}'])
        result = decompose("My query.", llm)
        assert result == ["My query."]

    def test_strips_whitespace_from_sub_questions(self):
        ans = '{"sub_questions": ["  What is DNA?  ", "  How does PCR work? "]}'
        llm = FakeLLM([ans])
        result = decompose("Gene editing.", llm)
        assert result[0] == "What is DNA?"
        assert result[1] == "How does PCR work?"

    def test_markdown_fence_stripped(self):
        ans = '```json\n{"sub_questions": ["Q1"]}\n```'
        llm = FakeLLM([ans])
        result = decompose("Anything.", llm)
        assert result == ["Q1"]


# ---------------------------------------------------------------------------
# 2. _extract_json()
# ---------------------------------------------------------------------------

class TestExtractJson:
    def test_plain_json(self):
        assert _extract_json('{"k": 1}') == {"k": 1}

    def test_json_fence(self):
        assert _extract_json("```json\n{\"a\": 2}\n```") == {"a": 2}

    def test_json_with_prose(self):
        assert _extract_json('Sure! Here: {"x": "y"} done.') == {"x": "y"}

    def test_no_json_raises(self):
        with pytest.raises((ValueError, Exception)):
            _extract_json("no braces here at all")


# ---------------------------------------------------------------------------
# 3. _compute_n_r()
# ---------------------------------------------------------------------------

class TestComputeNR:
    def test_no_chunks_returns_zero(self):
        n, r = _compute_n_r([])
        assert n == 0
        assert r == 0.0

    def test_doi_dedup_counts_one_paper(self):
        chunks = [
            _chunk("c1", doi="10.1234/x", reranker_score=0.0),
            _chunk("c2", doi="10.1234/x", reranker_score=0.0),  # same DOI
        ]
        n, _ = _compute_n_r(chunks)
        assert n == 1

    def test_title_dedup_counts_one_paper(self):
        chunks = [
            _chunk("c1", title="Deep Learning Survey"),
            _chunk("c2", title="Deep Learning Survey"),
        ]
        n, _ = _compute_n_r(chunks)
        assert n == 1

    def test_different_dois_count_separately(self):
        chunks = [
            _chunk("c1", doi="10.1/a"),
            _chunk("c2", doi="10.1/b"),
            _chunk("c3", doi="10.1/c"),
        ]
        n, _ = _compute_n_r(chunks)
        assert n == 3

    def test_reranker_score_sigmoid_clamped(self):
        # sigmoid(100) ≈ 1.0, sigmoid(-100) ≈ 0.0
        chunks = [_chunk("c1", reranker_score=100.0), _chunk("c2", doi="10/b", reranker_score=-100.0)]
        _, r = _compute_n_r(chunks)
        assert 0.0 <= r <= 1.0

    def test_hybrid_score_used_when_no_reranker(self):
        chunks = [_chunk("c1", hybrid_score=0.8, doi="10/a")]
        _, r = _compute_n_r(chunks)
        assert r == pytest.approx(0.8)

    def test_rank_fallback(self):
        chunks = [_chunk("c1", rank=1), _chunk("c2", doi="10/b", rank=2)]
        n, r = _compute_n_r(chunks)
        assert n == 2
        assert r == pytest.approx(0.95)  # (1.0 + 0.9) / 2

    def test_rrf_score_normalised(self):
        # RRF score of 1/61 should normalise to ≈ 1.0
        from app.rag.decomposer import _compute_n_r
        chunks = [{"chunk_id": "c1", "document": "d", "page": 1,
                   "text": "t", "rrf_score": 1.0 / 61}]
        _, r = _compute_n_r(chunks)
        assert 0.9 <= r <= 1.0


# ---------------------------------------------------------------------------
# 4. _classify_status()  (boundary tests)
# ---------------------------------------------------------------------------

class TestClassifyStatus:
    """Test all boundary conditions for n and r against default thresholds."""

    # DECOMPOSE_MIN_PAPERS=2, DECOMPOSE_TAU_R=0.50
    def test_sufficient_exact_boundary(self):
        assert _classify_status(n=2, r=0.50) == "sufficient"

    def test_sufficient_above_boundary(self):
        assert _classify_status(n=5, r=0.99) == "sufficient"

    def test_weak_one_paper_above_half_tau(self):
        assert _classify_status(n=1, r=0.25) == "weak"

    def test_weak_exact_half_tau(self):
        assert _classify_status(n=1, r=0.25) == "weak"

    def test_insufficient_no_papers(self):
        assert _classify_status(n=0, r=0.0) == "insufficient"

    def test_insufficient_low_r(self):
        # n >= 2 but r too low
        assert _classify_status(n=2, r=0.10) == "insufficient"

    def test_insufficient_one_paper_low_r(self):
        # n=1 but r < tau/2
        assert _classify_status(n=1, r=0.10) == "insufficient"

    def test_n1_exactly_half_tau_is_weak(self):
        assert _classify_status(n=1, r=0.25) == "weak"

    def test_n2_r_just_below_tau_but_above_half_is_weak(self):
        # n=2 >= 1 and r=0.499 >= tau/2=0.25 → weak (not sufficient because r < tau)
        assert _classify_status(n=2, r=0.499) == "weak"

    def test_n2_r_below_half_tau_is_insufficient(self):
        # n=2 but r < tau_r/2=0.25 → insufficient
        assert _classify_status(n=2, r=0.10) == "insufficient"


# ---------------------------------------------------------------------------
# 5. solve_sub_question() — status routing
# ---------------------------------------------------------------------------

class TestSolveSubQuestion:

    def _sufficient_retriever(self):
        """Returns 3 chunks from 2 distinct DOIs with high hybrid_score."""
        return FakeRetriever([
            _chunk("c1", doi="10/a", hybrid_score=0.9),
            _chunk("c2", doi="10/b", hybrid_score=0.8),
            _chunk("c3", doi="10/a", hybrid_score=0.7),
        ])

    def _weak_retriever(self):
        """Returns 1 chunk from 1 DOI with moderate score (≥ tau/2 = 0.25)."""
        return FakeRetriever([
            _chunk("c1", doi="10/a", hybrid_score=0.3),
        ])

    def _insufficient_retriever(self):
        """Returns 1 chunk with too-low score."""
        return FakeRetriever([
            _chunk("c1", doi="10/a", hybrid_score=0.05),
        ])

    def _empty_retriever(self):
        return FakeRetriever([])

    # --- sufficient path ---

    def test_sufficient_status_set(self):
        llm = FakeLLM([])
        result = solve_sub_question("What is FAISS?", self._sufficient_retriever(), llm)
        assert result.final_status == "sufficient"
        assert not result.added_to_gaps
        assert len(result.rounds) == 1

    def test_sufficient_returns_chunks(self):
        llm = FakeLLM([])
        result = solve_sub_question("Q", self._sufficient_retriever(), llm)
        assert len(result.chunks) > 0

    def test_sufficient_trace_has_one_round(self):
        llm = FakeLLM([])
        result = solve_sub_question("Q", self._sufficient_retriever(), llm)
        assert result.rounds[0].round_number == 1
        assert result.rounds[0].status == "sufficient"

    # --- weak path ---

    def test_weak_status_set(self):
        llm = FakeLLM([])
        result = solve_sub_question("Q", self._weak_retriever(), llm)
        assert result.final_status == "weak"
        assert not result.added_to_gaps

    def test_weak_not_added_to_gaps(self):
        llm = FakeLLM([])
        result = solve_sub_question("Q", self._weak_retriever(), llm)
        assert not result.added_to_gaps

    # --- insufficient → reformulate → still insufficient → gaps ---

    def test_insufficient_goes_to_gaps(self):
        # LLM returns reformulation JSON each time
        reformulations = ['{"reformulated": "reformulated query v1"}',
                          '{"reformulated": "reformulated query v2"}']
        llm = FakeLLM(reformulations)
        result = solve_sub_question(
            "Unanswerable Q", self._insufficient_retriever(), llm, max_rounds=2
        )
        assert result.final_status == "insufficient"
        assert result.added_to_gaps

    def test_insufficient_max_rounds_respected(self):
        llm = FakeLLM(['{"reformulated": "r1"}', '{"reformulated": "r2"}',
                       '{"reformulated": "r3"}'])
        result = solve_sub_question(
            "Q", self._insufficient_retriever(), llm, max_rounds=2
        )
        assert len(result.rounds) == 2   # capped at max_rounds

    def test_insufficient_reformulation_query_changes(self):
        """Retriever sees different queries across rounds."""
        retriever = self._insufficient_retriever()
        llm = FakeLLM(['{"reformulated": "new query"}'])
        solve_sub_question("original Q", retriever, llm, max_rounds=2)
        assert retriever.calls[0] == "original Q"
        assert retriever.calls[1] == "new query"

    def test_insufficient_no_chunks_returned(self):
        llm = FakeLLM(['{"reformulated": "r"}'])
        result = solve_sub_question("Q", self._empty_retriever(), llm, max_rounds=2)
        assert result.final_status == "insufficient"
        assert result.added_to_gaps

    # --- round numbering ---

    def test_round_numbers_sequential(self):
        llm = FakeLLM(['{"reformulated": "r"}'])
        result = solve_sub_question(
            "Q", self._insufficient_retriever(), llm, max_rounds=2
        )
        assert [rd.round_number for rd in result.rounds] == [1, 2]

    # --- first-round sufficient skips reformulation ---

    def test_sufficient_first_round_no_llm_call(self):
        """LLM should NOT be called if sufficient on round 1."""
        llm_mock = MagicMock()
        retriever = self._sufficient_retriever()
        solve_sub_question("Q", retriever, llm_mock)
        llm_mock.generate.assert_not_called()


# ---------------------------------------------------------------------------
# 6. run_decomposition() — integration
# ---------------------------------------------------------------------------

class TestRunDecomposition:

    def _make_trace(self, sub_qs_json: str, retriever_chunks: list[dict],
                    extra_llm_answers: list[str | None] | None = None) -> DecompositionTrace:
        """Helper: decompose then solve all sub-questions with given retriever."""
        answers = [sub_qs_json] + (extra_llm_answers or [])
        llm = FakeLLM(answers)
        retriever = FakeRetriever(retriever_chunks)
        return run_decomposition("Main query", retriever, llm, max_rounds=2)

    def test_gaps_populated_for_unanswerable(self):
        sub_qs_json = '{"sub_questions": ["Q1"]}'
        # very low score → insufficient in both rounds
        chunks = [_chunk("c1", doi="10/a", hybrid_score=0.02)]
        trace = self._make_trace(
            sub_qs_json, chunks,
            extra_llm_answers=['{"reformulated": "reformulated Q1"}'],
        )
        assert "Q1" in trace.gaps

    def test_no_gaps_when_all_sufficient(self):
        sub_qs_json = '{"sub_questions": ["Q1", "Q2"]}'
        chunks = [
            _chunk("c1", doi="10/a", hybrid_score=0.9),
            _chunk("c2", doi="10/b", hybrid_score=0.8),
        ]
        trace = self._make_trace(sub_qs_json, chunks)
        assert trace.gaps == []

    def test_total_rounds_count(self):
        # 2 sub-questions, each takes 1 round (sufficient)
        sub_qs_json = '{"sub_questions": ["Q1", "Q2"]}'
        chunks = [
            _chunk("c1", doi="10/a", hybrid_score=0.9),
            _chunk("c2", doi="10/b", hybrid_score=0.8),
        ]
        trace = self._make_trace(sub_qs_json, chunks)
        assert trace.total_rounds == 2

    def test_total_rounds_includes_reformulation_rounds(self):
        # 1 sub-question → 2 rounds (insufficient then still insufficient)
        sub_qs_json = '{"sub_questions": ["Q1"]}'
        chunks = [_chunk("c1", doi="10/a", hybrid_score=0.02)]
        trace = self._make_trace(
            sub_qs_json, chunks,
            extra_llm_answers=['{"reformulated": "R1"}'],
        )
        assert trace.total_rounds == 2

    def test_gap_sub_question_has_no_sentence(self):
        """
        Verify that gap sub-questions are tracked but not answerable:
        added_to_gaps=True means generate_grounded should skip them.
        """
        sub_qs_json = '{"sub_questions": ["Unanswerable Q"]}'
        chunks = [_chunk("c1", doi="10/a", hybrid_score=0.01)]
        trace = self._make_trace(
            sub_qs_json, chunks,
            extra_llm_answers=['{"reformulated": "try2"}'],
        )
        gap_results = [r for r in trace.results if r.added_to_gaps]
        assert len(gap_results) == 1
        gap_result = gap_results[0]
        assert gap_result.sub_question == "Unanswerable Q"
        # chunks may be present from last retrieval but status is insufficient
        assert gap_result.final_status == "insufficient"

    def test_trace_to_dict_contains_gaps(self):
        sub_qs_json = '{"sub_questions": ["Q1"]}'
        chunks = [_chunk("c1", doi="10/a", hybrid_score=0.01)]
        trace = self._make_trace(
            sub_qs_json, chunks,
            extra_llm_answers=['{"reformulated": "r"}'],
        )
        d = trace.to_dict()
        assert "gaps" in d
        assert "total_rounds" in d
        assert isinstance(d["results"], list)

    def test_trace_to_dict_round_count_matches(self):
        sub_qs_json = '{"sub_questions": ["Q1"]}'
        chunks = [
            _chunk("c1", doi="10/a", hybrid_score=0.9),
            _chunk("c2", doi="10/b", hybrid_score=0.8),
        ]
        trace = self._make_trace(sub_qs_json, chunks)
        d = trace.to_dict()
        assert d["total_rounds"] == 1

    def test_mixed_results(self):
        """One sufficient, one insufficient → one gap."""
        sub_qs_json = '{"sub_questions": ["Answerable Q", "Unanswerable Q"]}'
        # First search (Answerable Q) → sufficient chunks
        # Second search (Unanswerable Q) → low score
        # But both use same FakeRetriever — we need per-call behaviour
        call_count = 0
        class SmartRetriever:
            def search(self, query, top_k=10):
                nonlocal call_count
                call_count += 1
                if call_count <= 1:   # first sub-question: sufficient
                    return [
                        _chunk("c1", doi="10/a", hybrid_score=0.9),
                        _chunk("c2", doi="10/b", hybrid_score=0.8),
                    ]
                return [_chunk("c3", doi="10/c", hybrid_score=0.02)]  # insufficient

        llm = FakeLLM([
            sub_qs_json,
            '{"reformulated": "better Q"}',   # reformulation for Unanswerable Q
        ])
        trace = run_decomposition("Main", SmartRetriever(), llm, max_rounds=2)
        assert len(trace.gaps) == 1
        assert trace.gaps[0] == "Unanswerable Q"
        assert len([r for r in trace.results if not r.added_to_gaps]) == 1


# ---------------------------------------------------------------------------
# 7. _reformulate()
# ---------------------------------------------------------------------------

class TestReformulate:
    def test_successful_reformulation(self):
        llm = FakeLLM(['{"reformulated": "better query about neural networks"}'])
        result = _reformulate("What is DL?", "What is DL?", llm)
        assert result == "better query about neural networks"

    def test_llm_failure_returns_original(self):
        llm = FakeLLM([None])
        result = _reformulate("Q", "Q", llm)
        assert result == "Q"

    def test_bad_json_returns_original(self):
        llm = FakeLLM(["not json"])
        result = _reformulate("Q", "Q", llm)
        assert result == "Q"

    def test_empty_reformulated_returns_original(self):
        llm = FakeLLM(['{"reformulated": ""}'])
        result = _reformulate("Q", "Q", llm)
        assert result == "Q"


# ---------------------------------------------------------------------------
# 8. Connector search on insufficient
# ---------------------------------------------------------------------------

class TestConnectorSearch:
    def test_connector_called_when_insufficient(self):
        connector_calls = []
        def fake_connector(query, top_k):
            connector_calls.append(query)
            return [
                _chunk("conn_1", doi="10/conn1", hybrid_score=0.9),
                _chunk("conn_2", doi="10/conn2", hybrid_score=0.8),
            ]

        empty_retriever = FakeRetriever([])
        llm = FakeLLM([])
        result = solve_sub_question(
            "Hard sub-question",
            empty_retriever,
            llm,
            max_rounds=2,
            connector_search=fake_connector,
        )
        assert len(connector_calls) >= 1
        assert connector_calls[0] == "Hard sub-question"
        assert result.final_status == "sufficient"
        assert not result.added_to_gaps
        assert any(c["chunk_id"] == "conn_1" for c in result.chunks)

    def test_connector_failure_handled_gracefully(self):
        def failing_connector(query, top_k):
            raise RuntimeError("API timeout")

        empty_retriever = FakeRetriever([])
        llm = FakeLLM(['{"reformulated": "retry query"}'])
        result = solve_sub_question(
            "Failing sub-question",
            empty_retriever,
            llm,
            max_rounds=2,
            connector_search=failing_connector,
        )
        assert result.final_status == "insufficient"
        assert result.added_to_gaps
