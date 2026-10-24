"""
UNKNOWN X – Retrieval Pipeline v3

New features (each behind a config flag — all default ON):

  RETRIEVAL_USE_RRF              Reciprocal Rank Fusion (k=60) instead of
                                 linear score combination.

  RETRIEVAL_USE_RERANKER         Cross-encoder reranker
                                 (sentence-transformers CrossEncoder).
                                 Requires sentence_transformers installed;
                                 skipped gracefully if missing.

  RETRIEVAL_DEDUPLICATE          Near-duplicate removal by normalised text
                                 similarity (SequenceMatcher ≥ 0.90).

  RETRIEVAL_PARENT_CHILD         Parent-chunk expansion: each returned child
                                 chunk is augmented with its page-level
                                 "parent" text block for richer context.

None of these touch the Chunk schema {chunk_id, document, page, text}.
"""

from __future__ import annotations

import os
from typing import Any

from app.rag.config import settings
from app.rag.logger import logger
from app.rag.retrieval_utils import (
    DEDUP_THRESHOLD,
    RERANKER_MODEL,
    RETRIEVAL_DEDUPLICATE,
    RETRIEVAL_PARENT_CHILD,
    RETRIEVAL_USE_RERANKER,
    RETRIEVAL_USE_RRF,
    expand_to_parent,
    reciprocal_rank_fusion,
    remove_near_duplicates,
    rerank,
)


# ---------------------------------------------------------------------------
# HybridSearch (drop-in replacement — same public interface)
# ---------------------------------------------------------------------------

class HybridSearch:
    """
    UNKNOWN Hybrid Retrieval Engine v3.

    Combines BM25 + FAISS using either:
      - Linear score fusion (original; RETRIEVAL_USE_RRF=false), or
      - Reciprocal Rank Fusion (RETRIEVAL_USE_RRF=true, k=60).

    Optionally applies:
      - Cross-encoder reranking      (RETRIEVAL_USE_RERANKER)
      - Near-duplicate removal       (RETRIEVAL_DEDUPLICATE)
      - Parent-child chunk expansion (RETRIEVAL_PARENT_CHILD)
    """

    def __init__(
        self,
        *,
        use_rrf: bool = RETRIEVAL_USE_RRF,
        use_reranker: bool = RETRIEVAL_USE_RERANKER,
        deduplicate: bool = RETRIEVAL_DEDUPLICATE,
        parent_child: bool = RETRIEVAL_PARENT_CHILD,
        rrf_k: int = 60,
        alpha: float = 0.4,
        beta: float = 0.6,
    ) -> None:
        logger.info("Initializing Hybrid Retrieval Engine v3…")

        # Lazy imports so the module is importable without numpy/faiss installed
        # (tests can patch or bypass __init__ entirely via __new__)
        from app.rag.bm25_search import BM25Search  # noqa: PLC0415
        from app.rag.faiss_search import FAISSSearch  # noqa: PLC0415

        self.bm25 = BM25Search()
        self.faiss = FAISSSearch()

        self.use_rrf = use_rrf
        self.use_reranker = use_reranker
        self.deduplicate = deduplicate
        self.parent_child = parent_child
        self.rrf_k = rrf_k
        self.alpha = alpha
        self.beta = beta

        logger.info(
            "Retrieval flags: RRF=%s reranker=%s dedup=%s parent_child=%s",
            use_rrf, use_reranker, deduplicate, parent_child,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_scores(results: list[dict], score_key: str = "score") -> list[dict]:
        """Min-max normalise scores into [0, 1], adding 'normalized_score'."""
        if not results:
            return results
        scores = [r[score_key] for r in results]
        lo, hi = min(scores), max(scores)
        for r in results:
            r["normalized_score"] = 1.0 if hi == lo else (r[score_key] - lo) / (hi - lo)
        return results

    def _linear_fusion(
        self,
        bm25_results: list[dict],
        faiss_results: list[dict],
    ) -> list[dict]:
        """Original weighted-sum fusion (backward-compatible)."""
        bm25_results = self._normalize_scores(bm25_results)
        faiss_results = self._normalize_scores(faiss_results)

        merged: dict[str, dict] = {}
        for r in bm25_results:
            merged[r["chunk_id"]] = {**r, "bm25_score": r["normalized_score"], "faiss_score": 0.0}
        for r in faiss_results:
            cid = r["chunk_id"]
            if cid not in merged:
                merged[cid] = {**r, "bm25_score": 0.0, "faiss_score": r["normalized_score"]}
            else:
                merged[cid]["faiss_score"] = r["normalized_score"]

        results = list(merged.values())
        for r in results:
            r["hybrid_score"] = round(self.alpha * r["bm25_score"] + self.beta * r["faiss_score"], 4)
        results.sort(key=lambda x: x["hybrid_score"], reverse=True)
        return results

    def _rrf_fusion(
        self,
        bm25_results: list[dict],
        faiss_results: list[dict],
    ) -> list[dict]:
        """Reciprocal Rank Fusion fusion."""
        merged = reciprocal_rank_fusion(
            [bm25_results, faiss_results],
            k=self.rrf_k,
        )
        # Back-fill bm25_score / faiss_score / hybrid_score for API compatibility
        bm25_map = {r["chunk_id"]: r.get("normalized_score", r.get("score", 0.0))
                    for r in self._normalize_scores(list(bm25_results))}
        faiss_map = {r["chunk_id"]: r.get("normalized_score", r.get("score", 0.0))
                     for r in self._normalize_scores(list(faiss_results))}
        for r in merged:
            cid = r["chunk_id"]
            r["bm25_score"] = round(bm25_map.get(cid, 0.0), 4)
            r["faiss_score"] = round(faiss_map.get(cid, 0.0), 4)
            r["hybrid_score"] = r["rrf_score"]
        return merged

    # ------------------------------------------------------------------
    # Public API (same signature as original HybridSearch.search)
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int | None = None,
        document_names: list[str] | None = None,
    ) -> list[dict]:
        """
        Perform hybrid retrieval with optional RRF, reranking, dedup,
        and parent-child expansion.

        Args:
            query:          User query.
            top_k:          Number of final results.
            document_names: Scope search to specified documents.

        Returns:
            Ranked result dicts (schema unchanged).
        """
        if top_k is None:
            top_k = settings.TOP_K_RESULTS

        if document_names is not None and len(document_names) == 0:
            logger.info("Hybrid search: empty document scope → 0 results.")
            return []

        doc_filter = set(document_names) if document_names else None

        # Over-fetch candidates for multi-doc queries
        if doc_filter and len(doc_filter) > 1:
            effective_top_k = max(top_k, min(len(doc_filter) * 2, 30))
        else:
            effective_top_k = top_k

        candidate_k = effective_top_k * 3

        logger.info("Hybrid search query: %r (scoped to %s docs)", query,
                    len(doc_filter) if doc_filter else "all")

        bm25_results = self.bm25.search(query, candidate_k, document_names=document_names)
        faiss_results = self.faiss.search(query, candidate_k, document_names=document_names)

        # --- Fusion ---
        if self.use_rrf:
            fused = self._rrf_fusion(bm25_results, faiss_results)
        else:
            fused = self._linear_fusion(bm25_results, faiss_results)

        # --- Near-duplicate removal ---
        if self.deduplicate:
            fused = remove_near_duplicates(fused)

        # --- Balanced multi-doc selection (from original) ---
        if doc_filter and len(doc_filter) > 1:
            selected: list[dict] = []
            for doc in doc_filter:
                for chunk in [r for r in fused if r.get("document") == doc][:2]:
                    if chunk not in selected:
                        selected.append(chunk)
            for chunk in fused:
                if len(selected) >= effective_top_k:
                    break
                if chunk not in selected:
                    selected.append(chunk)
            selected.sort(key=lambda x: x["hybrid_score"], reverse=True)
            fused = selected[:effective_top_k]
        else:
            fused = fused[:effective_top_k]

        # --- Cross-encoder reranking ---
        if self.use_reranker:
            fused = rerank(query, fused, top_n=top_k)
        else:
            fused = fused[:top_k]

        # --- Parent-child expansion ---
        if self.parent_child:
            all_chunks = list(self.bm25.chunks)  # already loaded in BM25Search
            fused = expand_to_parent(fused, all_chunks)

        # --- Assign final ranks ---
        for rank, result in enumerate(fused, start=1):
            result["rank"] = rank

        logger.info("Retrieved %d chunks.", len(fused))
        return fused
