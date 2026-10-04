"""
UNKNOWN X - Adaptive Answer Mode

Selects an answer style based on the user's query while keeping
the final response grounded in retrieved evidence.
"""

import json
import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AnswerMode(str, Enum):
    SHORT = "SHORT"
    DETAILED = "DETAILED"
    TECHNICAL = "TECHNICAL"
    RESEARCH = "RESEARCH"
    COMPARATIVE = "COMPARATIVE"


class AdaptiveAnswerDecision(BaseModel):
    mode: AnswerMode
    reasoning: str = Field(..., min_length=1)


class AdaptiveAnswerEngine:
    """Determine the most appropriate answer mode for a query."""

    _MODE_HINTS: dict[AnswerMode, str] = {  # noqa: RUF012
        AnswerMode.SHORT: (
            "Use for direct factual questions where a concise answer " "is sufficient."
        ),
        AnswerMode.DETAILED: (
            "Use when the user asks for an explanation, description, "
            "steps, or broader understanding."
        ),
        AnswerMode.TECHNICAL: (
            "Use for technical implementation, algorithms, architecture, "
            "code, protocols, or engineering questions."
        ),
        AnswerMode.RESEARCH: (
            "Use for academic, research-oriented, literature, findings, "
            "limitations, methodology, or evidence-focused questions."
        ),
        AnswerMode.COMPARATIVE: (
            "Use when the query explicitly compares two or more entities, "
            "methods, technologies, approaches, or concepts."
        ),
    }

    @classmethod
    def build_prompt(cls, query: str) -> str:
        """Build a deterministic classification prompt."""

        modes = "\n".join(
            f"- {mode.value}: {description}"
            for mode, description in cls._MODE_HINTS.items()
        )

        return f"""
You are the Adaptive Answer Mode classifier for UNKNOWN.

Choose exactly ONE answer mode for the user's query.

Available modes:
{modes}

Rules:
1. Return ONLY valid JSON.
2. The mode must be exactly one of:
   SHORT, DETAILED, TECHNICAL, RESEARCH, COMPARATIVE.
3. Give a brief reason based only on the query.
4. Do not answer the user's question.
5. Do not use outside knowledge.

Required JSON format:
{{
  "mode": "SHORT",
  "reasoning": "Brief explanation."
}}

User query:
{query}
""".strip()

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        """Extract the first valid JSON object from an LLM response."""

        cleaned = text.strip()

        if cleaned.startswith("```"):
            cleaned = re.sub(
                r"^```(?:json)?\s*",
                "",
                cleaned,
                flags=re.IGNORECASE,
            )
            cleaned = re.sub(r"\s*```$", "", cleaned).strip()

        try:
            value = json.loads(cleaned)
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)

        if not match:
            raise ValueError("Adaptive answer classifier returned invalid JSON.")

        try:
            value = json.loads(match.group(0))
        except json.JSONDecodeError as error:
            raise ValueError(
                "Adaptive answer classifier returned invalid JSON."
            ) from error

        if not isinstance(value, dict):
            raise ValueError(  # noqa: TRY004
                "Adaptive answer classifier returned a JSON object."
            )  # noqa: RUF100, TRY004

        return value

    @classmethod
    def parse_response(cls, response_text: str) -> AdaptiveAnswerDecision:
        """Parse and validate an LLM classification response."""

        data = cls._extract_json(response_text)

        if "reasoning" not in data and "reason" in data:
            data["reasoning"] = data["reason"]

        try:
            return AdaptiveAnswerDecision.model_validate(data)
        except Exception as error:
            raise ValueError("Invalid adaptive answer mode response.") from error

    @classmethod
    def classify_query(cls, query: str) -> AnswerMode:
        """
        Deterministically classify obvious query patterns.

        This is used as a safe local fallback when an LLM classifier
        is unavailable.
        """

        normalized = " ".join(query.lower().split())

        comparison_patterns = (
            "compare ",
            "comparison",
            "difference between",
            "differences between",
            "versus ",
            " vs ",
            "advantages and disadvantages",
        )

        research_patterns = (
            "research",
            "paper",
            "literature",
            "findings",
            "methodology",
            "limitations",
            "study ",
            "academic",
            "evidence",
        )

        technical_patterns = (
            "algorithm",
            "architecture",
            "implementation",
            "code",
            "program",
            "protocol",
            "api",
            "database",
            "network",
            "system design",
        )

        detailed_patterns = (
            "explain",
            "how does",
            "how do",
            "describe",
            "steps",
            "why ",
            "elaborate",
            "in detail",
        )

        if any(pattern in normalized for pattern in comparison_patterns):
            return AnswerMode.COMPARATIVE

        if any(pattern in normalized for pattern in research_patterns):
            return AnswerMode.RESEARCH

        if any(pattern in normalized for pattern in technical_patterns):
            return AnswerMode.TECHNICAL

        if any(pattern in normalized for pattern in detailed_patterns):
            return AnswerMode.DETAILED

        return AnswerMode.SHORT
