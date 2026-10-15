"""
Hybrid Retrieval Engine for UNKNOWN

Combines BM25 lexical retrieval and FAISS semantic retrieval
using weighted score fusion.
"""

from app.rag.bm25_search import BM25Search
from app.rag.config import settings
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
        document_names: list[str] | None = None,
    ):
        """
        Perform hybrid retrieval.

        Args:
            query (str): User query.
            top_k (int): Number of final results.
            document_names (list[str], optional): Scope search to specified documents.

        Returns:
            list: Hybrid ranked results.
        """

        if top_k is None:
            top_k = settings.TOP_K_RESULTS

        doc_filter = set(document_names) if document_names else None

        # Expand budget for multi-document comparisons/queries to guarantee coverage across all selected papers
        if doc_filter and len(doc_filter) > 1:
            effective_top_k = max(top_k, min(len(doc_filter) * 2, 30))
        else:
            effective_top_k = top_k

        logger.info(f"Hybrid search query: {query} (scoped to {len(doc_filter) if doc_filter else 'all'} docs)")

        # Retrieve extra candidates from both engines
        bm25_results = self.bm25.search(query, effective_top_k * 2, document_names=document_names)
        faiss_results = self.faiss.search(query, effective_top_k * 2, document_names=document_names)

        # Normalize scores independently
        bm25_results = self.normalize_scores(bm25_results)
        faiss_results = self.normalize_scores(faiss_results)

        merged_results = {}

        # ---------------- BM25 Results ----------------
        for result in bm25_results:
            chunk_id = result["chunk_id"]

            merged_results[chunk_id] = {
                **result,
                "bm25_score": result["normalized_score"],
                "faiss_score": 0.0,
            }

        # ---------------- FAISS Results ----------------
        for result in faiss_results:
            chunk_id = result["chunk_id"]

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

        # Balanced multi-document selection:
        # Guarantee that every selected document with available matching chunks is represented
        if doc_filter and len(doc_filter) > 1:
            selected_final = []
            for doc in doc_filter:
                doc_chunks = [r for r in hybrid_results if r.get("document") == doc]
                for chunk in doc_chunks[:2]:
                    if chunk not in selected_final:
                        selected_final.append(chunk)

            for chunk in hybrid_results:
                if len(selected_final) >= effective_top_k:
                    break
                if chunk not in selected_final:
                    selected_final.append(chunk)

            selected_final.sort(key=lambda item: item["hybrid_score"], reverse=True)
            final_results = selected_final[:effective_top_k]
        else:
            final_results = hybrid_results[:effective_top_k]

        for rank, result in enumerate(final_results, start=1):
            result["rank"] = rank

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
