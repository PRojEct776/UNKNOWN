"""
UNKNOWN X - Contradiction Finder

Detects conflicting claims across retrieved document evidence.
"""

import json
import re
from enum import Enum

from pydantic import BaseModel, Field


class ClaimRelation(str, Enum):
    """Relationship between two claims."""

    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    QUALIFIES = "QUALIFIES"
    UNRELATED = "UNRELATED"


class EvidenceClaim(BaseModel):
    """A claim extracted from document evidence."""

    claim: str = Field(..., min_length=1)
    evidence: str = Field(..., min_length=1)
    document: str
    page: int | str
    chunk_id: str


class ClaimRelationship(BaseModel):
    """Relationship between two evidence claims."""

    claim_a: EvidenceClaim
    claim_b: EvidenceClaim
    relation: ClaimRelation
    confidence: float = Field(..., ge=0.0, le=1.0)
    explanation: str


class ContradictionReport(BaseModel):
    """Complete contradiction analysis report."""

    query: str
    claims: list[EvidenceClaim] = Field(default_factory=list)
    relationships: list[ClaimRelationship] = Field(default_factory=list)
    contradictions_found: int = 0


class ContradictionFinder:
    """Builds prompts and parses LLM contradiction analysis."""

    def build_contradiction_prompt(
        self,
        query: str,
        evidence: list[dict],
    ) -> str:  # type: ignore
        evidence_blocks = []

        for index, item in enumerate(evidence, start=1):  # type: ignore
            evidence_blocks.append(f"""
EVIDENCE {index}

Document: {item.get("document", "")}

Page: {item.get("page", "")}

Chunk ID: {item.get("chunk_id", "")}

Text:
{item.get("text", "")}
""".strip())

        evidence_text = "\n\n".join(evidence_blocks)

        return f"""

Use ONLY the supplied document evidence.

Do not use outside knowledge.
Do not invent claims.
Do not invent evidence.
Do not infer facts that are not present in the evidence.

USER QUERY:
{query}

DOCUMENT EVIDENCE:
{evidence_text}

For each important claim that is explicitly supported by the evidence,
create an EvidenceClaim.

Every EvidenceClaim MUST contain:
- claim
- evidence
- document
- page
- chunk_id

The "evidence" field is mandatory.

The evidence field MUST contain the exact or concise supporting passage
from the supplied document evidence. It must never be empty.

When a claim appears inside a relationship as claim_a or claim_b,
that nested claim MUST ALSO contain all five fields:
claim, evidence, document, page, and chunk_id.

Then compare relevant pairs of claims.

Use exactly one relationship:

SUPPORTS
- One claim supports or reinforces the other.

CONTRADICTS
- The claims make incompatible statements about the same subject,
  condition, metric, result, or conclusion.

QUALIFIES
- One claim limits, conditions, narrows, or adds an important
  qualification to the other without directly contradicting it.

UNRELATED
- The claims do not meaningfully address the same proposition.

Only report relationships that are supported by the supplied evidence.

Return ONLY valid JSON in this exact structure:

{{
  "claims": [
    {{
      "claim": "Short factual claim extracted from the evidence.",
      "evidence": "Exact or concise supporting passage from the supplied evidence.",
      "document": "document.pdf",
      "page": 1,
      "chunk_id": "chunk_1"
    }}
  ],
  "relationships": [
    {{
      "claim_a": {{
        "claim": "First claim.",
        "evidence": "Supporting passage for the first claim.",
        "document": "document_a.pdf",
        "page": 1,
        "chunk_id": "chunk_1"
      }},
      "claim_b": {{
        "claim": "Second claim.",
        "evidence": "Supporting passage for the second claim.",
        "document": "document_b.pdf",
        "page": 2,
        "chunk_id": "chunk_4"
      }},
      "relation": "CONTRADICTS",
      "confidence": 0.95,
      "explanation": "Brief explanation based only on the supplied evidence."
    }}
  ],
  "contradictions_found": 1
}}

Rules:

- confidence must be between 0 and 1.
- contradictions_found must equal the number of CONTRADICTS relationships.
- Every top-level claim must be traceable to one supplied evidence chunk.
- Every top-level claim MUST include non-empty evidence.
- Every nested claim_a MUST include non-empty evidence.
- Every nested claim_b MUST include non-empty evidence.
- The evidence must come directly from the supplied document evidence.
- Do not paraphrase the evidence so strongly that its meaning changes.
- Do not create claims from outside knowledge.
- Do not create citations that are not present in the evidence.
- If there is no sufficient evidence for a claim, do not include that claim.
- Never leave the evidence field empty.
""".strip()

    @staticmethod
    def _extract_json(text: str) -> dict:
        """Extract JSON from a raw or markdown-wrapped LLM response."""

        cleaned = text.strip()

        # Direct JSON
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Markdown JSON block
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

        # JSON embedded in additional text
        start = cleaned.find("{")
        end = cleaned.rfind("}")

        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                pass

        raise ValueError("Provider returned invalid contradiction analysis JSON.")

    @staticmethod
    def _parse_claim(data: dict) -> EvidenceClaim:
        claim = str(data.get("claim", "")).strip()
        evidence = str(data.get("evidence", "")).strip()
        document = str(data.get("document", "")).strip()
        page = data.get("page", "")
        chunk_id = str(data.get("chunk_id", "")).strip()

        if not claim:
            raise ValueError(
                "Contradiction model response contains a claim without claim text."
            )

        if not evidence:
            raise ValueError(
                f"Contradiction model response contains claim without evidence: {claim}"
            )

        if not document:
            raise ValueError(
                f"Contradiction model response contains claim without document: {claim}"
            )

        if not chunk_id:
            raise ValueError(
                f"Contradiction model response contains claim without chunk_id: {claim}"
            )

        return EvidenceClaim(
            claim=claim,
            evidence=evidence,
            document=document,
            page=page,
            chunk_id=chunk_id,
        )

    def parse_response(
        self,
        query: str,
        response_text: str,
    ) -> ContradictionReport:
        """Parse and validate the LLM contradiction response."""

        data = self._extract_json(response_text)

        raw_claims = data.get("claims", [])
        raw_relationships = data.get("relationships", [])

        if not isinstance(raw_claims, list):
            raise ValueError(  # noqa: TRY004
                "Contradiction response 'claims' must be a list."
            )

        if not isinstance(raw_relationships, list):
            raise ValueError(  # noqa: TRY004
                "Contradiction response 'relationships' must be a list."
            )

        claims = [
            self._parse_claim(item) for item in raw_claims if isinstance(item, dict)
        ]

        relationships = []

        for item in raw_relationships:
            if not isinstance(item, dict):
                continue

            relation = str(item.get("relation", "")).upper().strip()

            try:
                parsed_relation = ClaimRelation(relation)
            except ValueError as error:
                raise ValueError(f"Invalid claim relationship: {relation}") from error

            claim_a = self._parse_claim(item.get("claim_a", {}))
            claim_b = self._parse_claim(item.get("claim_b", {}))

            confidence = float(item.get("confidence", 0.0))
            confidence = max(0.0, min(1.0, confidence))

            explanation = str(
                item.get(
                    "explanation",
                    "No explanation was provided.",
                )
            ).strip()

            relationships.append(
                ClaimRelationship(
                    claim_a=claim_a,
                    claim_b=claim_b,
                    relation=parsed_relation,
                    confidence=confidence,
                    explanation=explanation,
                )
            )

        contradictions_found = sum(
            1
            for relationship in relationships
            if relationship.relation == ClaimRelation.CONTRADICTS
        )

        return ContradictionReport(
            query=query,
            claims=claims,
            relationships=relationships,
            contradictions_found=contradictions_found,
        )
