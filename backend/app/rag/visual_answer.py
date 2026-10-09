"""
UNKNOWN X - Visual Answer Generator

Creates evidence-grounded visual specifications from retrieved research
evidence. The engine never invents numerical values or unsupported facts.
"""

import json
import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class VisualType(str, Enum):
    BAR_CHART = "BAR_CHART"
    TABLE = "TABLE"
    FLOWCHART = "FLOWCHART"
    CONCEPT_MAP = "CONCEPT_MAP"
    TIMELINE = "TIMELINE"
    NONE = "NONE"


class VisualDataPoint(BaseModel):
    label: str = Field(..., min_length=1)
    value: str = Field(..., min_length=1)
    unit: str = ""
    evidence: str = Field(..., min_length=1)
    document: str = ""
    page: int | str = ""
    chunk_id: str = ""


class VisualElement(BaseModel):
    id: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    description: str = ""
    evidence: str = Field(..., min_length=1)


class VisualEdge(BaseModel):
    source: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)
    relationship: str = Field(..., min_length=1)
    evidence: str = Field(..., min_length=1)


class VisualAnswer(BaseModel):
    query: str
    visual_type: VisualType
    title: str = Field(..., min_length=1)
    description: str = ""
    data: list[VisualDataPoint] = Field(default_factory=list)
    elements: list[VisualElement] = Field(default_factory=list)
    edges: list[VisualEdge] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)


class VisualAnswerEngine:
    """Parse and validate evidence-grounded visual specifications."""

    def build_prompt(self, query: str, evidence: str) -> str:
        """Build the structured visual-generation prompt."""

        return f"""
You are the Visual Answer Generator for UNKNOWN.

Create a visual representation of the user's query using ONLY the
supplied evidence.

User query:
{query}

Retrieved evidence:
{evidence}

Available visual types:
- BAR_CHART: Use only when the evidence contains comparable numeric values.
- TABLE: Use when multiple entities have comparable attributes or values.
- FLOWCHART: Use when the evidence explicitly describes a process or sequence.
- CONCEPT_MAP: Use when the evidence explicitly supports concepts and relationships.
- TIMELINE: Use only when the evidence explicitly contains chronological events.
- NONE: Use when the evidence does not support a meaningful visual.

Strict rules:
1. Return ONLY valid JSON.
2. Never invent values, entities, relationships, dates, or citations.
3. Every data point must be directly supported by supplied evidence.
4. Every element and edge must be traceable to supplied evidence.
5. Do not use outside knowledge.
6. For unsupported numeric visualization, use NONE or TABLE.
7. Use stable unique IDs for elements.
8. If visual_type is BAR_CHART, data must contain actual values from evidence.
9. If visual_type is FLOWCHART, CONCEPT_MAP, or TIMELINE, use elements and edges.
10. If visual_type is TABLE, use data for the table rows.
11. Include source metadata whenever supplied by the evidence.
12. Keep the visual focused on the user's query.


Required JSON structure:
Return exactly one JSON object with all these top-level fields:
{{
  "visual_type": "CONCEPT_MAP",
  "title": "Descriptive title",
  "description": "Short explanation grounded in evidence",
  "data": [],
  "elements": [
    {{
      "id": "element_1",
      "label": "Concept explicitly supported by evidence",
      "description": "Optional short explanation",
      "evidence": "Exact supporting text from retrieved evidence"
    }}
  ],
  "edges": [
    {{
      "source": "element_1",
      "target": "element_2",
      "relationship": "Relationship supported by evidence",
      "evidence": "Exact supporting text from retrieved evidence"
    }}
  ],
  "sources": [
    {{
      "document": "Exact document filename",
      "page": 1,
      "chunk_id": "Exact chunk ID"
    }}
  ]
}}

Field requirements:
- Every data item must contain "label", "value", and "evidence".
- Every element must contain "id", "label", and "evidence".
- Every edge must contain "source", "target", "relationship", and "evidence".
- Every evidence value must be supported by the retrieved evidence above.
- Every edge source and target must match existing element IDs.
- Copy source metadata exactly as supplied. Never invent missing metadata.
- Use empty arrays when a section has no supported items.
- For visual_type "NONE", return empty data, elements, and edges.
- Do not include Markdown fences, comments, or additional fields.
</escape>

""".strip()

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        """Extract the first valid JSON object."""

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
            raise ValueError("Visual answer generator returned invalid JSON.")

        try:
            value = json.loads(match.group(0))
        except json.JSONDecodeError as error:
            raise ValueError(
                "Visual answer generator returned invalid JSON."
            ) from error

        if not isinstance(value, dict):
            raise ValueError(  # noqa: TRY004
                "Visual answer generator must return a JSON object."
            )

        return value

    @staticmethod
    def _parse_data_point(value: Any) -> VisualDataPoint:
        """Validate a visual data point."""

        if not isinstance(value, dict):
            raise ValueError("Visual data point must be an object.")  # noqa: TRY004

        return VisualDataPoint.model_validate(value)

    @staticmethod
    def _parse_element(value: Any) -> VisualElement:
        """Validate a visual element."""

        if not isinstance(value, dict):
            raise ValueError("Visual element must be an object.")  # noqa: TRY004

        return VisualElement.model_validate(value)

    @staticmethod
    def _parse_edge(value: Any) -> VisualEdge:
        """Validate a visual edge."""

        if not isinstance(value, dict):
            raise ValueError("Visual edge must be an object.")  # noqa: TRY004

        return VisualEdge.model_validate(value)

    @staticmethod
    def _parse_sources(value: Any) -> list[dict[str, Any]]:
        """Validate source metadata."""

        if value is None:
            return []

        if not isinstance(value, list):
            raise ValueError("Visual sources must be a list.")  # noqa: TRY004

        return [item for item in value if isinstance(item, dict)]

    def parse_response(
        self,
        query: str,
        response_text: str,
    ) -> VisualAnswer:
        """Parse and validate an LLM visual specification."""

        data = self._extract_json(response_text)

        data["query"] = query

        data["data"] = [self._parse_data_point(item) for item in data.get("data", [])]

        data["elements"] = [
            self._parse_element(item) for item in data.get("elements", [])
        ]

        data["edges"] = [self._parse_edge(item) for item in data.get("edges", [])]

        data["sources"] = self._parse_sources(data.get("sources", []))

        visual_answer = VisualAnswer.model_validate(data)

        element_ids = {element.id for element in visual_answer.elements}

        for edge in visual_answer.edges:
            if edge.source not in element_ids or edge.target not in element_ids:
                raise ValueError("Visual edge references an unknown element.")

        return visual_answer
