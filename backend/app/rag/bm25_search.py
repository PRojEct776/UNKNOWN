"""
BM25 Search Engine for UNKNOWN

Loads the BM25 index and retrieves the Top-K most relevant
document chunks for a user query.
"""

import json
import pickle

from app.rag.config import settings
from app.rag.logger import logger
from app.rag.query_processor import tokenize_text


class BM25Search:
    """
    BM25 lexical search engine.
    """

    def __init__(self):
        logger.info("Initializing BM25 Search Engine...")

        # Load BM25 index
        index_path = settings.VECTOR_DIR / "bm25_index.pkl"

        with open(index_path, "rb") as file:
            self.bm25 = pickle.load(file)

        # Load chunk metadata
        chunk_path = settings.CHUNK_DIR / "chunks.json"

        with open(chunk_path, "r", encoding="utf-8") as file:
            self.chunks = json.load(file)

        logger.info(f"Loaded BM25 index with {len(self.chunks)} chunks.")

    def search(self, query: str, top_k: int = None):
        """
        Perform BM25 search.

        Args:
            query (str): User query.
            top_k (int): Number of results to return.

        Returns:
            list: Ranked search results.
        """

        if top_k is None:
            top_k = settings.TOP_K_RESULTS

        # Tokenize query
        query_tokens = tokenize_text(query)

        # BM25 scores for every chunk
        scores = self.bm25.get_scores(query_tokens)

        # Sort chunks by score (highest first)
        ranked_indices = sorted(
            range(len(scores)),
            key=lambda i: scores[i],
            reverse=True
        )

        results = []

        for idx in ranked_indices:

            # Ignore chunks with zero relevance
            if scores[idx] <= 0:
                continue

            chunk = self.chunks[idx]

            results.append(
                {
                    "rank": len(results) + 1,
                    "score": round(float(scores[idx]), 4),
                    "chunk_id": chunk["chunk_id"],
                    "document": chunk["document"],
                    "page": chunk["page"],
                    "text": chunk["text"],
                }
            )

            # Stop after top_k relevant results
            if len(results) == top_k:
                break

        return results


# ---------------------- TEST BLOCK ---------------------- #

if __name__ == "__main__":

    engine = BM25Search()

    test_queries = [
        "semantic retrieval",
        "context compression",
        "retrieval augmented generation",
        "cloud virtualization"  # Expected to return no results for this paper
    ]

    print("\n========== BM25 SEARCH TEST ==========")

    for query in test_queries:

        print(f"\nQuery: {query}")

        results = engine.search(query)

        if not results:
            print("No relevant chunks found.")
            continue

        for result in results:
            print("-" * 40)
            print(f"Rank     : {result['rank']}")
            print(f"Score    : {result['score']}")
            print(f"Document : {result['document']}")
            print(f"Page     : {result['page']}")
            print(f"Chunk ID : {result['chunk_id']}")
            print(f"Preview  : {result['text'][:120]}...")

    print("\n======================================")