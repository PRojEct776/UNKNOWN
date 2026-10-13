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


KnowledgeMindMapReport = KnowledgeMindMap


class KnowledgeMindMapEngine:
    """
    Evidence-grounded knowledge mind-map generator.

    Converts retrieved research evidence into nodes and relationships
    that can be rendered as an interactive graph by a frontend.
    """

    def build_mind_map_prompt(
        self,
        *,
        query: str,
        evidence: list[dict[str, Any]],
    ) -> str:
        """Build a compact prompt to reduce input-token consumption."""

        compact_evidence: list[dict[str, Any]] = []

        for item in evidence:
            if not isinstance(item, dict):
                continue

            # Preserve the available evidence text and source metadata.
            text = item.get(
                "text",
                item.get(
                    "content",
                    item.get("chunk_text", item.get("page_content", "")),
                ),
            )

            document = item.get(
                "document",
                item.get("document_name", item.get("filename", "")),
            )

            page = item.get("page", "")
            chunk_id = item.get("chunk_id", "")

            compact_evidence.append(
                {
                    "text": text,
                    "document": document,
                    "page": page,
                    "chunk_id": chunk_id,
                }
            )

        evidence_json = json.dumps(
            compact_evidence,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )

        query_json = json.dumps(query, ensure_ascii=False)

        return f"""
Create an evidence-grounded research mind map using ONLY the evidence below.

QUERY: {query_json}
EVIDENCE: {evidence_json}

RULES:
- Do not use outside knowledge or invent facts.
- Every node and edge must be supported by the evidence.
- Allowed node types: TOPIC, CONCEPT, METHOD, FINDING, LIMITATION, DOCUMENT.
- Use concise labels and descriptions.
- Node IDs must be unique.
- Every edge source and target must reference an existing node.
- Preserve document, page, and chunk_id when available.
- Confidence must be between 0 and 1.
- Return at most 10 nodes and 12 edges.
- Do not create relationships merely because nodes share a document.
- If evidence is insufficient, return empty nodes and edges.
- Return one valid JSON object only. No Markdown fences or commentary.

EXPECTED JSON:
{{
  "query": {query_json},
  "research_area": "short evidence-grounded description",
  "nodes": [
    {{
      "id": "node_1",
      "label": "concept",
      "type": "CONCEPT",
      "description": "evidence-grounded description",
      "evidence": ["supporting evidence"],
      "confidence": 0.9,
      "document": "document name",
      "page": 1,
      "chunk_id": "chunk_1"
    }}
  ],
  "edges": [
    {{
      "source": "node_1",
      "target": "node_2",
      "relationship": "SUPPORTS",
      "evidence": "supporting evidence",
      "confidence": 0.9
    }}
  ],
  "sources": [
    {{
      "document": "document name",
      "page": 1,
      "chunk_id": "chunk_1"
    }}
  ]
}}
""".strip()

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        """Extract one JSON object, including when surrounded by extra text."""

        if not text or not text.strip():
            raise ValueError("Knowledge mind map engine returned an empty response.")

        cleaned = text.strip()

        # Remove Markdown code fences if the provider includes them.
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()

            if lines and lines[0].strip().startswith("```"):
                lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            cleaned = "\n".join(lines).strip()

        # First, try parsing the entire response.
        try:
            value = json.loads(cleaned)
        except json.JSONDecodeError:
            # Then scan for the first complete JSON object.
            decoder = json.JSONDecoder()
            value = None

            for index, character in enumerate(cleaned):
                if character != "{":
                    continue

                try:
                    candidate, _ = decoder.raw_decode(cleaned[index:])
                except json.JSONDecodeError:
                    continue

                if isinstance(candidate, dict):
                    value = candidate
                    break

            if value is None:
                raise ValueError(
                    "Knowledge mind map engine returned invalid JSON."
                ) from None

        if not isinstance(value, dict):
            raise ValueError(  # noqa: TRY004
                "Knowledge mind map response must be a JSON object."
            )

        return value

    @staticmethod
    def _parse_node(value: Any) -> MindMapNode:
        if not isinstance(value, dict):
            raise ValueError("Invalid mind map node.")  # noqa: TRY004

        page = value.get("page")
        if page is None:
            page = ""

        chunk_id = value.get("chunk_id")
        if chunk_id is None:
            chunk_id = ""

        document = value.get("document")
        if document is None:
            document = ""

        return MindMapNode(
            id=value.get("id") or "",
            label=value.get("label") or "",
            type=value.get("type"),  # type: ignore
            description=value.get("description") or "",
            evidence=value.get("evidence") or [],
            confidence=value.get("confidence") or 0.0,
            document=document,
            page=page,
            chunk_id=chunk_id,
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
        """Validate the generated JSON and ensure all edge references exist."""

        payload = self._extract_json(response_text)

        raw_nodes = payload.get("nodes", [])
        raw_edges = payload.get("edges", [])

        if not isinstance(raw_nodes, list):
            raise ValueError("Mind map nodes must be a list.")  # noqa: TRY004

        if not isinstance(raw_edges, list):
            raise ValueError("Mind map edges must be a list.")  # noqa: TRY004

        nodes = [self._parse_node(item) for item in raw_nodes]
        edges = [self._parse_edge(item) for item in raw_edges]


        node_ids = [node.id for node in nodes]

        if len(node_ids) != len(set(node_ids)):
            raise ValueError("Mind map contains duplicate node IDs.")

        valid_node_ids = set(node_ids)

        for edge in edges:
            if edge.source not in valid_node_ids:
                raise ValueError(
                    f"Mind map edge references unknown source node: " f"{edge.source}"
                )

            if edge.target not in valid_node_ids:
                raise ValueError(
                    f"Mind map edge references unknown target node: " f"{edge.target}"
                )

        return KnowledgeMindMap(
            query=query,
            research_area=payload.get("research_area", query),
            nodes=nodes,
            edges=edges,
            sources=self._parse_sources(payload.get("sources", [])),
        )
