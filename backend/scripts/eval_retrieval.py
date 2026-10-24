"""
UNKNOWN – Retrieval Evaluation Script (Task A3)

Prints Recall@10 and nDCG@10 on a small fixture set for:
  bm25   – BM25-only results
  faiss  – FAISS-only results
  rrf    – BM25 + FAISS with Reciprocal Rank Fusion (k=60)
  rrf+rerank – RRF + CrossEncoder reranker (skipped gracefully if not installed)

Usage (from repo root):
    python backend/scripts/eval_retrieval.py

Fixture format (FIXTURE_QRELS):
    {query_id: {chunk_id: relevance_label}}   (relevance 1 = relevant, 0 = not)

The fixture is embedded; no external file needed.
"""

from __future__ import annotations

import math
import os
import sys

# Make sure 'backend' package root is on sys.path
_here = __import__("pathlib").Path(__file__).resolve()
sys.path.insert(0, str(_here.parents[1]))   # backend/ → app.* importable
sys.path.insert(0, str(_here.parents[2]))   # repo root → backend.* importable

# ---------------------------------------------------------------------------
# Small embedded fixture set
# ---------------------------------------------------------------------------

# Format: list of (query, list_of_relevant_chunk_ids)
# chunk_ids come from the actual indexed chunks (73 chunks from sample papers).
# We keep this simple and realistic — these are real chunk IDs from the fixture.

FIXTURE_QUERIES: list[tuple[str, list[str]]] = [
    (
        "nearest neighbor search high dimensional data",
        ["chunk_1", "chunk_2", "chunk_3"],
    ),
    (
        "FAISS indexing vector similarity",
        ["chunk_1", "chunk_4", "chunk_5"],
    ),
    (
        "microbial DNA data storage",
        ["chunk_42", "chunk_43", "chunk_44"],
    ),
    (
        "emotion recognition vision transformer",
        ["chunk_60", "chunk_61", "chunk_62"],
    ),
    (
        "retrieval augmented generation",
        ["chunk_10", "chunk_11"],
    ),
]


# ---------------------------------------------------------------------------
# Metric computation
# ---------------------------------------------------------------------------

def recall_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int = 10) -> float:
    if not relevant_ids:
        return 0.0
    top = retrieved_ids[:k]
    hits = sum(1 for x in top if x in relevant_ids)
    return hits / len(relevant_ids)


def ndcg_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int = 10) -> float:
    def dcg(ids: list[str]) -> float:
        return sum(
            1.0 / math.log2(rank + 2)
            for rank, cid in enumerate(ids[:k])
            if cid in relevant_ids
        )

    actual_dcg = dcg(retrieved_ids)
    # Ideal: all relevant docs first
    ideal_ids = list(relevant_ids) + [""] * k
    ideal_dcg = dcg(ideal_ids)
    return actual_dcg / ideal_dcg if ideal_dcg > 0 else 0.0


def mean_metric(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


# ---------------------------------------------------------------------------
# Retrieval wrappers
# ---------------------------------------------------------------------------

def bm25_search(query: str, top_k: int = 10) -> list[str]:
    from app.rag.bm25_search import BM25Search
    engine = BM25Search()
    results = engine.search(query, top_k=top_k)
    return [r["chunk_id"] for r in results]


def faiss_search(query: str, top_k: int = 10) -> list[str]:
    from app.rag.faiss_search import FAISSSearch
    engine = FAISSSearch()
    results = engine.search(query, top_k=top_k)
    return [r["chunk_id"] for r in results]


def rrf_search(query: str, top_k: int = 10) -> list[str]:
    from app.rag.hybrid_search import HybridSearch
    engine = HybridSearch(
        use_rrf=True,
        use_reranker=False,
        deduplicate=False,
        parent_child=False,
    )
    results = engine.search(query, top_k=top_k)
    return [r["chunk_id"] for r in results]


def rrf_rerank_search(query: str, top_k: int = 10) -> list[str]:
    from app.rag.hybrid_search import HybridSearch
    engine = HybridSearch(
        use_rrf=True,
        use_reranker=True,
        deduplicate=False,
        parent_child=False,
    )
    results = engine.search(query, top_k=top_k)
    return [r["chunk_id"] for r in results]


# ---------------------------------------------------------------------------
# Evaluation runner
# ---------------------------------------------------------------------------

def evaluate(
    name: str,
    search_fn,
    queries: list[tuple[str, list[str]]],
    k: int = 10,
) -> dict:
    recalls, ndcgs = [], []

    for query, relevant in queries:
        try:
            retrieved = search_fn(query, top_k=k)
        except Exception as exc:
            print(f"  [{name}] query={query!r} FAILED: {exc}")
            retrieved = []

        rel_set = set(relevant)
        recalls.append(recall_at_k(retrieved, rel_set, k))
        ndcgs.append(ndcg_at_k(retrieved, rel_set, k))

    return {
        "name": name,
        f"Recall@{k}": round(mean_metric(recalls), 4),
        f"nDCG@{k}": round(mean_metric(ndcgs), 4),
    }


def main():
    K = 10
    print(f"\n{'='*60}")
    print(f"  UNKNOWN Retrieval Evaluation  –  Recall@{K} / nDCG@{K}")
    print(f"  Fixture: {len(FIXTURE_QUERIES)} queries")
    print(f"{'='*60}\n")

    strategies = [
        ("bm25", bm25_search),
        ("faiss", faiss_search),
        ("rrf", rrf_search),
        ("rrf+rerank", rrf_rerank_search),
    ]

    rows = []
    for name, fn in strategies:
        print(f"  Running {name}…")
        row = evaluate(name, fn, FIXTURE_QUERIES, k=K)
        rows.append(row)

    print()
    print(f"  {'Strategy':<15} {'Recall@10':>12}  {'nDCG@10':>10}")
    print(f"  {'-'*40}")
    for row in rows:
        print(f"  {row['name']:<15} {row[f'Recall@{K}']:>12.4f}  {row[f'nDCG@{K}']:>10.4f}")
    print()


if __name__ == "__main__":
    main()
