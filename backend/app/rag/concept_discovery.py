"""
UNKNOWN X - Concept Discovery

Identifies a technical concept from a user's natural-language
description using retrieved document evidence.
"""

import json
import re

from pydantic import BaseModel, Field


class ConceptDiscoveryResult(BaseModel):
    """Structured result of concept discovery."""

    description: str = Field(..., min_length=1)
    concept: str | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    explanation: str
    evidence: list[str] = Field(default_factory=list)
    source_chunk_ids: list[str] = Field(default_factory=list)


class ConceptDiscoveryEngine:
    """Identify unknown concepts using evidence-grounded reasoning."""

    def build_concept_prompt(
        self,
        description: str,
        context: str,
    ) -> str:
        """Build an evidence-grounded concept discovery prompt."""

        return f"""
You are the concept discovery component of UNKNOWN.

The user does not remember the exact technical term.
They are describing what the concept does or how it works.

Your task is to identify the most likely technical concept
described by the user using ONLY the supplied DOCUMENT EVIDENCE.

Do not use outside knowledge.
Do not invent evidence.
Do not invent citations.
Do not guess a concept unless the supplied evidence supports it.

The concept name does NOT need to appear explicitly in the
USER DESCRIPTION. Infer it from the described behavior only
when the DOCUMENT EVIDENCE supports that inference.

If multiple concepts are plausible, select the concept best
supported by the evidence.

If the evidence is insufficient to identify the concept,
return concept as null and confidence as 0.0.

USER DESCRIPTION:
{description}

DOCUMENT EVIDENCE:
{context}

Return ONLY valid JSON in exactly this structure:

{{
  "concept": "Technical concept name",
  "confidence": 0.0,
  "explanation": "Brief explanation connecting the description to the evidence.",
  "evidence": [
    "Short evidence statement"
  ],
  "source_chunk_ids": [
    "chunk_id"
  ]
}}

For insufficient evidence:

{{
  "concept": null,
  "confidence": 0.0,
  "explanation": "The supplied evidence is insufficient to identify the concept.",
  "evidence": [],
  "source_chunk_ids": []
}}

Confidence must be a number between 0 and 1.
""".strip()

    @staticmethod
    def _extract_json(text: str) -> dict:
        """Extract JSON from a model response."""

        cleaned = text.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        fenced = re.search(
            r"```(?:json)?\s*(\{.*?\})\s*```",
            cleaned,
            flags=re.DOTALL,
        )

        if fenced:
            try:
                return json.loads(fenced.group(1))
            except json.JSONDecodeError:
                pass

        start = cleaned.find("{")
        end = cleaned.rfind("}")

        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                pass

        raise ValueError("Provider returned invalid concept discovery JSON.")

    @staticmethod
    def _validate_result(
        description: str,
        data: dict,
    ) -> ConceptDiscoveryResult:
        """Validate and normalize model output."""

        concept = data.get("concept")

        if concept is not None:
            concept = str(concept).strip()

            if not concept:
                concept = None

        confidence = float(data.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))

        if concept is None:
            confidence = 0.0

        explanation = str(
            data.get(
                "explanation",
                "No explanation was provided.",
            )
        ).strip()

        evidence = data.get("evidence", [])
        if not isinstance(evidence, list):
            evidence = [str(evidence)]

        source_chunk_ids = data.get("source_chunk_ids", [])
        if not isinstance(source_chunk_ids, list):
            source_chunk_ids = [str(source_chunk_ids)]

        return ConceptDiscoveryResult(
            description=description,
            concept=concept,
            confidence=confidence,
            explanation=explanation,
            evidence=[str(item) for item in evidence],
            source_chunk_ids=[str(item) for item in source_chunk_ids],
        )

    def parse_response(
        self,
        description: str,
        response_text: str,
    ) -> ConceptDiscoveryResult:
        """Parse and validate an LLM concept discovery response."""

        data = self._extract_json(response_text)

        return self._validate_result(
            description=description,
            data=data,
        )
