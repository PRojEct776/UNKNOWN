"""
UNKNOWN X - Claim Verification

Verifies user-provided claims against retrieved document evidence.
"""

import json
import re
from enum import Enum

from pydantic import BaseModel, Field


class ClaimVerdict(str, Enum):
    """Possible verification outcomes."""

    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    NOT_FOUND = "NOT_FOUND"


class ClaimVerificationResult(BaseModel):
    """Structured result of claim verification."""

    claim: str = Field(..., min_length=1)
    verdict: ClaimVerdict
    confidence: float = Field(..., ge=0.0, le=1.0)
    explanation: str
    evidence: list[str] = Field(default_factory=list)
    source_chunk_ids: list[str] = Field(default_factory=list)


class ClaimVerifier:
    """Analyze a claim against retrieved document evidence."""

    def build_verification_prompt(
        self,
        claim: str,
        context: str,
    ) -> str:
        """Build a grounded claim-verification prompt."""

        return f"""
You are the claim verification component of UNKNOWN.

Your task is to evaluate the CLAIM using ONLY the supplied
DOCUMENT EVIDENCE.

Do not use outside knowledge.
Do not assume missing information.
Do not invent evidence.
Do not invent citations.

CLAIM:
{claim}

DOCUMENT EVIDENCE:
{context}

Classify the claim into exactly one of:

SUPPORTED
PARTIALLY_SUPPORTED
CONTRADICTED
NOT_FOUND

Definitions:

SUPPORTED:
The evidence directly supports the claim.

PARTIALLY_SUPPORTED:
The evidence supports only part of the claim or provides
qualified/incomplete support.

CONTRADICTED:
The evidence directly conflicts with the claim.

NOT_FOUND:
The supplied evidence does not provide enough information
to support or contradict the claim.

Return ONLY valid JSON in this exact structure:

{{
  "verdict": "SUPPORTED",
  "confidence": 0.0,
  "explanation": "Brief explanation based only on the evidence.",
  "evidence": [
    "Short evidence statement"
  ],
  "source_chunk_ids": [
    "chunk_id"
  ]
}}

Confidence must be a number between 0 and 1.
""".strip()

    @staticmethod
    def _extract_json(text: str) -> dict:
        """Extract JSON from a model response."""

        cleaned = text.strip()

        # Direct JSON response.
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Handle markdown JSON fences.
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

        # Last attempt: locate the outermost JSON object.
        start = cleaned.find("{")
        end = cleaned.rfind("}")

        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                pass

        raise ValueError("Provider returned invalid verification JSON.")

    @staticmethod
    def _validate_result(
        claim: str,
        data: dict,
    ) -> ClaimVerificationResult:
        """Validate and normalize model output."""

        verdict = str(data.get("verdict", "")).upper().strip()

        try:
            parsed_verdict = ClaimVerdict(verdict)
        except ValueError as error:
            raise ValueError(
                f"Invalid claim verification verdict: {verdict}"
            ) from error

        confidence = float(data.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))

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

        return ClaimVerificationResult(
            claim=claim,
            verdict=parsed_verdict,
            confidence=confidence,
            explanation=explanation,
            evidence=[str(item) for item in evidence],
            source_chunk_ids=[str(item) for item in source_chunk_ids],
        )

    def parse_response(
        self,
        claim: str,
        response_text: str,
    ) -> ClaimVerificationResult:
        """Parse and validate an LLM verification response."""

        data = self._extract_json(response_text)

        return self._validate_result(
            claim=claim,
            data=data,
        )