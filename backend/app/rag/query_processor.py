"""
Query Processing Engine for UNKNOWN

Converts a user's search query into:
1. Normalized keyword tokens for BM25.
2. Dense semantic embedding for FAISS.
"""

import re

from app.rag.embedder import embed_text


# -------------------------------------------------------------------
# Standalone lexical preprocessing functions (used by BM25 indexing/search)
# -------------------------------------------------------------------

def normalize_text(text: str) -> str:
    """
    Normalize text for lexical retrieval (BM25).
    """
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize_text(text: str) -> list[str]:
    """
    Convert text into BM25 tokens.
    """
    return normalize_text(text).split()


# -------------------------------------------------------------------
# Query Processor
# -------------------------------------------------------------------

class QueryProcessor:
    """
    Process user queries for the hybrid retrieval pipeline.
    """

    @staticmethod
    def normalize_query(query: str) -> str:
        return normalize_text(query)

    def tokenize_query(self, query: str):
        return tokenize_text(query)

    def generate_embedding(self, query: str):
        """
        Generate semantic embedding from the RAW query.
        """
        return embed_text(query)

    def process(self, query: str):
        """
        Complete processing pipeline.
        """
        normalized_query = self.normalize_query(query)

        return {
            "original_query": query,
            "normalized_query": normalized_query,
            "tokens": self.tokenize_query(query),
            "embedding": self.generate_embedding(query),
        }


# ---------------------- TEST BLOCK ---------------------- #

if __name__ == "__main__":

    processor = QueryProcessor()

    sample_query = "Explain virtualization in Cloud Computing!!"

    result = processor.process(sample_query)

    print("\n========== QUERY PROCESSOR TEST ==========")
    print(f"Original Query   : {result['original_query']}")
    print(f"Normalized Query : {result['normalized_query']}")
    print(f"Tokens           : {result['tokens']}")
    print(f"Embedding Shape  : {result['embedding'].shape}")
    print(f"First 5 Values   : {result['embedding'][:5]}")
    print("==========================================")