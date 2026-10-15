"""
FAISS Semantic Search Engine for UNKNOWN

Loads the FAISS vector index and retrieves the Top-K
semantically similar document chunks for a user query.
"""

import json

import faiss
import numpy as np

from app.rag.config import settings
from app.rag.embedder import embed_text
from app.rag.logger import logger


class FAISSSearch:
    """
    Semantic search engine powered by FAISS.
    """

    def __init__(self):
        logger.info("Initializing FAISS Search Engine...")

        # Load FAISS index
        index_path = settings.VECTOR_DIR / "faiss.index"
        self.index = faiss.read_index(str(index_path))

        # Load metadata
        metadata_path = settings.VECTOR_DIR / "faiss_metadata.json"
        with open(metadata_path, "r", encoding="utf-8") as file:
            self.metadata = json.load(file)

        logger.info(f"Loaded FAISS index with {self.index.ntotal} vectors.")

    def search(
        self,
        query: str,
        top_k: int | None = None,
        document_names: list[str] | None = None,
    ):
        """
        Perform semantic similarity search.

        Args:
            query (str): User query.
            top_k (int): Number of results to return.
            document_names (list[str], optional): Scope search to specified documents.

        Returns:
            list: Ranked semantic search results.
        """

        if top_k is None:
            top_k = settings.TOP_K_RESULTS

        if not self.metadata or self.index.ntotal == 0:
            return []

        doc_filter = set(document_names) if document_names else None

        # Embed query (force float32 for FAISS compatibility)
        query_embedding = embed_text(query).reshape(1, -1).astype(np.float32)  # type: ignore

        # Retrieve extra candidates from FAISS when filtering by document
        fetch_k = min(self.index.ntotal, max(top_k * 4, 50)) if doc_filter else top_k

        similarities, indices = self.index.search(query_embedding, fetch_k)

        results = []

        for score, idx in zip(similarities[0], indices[0]):
            if idx == -1 or idx >= len(self.metadata):
                continue

            chunk = self.metadata[idx]

            if doc_filter is not None and chunk.get("document") not in doc_filter:
                continue

            results.append(
                {
                    "rank": len(results) + 1,
                    "score": round(float(score), 4),
                    "chunk_id": chunk["chunk_id"],
                    "document": chunk["document"],
                    "page": chunk["page"],
                    "text": chunk["text"],
                }
            )

            if len(results) == top_k:
                break

        return results


# ---------------------- TEST BLOCK ---------------------- #

if __name__ == "__main__":

    engine = FAISSSearch()

    test_queries = [
        "semantic retrieval",
        "reduce hallucinations in RAG",
        "adaptive context compression",
        "cloud virtualization",
    ]

    print("\n========== FAISS SEARCH TEST ==========")

    for query in test_queries:
        print(f"\nQuery: {query}")

        results = engine.search(query)

        if not results:
            print("No semantic results found.")
            continue

        for result in results:
            print("-" * 40)
            print(f"Rank     : {result['rank']}")
            print(f"Score    : {result['score']}")
            print(f"Document : {result['document']}")
            print(f"Page     : {result['page']}")
            print(f"Chunk ID : {result['chunk_id']}")
            print(f"Preview  : {result['text'][:120]}...")

    print("\n=======================================")
