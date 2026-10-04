from __future__ import annotations

import json
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class NodeType(str, Enum):
    TOPIC = "TOPIC"
    CONCEPT = "CONCEPT"
    METHOD = "METHOD"
    FINDING = "FINDING"
    LIMITATION = "LIMITATION"
    DOCUMENT = "DOCUMENT"


class MindMapNode(BaseModel):
    id: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    type: NodeType
    description: str = ""
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    document: str = ""
    page: int | str = ""
    chunk_id: str = ""


class MindMapEdge(BaseModel):
    source: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)
    relationship: str = Field(..., min_length=1)
    evidence: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)


class KnowledgeMindMap(BaseModel):
    query: str
    research_area: str
    nodes: list[MindMapNode] = Field(default_factory=list)
    edges: list[MindMapEdge] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)


class KnowledgeMindMapEngine:
    """
    Evidence-grounded knowledge mind-map generator.

    Converts retrieved research evidence into nodes and relationships
    that can later be rendered as an interactive graph by a frontend.
    """

    def build_mind_map_prompt(
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
You are the Knowledge Mind Map Engine of UNKNOWN.

Your task is to construct an evidence-grounded knowledge graph from
the supplied research evidence.

RESEARCH QUERY:
{query}

SUPPLIED EVIDENCE:
{evidence_json}

STRICT RULES:

1. Use ONLY the supplied evidence.
2. Do NOT use outside knowledge.
3. Do NOT invent concepts, methods, findings, limitations,
   documents, pages, chunk IDs, or relationships.
4. Every node must be traceable to supplied evidence.
5. Every edge must be explicitly supported by supplied evidence.
6. Use one of these node types only:
   TOPIC, CONCEPT, METHOD, FINDING, LIMITATION, DOCUMENT.
7. Node IDs must be unique and stable.
8. Keep node labels concise.
9. Use relationships such as:
   "USES", "SUPPORTS", "RELATES_TO", "LIMITS",
   "EVALUATES", "REPORTS", "PART_OF"
   only when supported by evidence.
10. Do not create relationships merely because two nodes appear
    in the same document.
11. Confidence values must be between 0 and 1.
12. Preserve document, page, and chunk identifiers whenever available.
13. If evidence is insufficient, return an empty nodes/edges list.
14. Return ONLY valid JSON.
15. Do not add Markdown fences.
16. Do not add commentary outside the JSON object.

EXPECTED JSON STRUCTURE:

{{
  "query": "{query}",
  "research_area": "short evidence-grounded research area",
  "nodes": [
    {{
      "id": "unique_node_id",
      "label": "node label",
      "type": "CONCEPT",
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
  "edges": [
    {{
      "source": "source_node_id",
      "target": "target_node_id",
      "relationship": "relationship",
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

The mind map represents ONLY the supplied research evidence.

Do not manufacture missing metadata.

Do not create unsupported relationships.

If the evidence does not support a meaningful graph, return empty
nodes and edges instead of guessing.
""".strip()

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        if not text or not text.strip():
            raise ValueError("Knowledge mind map engine returned an empty response.")

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
                    "Knowledge mind map engine returned invalid JSON."
                ) from None

            try:
                value = json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError as error:
                raise ValueError(
                    "Knowledge mind map engine returned invalid JSON."
                ) from error

        if not isinstance(value, dict):
            raise ValueError(  # noqa: TRY004
                "Knowledge mind map response must be a JSON object."
            )

        return value

    @staticmethod
    def _parse_node(value: Any) -> MindMapNode:
        if not isinstance(value, dict):
            raise ValueError("Invalid mind map node.")  # noqa: TRY004

        return MindMapNode(
            id=value.get("id", ""),
            label=value.get("label", ""),
            type=value.get("type"),  # type: ignore
            description=value.get("description", ""),
            evidence=value.get("evidence", []),
            confidence=value.get("confidence", 0.0),
            document=value.get("document", ""),
            page=value.get("page", ""),
            chunk_id=value.get("chunk_id", ""),
        )

    @staticmethod
    def _parse_edge(value: Any) -> MindMapEdge:
        if not isinstance(value, dict):
            raise ValueError("Invalid mind map edge.")  # noqa: TRY004

        return MindMapEdge(
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
    ) -> KnowledgeMindMap:
        payload = self._extract_json(response_text)

        nodes = [self._parse_node(item) for item in payload.get("nodes", [])]

        edges = [self._parse_edge(item) for item in payload.get("edges", [])]

        node_ids = {node.id for node in nodes}

        # Reject edges that point to nodes which do not exist.
        for edge in edges:
            if edge.source not in node_ids:
                raise ValueError(
                    f"Mind map edge references unknown source node: " f"{edge.source}"
                )

            if edge.target not in node_ids:
                raise ValueError(
                    f"Mind map edge references unknown target node: " f"{edge.target}"
                )

        return KnowledgeMindMap(
            query=query,
            research_area=payload.get(
                "research_area",
                query,
            ),
            nodes=nodes,
            edges=edges,
            sources=self._parse_sources(payload.get("sources", [])),
        )
