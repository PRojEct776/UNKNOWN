"""
UNKNOWN X - Claim Verification

Verifies user-provided claims against retrieved document evidence.
"""

import json
import math
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
    supporting_evidence: list[str] = Field(default_factory=list)
    contradicting_evidence: list[str] = Field(default_factory=list)


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
Every item in supporting_evidence and contradicting_evidence MUST be an exact,
verbatim quote copied from the DOCUMENT EVIDENCE. Do not paraphrase. You may
join two parts of one passage with "...".
Put quotes that support the claim in supporting_evidence and quotes that
conflict with it in contradicting_evidence.
If the claim contains numbers or units, they must match the evidence exactly;
otherwise use PARTIALLY_SUPPORTED or CONTRADICTED.
For source_chunk_ids use only the Chunk ID values shown in the evidence.

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
  "supporting_evidence": [
    "Exact quote from the evidence that supports the claim"
  ],
  "contradicting_evidence": [
    "Exact quote from the evidence that conflicts with the claim"
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

        confidence = ClaimVerifier._safe_confidence(data.get("confidence", 0.0))

        explanation = str(
            data.get(
                "explanation",
                "No explanation was provided.",
            )
        ).strip()

        supporting = ClaimVerifier._as_str_list(data.get("supporting_evidence"))
        contradicting = ClaimVerifier._as_str_list(data.get("contradicting_evidence"))
        legacy = ClaimVerifier._as_str_list(data.get("evidence"))
        if legacy and not supporting and not contradicting:
            supporting, contradicting = ClaimVerifier._split_legacy(parsed_verdict, legacy)

        source_chunk_ids = data.get("source_chunk_ids", [])
        if not isinstance(source_chunk_ids, list):
            source_chunk_ids = [str(source_chunk_ids)]

        return ClaimVerificationResult(
            claim=claim,
            verdict=parsed_verdict,
            confidence=confidence,
            explanation=explanation,
            evidence=supporting + contradicting,
            supporting_evidence=supporting,
            contradicting_evidence=contradicting,
            source_chunk_ids=[str(item) for item in source_chunk_ids],
        )

    @staticmethod
    def _safe_confidence(value) -> float:
        """Return a confidence in [0, 1]; anything unusable becomes 0.0."""

        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.0
        if math.isnan(number) or math.isinf(number):
            return 0.0
        return max(0.0, min(1.0, number))

    @staticmethod
    def _as_str_list(value) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            value = [value]
        return [str(item) for item in value if str(item).strip()]

    @staticmethod
    def _split_legacy(verdict, evidence):
        """Legacy single evidence list -> (supporting, contradicting) by verdict."""

        if verdict == ClaimVerdict.CONTRADICTED:
            return [], list(evidence)
        return list(evidence), []

    @staticmethod
    def _norm(text) -> str:
        value = str(text).lower()
        value = (
            value.replace("\u2019", "'")
            .replace("\u2018", "'")
            .replace("\u201c", '"')
            .replace("\u201d", '"')
        )
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _fragments(quote) -> list[str]:
        """Split a quote on '...' gaps into normalized fragments to look up."""

        parts = re.split(r"\.\.\.|\u2026", ClaimVerifier._norm(quote))
        fragments = []
        for part in parts:
            part = part.strip(" '\".,;:")
            if len(part) >= 3:
                fragments.append(part)
        return fragments

    @staticmethod
    def _numbers(text) -> list[str]:
        value = re.sub(r"(?<=\d),(?=\d{3})", "", str(text))
        return re.findall(r"\d+(?:\.\d+)?", value)

    def _ground_quotes(self, quotes, chunks, max_chars):
        """Keep only quotes found in one visible chunk; return (kept, chunk_ids)."""

        texts = []
        for chunk in chunks:
            text = str(chunk.get("text", "") or "").strip()
            if max_chars and len(text) > max_chars:
                text = text[:max_chars]
            chunk_id = chunk.get("chunk_id")
            texts.append((str(chunk_id) if chunk_id is not None else None, self._norm(text)))

        kept = []
        ids = []
        for quote in quotes:
            fragments = self._fragments(quote)
            if not fragments:
                continue
            for chunk_id, text in texts:
                if all(fragment in text for fragment in fragments):
                    kept.append(quote)
                    if chunk_id and chunk_id not in ids:
                        ids.append(chunk_id)
                    break
        return kept, ids

    def ground_result(self, result, chunks, max_chars=None):
        """Check a parsed result against the chunks the model was shown."""

        if not chunks:
            return result.model_copy(
                update={
                    "verdict": ClaimVerdict.NOT_FOUND,
                    "confidence": 0.0,
                    "explanation": (
                        "No relevant passages were retrieved, so this claim "
                        "could not be checked."
                    ),
                    "evidence": [],
                    "supporting_evidence": [],
                    "contradicting_evidence": [],
                    "source_chunk_ids": [],
                }
            )

        supporting = list(result.supporting_evidence)
        contradicting = list(result.contradicting_evidence)
        if not supporting and not contradicting and result.evidence:
            supporting, contradicting = self._split_legacy(result.verdict, result.evidence)

        supporting, ids_s = self._ground_quotes(supporting, chunks, max_chars)
        contradicting, ids_c = self._ground_quotes(contradicting, chunks, max_chars)
        ids = ids_s + [item for item in ids_c if item not in ids_s]

        verdict = result.verdict
        ungrounded = (
            (verdict == ClaimVerdict.SUPPORTED and not supporting)
            or (verdict == ClaimVerdict.CONTRADICTED and not contradicting)
            or (
                verdict == ClaimVerdict.PARTIALLY_SUPPORTED
                and not (supporting or contradicting)
            )
        )
        if ungrounded:
            return result.model_copy(
                update={
                    "verdict": ClaimVerdict.NOT_FOUND,
                    "confidence": 0.0,
                    "explanation": (
                        "The model's verdict could not be confirmed: none of its "
                        "quoted evidence appears in the retrieved passages."
                    ),
                    "evidence": [],
                    "supporting_evidence": [],
                    "contradicting_evidence": [],
                    "source_chunk_ids": [],
                }
            )

        explanation = result.explanation
        if verdict == ClaimVerdict.SUPPORTED:
            evidence_numbers = set(self._numbers(" ".join(supporting)))
            missing = []
            for number in self._numbers(result.claim):
                if number not in evidence_numbers and number not in missing:
                    missing.append(number)
            if missing:
                verdict = ClaimVerdict.PARTIALLY_SUPPORTED
                explanation = (
                    f"{explanation} Note: the claim's number(s) {', '.join(missing)} "
                    "do not appear in the quoted evidence, so full support could "
                    "not be confirmed."
                )

        return result.model_copy(
            update={
                "verdict": verdict,
                "explanation": explanation,
                "evidence": supporting + contradicting,
                "supporting_evidence": supporting,
                "contradicting_evidence": contradicting,
                "source_chunk_ids": ids,
            }
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