"""
Hybrid Retrieval Engine for UNKNOWN

Combines BM25 lexical retrieval and FAISS semantic retrieval
using weighted score fusion.
"""

from app.rag.bm25_search import BM25Search
from app.rag.config import settings
from app.rag.document_eligibility import (
    get_user_authorized_documents,
    is_test_document,
)
from app.rag.faiss_search import FAISSSearch
from app.rag.logger import logger


class HybridSearch:
    """
    UNKNOWN Hybrid Retrieval Engine.

    Combines:
    - BM25 lexical search
    - FAISS semantic search

    using weighted score fusion.
    """

    def __init__(self):
        logger.info("Initializing Hybrid Retrieval Engine...")

        self.bm25 = BM25Search()
        self.faiss = FAISSSearch()

        # Hybrid fusion weights
        # (Adaptive weights will come later in Sprint 4)
        self.alpha = 0.4  # BM25 weight
        self.beta = 0.6  # FAISS weight

    @staticmethod
    def normalize_scores(results, score_key="score"):
        """
        Min-Max normalize scores into the range [0,1].

        Args:
            results (list): Retrieval results.
            score_key (str): Key containing the raw score.

        Returns:
            list: Results with normalized_score.
        """

        if not results:
            return results

        scores = [result[score_key] for result in results]

        minimum = min(scores)
        maximum = max(scores)

        # Edge case: all scores are identical.
        if maximum == minimum:
            for result in results:
                result["normalized_score"] = 1.0
            return results

        for result in results:
            result["normalized_score"] = (result[score_key] - minimum) / (
                maximum - minimum
            )

        return results

    def search(
        self,
        query: str,
        top_k: int | None = None,
        doc_filter: list[str] | set[str] | None = None,
        user_id: str | None = None,
        exclude_test_docs: bool = False,
    ):
        """
        Perform hybrid retrieval.

        Args:
            query (str): User query.
            top_k (int): Number of final results.
            doc_filter (list | set | None): Optional list of allowed document names.
            user_id (str | None): Scopes search strictly to documents belonging to this workspace.
            exclude_test_docs (bool): Whether to exclude sample_ieee and test fixtures.

        Returns:
            list: Hybrid ranked results.
        """

        if top_k is None:
            top_k = settings.TOP_K_RESULTS

        logger.info(f"Hybrid search query: {query}")

        # If user_id is provided, resolve authorized documents for this workspace
        if user_id is not None:
            user_authorized = get_user_authorized_documents(
                user_id=user_id,
                include_test_docs=not exclude_test_docs,
            )
            if doc_filter is not None:
                allowed_docs = set(doc_filter).intersection(user_authorized)
            else:
                allowed_docs = user_authorized
        else:
            allowed_docs = set(doc_filter) if doc_filter is not None else None

        # Early exit: If workspace has no documents or allowed_docs is empty set
        if allowed_docs is not None and len(allowed_docs) == 0:
            logger.info("No authorized documents available for this query scope.")
            return []

        multiplier = 4 if (allowed_docs is not None or exclude_test_docs) else 2
        # Retrieve extra candidates from both engines.
        bm25_results = self.bm25.search(query, top_k * multiplier)
        faiss_results = self.faiss.search(query, top_k * multiplier)

        # Normalize scores independently.
        bm25_results = self.normalize_scores(bm25_results)
        faiss_results = self.normalize_scores(faiss_results)

        merged_results = {}

        # ---------------- BM25 Results ----------------
        for result in bm25_results:
            chunk_id = result["chunk_id"]
            doc_name = result.get("document", "")

            if allowed_docs is not None and doc_name not in allowed_docs:
                continue
            if exclude_test_docs and is_test_document(doc_name):
                continue

            merged_results[chunk_id] = {
                **result,
                "bm25_score": result["normalized_score"],
                "faiss_score": 0.0,
            }

        # ---------------- FAISS Results ----------------
        for result in faiss_results:
            chunk_id = result["chunk_id"]
            doc_name = result.get("document", "")

            if allowed_docs is not None and doc_name not in allowed_docs:
                continue
            if exclude_test_docs and is_test_document(doc_name):
                continue

            if chunk_id not in merged_results:
                merged_results[chunk_id] = {
                    **result,
                    "bm25_score": 0.0,
                    "faiss_score": result["normalized_score"],
                }
            else:
                merged_results[chunk_id]["faiss_score"] = result["normalized_score"]

        # ---------------- Hybrid Score Fusion ----------------
        hybrid_results = []

        for result in merged_results.values():

            hybrid_score = (
                self.alpha * result["bm25_score"] + self.beta * result["faiss_score"]
            )

            result["hybrid_score"] = round(hybrid_score, 4)

            hybrid_results.append(result)

        # Sort by hybrid score (highest first)
        hybrid_results.sort(key=lambda item: item["hybrid_score"], reverse=True)

        # Final top-k ranked results
        final_results = hybrid_results[:top_k]

        for rank, result in enumerate(final_results, start=1):
            result["rank"] = rank

        # NEW: Useful logging for Sprint 3 integration
        logger.info(f"Retrieved {len(final_results)} chunks.")

        return final_results


# ---------------------- TEST BLOCK ---------------------- #

if __name__ == "__main__":

    engine = HybridSearch()

    test_queries = [
        "semantic retrieval",
        "adaptive context compression",
        "reduce hallucinations in RAG",
        "cloud virtualization",
    ]

    print("\n========== HYBRID SEARCH TEST ==========")

    for query in test_queries:

        print(f"\nQuery: {query}")

        results = engine.search(query)

        if not results:
            print("No hybrid results found.")
            continue

        for result in results:
            print("-" * 45)
            print(f"Rank          : {result['rank']}")
            print(f"Hybrid Score  : {result['hybrid_score']}")
            print(f"BM25 Score    : {round(result['bm25_score'], 4)}")
            print(f"FAISS Score   : {round(result['faiss_score'], 4)}")
            print(f"Document      : {result['document']}")
            print(f"Page          : {result['page']}")
            print(f"Chunk ID      : {result['chunk_id']}")
            print(f"Preview       : {result['text'][:120]}...")

    print("\n========================================")
