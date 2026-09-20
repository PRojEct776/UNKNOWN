"""
UNKNOWN Project - RAG Service

Connects the verified RAG pipeline to the FastAPI layer.

Pipeline:
Query
→ Query Understanding
→ Hybrid Search
→ Context Builder
→ Prompt Engine
→ Gemini
→ Response
"""

from app.api.schemas import QueryResponse, Source

from app.query.query_understanding import (
    QueryUnderstanding,
    QueryType as BhagyaQueryType,
)

from app.rag.context_builder import ContextBuilder
from app.rag.hybrid_search import HybridSearch
from app.rag.llm_engine import GeminiEngine
from app.rag.logger import logger
from app.rag.prompt_engine import (
    PromptEngine,
    QueryType as PromptQueryType,
)


class RAGService:
    """Application service for the UNKNOWN RAG pipeline."""

    def __init__(self):
        logger.info("Initializing UNKNOWN RAG Service...")

        # Initialize once at application startup.
        self.query_understanding = QueryUnderstanding()
        self.retriever = HybridSearch()
        self.context_builder = ContextBuilder(max_chunks=5)
        self.prompt_engine = PromptEngine()
        self.gemini = GeminiEngine()

        logger.info("UNKNOWN RAG Service initialized successfully.")

    @staticmethod
    def _map_query_type(
        query_type: BhagyaQueryType,
    ) -> PromptQueryType:
        """
        Convert Bhagya's QueryType enum into the
        existing PromptEngine QueryType enum.
        """
        try:
            return PromptQueryType[query_type.name]
        except KeyError as error:
            raise ValueError(
                f"Unsupported query type: {query_type}"
            ) from error

    def query(self, user_query: str) -> QueryResponse:
        """
        Execute the complete RAG pipeline for a user query.
        """

        logger.info(f"Processing API query: {user_query}")

        # --------------------------------------------------
        # 1. Query Understanding
        # --------------------------------------------------

        understanding = self.query_understanding.analyze(user_query)
        normalized_query = understanding.query

        # --------------------------------------------------
        # 2. Query Type Mapping
        # --------------------------------------------------

        query_type = self._map_query_type(
            understanding.query_type
        )

        logger.info(
            f"Query type detected: {query_type.value}"
        )

        # --------------------------------------------------
        # 3. Hybrid Retrieval
        # --------------------------------------------------

        results = self.retriever.search(normalized_query)

        # --------------------------------------------------
        # 4. Context Building
        # --------------------------------------------------

        context = self.context_builder.build(results)

        # --------------------------------------------------
        # 5. Adaptive Prompt Generation
        # --------------------------------------------------

        prompt = self.prompt_engine.build_prompt(
            query=normalized_query,
            context=context,
            query_type=query_type,
        )

        # --------------------------------------------------
        # 6. Gemini Generation
        # --------------------------------------------------

        answer = self.gemini.generate(prompt)

        # --------------------------------------------------
        # 7. Source Formatting
        # --------------------------------------------------

        sources = [
            Source(
                rank=result.get("rank", 0),
                document=result.get("document", "Unknown"),
                page=result.get("page", "N/A"),
                chunk_id=result.get("chunk_id", "N/A"),
                hybrid_score=float(
                    result.get("hybrid_score", 0.0)
                ),
                bm25_score=float(
                    result.get("bm25_score", 0.0)
                ),
                faiss_score=float(
                    result.get("faiss_score", 0.0)
                ),
            )
            for result in results
        ]

        logger.info(
            f"API query completed. Retrieved {len(sources)} sources."
        )

        return QueryResponse(
            query=normalized_query,
            query_type=query_type.value,
            answer=answer,
            sources=sources,
        )