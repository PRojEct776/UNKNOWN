"""
UNKNOWN X v2.0 - RAG Service

Production application service connecting:
Query
→ Query Understanding
→ Hybrid Retrieval
→ Evidence Trail
→ Context Builder
→ Prompt Engine
→ Gemini
→ Document IQ
→ API Response
"""

from app.api.schemas import QueryResponse, Source
from app.llm.gemini_provider import GeminiProvider
from app.query.query_understanding import (
    QueryType as BhagyaQueryType,
)
from app.query.query_understanding import (
    QueryUnderstanding,
)
from app.rag.context_builder import ContextBuilder
from app.rag.evidence import build_evidence
from app.rag.hybrid_search import HybridSearch
from app.rag.logger import logger
from app.rag.prompt_engine import (
    PromptEngine,
)
from app.rag.prompt_engine import (
    QueryType as PromptQueryType,
)
from app.rag.scoring import calculate_document_iq
from app.services.document_service import (
    build_document_metadata,
    save_document_metadata,
)


class RAGService:
    """Application service for the UNKNOWN X RAG pipeline."""

    def __init__(self):
        logger.info("Initializing UNKNOWN X RAG Service...")

        self.query_understanding = QueryUnderstanding()
        self.retriever = HybridSearch()
        self.context_builder = ContextBuilder(max_chunks=5)
        self.prompt_engine = PromptEngine()
        self.gemini = GeminiProvider()

        logger.info("UNKNOWN X RAG Service initialized successfully.")

    @staticmethod
    def _map_query_type(
        query_type: BhagyaQueryType,
    ) -> PromptQueryType:
        """Convert Bhagya QueryType into PromptEngine QueryType."""

        try:
            return PromptQueryType[query_type.name]
        except KeyError as error:
            raise ValueError(f"Unsupported query type: {query_type}") from error

    def query(self, user_query: str) -> QueryResponse:
        """
        Execute the complete UNKNOWN X RAG pipeline.
        """

        logger.info(f"Processing query: {user_query}")

        # ==================================================
        # 1. Query Understanding
        # ==================================================

        understanding = self.query_understanding.analyze(user_query)
        normalized_query = understanding.query

        query_type = self._map_query_type(understanding.query_type)

        logger.info(f"Query Type: {query_type.value}")

        # ==================================================
        # 2. Hybrid Retrieval
        # ==================================================

        results = self.retriever.search(normalized_query)

        logger.info(f"Retrieved {len(results)} chunks.")

        # ==================================================
        # 3. Evidence Trail
        # ==================================================

        evidence = build_evidence(results)

        logger.info(f"Evidence generated for {len(evidence)} chunks.")

        # ==================================================
        # 4. Document IQ Generation
        # ==================================================

        processed_documents = set()

        for item in evidence:

            document_name = item["document"]

            if document_name in processed_documents:
                continue

            try:
                metadata = build_document_metadata(document_name)

                iq_report = calculate_document_iq(metadata)

                metadata["document_iq"] = iq_report

                save_document_metadata(metadata)

                logger.info(
                    f"Document IQ generated for {document_name} "
                    f"({iq_report['iq_score']})"
                )

            except Exception as error:  # noqa: BLE001
                logger.warning(f"Document IQ failed for {document_name}: {error}")

            processed_documents.add(document_name)

        # ==================================================
        # 5. Context Building
        # ==================================================

        context = self.context_builder.build(results)

        # ==================================================
        # 6. Prompt Generation
        # ==================================================

        prompt = self.prompt_engine.build_prompt(
            query=normalized_query,
            context=context,
            query_type=query_type,
        )

        # ==================================================
        # 7. Gemini Generation
        # ==================================================

        response = self.gemini.generate(prompt)

        if not response.success:
            raise RuntimeError(response.error or "Gemini generation failed.")

        answer = response.answer

        # ==================================================
        # 8. API Source Formatting
        # ==================================================

        sources = [
            Source(
                rank=result.get("rank", 0),
                document=result.get("document", "Unknown"),
                page=result.get("page", "N/A"),
                chunk_id=result.get("chunk_id", "N/A"),
                hybrid_score=float(result.get("hybrid_score", 0.0)),
                bm25_score=float(result.get("bm25_score", 0.0)),
                faiss_score=float(result.get("faiss_score", 0.0)),
            )
            for result in results
        ]

        logger.info(f"Pipeline completed successfully with {len(sources)} sources.")

        # ==================================================
        # 9. FastAPI Response
        # ==================================================

        return QueryResponse(
            query=normalized_query,
            query_type=query_type.value,
            answer=answer,
            sources=sources,
        )
