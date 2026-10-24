"""
Pure-Python retrieval runners for evaluation.
No imports from app.* at module level.
"""
from __future__ import annotations

import collections
import difflib
import math
import re
import unicodedata
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from eval.datasets.base import EvalQuery

from eval.runners.base import RunResult

STRATEGIES = ["bm25", "faiss", "rrf", "rrf+rerank", "full"]


def _tokenize(text: str) -> list[str]:
    """Lowercase, split on non-alphanumeric."""
    t = unicodedata.normalize("NFKC", str(text)).lower()
    return re.findall(r"\b\w+\b", t)


def _bm25_scores(query: str, corpus: dict[str, str], k1: float = 1.5, b: float = 0.75) -> dict[str, float]:
    """Pure-Python Okapi BM25."""
    query_tokens = _tokenize(query)
    if not query_tokens or not corpus:
        return {doc_id: 0.0 for doc_id in corpus}

    N = len(corpus)
    doc_tokens: dict[str, list[str]] = {doc_id: _tokenize(text) for doc_id, text in corpus.items()}
    total_len = sum(len(toks) for toks in doc_tokens.values())
    avgdl = total_len / N if N > 0 else 1.0
    if avgdl == 0:
        avgdl = 1.0

    # DF calculation for unique query tokens
    unique_q = set(query_tokens)
    df: dict[str, int] = collections.defaultdict(int)
    for toks in doc_tokens.values():
        t_set = set(toks)
        for qt in unique_q:
            if qt in t_set:
                df[qt] += 1

    # IDF calculation: standard Robertson BM25 idf with +1.0 floor
    idf: dict[str, float] = {}
    for qt in unique_q:
        n_q = df[qt]
        idf[qt] = math.log((N - n_q + 0.5) / (n_q + 0.5) + 1.0)

    scores: dict[str, float] = {}
    for doc_id, toks in doc_tokens.items():
        doc_len = len(toks)
        tf_counts = collections.Counter(toks)
        score = 0.0
        for qt in query_tokens:
            f = tf_counts[qt]
            if f > 0:
                numerator = f * (k1 + 1.0)
                denominator = f + k1 * (1.0 - b + b * (doc_len / avgdl))
                score += idf[qt] * (numerator / denominator)
        scores[doc_id] = round(score, 6)

    return scores


def _cosine_scores(query: str, corpus: dict[str, str]) -> dict[str, float]:
    """TF-IDF cosine similarity, stdlib only."""
    query_tokens = _tokenize(query)
    if not query_tokens or not corpus:
        return {doc_id: 0.0 for doc_id in corpus}

    N = len(corpus)
    doc_tokens: dict[str, list[str]] = {doc_id: _tokenize(text) for doc_id, text in corpus.items()}

    # Compute DF across corpus
    df: dict[str, int] = collections.defaultdict(int)
    for toks in doc_tokens.values():
        for t in set(toks):
            df[t] += 1

    def get_idf(term: str) -> float:
        return math.log(1.0 + (N + 1.0) / (df.get(term, 0) + 1.0))

    q_counts = collections.Counter(query_tokens)
    q_vec: dict[str, float] = {}
    for t, count in q_counts.items():
        tf = 1.0 + math.log(count)
        q_vec[t] = tf * get_idf(t)

    q_norm = math.sqrt(sum(v * v for v in q_vec.values()))
    if q_norm == 0.0:
        return {doc_id: 0.0 for doc_id in corpus}

    scores: dict[str, float] = {}
    for doc_id, toks in doc_tokens.items():
        if not toks:
            scores[doc_id] = 0.0
            continue
        d_counts = collections.Counter(toks)
        d_vec: dict[str, float] = {}
        for t, count in d_counts.items():
            tf = 1.0 + math.log(count)
            d_vec[t] = tf * get_idf(t)

        d_norm = math.sqrt(sum(v * v for v in d_vec.values()))
        if d_norm == 0.0:
            scores[doc_id] = 0.0
            continue

        dot = sum(q_vec[t] * d_vec.get(t, 0.0) for t in q_vec)
        scores[doc_id] = round(dot / (q_norm * d_norm), 6)

    return scores


def _local_rrf(ranked_lists: list[list[dict]], k: int = 60, id_key: str = "chunk_id") -> list[dict]:
    scores: dict[str, float] = {}
    best: dict[str, dict] = {}
    for ranked in ranked_lists:
        for rank, item in enumerate(ranked, start=1):
            uid = item[id_key]
            scores[uid] = scores.get(uid, 0.0) + 1.0 / (k + rank)
            if uid not in best:
                best[uid] = dict(item)
    merged = sorted(best.values(), key=lambda x: scores[x[id_key]], reverse=True)
    for item in merged:
        item["rrf_score"] = round(scores[item[id_key]], 6)
    return merged


def _local_dedup(results: list[dict], threshold: float = 0.90, text_key: str = "text") -> list[dict]:
    seen: list[str] = []
    unique: list[dict] = []
    for item in results:
        t = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(item.get(text_key, ""))).lower()).strip()
        if any(difflib.SequenceMatcher(None, t, s).ratio() >= threshold for s in seen):
            continue
        seen.append(t)
        unique.append(item)
    return unique


def _local_expand_to_parent(results: list[dict], all_chunks: list[dict]) -> list[dict]:
    page_index: dict[tuple[str, Any], list[str]] = {}
    for chunk in all_chunks:
        key = (chunk.get("document", ""), chunk.get("page", 0))
        page_index.setdefault(key, []).append(chunk.get("text", ""))

    for item in results:
        key = (item.get("document", ""), item.get("page", 0))
        item["parent_text"] = " ".join(page_index.get(key, [])).strip()
    return results


def run_strategy(
    strategy: str,
    queries: list["EvalQuery"],
    top_k: int = 10,
    *,
    use_sufficiency: bool = True,
    use_verification: bool = True,
    use_reliability: bool = True,
    seed: int = 42,
) -> list[RunResult]:
    """
    strategy one of: bm25, faiss, rrf, rrf+rerank, full
    - bm25: BM25 only
    - faiss: cosine similarity (TF-IDF vectors)
    - rrf: RRF fusion of bm25 + faiss
    - rrf+rerank: RRF + simple reranker (query-doc overlap score as proxy)
    - full: rrf+rerank + dedup + parent expansion
    Ablation flags suppress steps.
    """
    if strategy not in STRATEGIES:
        raise ValueError(f"Unknown strategy: {strategy}. Must be one of {STRATEGIES}")

    # Lazy imports from app.rag.retrieval_utils if available
    try:
        from app.rag.retrieval_utils import reciprocal_rank_fusion
    except Exception:
        reciprocal_rank_fusion = _local_rrf

    try:
        from app.rag.retrieval_utils import remove_near_duplicates
    except Exception:
        remove_near_duplicates = _local_dedup

    try:
        from app.rag.retrieval_utils import expand_to_parent
    except Exception:
        expand_to_parent = _local_expand_to_parent

    try:
        from app.rag.retrieval_utils import rerank as cross_rerank
    except Exception:
        cross_rerank = None

    results: list[RunResult] = []

    for q in queries:
        corpus = q.passages
        if not corpus:
            results.append(
                RunResult(
                    query_id=q.query_id,
                    retrieved_ids=[],
                    scores=[],
                    strategy=strategy,
                )
            )
            continue

        if strategy == "bm25":
            scores = _bm25_scores(q.query, corpus)
            # Sort descending by score, tie-break by doc_id ascending
            sorted_items = sorted(scores.items(), key=lambda x: (x[1], -len(x[0])), reverse=True)
            retrieved = [doc_id for doc_id, _ in sorted_items][:top_k]
            res_scores = [scores[doc_id] for doc_id in retrieved]

        elif strategy == "faiss":
            scores = _cosine_scores(q.query, corpus)
            sorted_items = sorted(scores.items(), key=lambda x: (x[1], -len(x[0])), reverse=True)
            retrieved = [doc_id for doc_id, _ in sorted_items][:top_k]
            res_scores = [scores[doc_id] for doc_id in retrieved]

        elif strategy in ("rrf", "rrf+rerank", "full"):
            bm25_scores = _bm25_scores(q.query, corpus)
            cosine_scores = _cosine_scores(q.query, corpus)

            bm25_ranked = [
                {"chunk_id": did, "score": s, "text": corpus[did]}
                for did, s in sorted(bm25_scores.items(), key=lambda x: (x[1], -len(x[0])), reverse=True)
            ]
            faiss_ranked = [
                {"chunk_id": did, "score": s, "text": corpus[did]}
                for did, s in sorted(cosine_scores.items(), key=lambda x: (x[1], -len(x[0])), reverse=True)
            ]

            fused = reciprocal_rank_fusion([bm25_ranked, faiss_ranked], k=60, id_key="chunk_id")
            for item in fused:
                item["text"] = corpus.get(item["chunk_id"], "")

            if strategy in ("rrf+rerank", "full") and use_verification:
                # Apply reranker (CrossEncoder if working, else proxy query-doc overlap)
                reranked = None
                if cross_rerank is not None:
                    try:
                        reranked = cross_rerank(q.query, fused, top_n=len(fused))
                    except Exception:
                        reranked = None

                if reranked and any("reranker_score" in r for r in reranked):
                    fused = reranked
                else:
                    # Pure-Python proxy reranker: query-doc token overlap
                    q_tokens = set(_tokenize(q.query))
                    for item in fused:
                        doc_toks = set(_tokenize(item.get("text", "")))
                        overlap = len(q_tokens & doc_toks) / len(q_tokens) if q_tokens else 0.0
                        item["reranker_score"] = round(item.get("rrf_score", 0.0) + overlap * 0.5, 6)
                    fused.sort(key=lambda x: (x.get("reranker_score", 0.0), x.get("rrf_score", 0.0)), reverse=True)

            if strategy == "full":
                if use_reliability:
                    # Near-duplicate removal
                    fused = remove_near_duplicates(fused, threshold=0.90, text_key="text")

                # Parent expansion
                all_chunks = [
                    {"chunk_id": did, "document": did.split("_")[0], "page": 1, "text": txt}
                    for did, txt in corpus.items()
                ]
                for item in fused:
                    if "document" not in item:
                        item["document"] = item["chunk_id"].split("_")[0]
                        item["page"] = 1
                fused = expand_to_parent(fused, all_chunks)

                if use_sufficiency:
                    # Sufficiency step: drop empty text
                    fused = [item for item in fused if item.get("text", "").strip()]

            retrieved = [item["chunk_id"] for item in fused][:top_k]
            res_scores = [
                item.get("reranker_score", item.get("rrf_score", item.get("score", 0.0)))
                for item in fused
            ][:top_k]

        results.append(
            RunResult(
                query_id=q.query_id,
                retrieved_ids=retrieved,
                scores=res_scores,
                strategy=strategy,
            )
        )

    return results
