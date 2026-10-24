"""
Unit Tests for Retrieval Pipeline v3 (Task A3)

Tests each new feature in isolation using mocks — no real BM25/FAISS index needed.

Features tested:
  - Reciprocal Rank Fusion (RRF) with k=60
  - Near-duplicate removal
  - Parent-child chunk expansion
  - CrossEncoder reranker (graceful fallback when unavailable)
  - HybridSearch config flags (RRF on/off, dedup on/off, etc.)
  - Eval metric functions (Recall@k, nDCG@k)

Import strategy
---------------
Pure utility functions (no numpy/faiss) are imported from retrieval_utils
at module level — safe to import anywhere.

HybridSearch is imported *inside* each test/fixture that needs it, so
collection succeeds even if numpy is not installed.  The lazy-import pattern
avoids triggering BM25Search → numpy at collection time.
"""

from __future__ import annotations

import math
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Pure-Python imports (no numpy / faiss chain)
# ---------------------------------------------------------------------------
from app.rag.retrieval_utils import (
    expand_to_parent,
    reciprocal_rank_fusion,
    remove_near_duplicates,
    rerank,
)
from scripts.eval_retrieval import ndcg_at_k, recall_at_k


# ---------------------------------------------------------------------------
# Helpers to build synthetic results
# ---------------------------------------------------------------------------

def _make_results(ids: list[str], texts: list[str] | None = None) -> list[dict]:
    return [
        {
            "chunk_id": cid,
            "rank": i + 1,
            "score": 10.0 - i,
            "document": "doc.pdf",
            "page": i + 1,
            "text": (texts[i] if texts else f"Unique passage about topic {cid}."),
        }
        for i, cid in enumerate(ids)
    ]


# ---------------------------------------------------------------------------
# 1. Reciprocal Rank Fusion
# ---------------------------------------------------------------------------

class TestRRF:
    def test_single_list_preserves_order(self):
        results = _make_results(["a", "b", "c"])
        merged = reciprocal_rank_fusion([results])
        assert [r["chunk_id"] for r in merged] == ["a", "b", "c"]

    def test_two_lists_boost_shared_item(self):
        list1 = _make_results(["a", "b", "c"])
        list2 = _make_results(["c", "d", "e"])  # "c" appears in both
        merged = reciprocal_rank_fusion([list1, list2])
        ids = [r["chunk_id"] for r in merged]
        # "c" appears at rank-1 in list2 and rank-3 in list1 → boosted
        assert "c" in ids[:2], f"Expected 'c' near top, got: {ids}"

    def test_k60_constant_affects_scores(self):
        # Use separate result objects so in-place mutation doesn't alias
        results_k60 = _make_results(["x"])
        results_k1 = _make_results(["x"])
        merged_k60 = reciprocal_rank_fusion([results_k60], k=60)
        merged_k1 = reciprocal_rank_fusion([results_k1], k=1)
        # k=1 → 1/(1+1)=0.5, k=60 → 1/(60+1)≈0.0164
        assert merged_k1[0]["rrf_score"] > merged_k60[0]["rrf_score"]

    def test_empty_lists_returns_empty(self):
        assert reciprocal_rank_fusion([[], []]) == []

    def test_disjoint_lists_union(self):
        list1 = _make_results(["a", "b"])
        list2 = _make_results(["c", "d"])
        merged = reciprocal_rank_fusion([list1, list2])
        assert len(merged) == 4

    def test_rrf_score_decreases_with_rank(self):
        results = _make_results(["a", "b", "c", "d"])
        merged = reciprocal_rank_fusion([results])
        scores = [r["rrf_score"] for r in merged]
        assert scores == sorted(scores, reverse=True)

    def test_preserves_all_fields(self):
        results = _make_results(["z"])
        results[0]["extra_field"] = "should_survive"
        merged = reciprocal_rank_fusion([results])
        assert merged[0].get("extra_field") == "should_survive"


# ---------------------------------------------------------------------------
# 2. Near-duplicate removal
# ---------------------------------------------------------------------------

class TestNearDuplicateRemoval:
    def test_identical_texts_deduplicated(self):
        text = "The quick brown fox jumps over the lazy dog."
        items = [
            {"chunk_id": "a", "text": text, "rank": 1},
            {"chunk_id": "b", "text": text, "rank": 2},  # identical → drop
        ]
        result = remove_near_duplicates(items)
        assert len(result) == 1
        assert result[0]["chunk_id"] == "a"

    def test_near_duplicate_removed(self):
        text1 = "Deep learning uses neural networks for classification."
        text2 = "Deep learning uses neural networks for classifications."  # nearly same
        items = [
            {"chunk_id": "a", "text": text1, "rank": 1},
            {"chunk_id": "b", "text": text2, "rank": 2},
        ]
        result = remove_near_duplicates(items, threshold=0.90)
        assert len(result) == 1

    def test_distinct_texts_all_kept(self):
        items = [
            {"chunk_id": "a", "text": "DNA storage encodes binary data in nucleotides.", "rank": 1},
            {"chunk_id": "b", "text": "FAISS provides approximate nearest neighbor search.", "rank": 2},
            {"chunk_id": "c", "text": "Transformers use self-attention mechanisms.", "rank": 3},
        ]
        result = remove_near_duplicates(items)
        assert len(result) == 3

    def test_first_occurrence_wins(self):
        text = "BERT pre-trains on masked language modelling."
        items = [
            {"chunk_id": "first", "text": text, "rank": 1},
            {"chunk_id": "second", "text": text, "rank": 2},
        ]
        result = remove_near_duplicates(items)
        assert result[0]["chunk_id"] == "first"

    def test_empty_list_returns_empty(self):
        assert remove_near_duplicates([]) == []

    def test_threshold_1_keeps_only_exact_duplicates(self):
        text1 = "abc"
        text2 = "abcX"  # different enough at threshold 1.0
        items = [
            {"chunk_id": "a", "text": text1, "rank": 1},
            {"chunk_id": "b", "text": text2, "rank": 2},
        ]
        result = remove_near_duplicates(items, threshold=1.0)
        # Both should be kept because they're not identical
        assert len(result) == 2


# ---------------------------------------------------------------------------
# 3. Parent-child chunk expansion
# ---------------------------------------------------------------------------

class TestParentChildExpansion:
    def _make_all_chunks(self):
        return [
            {"chunk_id": "c1", "document": "paper.pdf", "page": 1, "text": "Introduction text."},
            {"chunk_id": "c2", "document": "paper.pdf", "page": 1, "text": "More intro text."},
            {"chunk_id": "c3", "document": "paper.pdf", "page": 2, "text": "Methods section."},
        ]

    def test_parent_text_contains_siblings(self):
        all_chunks = self._make_all_chunks()
        result = [{"chunk_id": "c1", "document": "paper.pdf", "page": 1, "text": "Introduction text."}]
        expanded = expand_to_parent(result, all_chunks)
        assert "parent_text" in expanded[0]
        assert "More intro text." in expanded[0]["parent_text"]

    def test_single_chunk_page_parent_equals_self(self):
        all_chunks = self._make_all_chunks()
        result = [{"chunk_id": "c3", "document": "paper.pdf", "page": 2, "text": "Methods section."}]
        expanded = expand_to_parent(result, all_chunks)
        assert expanded[0]["parent_text"] == "Methods section."

    def test_original_fields_unchanged(self):
        all_chunks = self._make_all_chunks()
        result = [{"chunk_id": "c1", "document": "paper.pdf", "page": 1, "text": "Introduction text."}]
        expanded = expand_to_parent(result, all_chunks)
        assert expanded[0]["chunk_id"] == "c1"
        assert expanded[0]["text"] == "Introduction text."

    def test_empty_results_returns_empty(self):
        assert expand_to_parent([], []) == []

    def test_unknown_page_gets_empty_parent(self):
        result = [{"chunk_id": "cx", "document": "ghost.pdf", "page": 99, "text": "Orphan."}]
        expanded = expand_to_parent(result, [])
        assert expanded[0]["parent_text"] == ""


# ---------------------------------------------------------------------------
# 4. CrossEncoder reranker (graceful fallback)
#    Singleton lives in retrieval_utils; we patch there.
# ---------------------------------------------------------------------------

class TestReranker:
    def test_rerank_fallback_when_unavailable(self):
        """When CrossEncoder is not installed, rerank() returns top_n results in original order."""
        import app.rag.retrieval_utils as ru
        original_tried = ru._cross_encoder_tried
        original_ce = ru._cross_encoder
        ru._cross_encoder_tried = False
        ru._cross_encoder = None

        results = _make_results(["a", "b", "c"])
        with patch.dict("sys.modules", {"sentence_transformers": None}):
            out = rerank("test query", results, top_n=2)

        ru._cross_encoder_tried = original_tried  # restore
        ru._cross_encoder = original_ce
        assert len(out) == 2
        assert out[0]["chunk_id"] == "a"

    def test_rerank_with_mock_cross_encoder(self):
        """When CrossEncoder is available, results are reordered by reranker score."""
        mock_ce = MagicMock()
        # Make the last item score highest
        mock_ce.predict.return_value = [0.1, 0.5, 0.9]

        import app.rag.retrieval_utils as ru
        old_ce = ru._cross_encoder
        old_tried = ru._cross_encoder_tried
        ru._cross_encoder = mock_ce
        ru._cross_encoder_tried = True

        results = _make_results(["a", "b", "c"])
        out = rerank("query", results, top_n=3)

        ru._cross_encoder = old_ce
        ru._cross_encoder_tried = old_tried

        assert out[0]["chunk_id"] == "c"   # highest score
        assert out[1]["chunk_id"] == "b"
        assert out[2]["chunk_id"] == "a"

    def test_reranker_empty_input(self):
        out = rerank("query", [], top_n=5)
        assert out == []

    def test_reranker_score_field_added(self):
        mock_ce = MagicMock()
        mock_ce.predict.return_value = [0.7, 0.3]

        import app.rag.retrieval_utils as ru
        old_ce = ru._cross_encoder
        ru._cross_encoder = mock_ce
        ru._cross_encoder_tried = True

        results = _make_results(["a", "b"])
        out = rerank("q", results, top_n=2)
        ru._cross_encoder = old_ce

        assert "reranker_score" in out[0]


# ---------------------------------------------------------------------------
# 5. HybridSearch config flags (pure unit, no real indexes)
#    HybridSearch imported lazily inside this section to avoid numpy at
#    collection time.
# ---------------------------------------------------------------------------

def _mock_hybrid(
    bm25_ids: list[str],
    faiss_ids: list[str],
    **kwargs,
):
    """Create a HybridSearch with mocked BM25 and FAISS engines."""
    # Lazy import so numpy is not required at collection time
    from app.rag.hybrid_search import HybridSearch  # noqa: PLC0415

    hs = HybridSearch.__new__(HybridSearch)
    # Set defaults from __init__ without calling it
    hs.alpha = kwargs.get("alpha", 0.4)
    hs.beta = kwargs.get("beta", 0.6)
    hs.rrf_k = kwargs.get("rrf_k", 60)
    hs.use_rrf = kwargs.get("use_rrf", False)
    hs.use_reranker = kwargs.get("use_reranker", False)
    hs.deduplicate = kwargs.get("deduplicate", False)
    hs.parent_child = kwargs.get("parent_child", False)

    bm25_mock = MagicMock()
    bm25_mock.search.return_value = _make_results(bm25_ids)
    bm25_mock.chunks = _make_results(bm25_ids + faiss_ids)
    hs.bm25 = bm25_mock

    faiss_mock = MagicMock()
    faiss_mock.search.return_value = _make_results(faiss_ids)
    hs.faiss = faiss_mock

    return hs


class TestHybridSearchFlags:
    def test_rrf_off_uses_linear_fusion(self):
        hs = _mock_hybrid(["a", "b"], ["b", "c"], use_rrf=False)
        results = hs.search("query", top_k=3)
        ids = [r["chunk_id"] for r in results]
        assert set(ids) == {"a", "b", "c"} or set(ids).issubset({"a", "b", "c"})
        # All results have hybrid_score set
        assert all("hybrid_score" in r for r in results)

    def test_rrf_on_returns_rrf_score(self):
        hs = _mock_hybrid(["a", "b"], ["b", "c"], use_rrf=True)
        results = hs.search("query", top_k=3)
        assert all("rrf_score" in r for r in results)

    def test_dedup_off_keeps_duplicates(self):
        text = "Same text repeated verbatim here for testing."
        bm25_mock = MagicMock()
        faiss_mock = MagicMock()
        bm25_results = [
            {"chunk_id": "a", "rank": 1, "score": 5.0, "document": "d", "page": 1, "text": text},
            {"chunk_id": "b", "rank": 2, "score": 4.0, "document": "d", "page": 2, "text": text},
        ]
        bm25_mock.search.return_value = bm25_results
        bm25_mock.chunks = bm25_results
        faiss_mock.search.return_value = []

        from app.rag.hybrid_search import HybridSearch  # noqa: PLC0415

        hs = HybridSearch.__new__(HybridSearch)
        hs.bm25 = bm25_mock
        hs.faiss = faiss_mock
        hs.use_rrf = False
        hs.use_reranker = False
        hs.deduplicate = False   # OFF
        hs.parent_child = False
        hs.alpha = 0.4
        hs.beta = 0.6
        hs.rrf_k = 60

        results = hs.search("query", top_k=5)
        # Both should survive when dedup is off
        assert len(results) == 2

    def test_empty_document_scope_returns_empty(self):
        hs = _mock_hybrid(["a"], ["b"])
        results = hs.search("query", document_names=[])
        assert results == []

    def test_rank_assigned_sequentially(self):
        hs = _mock_hybrid(["a", "b", "c"], ["c", "d"])
        results = hs.search("query", top_k=4)
        ranks = [r["rank"] for r in results]
        assert ranks == list(range(1, len(results) + 1))


# ---------------------------------------------------------------------------
# 6. Evaluation metric functions
# ---------------------------------------------------------------------------

class TestEvalMetrics:
    def test_recall_perfect(self):
        assert recall_at_k(["a", "b", "c"], {"a", "b", "c"}, k=10) == 1.0

    def test_recall_zero(self):
        assert recall_at_k(["x", "y"], {"a", "b"}, k=10) == 0.0

    def test_recall_partial(self):
        r = recall_at_k(["a", "x", "y"], {"a", "b"}, k=10)
        assert r == pytest.approx(0.5)

    def test_recall_cutoff_respected(self):
        # Relevant doc is outside k
        r = recall_at_k(["x", "y", "z", "a"], {"a"}, k=3)
        assert r == 0.0

    def test_ndcg_perfect(self):
        assert ndcg_at_k(["a", "b", "c"], {"a", "b", "c"}, k=10) == pytest.approx(1.0)

    def test_ndcg_zero(self):
        assert ndcg_at_k(["x", "y", "z"], {"a"}, k=10) == 0.0

    def test_ndcg_top_result_matters_more(self):
        # "a" at rank-1 vs "a" at rank-3 — rank-1 has higher nDCG
        ndcg_rank1 = ndcg_at_k(["a", "x", "y"], {"a"}, k=10)
        ndcg_rank3 = ndcg_at_k(["x", "y", "a"], {"a"}, k=10)
        assert ndcg_rank1 > ndcg_rank3

    def test_ndcg_empty_relevant_set_returns_zero(self):
        assert ndcg_at_k(["a", "b"], set(), k=10) == 0.0

    def test_recall_empty_relevant_set(self):
        assert recall_at_k(["a"], set(), k=10) == 0.0
