"""
UNKNOWN Project - Sprint 3
Context Builder (Final Version)

Builds Gemini-ready context from Hybrid Search results.
"""

from typing import List, Dict


class ContextBuilder:
    """Formats retrieved chunks into structured context for Gemini."""

    def __init__(self, max_chunks: int = 5, max_chars: int = 1200):
        self.max_chunks = max_chunks
        self.max_chars = max_chars

    def build(self, search_results: List[Dict]) -> str:
        """
        Convert HybridSearch.search() output into Gemini context.

        Expected schema:
        {
            "rank": 1,
            "hybrid_score": 0.94,
            "bm25_score": 13.5,
            "faiss_score": 0.87,
            "document": "cloud_notes.pdf",
            "page": 12,
            "chunk_id": "chunk_12_03",
            "text": "Cloud computing provides..."
        }
        """

        if not search_results:
            return "No relevant context found."

        context_blocks = []

        for result in search_results[: self.max_chunks]:

            rank = result.get("rank", "?")
            document = result.get("document", "Unknown Document")
            page = result.get("page", "N/A")
            chunk_id = result.get("chunk_id", "N/A")

            hybrid_score = result.get("hybrid_score", "N/A")
            bm25_score = result.get("bm25_score", "N/A")
            faiss_score = result.get("faiss_score", "N/A")

            text = result.get("text", "").strip()

            # Limit chunk length for Gemini
            if len(text) > self.max_chars:
                text = text[: self.max_chars] + "..."

            block = f"""
### Source {rank}

Document: {document}
Page: {page}
Chunk ID: {chunk_id}

Relevance Scores
- Hybrid : {hybrid_score}
- BM25   : {bm25_score}
- FAISS  : {faiss_score}

Evidence:
{text}
""".strip()

            context_blocks.append(block)

        return ("\n\n" + "=" * 60 + "\n\n").join(context_blocks)