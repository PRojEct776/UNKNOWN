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

from typing import Any

from app.api.schemas import (
    AnswerResponse,
    AnswerRequest,
    Claim,
    ClaimVerificationResponse,
    ComparisonPair,
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
from app.rag.config import settings
from app.rag.adaptive_answer import AdaptiveAnswerEngine
from app.rag.claim_verifier import ClaimVerifier
from app.rag.concept_discovery import ConceptDiscoveryEngine
from app.rag.context_builder import ContextBuilder
from app.rag.contradiction_finder import ContradictionFinder
from app.rag.debate_engine import DebateEngine
from app.rag.confidence import build_sources, compute_confidence
from app.rag.evidence import build_evidence
from app.rag.hybrid_search import HybridSearch
from app.rag.knowledge_dna import KnowledgeDNA
from app.rag.knowledge_mind_map import KnowledgeMindMapEngine
from app.rag.llm_engine import GeminiEngine
from app.rag.logger import logger
from app.rag.prompt_engine import (
    PromptEngine,
)
from app.rag.prompt_engine import (
    QueryType as PromptQueryType,
)
from app.rag.research_comparison import ResearchComparisonEngine, ResearchComparisonReport
from app.rag.research_gap_finder import ResearchGapFinder
from app.rag.scoring import calculate_document_iq
from app.rag.visual_answer import VisualAnswerEngine
from app.rag.grounded_generation import grounded_generate, NOT_FOUND as GROUNDED_NOT_FOUND
from app.rag.dual_retriever import (
    DualRetriever,
    _fetch_web_chunks,
    _web_gaps_from_statuses,
    web_chunk_to_source_dict,
)
from app.reasoning.reasoning_engine import ReasoningEngine
from app.services.document_service import (
    build_document_metadata,
    save_document_metadata,
)


def _verify_source_key(source):
    get = source.get if isinstance(source, dict) else (lambda k, d=None: getattr(source, k, d))
    key = (get("document"), get("page"), get("chunk_id"), get("url"))
    return repr(source) if all(v is None for v in key) else repr(key)


def _verify_web_failed(statuses):
    return any(
        s.get("outcome") in ("error", "timeout", "not_loaded") for s in (statuses or [])
    )


def _verify_web_gaps(statuses):
    try:
        return [str(g) for g in _web_gaps_from_statuses(statuses or [])]
    except Exception:  # noqa: BLE001
        return []


def _verify_web_note(web_chunks, statuses):
    parts = []
    if _verify_web_failed(statuses):
        parts.extend(_verify_web_gaps(statuses))
    if web_chunks:
        parts.append(
            "Web evidence reflects the retrieved web passages "
            "(abstracts or snippets), not the full pages."
        )
    return (" " + " ".join(parts)) if parts else ""


def _verify_empty_response(claim, mode, statuses):
    if mode == "web" or _verify_web_failed(statuses):
        verdict = "UNVERIFIABLE"
    else:
        verdict = "NOT_FOUND"
    scope = "web sources" if mode == "web" else "the selected documents or web sources"
    explanation = (
        "No usable evidence was retrieved from "
        + scope
        + ", so this claim could not be checked. "
        + " ".join(_verify_web_gaps(statuses))
    ).strip()
    return ClaimVerificationResponse(
        claim=claim,
        verdict=verdict,
        confidence=0.0,
        explanation=explanation,
        evidence=[],
        supporting_evidence=[],
        contradicting_evidence=[],
        source_chunk_ids=[],
        sources=[],
    )


def _verify_merge_web(doc_results, web_chunks, budget):
    docs = list(doc_results or [])
    web = [
        web_chunk_to_source_dict(c)
        for c in (web_chunks or [])
        if isinstance(c, dict) and c.get("text")
    ]
    if not web:
        return docs
    web_take = min(len(web), max(1, budget // 2))
    doc_take = min(len(docs), budget - web_take)
    web_take = min(len(web), budget - doc_take)
    merged = docs[:doc_take]
    for i, item in enumerate(web[:web_take]):
        item.setdefault("rank", doc_take + i + 1)
        merged.append(item)
    return merged


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

        self.concept_discovery = ConceptDiscoveryEngine()

        self.prompt_engine = PromptEngine()

        self.gemini = GeminiEngine()

        self.llm = get_orchestrator()

        self.reasoning_engine = ReasoningEngine(
            retriever=self.retriever,
            context_builder=self.context_builder,
            prompt_engine=self.prompt_engine,
            llm=self.llm,
            max_subquestions=3,
            top_k=5,
        )

        self.debate_engine = DebateEngine()

        self.knowledge_dna = KnowledgeDNA()

        self.knowledge_mind_map = KnowledgeMindMapEngine()

        self.adaptive_answer = AdaptiveAnswerEngine()

        self.visual_answer = VisualAnswerEngine()

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

        logger.info("UNKNOWN X RAG Service initialized successfully.")

    # ======================================================

    # DUAL-RETRIEVAL ANSWER  (Task A8)

    # ======================================================

    def answer(
        self,
        query: str,
        document_names: list[str] | None = None,
        doc_only: bool = False,
        scope: str | None = None,
    ) -> AnswerResponse:
        """
        Dual-retrieval answer: retrieve from user documents and (unless doc_only) from
        web connectors.  Produces doc_section, web_section, comparison[] pairs.

        When doc_only=True, connectors are never called (scope enforcement).
        """
        if not query or not query.strip():
            raise ValueError("Query must not be empty.")

        dr = DualRetriever(retriever=self.retriever, llm=self.llm)
        result = dr.dual_retrieve(
            query=query,
            document_names=document_names,
            doc_only=doc_only,
            scope=scope,
        )

        # Build canonical sources from both channels
        all_raw = list(result.doc_sources) + [
            web_chunk_to_source_dict(c) for c in result.web_sources
        ]
        sources = build_sources(all_raw)

        # Convert ComparisonPair dataclasses to schema objects
        comparison_schema = [
            ComparisonPair(
                sub_question=p.sub_question,
                label=p.label,
                doc_quote=p.doc_quote,
                web_quote=p.web_quote,
                doc_source=p.doc_source,
                web_source=p.web_source,
                nli_entail=p.nli_entail,
                nli_contra=p.nli_contra,
            )
            for p in result.comparison
        ]

        logger.info(
            "DualRetriever answer completed: %d doc chunks, %d web chunks, "
            "%d comparison pairs",
            len(result.doc_sources),
            len(result.web_sources),
            len(result.comparison),
        )

        # -----------------------------------------------------------
        # Compute confidence using the accuracy engine (A7)
        # -----------------------------------------------------------
        statuses = []
        if sources:
            statuses.append("sufficient")
        else:
            statuses.append("insufficient")

        # Derive claim-level labels from comparison pairs
        claims_for_conf: list[dict] = []
        for cp in comparison_schema:
            if cp.label == "agree":
                claims_for_conf.append({"text": cp.sub_question, "label": "supported"})
            elif cp.label == "disagree":
                claims_for_conf.append({"text": cp.sub_question, "label": "unsupported"})
            else:
                claims_for_conf.append({"text": cp.sub_question, "label": "partial"})

        # Derive conflict objects
        conflicts_for_conf: list[dict] = []
        for cp in comparison_schema:
            if cp.label == "disagree":
                conflicts_for_conf.append({
                    "topic": cp.sub_question,
                    "side_a": cp.doc_quote[:200] if cp.doc_quote else "",
                    "side_b": cp.web_quote[:200] if cp.web_quote else "",
                })

        confidence = compute_confidence(
            statuses=statuses,
            claims=claims_for_conf if claims_for_conf else None,
            sources=sources,
            conflicts=conflicts_for_conf if conflicts_for_conf else None,
        )

        logger.info(
            "DualRetriever answer: confidence score=%.1f",
            confidence.score,
        )

        return AnswerResponse(
            summary=result.summary,
            detail=result.detail,
            doc_section=result.doc_section,
            web_section=result.web_section,
            comparison=comparison_schema,
            sources=sources,
            gaps=result.gaps,
            confidence=confidence,
        )

    def reload_indexes(self):
        """Reload all search indexes and dependent engines after document ingestion."""
        self.retriever = HybridSearch()
        self.context_builder = ContextBuilder(max_chunks=5)
        self.reasoning_engine = ReasoningEngine(
            retriever=self.retriever,
            context_builder=self.context_builder,
            prompt_engine=self.prompt_engine,
            llm=self.llm,
            max_subquestions=3,
            top_k=5,
        )
        self.concept_discovery = ConceptDiscoveryEngine()
        self.debate_engine = DebateEngine()
        self.knowledge_dna = KnowledgeDNA()
        self.knowledge_mind_map = KnowledgeMindMapEngine()
        self.claim_verifier = ClaimVerifier()
        self.contradiction_finder = ContradictionFinder()
        self.research_comparison = ResearchComparisonEngine()
        self.research_gap_finder = ResearchGapFinder()
        logger.info("RAG Service indexes and dependent components reloaded successfully.")

    def reload_retriever(self) -> None:
        """Reload retrieval engine (BM25 + FAISS) after new documents are indexed."""
        self.reload_indexes()

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

    def _search(
        self,
        query: str,
        top_k: int | None = None,
        document_names: list[str] | None = None,
    ):
        """Invoke retriever.search, passing document_names and top_k only if specified."""
        kwargs: dict[str, Any] = {}
        if top_k is not None:
            kwargs["top_k"] = top_k
        if document_names is not None:
            kwargs["document_names"] = document_names
        return self.retriever.search(query, **kwargs)

    # ======================================================

    # MAIN RAG QUERY

    # ======================================================

    def reason(
        self,
        user_query: str,
        document_names: list[str] | None = None,
    ) -> dict[str, Any]:
        """Execute multi-step reasoning using Srinidhi's ReasoningEngine."""
        understanding = self.query_understanding.analyze(user_query)
        normalized_query = understanding.query
        return self.reasoning_engine.reason(normalized_query, document_names=document_names)

    def query(
        self,
        user_query: str,
        document_names: list[str] | None = None,
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
        # REASONING ROUTE
        # ==================================================

        if query_type == PromptQueryType.REASONING:
            logger.info("Routing query to Srinidhi's ReasoningEngine.")

            try:
                reasoning_result = self.reasoning_engine.reason(
                    normalized_query,
                    document_names=document_names,
                )

                abstention = (
                    "The retrieved context does not contain enough information."
                )
                answer = reasoning_result.get("answer", abstention).strip()

                if answer.casefold() == abstention.casefold():
                    logger.info("Reasoning abstained; returning no supporting sources.")
                    return QueryResponse(
                        query=normalized_query,
                        query_type=query_type.value,
                        answer=abstention,
                        sources=[],
                    )

                sources = build_sources(reasoning_result.get("sources", []))

                return QueryResponse(
                    query=normalized_query,
                    query_type=query_type.value,
                    answer=reasoning_result.get(
                        "answer",
                        "The retrieved context does not contain enough information.",
                    ),
                    sources=sources,
                )

            except Exception as exc:
                logger.exception(
                    "Srinidhi ReasoningEngine failed: %s",
                    exc,
                )

                return QueryResponse(
                    query=normalized_query,
                    query_type=query_type.value,
                    answer=(
                        "The reasoning engine could not complete this query "
                        "because an internal reasoning error occurred."
                    ),
                    sources=[],
                )

        # ==================================================

        # 2. HYBRID RETRIEVAL

        # ==================================================

        results = self._search(normalized_query, document_names=document_names)

        logger.info(f"Retrieved {len(results)} chunks.")

        # Evidence sufficiency gate: abstain before generation when the
        # retrieved passages do not cover the question.
        import os as _os

        from app.rag.evidence_sufficiency import assess_sufficiency

        _gate_texts = [
            (r.get("text") or r.get("chunk_text") or r.get("content") or "")
            if isinstance(r, dict)
            else str(getattr(r, "text", "") or "")
            for r in results
        ]
        if any(t.strip() for t in _gate_texts):
            _gate = assess_sufficiency(
                normalized_query,
                _gate_texts,
                min_coverage=float(_os.environ.get("SUFFICIENCY_MIN_COVERAGE", "0.3")),
            )
            logger.info(
                "Sufficiency gate: sufficient=%s coverage=%.2f uncovered=%s",
                _gate.sufficient,
                _gate.coverage,
                _gate.uncovered_terms,
            )
            if not _gate.sufficient:
                return QueryResponse(
                    query=normalized_query,
                    query_type=query_type.value,
                    answer="The retrieved context does not contain enough information.",
                    sources=[],
                )
        elif results:
            logger.warning("Sufficiency gate skipped: no text field found in results.")


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
        # 5-9. GROUNDED GENERATION (Task A1)
        # The LLM sees ONLY retrieved passages; temperature=0;
        # every sentence must have a verbatim quote from a cited passage.
        # ==================================================

        def _llm_call(prompt: str, temperature: float = 0.0) -> str:  # noqa: ARG001
            """Wrapper that routes through the grounded-temperature path."""
            resp = self.llm.generate_grounded(prompt)
            if not resp.success:
                error = RuntimeError(resp.error or "LLM generation failed.")
                error.error_kind = resp.error_kind  # type: ignore
                raise error
            return resp.answer

        answer, verified_sentences = grounded_generate(
            llm_generate_fn=_llm_call,
            query=normalized_query,
            passages=results,
        )

        if answer == GROUNDED_NOT_FOUND or not verified_sentences:
            logger.info("Grounded generation: no verified sentences; abstaining.")
            return QueryResponse(
                query=normalized_query,
                query_type=query_type.value,
                answer=GROUNDED_NOT_FOUND,
                sources=[],
            )

        # Task A5: Atomic claim verification, regeneration and filtering
        try:
            from app.rag.atomic_claims import (
                final_answer_after_claim_filter,
                process_and_verify_claims,
            )
            claims, refined_answer = process_and_verify_claims(
                answer=answer,
                passages=results,
                llm=self.llm,
            )
            final_answer = final_answer_after_claim_filter(
                claims, refined_answer, GROUNDED_NOT_FOUND
            )
            if final_answer is None:
                logger.info("Atomic claim verification: no claim survived; abstaining.")
                return QueryResponse(
                    query=normalized_query,
                    query_type=query_type.value,
                    answer=GROUNDED_NOT_FOUND,
                    sources=[],
                )
            answer = final_answer
        except Exception as exc:
            logger.warning("Atomic claim verification failed (%s); using verified sentences.", exc)
            claims = [
                Claim(
                    text=s.get("text", ""),
                    label="supported",
                    source_ids=[str(sid) for sid in s.get("source_ids", [])],
                    quote=s.get("quote"),
                )
                for s in verified_sentences
            ]

        sources = build_sources(results)
        logger.info("Grounded pipeline completed with %d verified sentences, %d claims.", len(verified_sentences), len(claims))

        conflicts_out: list[dict] = []
        reliability_out: list[dict] = []
        try:
            from app.rag.reliability import compute_reliability, detect_conflicts

            for _s in results:
                _get = _s.get if isinstance(_s, dict) else (lambda k, d=None, _o=_s: getattr(_o, k, d))
                reliability_out.append({
                    "source": str(_get("document") or _get("chunk_id") or _get("id") or ""),
                    "reliability": round(float(compute_reliability(_s)), 4),
                })
            _claim_dicts = [
                {"text": c.text, "source_ids": list(c.source_ids or [])}
                for c in claims[:8]
            ]
            for _cf in detect_conflicts(_claim_dicts):
                conflicts_out.append(_cf.model_dump() if hasattr(_cf, "model_dump") else dict(_cf))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Reliability/conflict analysis failed (%s); continuing without it.", exc)

        return QueryResponse(
            query=normalized_query,
            query_type=query_type.value,
            answer=answer,
            sources=sources,
            claims=claims,
            conflicts=conflicts_out,
            source_reliability=reliability_out,
        )

    # ======================================================

    # CONCEPT DISCOVERY

    # ======================================================

    def discover_concept(
        self,
        description: str,
        document_names: list[str] | None = None,
    ):
        """

        Identify an unknown technical concept from a user's

        natural-language description using retrieved evidence.

        """

        if not description or not description.strip():

            raise ValueError("Description must not be empty.")

        logger.info(f"Running concept discovery: {description}")

        results = self._search(
            description,
            top_k=10,
            document_names=document_names,
        )

        if not results:

            raise ValueError("No relevant evidence was found for concept discovery.")

        logger.info(f"Retrieved {len(results)} chunks for concept discovery.")

        concept_context_builder = ContextBuilder(max_chunks=10)

        context = concept_context_builder.build(results)

        prompt = self.concept_discovery.build_concept_prompt(
            description=description,
            context=context,
        )

        response = self.llm.generate_structured(prompt)

        if not response.success:

            error = RuntimeError(response.error or "Concept discovery failed.")

            error.error_kind = response.error_kind  # type: ignore

            raise error

        result = self.concept_discovery.parse_response(
            description=description,
            response_text=response.answer,
        )

        logger.info(
            "Concept discovery completed: "
            f"concept={result.concept}, "
            f"confidence={result.confidence}"
        )

        return result

    # ======================================================

    # CLAIM VERIFICATION

    # ======================================================

    def verify_claim(
        self,
        claim: str,
        document_names: list[str] | None = None,
        _split: bool = True,
        source_mode: str | None = None,
        _web: tuple | None = None,
    ) -> ClaimVerificationResponse:
        """

        Verify a user-provided claim against

        retrieved document evidence.

        """

        logger.info(f"Verifying claim: {claim}")

        mode = source_mode
        if mode is not None:
            from app.rag.source_mode import VALID_MODES

            if mode not in VALID_MODES:
                raise ValueError("Invalid source_mode: " + repr(mode))

        web = None
        web_chunks: list = []
        web_statuses: list = []
        web_note = ""
        if mode in ("web", "both"):
            web = _web
            if web is None:
                try:
                    web = _fetch_web_chunks(claim)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Web retrieval failed: %s", exc)
                    web = (
                        [],
                        [
                            {
                                "connector": "web",
                                "outcome": "error",
                                "count": 0,
                                "detail": type(exc).__name__,
                            }
                        ],
                    )
            web_chunks, web_statuses = web
            if mode == "web" and not web_chunks:
                return _verify_empty_response(claim, mode, web_statuses)
            web_note = _verify_web_note(web_chunks, web_statuses)

        if _split:
            try:
                from app.rag.atomic_claims import split_into_atomic_claims

                raw_parts = split_into_atomic_claims(claim, llm=self.llm)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Atomic claim splitting failed (%s); verifying as one claim.", exc
                )
                raw_parts = []

            parts = self.claim_verifier.select_atomic_claims(claim, raw_parts)

            if len(parts) > 1:
                extra: dict = {}
                if mode is not None:
                    extra["source_mode"] = mode
                if web is not None:
                    extra["_web"] = web
                part_results = [
                    self.verify_claim(
                        part, document_names=document_names, _split=False, **extra
                    )
                    for part in parts
                ]
                overall = self.claim_verifier.aggregate_verdicts(
                    [item.verdict for item in part_results]
                )
                merged_supporting: list[str] = []
                merged_contradicting: list[str] = []
                merged_ids: list[str] = []
                merged_sources: list = []
                seen_sources: set[str] = set()
                for item in part_results:
                    for quote in item.supporting_evidence:
                        if quote not in merged_supporting:
                            merged_supporting.append(quote)
                    for quote in item.contradicting_evidence:
                        if quote not in merged_contradicting:
                            merged_contradicting.append(quote)
                    for chunk_id in item.source_chunk_ids:
                        if chunk_id not in merged_ids:
                            merged_ids.append(chunk_id)
                    for source in item.sources:
                        key = _verify_source_key(source)
                        if key not in seen_sources:
                            seen_sources.add(key)
                            merged_sources.append(source)

                summary = "; ".join(
                    f"[{item.verdict}] {item.claim}" for item in part_results
                )
                return ClaimVerificationResponse(
                    claim=claim,
                    verdict=overall.value,
                    confidence=min(item.confidence for item in part_results),
                    explanation=(
                        f"The claim was checked as {len(part_results)} separate "
                        f"claims: {summary}."
                    )
                    + web_note,
                    evidence=merged_supporting + merged_contradicting,
                    source_chunk_ids=merged_ids,
                    supporting_evidence=merged_supporting,
                    contradicting_evidence=merged_contradicting,
                    atomic_claims=[
                        {
                            "claim": item.claim,
                            "verdict": item.verdict,
                            "confidence": item.confidence,
                            "explanation": item.explanation,
                            "evidence": item.evidence,
                            "supporting_evidence": item.supporting_evidence,
                            "contradicting_evidence": item.contradicting_evidence,
                            "source_chunk_ids": item.source_chunk_ids,
                        }
                        for item in part_results
                    ],
                    sources=merged_sources,
                )

        # ==================================================

        # 1. RETRIEVE EVIDENCE

        # ==================================================

        if mode == "web":
            results = []
        else:
            results = self._search(claim, document_names=document_names)

        if mode in ("web", "both"):
            results = _verify_merge_web(
                results,
                web_chunks,
                getattr(self.context_builder, "max_chunks", 5),
            )
            if not results:
                return _verify_empty_response(claim, mode, web_statuses)

        logger.info(f"Retrieved {len(results)} chunks " f"for claim verification.")

        if not results:
            return ClaimVerificationResponse(
                claim=claim,
                verdict="NOT_FOUND",
                confidence=0.0,
                explanation=(
                    "No relevant passages were retrieved from the selected "
                    "documents, so this claim could not be checked."
                ),
                evidence=[],
                supporting_evidence=[],
                contradicting_evidence=[],
                source_chunk_ids=[],
                sources=[],
            )

        # ==================================================

        # 2. BUILD CONTEXT

        # ==================================================

        context = self.context_builder.build(results, claim=claim)

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

        sources = build_sources(results)

        verification = self.claim_verifier.ground_result(
            verification,
            results[: getattr(self.context_builder, "max_chunks", 5)],
            max_chars=getattr(self.context_builder, "max_chars", None),
        )

        logger.info("Claim verification completed: " f"{verification.verdict.value}")

        return ClaimVerificationResponse(
            claim=verification.claim,
            verdict=verification.verdict.value,
            confidence=verification.confidence,
            explanation=(verification.explanation or "") + web_note,
            evidence=verification.evidence,
            source_chunk_ids=(verification.source_chunk_ids),
            supporting_evidence=verification.supporting_evidence,
            contradicting_evidence=verification.contradicting_evidence,
            sources=sources,
        )

    # ======================================================

    # CONTRADICTION FINDER

    # ======================================================

    def find_contradictions(
        self,
        query: str,
        document_names: list[str] | None = None,
    ):
        """

        Detect contradictions across retrieved

        document evidence.

        """

        logger.info(f"Running contradiction analysis: {query}")

        # ==================================================

        # 1. RETRIEVE EVIDENCE

        # ==================================================

        results = self._search(query, document_names=document_names)

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
        document_names: list[str] | None = None,
    ):
        """
        Compare research entities using only retrieved document evidence.
        Guarantees balanced retrieval across multiple documents, evidence
        grounding, and graceful handling of missing information.
        """
        logger.info(f"Running research comparison: {query}")

        # ==================================================
        # 1. RETRIEVE RELEVANT EVIDENCE ACROSS DOCUMENTS
        # ==================================================
        # Budgeting for Groq 8k TPM safety (Prompt <= 4500 tokens / ~3000 words total)
        max_total_words = 2800
        n_docs = len(document_names) if document_names else 2
        words_per_doc = max(400, max_total_words // max(n_docs, 2))

        all_results = []
        seen_chunks = set()
        seen_texts = set()
        doc_words: dict[str, int] = {}

        general_k = max(settings.TOP_K_RESULTS, len(document_names or []) * 4, 12)
        general_results = self._search(query, top_k=general_k, document_names=document_names)
        for r in general_results:
            cid = r.get("chunk_id")
            doc = r.get("document", "")
            raw_text = r.get("text") or ""
            clean_t = " ".join(raw_text.split())
            text_key = clean_t[:150]

            if cid and cid not in seen_chunks and text_key not in seen_texts:
                current_words = doc_words.get(doc, 0)
                chunk_words = len(clean_t.split())
                if current_words + chunk_words <= words_per_doc or current_words == 0:
                    seen_chunks.add(cid)
                    seen_texts.add(text_key)
                    all_results.append(r)
                    doc_words[doc] = current_words + chunk_words

        # Only top up specifically if any requested document received fewer than 2 chunks
        if document_names and len(document_names) >= 2:
            for doc in document_names:
                if doc not in doc_words or doc_words[doc] < 200:
                    doc_results = self._search(query, top_k=2, document_names=[doc])
                    for r in doc_results:
                        cid = r.get("chunk_id")
                        raw_text = r.get("text") or ""
                        clean_t = " ".join(raw_text.split())
                        text_key = clean_t[:150]
                        if cid and cid not in seen_chunks and text_key not in seen_texts:
                            seen_chunks.add(cid)
                            seen_texts.add(text_key)
                            all_results.append(r)
                            doc_words[doc] = doc_words.get(doc, 0) + len(clean_t.split())

        logger.info(f"Retrieved {len(all_results)} chunks for research comparison.")

        if not all_results:
            return ResearchComparisonReport(
                query=query,
                entities=document_names or [],
                comparison=[],
                summary="Not found in available sources. Insufficient evidence to perform a comparison for the specified query and documents.",
                similarities=[],
                differences=[],
                contradictions=[],
                unique_contributions=[],
                strengths_and_limitations=[],
                synthesis="Not found in available sources.",
                sources=[],
            )

        # ==================================================
        # 2. PREPARE EVIDENCE
        # ==================================================
        evidence = self._build_feature_evidence(all_results)

        # ==================================================
        # 3. BUILD COMPARISON PROMPT
        # ==================================================
        prompt = self.research_comparison.build_comparison_prompt(
            query=query,
            evidence=evidence,
        )

        # ==================================================
        # 4. LLM ANALYSIS WITH PROVIDER FALLBACK (MAX 2 ATTEMPTS)
        # ==================================================
        response = self.llm.generate_structured(
            prompt,
            max_attempts=2,
            time_budget_s=25.0,
        )

        if not response.success:
            logger.warning(
                "All LLM attempts failed or timed out (%s). Falling back to direct evidence-based comparison.",
                response.error,
            )
            return self.research_comparison.build_no_llm_comparison(
                query=query,
                evidence=evidence,
                document_names=document_names,
            )

        # ==================================================
        # 5. PARSE STRUCTURED RESULT WITH TRUNCATION RECOVERY
        # ==================================================
        try:
            report = self.research_comparison.parse_response(
                query=query,
                response_text=response.answer,
            )
        except ValueError as parse_err:
            logger.warning("Comparison JSON incomplete (%s); falling back to direct evidence-based comparison.", parse_err)
            return self.research_comparison.build_no_llm_comparison(
                query=query,
                evidence=evidence,
                document_names=document_names,
            )

        # Guarantee source attribution using build_sources if LLM omitted them
        if not report.sources and all_results:
            from app.rag.confidence import build_sources
            report.sources = [s.model_dump() for s in build_sources(all_results)]

        logger.info(
            "Research comparison completed: "
            f"{len(report.entities)} entities, "
            f"{len(report.comparison)} comparison aspects, "
            f"{len(report.similarities)} similarities, "
            f"{len(report.differences)} differences, "
            f"{len(report.contradictions)} contradictions."
        )

        return report

    # ======================================================

    # AI DEBATE MODE

    # ======================================================

    def run_debate(
        self,
        query: str,
        position_a: str,
        position_b: str,
        document_names: list[str] | None = None,
    ):
        """Generate an evidence-grounded AI debate across single or multiple papers."""
        target_query = (query or "").strip()
        logger.info(f"Running AI debate for: {target_query}")

        max_total_words = 1800
        n_docs = len(document_names) if document_names else 2
        words_per_doc = max(350, max_total_words // max(n_docs, 2))

        all_results = []
        seen_chunks = set()
        seen_texts = set()
        doc_words: dict[str, int] = {}

        general_k = max(settings.TOP_K_RESULTS, len(document_names or []) * 3, 10)
        general_results = self._search(target_query, top_k=general_k, document_names=document_names)

        for r in general_results:
            cid = r.get("chunk_id")
            doc = r.get("document", "")
            raw_text = r.get("text") or ""
            clean_t = " ".join(raw_text.split())
            text_key = clean_t[:150]

            if cid and cid not in seen_chunks and text_key not in seen_texts:
                current_words = doc_words.get(doc, 0)
                chunk_words = len(clean_t.split())
                if current_words + chunk_words <= words_per_doc or current_words == 0:
                    seen_chunks.add(cid)
                    seen_texts.add(text_key)
                    all_results.append(r)
                    doc_words[doc] = current_words + chunk_words

        # Ensure balanced representation across requested documents if >= 2 documents
        if document_names and len(document_names) >= 2:
            for doc in document_names:
                if doc not in doc_words or doc_words[doc] < 150:
                    doc_results = self._search(target_query, top_k=3, document_names=[doc])
                    for r in doc_results:
                        cid = r.get("chunk_id")
                        raw_text = r.get("text") or ""
                        clean_t = " ".join(raw_text.split())
                        text_key = clean_t[:150]
                        if cid and cid not in seen_chunks and text_key not in seen_texts:
                            seen_chunks.add(cid)
                            seen_texts.add(text_key)
                            all_results.append(r)
                            doc_words[doc] = doc_words.get(doc, 0) + len(clean_t.split())

        if not all_results:
            return self.debate_engine.build_no_llm_debate(
                query=target_query,
                position_a=position_a,
                position_b=position_b,
                evidence=[],
                document_names=document_names,
            )

        evidence = self._build_feature_evidence(all_results)

        prompt = self.debate_engine.build_debate_prompt(
            query=target_query,
            position_a=position_a,
            position_b=position_b,
            evidence=evidence,
        )

        response = self.llm.generate_structured(
            prompt,
            max_attempts=2,
            time_budget_s=25.0,
        )

        if not response.success:
            logger.warning(
                "All LLM attempts failed or timed out (%s). Falling back to direct evidence-based Debate.",
                response.error,
            )
            return self.debate_engine.build_no_llm_debate(
                query=target_query,
                position_a=position_a,
                position_b=position_b,
                evidence=evidence,
                document_names=document_names,
            )

        try:
            report = self.debate_engine.parse_response(
                query=target_query,
                position_a=position_a,
                position_b=position_b,
                response_text=response.answer,
            )
        except Exception as parse_err:
            logger.warning(
                "AI debate parsing failed (%s). Falling back to direct evidence-based Debate.",
                parse_err,
            )
            return self.debate_engine.build_no_llm_debate(
                query=target_query,
                position_a=position_a,
                position_b=position_b,
                evidence=evidence,
                document_names=document_names,
            )

        return report

    # ======================================================

    # KNOWLEDGE DNA

    # ======================================================

    def generate_knowledge_dna(
        self,
        query: str = "",
        document_names: list[str] | None = None,
        topic: str | None = None,
    ):
        """Generate evidence-grounded Knowledge DNA across 10 research dimensions."""
        target_query = (query or topic or "").strip()
        logger.info(f"Generating Knowledge DNA for: {target_query}")

        max_total_words = 1800
        n_docs = len(document_names) if document_names else 2
        words_per_doc = max(350, max_total_words // max(n_docs, 2))

        all_results = []
        seen_chunks = set()
        seen_texts = set()
        doc_words: dict[str, int] = {}

        general_k = max(settings.TOP_K_RESULTS, len(document_names or []) * 3, 10)
        general_results = self._search(target_query, top_k=general_k, document_names=document_names)

        for r in general_results:
            cid = r.get("chunk_id")
            doc = r.get("document", "")
            raw_text = r.get("text") or ""
            clean_t = " ".join(raw_text.split())
            text_key = clean_t[:150]

            if cid and cid not in seen_chunks and text_key not in seen_texts:
                current_words = doc_words.get(doc, 0)
                chunk_words = len(clean_t.split())
                if current_words + chunk_words <= words_per_doc or current_words == 0:
                    seen_chunks.add(cid)
                    seen_texts.add(text_key)
                    all_results.append(r)
                    doc_words[doc] = current_words + chunk_words

        # Ensure balanced representation across requested documents if >= 2 documents
        if document_names and len(document_names) >= 2:
            for doc in document_names:
                if doc not in doc_words or doc_words[doc] < 150:
                    doc_results = self._search(target_query, top_k=2, document_names=[doc])
                    for r in doc_results:
                        cid = r.get("chunk_id")
                        raw_text = r.get("text") or ""
                        clean_t = " ".join(raw_text.split())
                        text_key = clean_t[:150]
                        if cid and cid not in seen_chunks and text_key not in seen_texts:
                            seen_chunks.add(cid)
                            seen_texts.add(text_key)
                            all_results.append(r)
                            doc_words[doc] = doc_words.get(doc, 0) + len(clean_t.split())

        if not all_results:
            from app.rag.knowledge_dna import KnowledgeDNAReport
            return KnowledgeDNAReport(
                query=target_query,
                research_area="Insufficient evidence",
                partial=False,
                notice="Not found in available sources. Insufficient evidence to extract Knowledge DNA for the specified query and documents.",
            )

        evidence = self._build_feature_evidence(all_results)

        prompt = self.knowledge_dna.build_dna_prompt(
            query=target_query,
            evidence=evidence,
        )

        response = self.llm.generate_structured(
            prompt,
            max_attempts=2,
            time_budget_s=25.0,
        )

        if not response.success:
            logger.warning(
                "All LLM attempts failed or timed out (%s). Falling back to direct evidence-based Knowledge DNA.",
                response.error,
            )
            return self.knowledge_dna.build_no_llm_dna(
                query=target_query,
                evidence=evidence,
                document_names=document_names,
            )

        try:
            report = self.knowledge_dna.parse_response(
                query=target_query,
                response_text=response.answer,
            )
        except Exception as parse_err:
            logger.warning(
                "Knowledge DNA parsing failed (%s). Falling back to direct evidence-based Knowledge DNA.",
                parse_err,
            )
            return self.knowledge_dna.build_no_llm_dna(
                query=target_query,
                evidence=evidence,
                document_names=document_names,
            )

        return report

    # ======================================================

    # KNOWLEDGE MIND MAP

    # ======================================================

    def generate_knowledge_mind_map(
        self,
        query: str = "",
        document_names: list[str] | None = None,
        topic: str | None = None,
    ):
        """Generate an evidence-grounded knowledge mind map."""
        target_query = (query or topic or "").strip()
        logger.info(f"Generating knowledge mind map for: {target_query}")

        max_total_words = 1600
        n_docs = len(document_names) if document_names else 2
        words_per_doc = max(350, max_total_words // max(n_docs, 2))

        all_results = []
        seen_chunks = set()
        seen_texts = set()
        doc_words: dict[str, int] = {}

        general_k = max(settings.TOP_K_RESULTS, len(document_names or []) * 3, 10)
        general_results = self._search(target_query, top_k=general_k, document_names=document_names)

        for r in general_results:
            cid = r.get("chunk_id")
            doc = r.get("document", "")
            raw_text = r.get("text") or ""
            clean_t = " ".join(raw_text.split())
            text_key = clean_t[:150]

            if cid and cid not in seen_chunks and text_key not in seen_texts:
                current_words = doc_words.get(doc, 0)
                chunk_words = len(clean_t.split())
                if current_words + chunk_words <= words_per_doc or current_words == 0:
                    seen_chunks.add(cid)
                    seen_texts.add(text_key)
                    all_results.append(r)
                    doc_words[doc] = current_words + chunk_words

        # Ensure balanced representation across requested documents if >= 2 documents
        if document_names and len(document_names) >= 2:
            for doc in document_names:
                if doc not in doc_words or doc_words[doc] < 150:
                    doc_results = self._search(target_query, top_k=2, document_names=[doc])
                    for r in doc_results:
                        cid = r.get("chunk_id")
                        raw_text = r.get("text") or ""
                        clean_t = " ".join(raw_text.split())
                        text_key = clean_t[:150]
                        if cid and cid not in seen_chunks and text_key not in seen_texts:
                            seen_chunks.add(cid)
                            seen_texts.add(text_key)
                            all_results.append(r)
                            doc_words[doc] = doc_words.get(doc, 0) + len(clean_t.split())

        if not all_results:
            from app.rag.knowledge_mind_map import KnowledgeMindMap
            return KnowledgeMindMap(
                query=query,
                research_area="Insufficient evidence",
                nodes=[],
                edges=[],
                sources=[],
                partial=False,
                notice="Not found in available sources. Insufficient evidence to construct a mind map for the specified query and documents.",
            )

        evidence = self._build_feature_evidence(all_results)

        prompt = self.knowledge_mind_map.build_mind_map_prompt(
            query=target_query,
            evidence=evidence,
        )

        response = self.llm.generate_structured(
            prompt,
            max_attempts=2,
            time_budget_s=25.0,
        )

        if not response.success:
            logger.warning(
                "All LLM attempts failed or timed out (%s). Falling back to direct evidence-based mind map.",
                response.error,
            )
            return self.knowledge_mind_map.build_no_llm_mind_map(
                query=target_query,
                evidence=evidence,
                document_names=document_names,
            )

        try:
            report = self.knowledge_mind_map.parse_response(
                query=target_query,
                response_text=response.answer,
            )
        except ValueError as parse_err:
            logger.warning(
                "Knowledge mind map parsing failed (%s). Falling back to direct evidence-based mind map.",
                parse_err,
            )
            return self.knowledge_mind_map.build_no_llm_mind_map(
                query=target_query,
                evidence=evidence,
                document_names=document_names,
            )

        if not report.sources and report.nodes and all_results:
            from app.rag.confidence import build_sources
            report.sources = [s.model_dump() for s in build_sources(all_results)]

        return report

    # ======================================================

    # RESEARCH GAP FINDER

    # ======================================================

    def find_research_gaps(
        self,
        query: str,
        document_names: list[str] | None = None,
    ):
        """Identify evidence-grounded research gaps across single or multiple papers."""
        target_query = (query or "").strip()
        logger.info(f"Finding research gaps for: {target_query}")

        max_total_words = 1800
        n_docs = len(document_names) if document_names else 2
        words_per_doc = max(350, max_total_words // max(n_docs, 2))

        all_results = []
        seen_chunks = set()
        seen_texts = set()
        doc_words: dict[str, int] = {}

        general_k = max(settings.TOP_K_RESULTS, len(document_names or []) * 3, 10)
        general_results = self._search(target_query, top_k=general_k, document_names=document_names)

        for r in general_results:
            cid = r.get("chunk_id")
            doc = r.get("document", "")
            raw_text = r.get("text") or ""
            clean_t = " ".join(raw_text.split())
            text_key = clean_t[:150]

            if cid and cid not in seen_chunks and text_key not in seen_texts:
                current_words = doc_words.get(doc, 0)
                chunk_words = len(clean_t.split())
                if current_words + chunk_words <= words_per_doc or current_words == 0:
                    seen_chunks.add(cid)
                    seen_texts.add(text_key)
                    all_results.append(r)
                    doc_words[doc] = current_words + chunk_words

        # Ensure balanced representation across requested documents if >= 2 documents
        if document_names and len(document_names) >= 2:
            for doc in document_names:
                if doc not in doc_words or doc_words[doc] < 150:
                    doc_results = self._search(target_query, top_k=3, document_names=[doc])
                    for r in doc_results:
                        cid = r.get("chunk_id")
                        raw_text = r.get("text") or ""
                        clean_t = " ".join(raw_text.split())
                        text_key = clean_t[:150]
                        if cid and cid not in seen_chunks and text_key not in seen_texts:
                            seen_chunks.add(cid)
                            seen_texts.add(text_key)
                            all_results.append(r)
                            doc_words[doc] = doc_words.get(doc, 0) + len(clean_t.split())

        if not all_results:
            return self.research_gap_finder.build_no_llm_gaps(
                query=target_query,
                evidence=[],
                document_names=document_names,
            )

        evidence = self._build_feature_evidence(all_results)

        prompt = self.research_gap_finder.build_gap_prompt(
            query=target_query,
            evidence=evidence,
        )

        response = self.llm.generate_structured(
            prompt,
            max_attempts=2,
            time_budget_s=25.0,
        )

        if not response.success:
            logger.warning(
                "All LLM attempts failed or timed out (%s). Falling back to direct evidence-based Research Gaps.",
                response.error,
            )
            return self.research_gap_finder.build_no_llm_gaps(
                query=target_query,
                evidence=evidence,
                document_names=document_names,
            )

        try:
            report = self.research_gap_finder.parse_response(
                query=target_query,
                response_text=response.answer,
            )
        except Exception as parse_err:
            logger.warning(
                "Research gap parsing failed (%s). Falling back to direct evidence-based Research Gaps.",
                parse_err,
            )
            return self.research_gap_finder.build_no_llm_gaps(
                query=target_query,
                evidence=evidence,
                document_names=document_names,
            )

        return report

    # ======================================================

    # VISUAL ANSWER GENERATOR

    # ======================================================

    def generate_visual_answer(
        self,
        query: str,
        document_names: list[str] | None = None,
    ):
        """Generate an evidence-grounded visual answer specification."""

        if not query or not query.strip():

            raise ValueError("Query must not be empty.")

        retrieval_results = self._search(
            query,
            top_k=5,
            document_names=document_names,
        )

        if not retrieval_results:

            raise ValueError(
                "No relevant evidence was found for visual answer generation."
            )

        evidence_objects = self._build_feature_evidence(
            retrieval_results,
        )

        evidence = "\n\n".join(
            (
                f"Document: {item['document']}\n"
                f"Page: {item['page']}\n"
                f"Chunk ID: {item['chunk_id']}\n"
                f"Evidence: {item['text']}"
            )
            for item in evidence_objects
        )

        prompt = self.visual_answer.build_prompt(
            query=query,
            evidence=evidence,
        )

        response = self.llm.generate_structured(
            prompt=prompt,
        )

        if not response.success:

            error = RuntimeError(response.error or "Visual answer generation failed.")

            error.error_kind = response.error_kind  # type: ignore

            raise error

        try:
            return self.visual_answer.parse_response(
                query=query,
                response_text=response.answer,
            )
        except ValueError as original_error:
            logger.warning(
                "Visual answer validation failed; attempting one repair: %s",
                original_error,
            )

            repair_prompt = f"""
You are repairing an invalid visual-answer JSON response.

Return ONLY valid JSON matching the original visual-answer schema.

User query:
{query}

Original retrieved evidence:
{evidence}

Previous response:
{response.answer}

Rules:
- Use ONLY the original retrieved evidence.
- Every element must include a non-empty "evidence" field.
- Every edge must include a non-empty "evidence" field.
- Every data point must include a non-empty "evidence" field.
- Evidence must be copied from the retrieved evidence above.
- Do not invent facts, values, relationships, or citations.
- Remove any unsupported elements and edges.
- Every edge must reference existing element IDs.
- Preserve the original visual type and title when valid.
- Return the complete corrected JSON object, with no Markdown fences.
""".strip()

            repair_response = self.llm.generate_structured(
                prompt=repair_prompt,
            )

            if not repair_response.success:
                raise ValueError(
                    "Visual answer validation failed, and the repair attempt "
                    "could not generate a valid response."
                ) from original_error

            try:
                return self.visual_answer.parse_response(
                    query=query,
                    response_text=repair_response.answer,
                )
            except ValueError as repair_error:
                raise ValueError(
                    "Visual answer remained invalid after one repair attempt."
                ) from repair_error

    def query_assistant(
        self,
        query: str,
        task: str | None = None,
    ) -> dict[str, Any]:
        """
        AI Research Assistant chatbot helper.
        Clarifies intent, refines vague queries, and recommends the optimal UNKNOWN tool.
        """
        if not query or not query.strip():
            raise ValueError("Query must not be empty.")

        cleaned_query = query.strip()
        system_prompt = f"""You are the UNKNOWN Academic Query Assistant.
Your goal is to transform user queries into precise, high-yield academic research prompts and select the best specialized tool.

Available UNKNOWN Tools:
- "Research Assistant": Standard factual or descriptive Q&A from literature.
- "Multi-Step Reasoning": Complex analytical or causal questions requiring decomposed sub-questions.
- "Verify Claim": Assessing whether a specific factual hypothesis/assertion is supported.
- "Discover Concept": Reverse-engineering a technical concept from an informal description.
- "Contradictions": Detecting conflicting claims or disputes across papers.
- "Compare Research": Comparing 2 to 10 entities, techniques, or algorithms across aspects.
- "Research Gaps": Identifying open questions, unresolved limitations, or future directions.
- "Research Debate": Formulating two opposing intellectual perspectives.
- "Knowledge DNA": Deconstructing foundational concepts, methods, findings, and themes.
- "Knowledge Mind Map": Graph-based conceptual and relationship visualization.
- "Adaptive Answer": Producing custom-depth explanations for beginners to experts.
- "Visual Answer": Step-by-step visual, table, or flowchart breakdown.

Input Query: "{cleaned_query}"
Current Task: "{task or 'General'}"

Return ONLY valid JSON:
{{
  "refined_query": "...",
  "suggested_task": "...",
  "explanation": "...",
  "alternative_queries": ["...", "..."],
  "tips": ["..."]
}}""".strip()

        try:
            resp = self.llm.generate_structured(system_prompt)
            if resp.success and resp.answer:
                cleaned = re.sub(r"^```(?:json)?\s*", "", resp.answer.strip(), flags=re.IGNORECASE)
                cleaned = re.sub(r"\s*```$", "", cleaned).strip()
                data = json.loads(cleaned)
                if isinstance(data, dict) and "refined_query" in data and "suggested_task" in data:
                    return {
                        "original_query": cleaned_query,
                        "refined_query": str(data.get("refined_query", cleaned_query)),
                        "suggested_task": str(data.get("suggested_task", "Research Assistant")),
                        "explanation": str(data.get("explanation", "Optimized for academic evidence retrieval.")),
                        "alternative_queries": list(data.get("alternative_queries", [])),
                        "tips": list(data.get("tips", ["Use specific terminology found in peer-reviewed abstracts."])),
                    }
        except Exception as exc:
            logger.warning(f"LLM query assistant failed: {exc}")

        # Rule-based fallback
        low = cleaned_query.lower()
        if any(w in low for w in ["compare", "vs", "versus", "difference between", "better than"]):
            suggested = "Compare Research"
            refined = f"Comparative analysis: {cleaned_query}"
            explanation = "Detected comparison keywords. The Compare Research tool structures entities and evaluation criteria."
        elif any(w in low for w in ["verify", "is it true", "fact check", "claim", "proven"]):
            suggested = "Verify Claim"
            refined = f"Evaluate the claim: {cleaned_query}"
            explanation = "Detected verification intent. The Verify Claim tool validates statements against citations."
        elif any(w in low for w in ["gap", "limitation", "open question", "future work", "unresolved"]):
            suggested = "Research Gaps"
            refined = f"Systematic identification of research gaps regarding {cleaned_query}"
            explanation = "Detected exploratory gap intent. The Research Gaps tool isolates unaddressed challenges in literature."
        elif any(w in low for w in ["why", "how does", "mechanism", "causal", "cause"]):
            suggested = "Multi-Step Reasoning"
            refined = f"Multi-step causal and analytical breakdown of {cleaned_query}"
            explanation = "Detected analytical inquiry. Srinidhi's Reasoning Engine decomposes queries into multi-hop subquestions."
        elif any(w in low for w in ["conflict", "contradict", "disagree", "dispute", "debate"]):
            suggested = "Contradictions"
            refined = f"Conflicting evidence and divergent findings regarding {cleaned_query}"
            explanation = "Detected contradiction/dispute intent. Contradictions tool locates opposing evidence."
        elif any(w in low for w in ["mind map", "graph", "relations", "connect"]):
            suggested = "Knowledge Mind Map"
            refined = f"Conceptual mind map and relational structure of {cleaned_query}"
            explanation = "Detected relational structure intent. Knowledge Mind Map generates interactive concept DAGs."
        elif any(w in low for w in ["what is called", "what term", "concept for", "forgot the name"]):
            suggested = "Discover Concept"
            refined = cleaned_query
            explanation = "Detected term discovery intent. Discover Concept matches informal descriptions to formal concepts."
        else:
            suggested = "Research Assistant"
            refined = f"Investigating the principles, evidence, and state-of-the-art of {cleaned_query}"
            explanation = "Formulated query with academic terminology for maximum lexical and semantic retrieval precision."

        return {
            "original_query": cleaned_query,
            "refined_query": refined,
            "suggested_task": suggested,
            "explanation": explanation,
            "alternative_queries": [
                f"Empirical evaluation of {cleaned_query}",
                f"Theoretical framework and methodology in {cleaned_query}",
            ],
            "tips": [
                "Specify target performance metrics or experimental variables.",
                "Mention key authors, model names, or benchmark datasets.",
            ],
        }
