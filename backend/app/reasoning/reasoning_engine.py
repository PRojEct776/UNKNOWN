"""
UNKNOWN Project - AI Reasoning Engine

Srinidhi's reasoning module.

Uses Aashrith's existing RAG components:

    Reasoning Query
          ↓
    Query Decomposition
          ↓
    HybridSearch for each sub-question
          ↓
    Evidence Aggregation
          ↓
    ContextBuilder
          ↓
    PromptEngine (REASONING)
          ↓
    GeminiEngine
          ↓
    Final Grounded Answer
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.llm.orchestrator import LLMOrchestrator
from app.rag.context_builder import ContextBuilder
from app.rag.hybrid_search import HybridSearch
from app.rag.logger import logger
from app.rag.prompt_engine import PromptEngine, QueryType


class ReasoningEngine:
    """
    Multi-step reasoning layer built on top of the existing RAG.
    """

    def __init__(
        self,
        retriever: HybridSearch,
        context_builder: ContextBuilder,
        prompt_engine: PromptEngine,
        llm: LLMOrchestrator,
        max_subquestions: int = 3,
        top_k: int = 5,
    ) -> None:

        if max_subquestions < 1:
            raise ValueError("max_subquestions must be at least 1.")

        if top_k < 1:
            raise ValueError("top_k must be at least 1.")

        self.retriever = retriever
        self.context_builder = context_builder
        self.prompt_engine = prompt_engine
        self.llm = llm
        self.max_subquestions = max_subquestions
        self.top_k = top_k

        logger.info("UNKNOWN Reasoning Engine initialized.")

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

        response = self.llm.generate_structured(decomposition_prompt)

        if not response.success:
            raise RuntimeError(f"Reasoning decomposition failed: {response.error}")

        response_text = response.answer

        try:
            cleaned = self._clean_json(response_text)

            data = json.loads(cleaned)

            questions = data.get(
                "subquestions",
                [],
            )

            if not isinstance(
                questions,
                list,
            ):
                raise ValueError("subquestions must be a list.")  # noqa: TRY004

            cleaned_questions = []

            for question in questions:

                question = str(question).strip()

                if question:
                    cleaned_questions.append(question)

            cleaned_questions = self._deduplicate_questions(cleaned_questions)

            if cleaned_questions:

                return cleaned_questions[: self.max_subquestions]

        except (
            json.JSONDecodeError,
            ValueError,
            TypeError,
        ) as error:

            logger.warning(f"Reasoning decomposition failed: {error}")

        # Safe fallback:
        # retrieve directly using the original question.
        return [query]

    # =========================================================
    # MULTI-QUERY RETRIEVAL
    # =========================================================

    def retrieve_evidence(
        self,
        subquestions: list[str],
    ) -> list[dict[str, Any]]:
        """
        Retrieve evidence for each sub-question using
        Aashrith's existing HybridSearch.
        """

        evidence_by_chunk: dict[
            str,
            dict[str, Any],
        ] = {}

        for subquestion in subquestions:

            logger.info(f"Reasoning retrieval: {subquestion}")

            results = self.retriever.search(
                subquestion,
                top_k=self.top_k,
            )

            for result in results:

                chunk_id = result.get("chunk_id")

                if chunk_id is None:
                    continue

                key = str(chunk_id)

                current_score = self._score(
                    result.get(
                        "hybrid_score",
                        0.0,
                    )
                )

                existing = evidence_by_chunk.get(key)

                if existing is None:

                    evidence_by_chunk[key] = result

                else:

                    existing_score = self._score(
                        existing.get(
                            "hybrid_score",
                            0.0,
                        )
                    )

                    if current_score > existing_score:

                        evidence_by_chunk[key] = result

        evidence = list(evidence_by_chunk.values())

        # Highest hybrid score first
        evidence.sort(
            key=lambda result: self._score(
                result.get(
                    "hybrid_score",
                    0.0,
                )
            ),
            reverse=True,
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
        Reuse the existing ContextBuilder and PromptEngine.
        """

        context = self.context_builder.build(evidence)

        prompt = self.prompt_engine.build_prompt(
            query=query,
            context=context,
            query_type=QueryType.REASONING,
        )

        prompt += """

Additional reasoning requirements:
- Connect the retrieved evidence logically.
- Answer the main question, not the sub-questions separately.
- Use only the retrieved context.
- Do not introduce unsupported facts.
- Do not fabricate sources or citations.
- Do not reveal hidden chain-of-thought.
- Give a concise explanation of the reasoning outcome.
- If the evidence is insufficient, say:
  "The retrieved context does not contain enough information."
""".strip()

        return prompt

    # =========================================================
    # COMPLETE REASONING PIPELINE
    # =========================================================

    def reason(
        self,
        query: str,
    ) -> dict[str, Any]:
        """
        Execute:

        Query
          ↓
        Decomposition
          ↓
        Multiple HybridSearch calls
          ↓
        Evidence aggregation
          ↓
        ContextBuilder
          ↓
        Reasoning Prompt
          ↓
        Gemini
          ↓
        Final answer
        """

        if not isinstance(query, str):
            raise TypeError("query must be a string.")

        query = query.strip()

        if not query:
            raise ValueError("query cannot be empty.")

        logger.info(f"Starting reasoning query: {query}")

        # -----------------------------------------------
        # 1. Decompose
        # -----------------------------------------------

        subquestions = self.decompose_query(query)

        logger.info(f"Generated {len(subquestions)} " f"reasoning subquestions.")

        # -----------------------------------------------
        # 2. Retrieve
        # -----------------------------------------------

        evidence = self.retrieve_evidence(subquestions)

        # -----------------------------------------------
        # 3. Insufficient evidence
        # -----------------------------------------------

        if not evidence:

            return {
                "query": query,
                "subquestions": subquestions,
                "answer": (
                    "The retrieved context does not " "contain enough information."
                ),
                "sources": [],
            }

        # -----------------------------------------------
        # 4. Build reasoning prompt
        # -----------------------------------------------

        prompt = self.build_reasoning_prompt(
            query=query,
            evidence=evidence,
        )

        # -----------------------------------------------
        # 5. Generate final answer
        # -----------------------------------------------

        response = self.llm.generate(prompt)

        if not response.success:
            raise RuntimeError(f"Reasoning generation failed: {response.error}")

        answer = response.answer.strip()

        # -----------------------------------------------
        # 6. Format sources
        # -----------------------------------------------

        sources = []

        for rank, result in enumerate(
            evidence[: self.top_k],
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
                        result.get(
                            "hybrid_score",
                            0.0,
                        )
                    ),
                    "bm25_score": self._score(
                        result.get(
                            "bm25_score",
                            0.0,
                        )
                    ),
                    "faiss_score": self._score(
                        result.get(
                            "faiss_score",
                            0.0,
                        )
                    ),
                }
            )

        logger.info(f"Reasoning completed with " f"{len(sources)} sources.")

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
        inside ```json ... ``` .
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
        """

        try:
            return float(value)

        except (
            TypeError,
            ValueError,
        ):
            return 0.0
