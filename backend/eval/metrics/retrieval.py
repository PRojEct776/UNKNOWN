"""
Retrieval evaluation metrics: Recall@k, nDCG@k, MRR.
"""
from __future__ import annotations

import math


def recall_at_k(retrieved: list[str], relevant: set[str], k: int = 10) -> float:
    """
    Compute Recall@k.
    Fraction of relevant documents retrieved in top k results.
    """
    if not relevant:
        return 0.0
    top = retrieved[:k]
    hits = sum(1 for doc_id in top if doc_id in relevant)
    return hits / len(relevant)


def ndcg_at_k(retrieved: list[str], relevant: set[str], k: int = 10) -> float:
    """
    Compute Normalized Discounted Cumulative Gain at k (nDCG@k) for binary relevance.
    """
    if not relevant:
        return 0.0

    top = retrieved[:k]
    dcg = sum(
        1.0 / math.log2(rank + 2)
        for rank, doc_id in enumerate(top)
        if doc_id in relevant
    )

    ideal_hits = min(len(relevant), k)
    ideal_dcg = sum(
        1.0 / math.log2(rank + 2)
        for rank in range(ideal_hits)
    )

    return dcg / ideal_dcg if ideal_dcg > 0.0 else 0.0


def mrr(retrieved: list[str], relevant: set[str]) -> float:
    """
    Mean Reciprocal Rank (MRR).
    Reciprocal rank of the first relevant document in retrieved list.
    """
    for i, doc_id in enumerate(retrieved, 1):
        if doc_id in relevant:
            return 1.0 / i
    return 0.0


def mean_metrics(queries_results: list[dict[str, float]]) -> dict[str, float]:
    """
    Average all metric keys across queries.
    """
    if not queries_results:
        return {}
    keys = queries_results[0].keys()
    out: dict[str, float] = {}
    for k in keys:
        vals = [q[k] for q in queries_results if k in q]
        out[k] = sum(vals) / len(vals) if vals else 0.0
    return out
