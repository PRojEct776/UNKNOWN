from __future__ import annotations

import json
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DebateSide(str, Enum):
    POSITION_A = "POSITION_A"
    POSITION_B = "POSITION_B"


class DebateArgument(BaseModel):
    side: DebateSide
    argument: str = Field(..., min_length=1)
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    document: str = ""
    page: int | str = ""
    chunk_id: str = ""


class DebateRebuttal(BaseModel):
    side: DebateSide
    target_argument: str = Field(..., min_length=1)
    rebuttal: str = Field(..., min_length=1)
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)


class DebateReport(BaseModel):
    query: str
    topic: str
    position_a: str
    position_b: str
    arguments: list[DebateArgument] = Field(default_factory=list)
    rebuttals: list[DebateRebuttal] = Field(default_factory=list)
    final_verdict: str = Field(..., min_length=1)
    verdict_confidence: float = Field(..., ge=0.0, le=1.0)
    sources: list[dict[str, Any]] = Field(default_factory=list)


class DebateEngine:
    """
    Evidence-grounded AI debate engine.

    The model is strictly constrained to the supplied retrieval evidence.
    It must not introduce outside facts or unsupported citations.
    """

    def build_debate_prompt(
        self,
        *,
        query: str,
        position_a: str,
        position_b: str,
        evidence: list[dict[str, Any]],
    ) -> str:
        evidence_json = json.dumps(evidence, ensure_ascii=False, indent=2)

        return f"""
You are the AI Debate Engine of UNKNOWN.

Your task is to analyze a research question by debating two supplied
positions using ONLY the evidence provided below.

RESEARCH QUESTION:
{query}

POSITION A:
{position_a}

POSITION B:
{position_b}

SUPPLIED EVIDENCE:
{evidence_json}

STRICT RULES:

1. Use ONLY the supplied evidence.
2. Do NOT use outside knowledge.
3. Do NOT invent facts, findings, papers, citations, documents, pages,
   chunk IDs, experiments, numbers, or claims.
4. Every factual argument must be traceable to supplied evidence.
5. Clearly distinguish POSITION_A and POSITION_B.
6. Arguments must represent what the evidence supports for each position.
7. Rebuttals must address an argument using only supplied evidence.
8. If evidence does not support a position, do not manufacture support.
9. Confidence values must be between 0 and 1.
10. The final verdict must reflect the supplied evidence only.
11. Do not declare a definitive winner when the evidence is insufficient.
12. Preserve document, page, and chunk identifiers when available.
13. Return ONLY valid JSON.
14. Follow the exact JSON structure requested below.

EXPECTED JSON STRUCTURE:

{{
  "query": "{query}",
  "topic": "short description of the research topic",
  "position_a": "{position_a}",
  "position_b": "{position_b}",
  "arguments": [
    {{
      "side": "POSITION_A",
      "argument": "evidence-grounded argument",
      "evidence": ["supporting evidence"],
      "confidence": 0.0,
      "document": "document name",
      "page": 0,
      "chunk_id": "chunk id"
    }}
  ],
  "rebuttals": [
    {{
      "side": "POSITION_B",
      "target_argument": "argument being challenged",
      "rebuttal": "evidence-grounded rebuttal",
      "evidence": ["supporting evidence"],
      "confidence": 0.0
    }}
  ],
  "final_verdict": "balanced evidence-grounded synthesis",
  "verdict_confidence": 0.0,
  "sources": [
    {{
      "document": "document name",
      "page": 0,
      "chunk_id": "chunk id"
    }}
  ]
}}

IMPORTANT:
If the supplied evidence is insufficient to meaningfully debate the
positions, return empty arguments/rebuttals and explain the limitation
in final_verdict.

Do not add Markdown fences.
Do not add commentary outside the JSON object.
""".strip()

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        """
        Extract a JSON object from a provider response.

        Handles occasional Markdown fences or surrounding text while
        still requiring the final payload to be a JSON object.
        """
        if not text or not text.strip():
            raise ValueError("Debate engine returned an empty response.")

        cleaned = text.strip()

        if cleaned.startswith("```"):
            lines = cleaned.splitlines()

            if lines and lines[0].strip().startswith("```"):
                lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            cleaned = "\n".join(lines).strip()

        try:
            value = json.loads(cleaned)
        except json.JSONDecodeError:
            start = cleaned.find("{")
            end = cleaned.rfind("}")

            if start == -1 or end == -1 or end <= start:
                raise ValueError("Debate engine returned invalid JSON.") from None

            try:
                value = json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError as error:
                raise ValueError("Debate engine returned invalid JSON.") from error

        if not isinstance(value, dict):
            raise ValueError("Debate engine response must be a JSON object.")

        return value

    @staticmethod
    def _parse_argument(value: Any) -> DebateArgument:
        if not isinstance(value, dict):
            raise ValueError("Invalid debate argument.")  # noqa: TRY004

        return DebateArgument(
            side=value.get("side"),  # type: ignore
            argument=value.get("argument", ""),
            evidence=value.get("evidence", []),
            confidence=value.get("confidence", 0.0),
            document=value.get("document", ""),
            page=value.get("page", ""),
            chunk_id=value.get("chunk_id", ""),
        )

    @staticmethod
    def _parse_rebuttal(value: Any) -> DebateRebuttal:
        if not isinstance(value, dict):
            raise ValueError("Invalid debate rebuttal.")  # noqa: TRY004

        return DebateRebuttal(
            side=value.get("side"),  # type: ignore
            target_argument=value.get("target_argument", ""),
            rebuttal=value.get("rebuttal", ""),
            evidence=value.get("evidence", []),
            confidence=value.get("confidence", 0.0),
        )

    @staticmethod
    def _parse_sources(value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []

        sources: list[dict[str, Any]] = []

        for source in value:
            if not isinstance(source, dict):
                continue

            sources.append(
                {
                    "document": source.get("document", ""),
                    "page": source.get("page", ""),
                    "chunk_id": source.get("chunk_id", ""),
                }
            )

        return sources

    def parse_response(
        self,
        *,
        query: str,
        position_a: str,
        position_b: str,
        response_text: str,
    ) -> DebateReport:
        payload = self._extract_json(response_text)

        arguments = [
            self._parse_argument(item) for item in payload.get("arguments", [])
        ]

        rebuttals = [
            self._parse_rebuttal(item) for item in payload.get("rebuttals", [])
        ]

        return DebateReport(
            query=query,
            topic=payload.get("topic", query),
            position_a=payload.get("position_a", position_a),
            position_b=payload.get("position_b", position_b),
            arguments=arguments,
            rebuttals=rebuttals,
            final_verdict=payload.get(
                "final_verdict",
                "Insufficient evidence for a reliable verdict.",
            ),
            verdict_confidence=payload.get(
                "verdict_confidence",
                0.0,
            ),
            sources=self._parse_sources(payload.get("sources", [])),
        )
