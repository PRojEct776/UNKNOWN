from __future__ import annotations

import json
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class GapType(str, Enum):
    EXPLICIT = "EXPLICIT"
    INFERRED = "INFERRED"


class ResearchGap(BaseModel):
    gap: str = Field(..., min_length=1)
    type: GapType
    confidence: float = Field(..., ge=0.0, le=1.0)
    rationale: str = Field(..., min_length=1)
    evidence: list[str] = Field(default_factory=list)
    document: str = ""
    page: int | str = ""
    chunk_id: str = ""


class ResearchGapReport(BaseModel):
    query: str
    research_area: str
    existing_findings: list[str] = Field(default_factory=list)
    reported_limitations: list[str] = Field(default_factory=list)
    gaps: list[ResearchGap] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)


class ResearchGapFinder:
    """Evidence-grounded research gap detection engine."""

    def build_gap_prompt(
        self,
        *,
        query: str,
        evidence: list[dict[str, Any]],
    ) -> str:
        evidence_json = json.dumps(
            evidence,
            ensure_ascii=False,
            indent=2,
        )

        return f"""
You are the Research Gap Finder component of UNKNOWN X.

Your task is to identify research gaps using ONLY the supplied retrieved
research evidence.

RESEARCH QUESTION:
{query}

RETRIEVED EVIDENCE:
{evidence_json}

STRICT RULES:

1. Use ONLY the supplied evidence.
2. Do NOT use outside knowledge.
3. Do NOT invent papers, findings, limitations, datasets, metrics,
   citations, or research gaps.
4. Every reported finding and limitation must be traceable to the evidence.
5. Every gap must contain evidence supporting why the area appears
   underexplored, limited, missing, or insufficiently addressed.
6. Distinguish:
   - EXPLICIT: the source directly states or strongly indicates the gap.
   - INFERRED: the gap is a cautious synthesis from multiple supplied
     evidence items.
7. Do not present an inferred gap as an explicit statement from a paper.
8. If evidence is insufficient to establish a gap, do not invent one.
9. Preserve dataset-specific, experiment-specific, and document-specific
   claims.
10. Confidence must be between 0 and 1.
11. Return ONLY valid JSON.
12. Do not wrap JSON in markdown fences.
13. Do not add commentary before or after the JSON.

Return exactly this structure:

{{
  "query": "{query}",
  "research_area": "concise research area",
  "existing_findings": [
    "finding supported by supplied evidence"
  ],
  "reported_limitations": [
    "limitation supported by supplied evidence"
  ],
  "gaps": [
    {{
      "gap": "specific research gap",
      "type": "EXPLICIT",
      "confidence": 0.0,
      "rationale": "why the supplied evidence supports this gap",
      "evidence": [
        "exactly the supplied evidence used to support the gap"
      ],
      "document": "source document",
      "page": "page",
      "chunk_id": "chunk identifier"
    }}
  ],
  "sources": [
    {{
      "document": "source document",
      "page": "page",
      "chunk_id": "chunk identifier"
    }}
  ]
}}

If no defensible research gap can be established from the supplied
evidence, return an empty "gaps" list.
""".strip()

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        """Extract a JSON object from a provider response."""
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Provider returned empty research gap output.")

        raw = text.strip()

        # Direct JSON.
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

        # Markdown fenced JSON.
        if "```" in raw:
            blocks = raw.split("```")
            for block in blocks:
                candidate = block.strip()

                if candidate.lower().startswith("json"):
                    candidate = candidate[4:].strip()

                try:
                    data = json.loads(candidate)
                    if isinstance(data, dict):
                        return data
                except json.JSONDecodeError:
                    continue

        # Embedded JSON object.
        start = raw.find("{")

        while start >= 0:
            depth = 0
            in_string = False
            escaped = False

            for index in range(start, len(raw)):
                char = raw[index]

                if escaped:
                    escaped = False
                    continue

                if char == "\\" and in_string:
                    escaped = True
                    continue

                if char == '"':
                    in_string = not in_string
                    continue

                if in_string:
                    continue

                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1

                    if depth == 0:
                        candidate = raw[start : index + 1]

                        try:
                            data = json.loads(candidate)
                            if isinstance(data, dict):
                                return data
                        except json.JSONDecodeError:
                            pass

                        break

            start = raw.find("{", start + 1)

        raise ValueError("Provider returned invalid research gap JSON.")

    @staticmethod
    def _parse_gap(value: Any) -> ResearchGap:
        if not isinstance(value, dict):
            raise ValueError("Invalid research gap object.")

        gap = str(value.get("gap", "")).strip()
        rationale = str(value.get("rationale", "")).strip()

        if not gap:
            raise ValueError("Research gap is missing.")

        if not rationale:
            raise ValueError("Research gap rationale is missing.")

        evidence = value.get("evidence", [])

        if not isinstance(evidence, list):
            raise ValueError("Research gap evidence must be a list.")

        evidence = [str(item).strip() for item in evidence if str(item).strip()]

        gap_type = str(value.get("type", GapType.INFERRED.value)).upper()

        if gap_type not in {
            GapType.EXPLICIT.value,
            GapType.INFERRED.value,
        }:
            raise ValueError(f"Invalid research gap type: {gap_type}")

        confidence = float(value.get("confidence", 0.0))

        document = str(value.get("document", "")).strip()
        chunk_id = str(value.get("chunk_id", "")).strip()

        page = value.get("page", "")

        return ResearchGap(
            gap=gap,
            type=GapType(gap_type),
            confidence=max(0.0, min(1.0, confidence)),
            rationale=rationale,
            evidence=evidence,
            document=document,
            page=page,
            chunk_id=chunk_id,
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
                    "document": str(source.get("document", "")).strip(),
                    "page": source.get("page", ""),
                    "chunk_id": str(source.get("chunk_id", "")).strip(),
                }
            )

        return sources

    def parse_response(
        self,
        *,
        query: str,
        response_text: str,
    ) -> ResearchGapReport:
        data = self._extract_json(response_text)

        existing_findings = data.get("existing_findings", [])
        limitations = data.get("reported_limitations", [])
        raw_gaps = data.get("gaps", [])

        if not isinstance(existing_findings, list):
            existing_findings = []

        if not isinstance(limitations, list):
            limitations = []

        if not isinstance(raw_gaps, list):
            raise ValueError("Research gap 'gaps' must be a list.")

        gaps = [self._parse_gap(item) for item in raw_gaps]

        return ResearchGapReport(
            query=str(data.get("query") or query),
            research_area=str(data.get("research_area", "General research")).strip(),
            existing_findings=[
                str(item).strip() for item in existing_findings if str(item).strip()
            ],
            reported_limitations=[
                str(item).strip() for item in limitations if str(item).strip()
            ],
            gaps=gaps,
            sources=self._parse_sources(data.get("sources", [])),
        )
