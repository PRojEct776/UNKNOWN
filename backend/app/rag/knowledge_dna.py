from __future__ import annotations

import json
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class KnowledgeSignalType(str, Enum):
    TOPIC = "TOPIC"
    CONCEPT = "CONCEPT"
    METHOD = "METHOD"
    FINDING = "FINDING"
    LIMITATION = "LIMITATION"
    THEME = "THEME"


class KnowledgeSignal(BaseModel):
    type: KnowledgeSignalType
    name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    document: str = ""
    page: int | str = ""
    chunk_id: str = ""


class KnowledgeRelationship(BaseModel):
    source: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)
    relationship: str = Field(..., min_length=1)
    evidence: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)


class KnowledgeDNAReport(BaseModel):
    query: str
    research_area: str
    core_topics: list[str] = Field(default_factory=list)
    key_concepts: list[str] = Field(default_factory=list)
    methods: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    themes: list[str] = Field(default_factory=list)
    signals: list[KnowledgeSignal] = Field(default_factory=list)
    relationships: list[KnowledgeRelationship] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)


class KnowledgeDNA:
    """
    Evidence-grounded Knowledge DNA extractor.

    Builds a structured research profile from retrieved evidence without
    introducing outside knowledge.
    """

    def build_dna_prompt(
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
You are the Knowledge DNA Engine of UNKNOWN.

Your task is to extract the knowledge structure of a research area
using ONLY the supplied evidence.

RESEARCH QUERY:
{query}

SUPPLIED EVIDENCE:
{evidence_json}

STRICT RULES:

1. Use ONLY the supplied evidence.
2. Do NOT use outside knowledge.
3. Do NOT invent concepts, methods, findings, limitations, themes,
   relationships, documents, pages, or citations.
4. Every extracted signal must be traceable to supplied evidence.
5. Distinguish topics, concepts, methods, findings, limitations,
   and themes carefully.
6. Do not treat a speculative statement as an established finding.
7. Confidence values must be between 0 and 1.
8. Preserve document, page, and chunk identifiers whenever available.
9. Relationships must be supported by supplied evidence.
10. If the evidence is insufficient for a category, return an empty list.
11. Return ONLY valid JSON.
12. Do not add Markdown fences.
13. Do not add commentary outside the JSON object.

EXPECTED JSON STRUCTURE:

{{
  "query": "{query}",
  "research_area": "short evidence-grounded description",
  "core_topics": [
    "topic supported by evidence"
  ],
  "key_concepts": [
    "concept supported by evidence"
  ],
  "methods": [
    "method explicitly present in evidence"
  ],
  "findings": [
    "finding supported by evidence"
  ],
  "limitations": [
    "limitation supported by evidence"
  ],
  "themes": [
    "recurring research theme supported by evidence"
  ],
  "signals": [
    {{
      "type": "TOPIC",
      "name": "signal name",
      "description": "evidence-grounded description",
      "evidence": [
        "supporting evidence"
      ],
      "confidence": 0.0,
      "document": "document name",
      "page": 0,
      "chunk_id": "chunk id"
    }}
  ],
  "relationships": [
    {{
      "source": "concept or entity",
      "target": "concept or entity",
      "relationship": "relationship supported by evidence",
      "evidence": "supporting evidence",
      "confidence": 0.0
    }}
  ],
  "sources": [
    {{
      "document": "document name",
      "page": 0,
      "chunk_id": "chunk id"
    }}
  ]
}}

IMPORTANT:

The Knowledge DNA is a representation of the supplied research evidence,
not a general knowledge graph.

If evidence does not support a category, return an empty list.

Do not infer relationships merely because two concepts appear in the
same document.

Do not manufacture missing metadata.
""".strip()

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        if not text or not text.strip():
            raise ValueError("Knowledge DNA engine returned an empty response.")

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
                raise ValueError(
                    "Knowledge DNA engine returned invalid JSON."
                ) from None

            try:
                value = json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError as error:
                raise ValueError(
                    "Knowledge DNA engine returned invalid JSON."
                ) from error

        if not isinstance(value, dict):
            raise ValueError(  # noqa: TRY004
                "Knowledge DNA response must be a JSON object."
            )

        return value

    @staticmethod
    def _parse_signal(value: Any) -> KnowledgeSignal:
        if not isinstance(value, dict):
            raise ValueError("Invalid Knowledge DNA signal.")  # noqa: TRY004

        return KnowledgeSignal(
            type=value.get("type"),  # type: ignore
            name=value.get("name", ""),
            description=value.get("description", ""),
            evidence=value.get("evidence", []),
            confidence=value.get("confidence", 0.0),
            document=value.get("document", ""),
            page=value.get("page", ""),
            chunk_id=value.get("chunk_id", ""),
        )

    @staticmethod
    def _parse_relationship(
        value: Any,
    ) -> KnowledgeRelationship:
        if not isinstance(value, dict):
            raise ValueError("Invalid Knowledge DNA relationship.")  # noqa: TRY004

        return KnowledgeRelationship(
            source=value.get("source", ""),
            target=value.get("target", ""),
            relationship=value.get("relationship", ""),
            evidence=value.get("evidence", ""),
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
        response_text: str,
    ) -> KnowledgeDNAReport:
        payload = self._extract_json(response_text)

        signals = [self._parse_signal(item) for item in payload.get("signals", [])]

        relationships = [
            self._parse_relationship(item) for item in payload.get("relationships", [])
        ]

        return KnowledgeDNAReport(
            query=query,
            research_area=payload.get(
                "research_area",
                query,
            ),
            core_topics=payload.get("core_topics", []),
            key_concepts=payload.get("key_concepts", []),
            methods=payload.get("methods", []),
            findings=payload.get("findings", []),
            limitations=payload.get("limitations", []),
            themes=payload.get("themes", []),
            signals=signals,
            relationships=relationships,
            sources=self._parse_sources(payload.get("sources", [])),
        )
