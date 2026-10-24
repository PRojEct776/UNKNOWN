"""
UNKNOWN X – Retrieval utilities (pure Python, no heavy dependencies)

Contains functions that can be imported and tested without numpy/faiss/
sentence_transformers being installed:

  reciprocal_rank_fusion   – RRF score fusion (k=60 default)
  remove_near_duplicates   – near-dup removal by SequenceMatcher
  expand_to_parent         – parent-chunk context expansion
  rerank                   – CrossEncoder reranker (lazy, graceful fallback)
"""

from __future__ import annotations

import difflib
import os
import unicodedata
from typing import Any

from app.rag.logger import logger

# ---------------------------------------------------------------------------
# Config flags
# ---------------------------------------------------------------------------

def _flag(name: str, default: bool = True) -> bool:
    v = os.environ.get(name, "").strip().lower()
    if v in ("0", "false", "no", "off"):
        return False
    return default


RETRIEVAL_USE_RRF = _flag("RETRIEVAL_USE_RRF", True)
RETRIEVAL_USE_RERANKER = _flag("RETRIEVAL_USE_RERANKER", True)
RETRIEVAL_DEDUPLICATE = _flag("RETRIEVAL_DEDUPLICATE", True)
RETRIEVAL_PARENT_CHILD = _flag("RETRIEVAL_PARENT_CHILD", True)

RERANKER_MODEL = os.environ.get(
    "RETRIEVAL_RERANKER_MODEL",
    "cross-encoder/ms-marco-MiniLM-L-6-v2",
)
DEDUP_THRESHOLD = float(os.environ.get("RETRIEVAL_DEDUP_THRESHOLD", "0.90"))


# ---------------------------------------------------------------------------
# 1. Reciprocal Rank Fusion
# ---------------------------------------------------------------------------

def reciprocal_rank_fusion(
    ranked_lists: list[list[dict]],
    k: int = 60,
    id_key: str = "chunk_id",
) -> list[dict]:
    """
    Merge multiple ranked lists with RRF.

    score(d) = Σ  1 / (k + rank_i(d))
               i

    Args:
        ranked_lists: Each list is ordered best-first.
        k:            RRF constant (default 60).
        id_key:       Field that uniquely identifies a result.

    Returns:
        Merged list ordered by RRF score descending; adds 'rrf_score' field.
    """
    scores: dict[str, float] = {}
    best: dict[str, dict] = {}

    for ranked in ranked_lists:
        for rank, item in enumerate(ranked, start=1):
            uid = item[id_key]
            scores[uid] = scores.get(uid, 0.0) + 1.0 / (k + rank)
            if uid not in best:
                best[uid] = item

    merged = sorted(best.values(), key=lambda x: scores[x[id_key]], reverse=True)
    for item in merged:
        item["rrf_score"] = round(scores[item[id_key]], 6)
    return merged


# ---------------------------------------------------------------------------
# 2. Near-duplicate removal
# ---------------------------------------------------------------------------

def _norm(text: str) -> str:
    t = unicodedata.normalize("NFKC", text).lower()
    return " ".join(t.split())


def remove_near_duplicates(
    results: list[dict],
    threshold: float = DEDUP_THRESHOLD,
    text_key: str = "text",
) -> list[dict]:
    """
    Remove near-duplicate results (SequenceMatcher ratio ≥ threshold).
    First occurrence wins; subsequent near-dups are dropped.
    """
    seen: list[str] = []
    unique: list[dict] = []
    for item in results:
        t = _norm(item.get(text_key, ""))
        if any(difflib.SequenceMatcher(None, t, s).ratio() >= threshold for s in seen):
            continue
        seen.append(t)
        unique.append(item)
    return unique


# ---------------------------------------------------------------------------
# 3. Parent-child chunk expansion
# ---------------------------------------------------------------------------

def expand_to_parent(
    results: list[dict],
    all_chunks: list[dict],
) -> list[dict]:
    """
    Attach 'parent_text' = concatenation of all sibling chunks on the same
    (document, page) as the result.  Does NOT alter existing fields.
    """
    page_index: dict[tuple[str, Any], list[str]] = {}
    for chunk in all_chunks:
        key = (chunk.get("document", ""), chunk.get("page", 0))
        page_index.setdefault(key, []).append(chunk.get("text", ""))

    for item in results:
        key = (item.get("document", ""), item.get("page", 0))
        item["parent_text"] = " ".join(page_index.get(key, [])).strip()
    return results


# ---------------------------------------------------------------------------
# 4. Cross-encoder reranker (lazy singleton)
# ---------------------------------------------------------------------------

_cross_encoder = None
_cross_encoder_tried = False


def _get_cross_encoder():
    global _cross_encoder, _cross_encoder_tried
    if _cross_encoder_tried:
        return _cross_encoder
    _cross_encoder_tried = True
    try:
        from sentence_transformers import CrossEncoder as CE  # type: ignore
        _cross_encoder = CE(RERANKER_MODEL)
        logger.info("CrossEncoder reranker loaded: %s", RERANKER_MODEL)
    except Exception as exc:
        logger.warning("CrossEncoder unavailable (%s) – reranking skipped.", exc)
        _cross_encoder = None
    return _cross_encoder


def rerank(query: str, results: list[dict], top_n: int) -> list[dict]:
    """
    Rerank `results` with a CrossEncoder; adds 'reranker_score'.
    Falls back to original order if CrossEncoder is unavailable.
    """
    ce = _get_cross_encoder()
    if ce is None or not results:
        return results[:top_n]
    try:
        scores = ce.predict([(query, r["text"]) for r in results])
        for result, score in zip(results, scores):
            result["reranker_score"] = float(score)
        reranked = sorted(results, key=lambda x: x.get("reranker_score", 0.0), reverse=True)
        return reranked[:top_n]
    except Exception as exc:
        logger.warning("CrossEncoder reranking failed: %s – falling back.", exc)
        return results[:top_n]
