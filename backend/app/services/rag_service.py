"""
UNKNOWN X v2.3+ - RAG Service

Production application service connecting:

Query
→ Query Understanding
→ Hybrid Retrieval
→ Evidence Trail
→ Context Builder
→ Prompt Engine
→ Multi-LLM Orchestrator
→ Document IQ
→ API Response

Additional capabilities:
→ Claim Verification
→ Contradiction Finder
→ Research Comparison
"""

from app.api.schemas import (
    ClaimVerificationResponse,
    QueryResponse,
    Source,
)
from app.llm.orchestrator import get_orchestrator
from app.query.query_understanding import (
    QueryType as BhagyaQueryType,
)
from app.query.query_understanding import (
    QueryUnderstanding,
)
from app.rag.adaptive_answer import AdaptiveAnswerEngine
from app.rag.claim_verifier import ClaimVerifier
from app.rag.context_builder import ContextBuilder
from app.rag.contradiction_finder import ContradictionFinder
from app.rag.debate_engine import DebateEngine
from app.rag.evidence import build_evidence
from app.rag.hybrid_search import HybridSearch
from app.rag.knowledge_dna import KnowledgeDNA
from app.rag.knowledge_mind_map import KnowledgeMindMapEngine
from app.rag.logger import logger
from app.rag.prompt_engine import (
    PromptEngine,
)
from app.rag.prompt_engine import (
    QueryType as PromptQueryType,
)
from app.rag.research_comparison import ResearchComparisonEngine
from app.rag.research_gap_finder import ResearchGapFinder
from app.rag.scoring import calculate_document_iq
from app.services.document_service import (
    build_document_metadata,
    save_document_metadata,
)


class RAGService:
    """Application service for the UNKNOWN X RAG pipeline."""

    def __init__(self):
        logger.info("Initializing UNKNOWN X RAG Service...")

        # ==================================================
        # CORE RAG COMPONENTS
        # ==================================================

        self.query_understanding = QueryUnderstanding()

        self.retriever = HybridSearch()

        self.context_builder = ContextBuilder(max_chunks=5)

        self.prompt_engine = PromptEngine()

        self.debate_engine = DebateEngine()

        self.knowledge_dna = KnowledgeDNA()

        self.knowledge_mind_map = KnowledgeMindMapEngine()

        self.adaptive_answer = AdaptiveAnswerEngine()

        # ==================================================
        # UNIQUE UNKNOWN FEATURES
        # ==================================================

        self.claim_verifier = ClaimVerifier()

        self.contradiction_finder = ContradictionFinder()

        self.research_comparison = ResearchComparisonEngine()

        self.research_gap_finder = ResearchGapFinder()

        # ==================================================
        # MULTI-LLM ORCHESTRATOR
        # ==================================================

        self.llm = get_orchestrator()

        logger.info("UNKNOWN X RAG Service initialized successfully.")

    # ======================================================
    # QUERY TYPE MAPPING
    # ======================================================

    @staticmethod
    def _map_query_type(
        query_type: BhagyaQueryType,
    ) -> PromptQueryType:
        """
        Convert Query Understanding QueryType
        into PromptEngine QueryType.
        """

        try:
            return PromptQueryType[query_type.name]

        except KeyError as error:
            raise ValueError(f"Unsupported query type: {query_type}") from error

    def determine_answer_mode(self, query: str):
        """Determine the appropriate answer mode for a user query."""

        if not query or not query.strip():
            raise ValueError("Query must not be empty.")

        return self.adaptive_answer.classify_query(query)

    # ======================================================
    # SOURCE FORMATTER
    # ======================================================

    @staticmethod
    def _build_sources(results) -> list[Source]:
        """
        Convert retrieval results into API Source objects.
        """

        return [
            Source(
                rank=result.get(
                    "rank",
                    0,
                ),
                document=result.get(
                    "document",
                    "Unknown",
                ),
                page=result.get(
                    "page",
                    "N/A",
                ),
                chunk_id=result.get(
                    "chunk_id",
                    "N/A",
                ),
                hybrid_score=float(
                    result.get(
                        "hybrid_score",
                        0.0,
                    )
                ),
                bm25_score=float(
                    result.get(
                        "bm25_score",
                        0.0,
                    )
                ),
                faiss_score=float(
                    result.get(
                        "faiss_score",
                        0.0,
                    )
                ),
            )
            for result in results
        ]

    # ======================================================
    # EVIDENCE FORMATTER
    # ======================================================

    @staticmethod
    def _build_feature_evidence(results) -> list[dict]:
        """
        Convert retrieval results into evidence objects
        used by advanced RAG features.
        """

        return [
            {
                "document": result.get(
                    "document",
                    "Unknown",
                ),
                "page": result.get(
                    "page",
                    "N/A",
                ),
                "chunk_id": result.get(
                    "chunk_id",
                    "N/A",
                ),
                "text": result.get(
                    "text",
                    "",
                ),
            }
            for result in results
        ]

    # ======================================================
    # MAIN RAG QUERY
    # ======================================================

    def query(
        self,
        user_query: str,
    ) -> QueryResponse:
        """
        Execute the complete UNKNOWN X RAG pipeline.
        """

        logger.info(f"Processing query: {user_query}")

        # ==================================================
        # 1. QUERY UNDERSTANDING
        # ==================================================

        understanding = self.query_understanding.analyze(user_query)

        normalized_query = understanding.query

        query_type = self._map_query_type(understanding.query_type)

        logger.info(f"Query Type: {query_type.value}")

        # ==================================================
        # 2. HYBRID RETRIEVAL
        # ==================================================

        results = self.retriever.search(normalized_query)

        logger.info(f"Retrieved {len(results)} chunks.")

        # ==================================================
        # 3. EVIDENCE TRAIL
        # ==================================================

        evidence = build_evidence(results)

        logger.info(f"Evidence generated for {len(evidence)} chunks.")

        # ==================================================
        # 4. DOCUMENT IQ
        # ==================================================

        processed_documents = set()

        for item in evidence:

            document_name = item.get(
                "document",
                "Unknown",
            )

            if document_name in processed_documents:
                continue

            try:

                metadata = build_document_metadata(document_name)

                iq_report = calculate_document_iq(metadata)

                metadata["document_iq"] = iq_report

                save_document_metadata(metadata)

                logger.info(
                    f"Document IQ generated for "
                    f"{document_name} "
                    f"({iq_report['iq_score']})"
                )

            except Exception as error:  # noqa: BLE001
                logger.warning(f"Document IQ failed for " f"{document_name}: {error}")

            processed_documents.add(document_name)

        # ==================================================
        # 5. CONTEXT BUILDING
        # ==================================================

        context = self.context_builder.build(results)

        # ==================================================
        # 6. PROMPT GENERATION
        # ==================================================

        prompt = self.prompt_engine.build_prompt(
            query=normalized_query,
            context=context,
            query_type=query_type,
        )

        # ==================================================
        # 7. MULTI-LLM GENERATION
        # ==================================================

        response = self.llm.generate(prompt)

        if not response.success:

            error = RuntimeError(response.error or "LLM generation failed.")

            error.error_kind = response.error_kind  # type: ignore

            raise error

        answer = response.answer

        # ==================================================
        # 8. SOURCE FORMATTING
        # ==================================================

        sources = self._build_sources(results)

        logger.info("Pipeline completed successfully " f"with {len(sources)} sources.")

        # ==================================================
        # 9. API RESPONSE
        # ==================================================

        return QueryResponse(
            query=normalized_query,
            query_type=query_type.value,
            answer=answer,
            sources=sources,
        )

    # ======================================================
    # CLAIM VERIFICATION
    # ======================================================

    def verify_claim(
        self,
        claim: str,
    ) -> ClaimVerificationResponse:
        """
        Verify a user-provided claim against
        retrieved document evidence.
        """

        logger.info(f"Verifying claim: {claim}")

        # ==================================================
        # 1. RETRIEVE EVIDENCE
        # ==================================================

        results = self.retriever.search(claim)

        logger.info(f"Retrieved {len(results)} chunks " f"for claim verification.")

        # ==================================================
        # 2. BUILD CONTEXT
        # ==================================================

        context = self.context_builder.build(results)

        # ==================================================
        # 3. BUILD VERIFICATION PROMPT
        # ==================================================

        prompt = self.claim_verifier.build_verification_prompt(
            claim=claim,
            context=context,
        )

        # ==================================================
        # 4. LLM ANALYSIS
        # ==================================================

        response = self.llm.generate(prompt)

        if not response.success:

            error = RuntimeError(response.error or "Claim verification failed.")

            error.error_kind = response.error_kind  # type: ignore

            raise error

        # ==================================================
        # 5. PARSE VERIFICATION RESULT
        # ==================================================

        verification = self.claim_verifier.parse_response(
            claim=claim,
            response_text=response.answer,
        )

        # ==================================================
        # 6. SOURCES
        # ==================================================

        sources = self._build_sources(results)

        logger.info("Claim verification completed: " f"{verification.verdict.value}")

        return ClaimVerificationResponse(
            claim=verification.claim,
            verdict=verification.verdict.value,
            confidence=verification.confidence,
            explanation=verification.explanation,
            evidence=verification.evidence,
            source_chunk_ids=(verification.source_chunk_ids),
            sources=sources,
        )

    # ======================================================
    # CONTRADICTION FINDER
    # ======================================================

    def find_contradictions(
        self,
        query: str,
    ):
        """
        Detect contradictions across retrieved
        document evidence.
        """

        logger.info(f"Running contradiction analysis: {query}")

        # ==================================================
        # 1. RETRIEVE EVIDENCE
        # ==================================================

        results = self.retriever.search(query)

        logger.info(f"Retrieved {len(results)} chunks " f"for contradiction analysis.")

        # ==================================================
        # 2. PREPARE EVIDENCE
        # ==================================================

        evidence = self._build_feature_evidence(results)

        # ==================================================
        # 3. BUILD PROMPT
        # ==================================================

        prompt = self.contradiction_finder.build_contradiction_prompt(
            query=query,
            evidence=evidence,
        )

        # ==================================================
        # 4. LLM ANALYSIS
        # ==================================================

        response = self.llm.generate(prompt)

        if not response.success:

            error = RuntimeError(response.error or "Contradiction analysis failed.")

            error.error_kind = response.error_kind  # type: ignore

            raise error

        # ==================================================
        # 5. PARSE RESULT
        # ==================================================

        report = self.contradiction_finder.parse_response(
            query=query,
            response_text=response.answer,
        )

        logger.info(
            "Contradiction analysis completed: "
            f"{report.contradictions_found} "
            "contradictions found."
        )

        return report

    # ======================================================
    # RESEARCH COMPARISON
    # ======================================================

    def compare_research(
        self,
        query: str,
    ):
        """
        Compare research entities using only
        retrieved document evidence.
        """

        logger.info(f"Running research comparison: {query}")

        # ==================================================
        # 1. RETRIEVE RELEVANT EVIDENCE
        # ==================================================

        results = self.retriever.search(query)

        logger.info(f"Retrieved {len(results)} chunks " f"for research comparison.")

        # ==================================================
        # 2. PREPARE EVIDENCE
        # ==================================================

        evidence = self._build_feature_evidence(results)

        # ==================================================
        # 3. BUILD COMPARISON PROMPT
        # ==================================================

        prompt = self.research_comparison.build_comparison_prompt(
            query=query,
            evidence=evidence,
        )

        # ==================================================
        # 4. LLM ANALYSIS
        # ==================================================

        response = self.llm.generate_structured(prompt)

        if not response.success:

            error = RuntimeError(response.error or "Research comparison failed.")

            error.error_kind = response.error_kind  # type: ignore

            raise error

        # ==================================================
        # 5. PARSE STRUCTURED RESULT
        # ==================================================

        report = self.research_comparison.parse_response(
            query=query,
            response_text=response.answer,
        )

        logger.info(
            "Research comparison completed: "
            f"{len(report.entities)} entities, "
            f"{len(report.comparison)} comparison aspects."
        )

        return report

    def generate_knowledge_dna(self, query): ...


def run_debate(
    self,
    query: str,
    position_a: str,
    position_b: str,
):
    results = self.retriever.search(query)

    evidence = self._build_feature_evidence(results)

    prompt = self.debate_engine.build_debate_prompt(
        query=query,
        position_a=position_a,
        position_b=position_b,
        evidence=evidence,
    )

    response = self.llm.generate_structured(prompt)

    if not response.success:
        error = RuntimeError(response.error or "AI debate generation failed.")
        error.error_kind = response.error_kind  # type: ignore
        raise error

    return self.debate_engine.parse_response(
        query=query,
        position_a=position_a,
        position_b=position_b,
        response_text=response.answer,
    )


def generate_knowledge_dna(self, query: str):
    results = self.retriever.search(query)

    evidence = self._build_feature_evidence(results)

    prompt = self.knowledge_dna.build_dna_prompt(
        query=query,
        evidence=evidence,
    )

    response = self.llm.generate_structured(prompt)

    if not response.success:
        error = RuntimeError(response.error or "Knowledge DNA generation failed.")
        error.error_kind = response.error_kind  # type: ignore
        raise error

    return self.knowledge_dna.parse_response(
        query=query,
        response_text=response.answer,
    )


def generate_knowledge_mind_map(self, query: str):
    results = self.retriever.search(query)

    evidence = self._build_feature_evidence(results)

    prompt = self.knowledge_mind_map.build_mind_map_prompt(
        query=query,
        evidence=evidence,
    )

    response = self.llm.generate_structured(prompt)

    if not response.success:
        error = RuntimeError(response.error or "Knowledge mind map generation failed.")
        error.error_kind = response.error_kind  # type: ignore
        raise error

    return self.knowledge_mind_map.parse_response(
        query=query,
        response_text=response.answer,
    )


def find_research_gaps(self, query: str):
    """Identify evidence-grounded research gaps."""
    results = self.retriever.search(query)

    evidence = self._build_feature_evidence(results)

    prompt = self.research_gap_finder.build_gap_prompt(
        query=query,
        evidence=evidence,
    )

    response = self.llm.generate_structured(prompt)

    if not response.success:
        error = RuntimeError(response.error or "Research gap detection failed.")
        error.error_kind = response.error_kind  # type: ignore
        raise error

    return self.research_gap_finder.parse_response(
        query=query,
        response_text=response.answer,
    )
