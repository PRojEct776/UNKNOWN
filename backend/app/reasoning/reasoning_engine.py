"""
UNKNOWN Project - AI Reasoning Engine

Srinidhi's reasoning module.

Pipeline:
    Reasoning Query
        -> Query Decomposition
        -> Hybrid Retrieval for Each Sub-question
        -> Evidence Validation and Aggregation
        -> ContextBuilder
        -> PromptEngine (REASONING)
        -> Multi-LLM / GeminiEngine
        -> Final Grounded Answer
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.rag.context_builder import ContextBuilder
from app.rag.hybrid_search import HybridSearch
from app.rag.logger import logger
from app.rag.prompt_engine import PromptEngine, QueryType


INSUFFICIENT_EVIDENCE_MESSAGE = (
    "The retrieved context does not contain enough information."
)

GENERATION_FAILURE_MESSAGE = (
    "The answer could not be generated reliably from the "
    "retrieved context. Please try again."
)


class ReasoningEngine:
    """
    Multi-step reasoning layer built on top of the existing RAG.

    Responsibilities:
    - Decompose complex questions.
    - Retrieve evidence for individual sub-questions.
    - Validate and deduplicate retrieved evidence.
    - Build a grounded reasoning prompt.
    - Generate an answer and preserve source metadata.
    """

    def __init__(
        self,
        retriever: HybridSearch,
        context_builder: ContextBuilder,
        prompt_engine: PromptEngine,
        gemini: Any = None,
        llm: Any = None,
        max_subquestions: int = 3,
        top_k: int = 5,
    ) -> None:
        if max_subquestions < 1:
            raise ValueError(
                "max_subquestions must be at least 1."
            )

        if top_k < 1:
            raise ValueError(
                "top_k must be at least 1."
            )

        self.retriever = retriever
        self.context_builder = context_builder
        self.prompt_engine = prompt_engine
        self.gemini = gemini or llm
        self.llm = llm or gemini
        self.max_subquestions = max_subquestions
        self.top_k = top_k

        logger.info(
            "UNKNOWN Reasoning Engine initialized."
        )

    # =========================================================
    # LLM CALL HELPER (Supports GeminiEngine, Orchestrator, & Mock)
    # =========================================================

    def _call_llm(self, prompt: str, structured: bool = False) -> str:
        """
        Execute an LLM call using either LLMOrchestrator, GeminiEngine,
        or any compatible interface. Returns string content.
        """
        client = self.llm or self.gemini
        if client is None:
            return ""

        try:
            if structured and hasattr(client, "generate_structured"):
                resp = client.generate_structured(prompt)
                if hasattr(resp, "success") and not resp.success:
                    logger.warning(f"Structured generation error: {getattr(resp, 'error', '')}")
                    return ""
                return resp.answer if hasattr(resp, "answer") else str(resp)

            if hasattr(client, "generate"):
                resp = client.generate(prompt)
                if hasattr(resp, "success") and not resp.success:
                    logger.warning(f"Generation error: {getattr(resp, 'error', '')}")
                    return ""
                return resp.answer if hasattr(resp, "answer") else str(resp)

            if callable(client):
                return str(client(prompt))

        except Exception as error:
            logger.error(f"Reasoning LLM call failed: {error}")

        return ""

    # =========================================================
    # QUERY DECOMPOSITION
    # =========================================================

    def decompose_query(
        self,
        query: str,
    ) -> list[str]:
        """
        Break a complex reasoning query into smaller
        retrieval-oriented sub-questions.

        If decomposition fails, fall back to the original query.
        """
        decomposition_prompt = f"""
You are the query decomposition component of UNKNOWN AI.

Break the main question below into at most
{self.max_subquestions} smaller questions.

Rules:
- Each sub-question must help retrieve evidence
  needed for the main answer.
- Keep each sub-question concise.
- Do not answer the sub-questions.
- Avoid duplicates.
- Return ONLY valid JSON.

Required format:

{{
    "subquestions": [
        "question 1",
        "question 2",
        "question 3"
    ]
}}

Main question:
{query}
""".strip()

        try:
            response = self._call_llm(decomposition_prompt, structured=True)

            if not isinstance(response, str) or not response.strip():
                logger.warning(
                    "Reasoning decomposition returned an empty "
                    "or invalid response."
                )
                return [query]

            cleaned = self._clean_json(response)
            data = json.loads(cleaned)

            if not isinstance(data, dict):
                raise ValueError(
                    "Decomposition output must be a JSON object."
                )

            questions = data.get("subquestions", [])

            if not isinstance(questions, list):
                raise ValueError(
                    "subquestions must be a list."
                )

            cleaned_questions = []

            for question in questions:
                if not isinstance(question, str):
                    continue

                question = question.strip()

                if question:
                    cleaned_questions.append(question)

            cleaned_questions = self._deduplicate_questions(
                cleaned_questions
            )

            if cleaned_questions:
                return cleaned_questions[:self.max_subquestions]

            logger.warning(
                "No valid sub-questions were generated. "
                "Using the original query."
            )

        except (
            json.JSONDecodeError,
            ValueError,
            TypeError,
            AttributeError,
        ) as error:
            logger.warning(
                f"Reasoning decomposition failed: {error}"
            )

        except Exception as error:
            logger.error(
                f"Query decomposition failed: {error}"
            )

        # Safe fallback: retrieve using the original question.
        return [query]

    # =========================================================
    # MULTI-QUERY RETRIEVAL
    # =========================================================

    def retrieve_evidence(
        self,
        subquestions: list[str],
        doc_filter: list[str] | set[str] | None = None,
        user_id: str | None = None,
        exclude_test_docs: bool | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve evidence for each sub-question using the
        existing HybridSearch implementation.

        Evidence records without usable text or a chunk ID
        are discarded. Duplicate chunks are merged by ID,
        retaining the version with the highest hybrid score.
        """
        if exclude_test_docs is None:
            exclude_test_docs = True if user_id is not None else False

        evidence_by_chunk: dict[str, dict[str, Any]] = {}

        if doc_filter is not None:
            allowed_docs = set(doc_filter)
        else:
            allowed_docs = None

        for subquestion in subquestions:
            if (
                not isinstance(subquestion, str)
                or not subquestion.strip()
            ):
                continue

            logger.info(
                f"Reasoning retrieval: {subquestion}"
            )

            try:
                results = self.retriever.search(
                    subquestion,
                    top_k=self.top_k,
                    doc_filter=doc_filter,
                    user_id=user_id,
                    exclude_test_docs=exclude_test_docs,
                )
            except TypeError:
                results = self.retriever.search(subquestion, self.top_k)

            for result in results:
                if not isinstance(result, dict):
                    continue

                # Evidence validation:
                # Ignore records with missing, non-string,
                # or whitespace-only text.
                evidence_text = result.get("text")

                if (
                    not isinstance(evidence_text, str)
                    or not evidence_text.strip()
                ):
                    logger.debug(
                        "Skipping evidence record without usable text."
                    )
                    continue

                chunk_id = result.get("chunk_id")

                if chunk_id is None:
                    logger.debug(
                        "Skipping evidence record without a chunk ID."
                    )
                    continue

                # Optional document filter scoping
                if allowed_docs is not None:
                    doc_name = result.get("document", "")
                    if doc_name not in allowed_docs:
                        continue

                key = str(chunk_id)

                current_score = self._score(
                    result.get("hybrid_score", 0.0)
                )

                existing = evidence_by_chunk.get(key)

                if existing is None:
                    evidence_by_chunk[key] = result
                else:
                    existing_score = self._score(
                        existing.get("hybrid_score", 0.0)
                    )

                    if current_score > existing_score:
                        evidence_by_chunk[key] = result

        evidence = list(evidence_by_chunk.values())

        # Rank evidence by hybrid score, highest first.
        evidence.sort(
            key=lambda result: self._score(
                result.get("hybrid_score", 0.0)
            ),
            reverse=True,
        )

        logger.info(
            f"Reasoning evidence validation retained "
            f"{len(evidence)} unique chunks."
        )

        return evidence

    # =========================================================
    # BUILD REASONING PROMPT
    # =========================================================

    def build_reasoning_prompt(
        self,
        query: str,
        evidence: list[dict[str, Any]],
    ) -> str:
        """
        Reuse the existing ContextBuilder and PromptEngine
        to construct a grounded reasoning prompt.
        """
        context = self.context_builder.build(evidence)

        prompt = self.prompt_engine.build_prompt(
            query=query,
            context=context,
            query_type=QueryType.REASONING,
        )

        prompt += """

Additional reasoning requirements:
- Answer the main question, not the sub-questions separately.
- Connect the retrieved evidence logically.
- Use only information supported by the retrieved context.
- Do not introduce unsupported facts or assumptions.
- Do not fabricate sources, quotations, or citations.
- Do not reveal hidden chain-of-thought.
- Give a concise explanation of the reasoning outcome.
- If the evidence does not support an answer, explicitly state:
  "The retrieved context does not contain enough information."
""".strip()

        return prompt

    # =========================================================
    # COMPLETE REASONING PIPELINE
    # =========================================================

    def reason(
        self,
        query: str,
        doc_filter: list[str] | set[str] | None = None,
        user_id: str | None = None,
        exclude_test_docs: bool | None = None,
    ) -> dict[str, Any]:
        """
        Execute the complete reasoning pipeline.

        Query
            -> Decomposition
            -> Hybrid Retrieval
            -> Evidence Validation and Aggregation
            -> Context Building
            -> Grounded Prompt
            -> Answer Generation
            -> Source Formatting
        """
        if exclude_test_docs is None:
            exclude_test_docs = True if user_id is not None else False
        if not isinstance(query, str):
            raise TypeError(
                "query must be a string."
            )

        query = query.strip()

        if not query:
            raise ValueError(
                "query cannot be empty."
            )

        logger.info(
            f"Starting reasoning query: {query}"
        )

        # -----------------------------------------------------
        # 1. Decompose the query
        # -----------------------------------------------------
        subquestions = self.decompose_query(query)

        logger.info(
            f"Generated {len(subquestions)} "
            f"reasoning subquestions."
        )

        # -----------------------------------------------------
        # 2. Retrieve and aggregate evidence
        # -----------------------------------------------------
        evidence = self.retrieve_evidence(
            subquestions,
            doc_filter=doc_filter,
            user_id=user_id,
            exclude_test_docs=exclude_test_docs,
        )

        # -----------------------------------------------------
        # 3. Handle missing usable evidence
        # -----------------------------------------------------
        if not evidence:
            logger.warning(
                "No usable evidence was retrieved. "
                "Skipping answer generation."
            )

            return {
                "query": query,
                "subquestions": subquestions,
                "answer": INSUFFICIENT_EVIDENCE_MESSAGE,
                "sources": [],
            }

        # -----------------------------------------------------
        # 4. Build the grounded reasoning prompt
        # -----------------------------------------------------
        prompt = self.build_reasoning_prompt(
            query=query,
            evidence=evidence,
        )

        # -----------------------------------------------------
        # 5. Generate the final answer safely
        # -----------------------------------------------------
        try:
            generated_answer = self._call_llm(prompt)

            if isinstance(generated_answer, str):
                answer = generated_answer.strip()
            else:
                answer = ""

            if not answer:
                logger.warning(
                    "Reasoning model returned an empty answer."
                )
                answer = GENERATION_FAILURE_MESSAGE

        except Exception as error:
            logger.error(
                f"Reasoning answer generation failed: {error}"
            )
            answer = GENERATION_FAILURE_MESSAGE

        # -----------------------------------------------------
        # 6. Format source metadata
        # -----------------------------------------------------
        sources = []

        for rank, result in enumerate(
            evidence[:self.top_k],
            start=1,
        ):
            sources.append(
                {
                    "rank": rank,
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
                    "hybrid_score": self._score(
                        result.get("hybrid_score", 0.0)
                    ),
                    "bm25_score": self._score(
                        result.get("bm25_score", 0.0)
                    ),
                    "faiss_score": self._score(
                        result.get("faiss_score", 0.0)
                    ),
                }
            )

        logger.info(
            f"Reasoning completed with {len(sources)} sources."
        )

        return {
            "query": query,
            "subquestions": subquestions,
            "answer": answer,
            "sources": sources,
        }

    # =========================================================
    # HELPERS
    # =========================================================

    @staticmethod
    def _clean_json(
        response: str,
    ) -> str:
        """
        Remove Markdown code fences if the LLM returns JSON
        inside a fenced code block.
        """
        response = response.strip()

        response = re.sub(
            r"^```(?:json)?\s*",
            "",
            response,
            flags=re.IGNORECASE,
        )

        response = re.sub(
            r"\s*```$",
            "",
            response,
        )

        return response.strip()

    @staticmethod
    def _deduplicate_questions(
        questions: list[str],
    ) -> list[str]:
        """
        Remove duplicate sub-questions while preserving order.
        """
        seen = set()
        result = []

        for question in questions:
            normalized = question.lower().strip()

            if normalized not in seen:
                seen.add(normalized)
                result.append(question)

        return result

    @staticmethod
    def _score(
        value: Any,
    ) -> float:
        """
        Convert a retrieval score safely to float.
        Invalid or missing scores are treated as zero.
        """
        try:
            return float(value)

        except (
            TypeError,
            ValueError,
            OverflowError,
        ):
            return 0.0
