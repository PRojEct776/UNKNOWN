from __future__ import annotations

import json
import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ==============================================================================
# ENUMS & MODELS
# ==============================================================================

class KnowledgeSignalType(str, Enum):
    TOPIC = "TOPIC"
    CONCEPT = "CONCEPT"
    METHOD = "METHOD"
    METHODOLOGY = "METHODOLOGY"
    DATASET = "DATASET"
    METRIC = "METRIC"
    FINDING = "FINDING"
    RESULT = "RESULT"
    CONTRIBUTION = "CONTRIBUTION"
    ADVANTAGE = "ADVANTAGE"
    LIMITATION = "LIMITATION"
    FUTURE_DIRECTION = "FUTURE_DIRECTION"
    THEME = "THEME"


class KnowledgeSignal(BaseModel):
    type: KnowledgeSignalType
    name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    document: str = ""
    page: int | str = ""
    chunk_id: str = ""


class KnowledgeRelationship(BaseModel):
    source: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)
    relationship: str = Field(..., min_length=1)
    evidence: str = Field(..., min_length=1)
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    is_inferred: bool = False
    supporting_papers: list[str] = Field(default_factory=list)


class KnowledgeDNANode(BaseModel):
    id: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1)
    explanation: str = ""
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    document: str = ""
    supporting_papers: list[str] = Field(default_factory=list)
    page: int | str | None = None
    chunk_id: str | None = None
    is_inferred: bool = False
    quantitative_value: str | None = None
    citations: list[dict[str, Any]] = Field(default_factory=list)


class KnowledgeDNAConflict(BaseModel):
    topic: str = Field(..., min_length=1)
    paper_a: str = Field(..., min_length=1)
    finding_a: str = Field(..., min_length=1)
    paper_b: str = Field(..., min_length=1)
    finding_b: str = Field(..., min_length=1)
    explanation: str = ""
    evidence_chunks: list[str] = Field(default_factory=list)


class KnowledgeDNAReport(BaseModel):
    query: str
    research_area: str
    nodes: list[KnowledgeDNANode] = Field(default_factory=list)
    edges: list[KnowledgeRelationship] = Field(default_factory=list)
    
    # 10 Core Research Knowledge Profile Dimensions
    objectives: list[str] = Field(default_factory=list)
    core_concepts: list[str] = Field(default_factory=list)
    methodologies: list[str] = Field(default_factory=list)
    datasets: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    results: list[str] = Field(default_factory=list)
    contributions: list[str] = Field(default_factory=list)
    advantages: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    future_directions: list[str] = Field(default_factory=list)

    # Multi-Document Intelligence & Relationships
    conflicting_findings: list[KnowledgeDNAConflict] = Field(default_factory=list)
    cross_paper_connections: list[KnowledgeRelationship] = Field(default_factory=list)
    statistics: dict[str, Any] = Field(default_factory=dict)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    partial: bool = False
    notice: str | None = None

    # Backward compatibility with legacy schema fields & tests
    core_topics: list[str] = Field(default_factory=list)
    key_concepts: list[str] = Field(default_factory=list)
    methods: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    themes: list[str] = Field(default_factory=list)
    signals: list[KnowledgeSignal] = Field(default_factory=list)
    relationships: list[KnowledgeRelationship] = Field(default_factory=list)

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        # Ensure legacy aliases stay in sync
        if not self.key_concepts and self.core_concepts:
            self.key_concepts = list(self.core_concepts)
        elif not self.core_concepts and self.key_concepts:
            self.core_concepts = list(self.key_concepts)

        if not self.methods and self.methodologies:
            self.methods = list(self.methodologies)
        elif not self.methodologies and self.methods:
            self.methodologies = list(self.methods)

        if not self.findings and self.results:
            self.findings = list(self.results)
        elif not self.results and self.findings:
            self.results = list(self.findings)

        if not self.core_topics:
            self.core_topics = self.objectives[:3] if self.objectives else ([self.research_area] if self.research_area else [])

        if not self.relationships and self.edges:
            self.relationships = list(self.edges)
        elif not self.edges and self.relationships:
            self.edges = list(self.relationships)

        if not self.signals and self.nodes:
            self.signals = [
                KnowledgeSignal(
                    type=self._map_category_to_signal_type(n.category),
                    name=n.label,
                    description=n.explanation or n.label,
                    evidence=n.evidence,
                    confidence=n.confidence,
                    document=n.document,
                    page=n.page if n.page is not None else "",
                    chunk_id=n.chunk_id or "",
                )
                for n in self.nodes
            ]

    @staticmethod
    def _map_category_to_signal_type(category: str) -> KnowledgeSignalType:
        cat = category.upper()
        if "METHOD" in cat:
            return KnowledgeSignalType.METHOD
        if "RESULT" in cat or "FINDING" in cat:
            return KnowledgeSignalType.FINDING
        if "LIMIT" in cat:
            return KnowledgeSignalType.LIMITATION
        if "TOPIC" in cat or "OBJECTIVE" in cat:
            return KnowledgeSignalType.TOPIC
        if "THEME" in cat:
            return KnowledgeSignalType.THEME
        return KnowledgeSignalType.CONCEPT


# ==============================================================================
# MAIN KNOWLEDGE DNA ENGINE
# ==============================================================================

class KnowledgeDNA:
    """
    Evidence-grounded Knowledge DNA extractor.

    Extracts, organizes, connects, and preserves underlying research knowledge
    across 10 core dimensions:
    1. Research Objectives
    2. Core Concepts
    3. Methodologies
    4. Datasets
    5. Evaluation Metrics
    6. Experimental Results
    7. Key Contributions
    8. Advantages
    9. Limitations
    10. Future Directions
    """

    def build_dna_prompt(
        self,
        *,
        query: str,
        evidence: list[dict[str, Any]],
    ) -> str:
        evidence_json = json.dumps(evidence, ensure_ascii=False, indent=2)

        return f"""You are the UNKNOWN Knowledge DNA Engine.
Extract the structured research knowledge from the supplied evidence into a comprehensive Knowledge DNA Profile and Knowledge Graph.

RESEARCH QUERY:
{query}

SUPPLIED EVIDENCE:
{evidence_json}

INSTRUCTIONS & STRICT RULES:
1. Extract ONLY facts, methods, datasets, metrics, and findings supported by the supplied evidence. Do NOT invent or extrapolate outside evidence.
2. If evidence is insufficient for any category, return an empty array for that category.
3. Extract accurate quantitative experimental results (e.g., percentages, metrics, benchmarks) when present in the text.
4. Distinguish explicitly stated relationships from inferred relationships:
   - "is_inferred": false -> Stated directly in the text (e.g. "We evaluate [Method] using [Metric]").
   - "is_inferred": true -> Conceptually linked across findings or papers, but not verbatim stated.
5. In multi-document contexts:
   - Identify shared concepts across papers.
   - Detect conflicting findings (e.g., Paper A finds X improves performance while Paper B demonstrates X degrades accuracy). NOTE: missing evidence in one paper is NOT a conflict!
   - Link cross-paper connections (e.g., Paper A's methodology addresses Paper B's stated limitation).
6. Return ONLY a single, valid JSON object without markdown fences or extraneous text.

JSON OUTPUT SCHEMA:
{{
  "query": "{query}",
  "research_area": "Concise 2-5 word research topic name",
  "objectives": ["Problem 1 addressed by the research", "Problem 2"],
  "core_concepts": ["Concept 1", "Concept 2"],
  "methodologies": ["Method/Framework 1", "Algorithm 2"],
  "datasets": ["Dataset 1", "Data Source 2"],
  "metrics": ["Metric 1 (e.g. Accuracy, F1, Density)", "Metric 2"],
  "results": ["Result 1 (include numbers if available)", "Result 2"],
  "contributions": ["Key contribution 1", "Key contribution 2"],
  "advantages": ["Advantage 1", "Advantage 2"],
  "limitations": ["Weakness or constraint 1", "Constraint 2"],
  "future_directions": ["Opportunity 1", "Opportunity 2"],
  "nodes": [
    {{
      "id": "unique_node_id",
      "label": "Short Technical Name",
      "category": "OBJECTIVE|CONCEPT|METHODOLOGY|DATASET|METRIC|RESULT|CONTRIBUTION|ADVANTAGE|LIMITATION|FUTURE_DIRECTION",
      "explanation": "Clear evidence-grounded explanation",
      "evidence": ["Exact or near-exact quote from passage"],
      "confidence": 0.95,
      "document": "source_paper_name.pdf",
      "supporting_papers": ["source_paper_name.pdf"],
      "page": 1,
      "chunk_id": "chunk_001",
      "is_inferred": false,
      "quantitative_value": "e.g. 98.4% or null"
    }}
  ],
  "edges": [
    {{
      "source": "node_id_1",
      "target": "node_id_2",
      "relationship": "used in|evaluated using|produces|used for|addressed by|supports|motivates",
      "evidence": "Supporting passage from text",
      "confidence": 0.9,
      "is_inferred": false,
      "supporting_papers": ["source_paper_name.pdf"]
    }}
  ],
  "conflicting_findings": [
    {{
      "topic": "Conflicted topic or metric",
      "paper_a": "doc_a.pdf",
      "finding_a": "Claim in doc a",
      "paper_b": "doc_b.pdf",
      "finding_b": "Conflicting claim in doc b",
      "explanation": "Explanation of genuine contradiction",
      "evidence_chunks": ["chunk_a", "chunk_b"]
    }}
  ]
}}""".strip()

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
            if start == -1:
                raise ValueError("Knowledge DNA engine returned invalid JSON.") from None

            end = cleaned.rfind("}")
            value = None
            if end != -1 and end > start:
                sub = cleaned[start : end + 1]
                try:
                    value = json.loads(sub)
                except json.JSONDecodeError:
                    value = None
            else:
                sub = cleaned[start:]

            if value is None:
                # Attempt syntax-aware stack-based repair for truncated JSON
                for cut in range(len(sub), max(0, len(sub) - 800), -1):
                    test_str = sub[:cut].rstrip(" \t\r\n,")
                    stack = []
                    in_string = False
                    escape = False
                    for char in test_str:
                        if char == '"' and not escape:
                            in_string = not in_string
                        elif not in_string:
                            if char in "{[":
                                stack.append(char)
                            elif char == "}" and stack and stack[-1] == "{":
                                stack.pop()
                            elif char == "]" and stack and stack[-1] == "[":
                                stack.pop()
                        escape = (char == "\\" and not escape)

                    if not in_string and stack:
                        closing = "".join("}" if b == "{" else "]" for b in reversed(stack))
                        try:
                            candidate = json.loads(test_str + closing)
                            if isinstance(candidate, dict):
                                value = candidate
                                break
                        except Exception:
                            continue

                if not isinstance(value, dict):
                    raise ValueError("Knowledge DNA engine returned invalid JSON.")

        if not isinstance(value, dict):
            raise ValueError("Knowledge DNA response must be a JSON object.")

        return value

    def parse_response(
        self,
        *,
        query: str,
        response_text: str,
    ) -> KnowledgeDNAReport:
        payload = self._extract_json(response_text)

        research_area = payload.get("research_area") or query
        objectives = [str(x) for x in payload.get("objectives", []) if str(x).strip()]
        core_concepts = [str(x) for x in (payload.get("core_concepts") or payload.get("key_concepts", [])) if str(x).strip()]
        methodologies = [str(x) for x in (payload.get("methodologies") or payload.get("methods", [])) if str(x).strip()]
        datasets = [str(x) for x in payload.get("datasets", []) if str(x).strip()]
        metrics = [str(x) for x in payload.get("metrics", []) if str(x).strip()]
        results = [str(x) for x in (payload.get("results") or payload.get("findings", [])) if str(x).strip()]
        contributions = [str(x) for x in payload.get("contributions", []) if str(x).strip()]
        advantages = [str(x) for x in payload.get("advantages", []) if str(x).strip()]
        limitations = [str(x) for x in payload.get("limitations", []) if str(x).strip()]
        future_directions = [str(x) for x in payload.get("future_directions", []) if str(x).strip()]
        core_topics = [str(x) for x in payload.get("core_topics", []) if str(x).strip()]
        themes = [str(x) for x in payload.get("themes", []) if str(x).strip()]

        raw_nodes = payload.get("nodes", [])
        raw_signals = payload.get("signals", [])
        raw_edges = payload.get("edges") or payload.get("relationships", [])
        raw_conflicts = payload.get("conflicting_findings", [])
        raw_sources = payload.get("sources", [])

        # Parse nodes
        nodes: list[KnowledgeDNANode] = []
        node_id_map: dict[str, KnowledgeDNANode] = {}

        if raw_nodes:
            for item in raw_nodes:
                if not isinstance(item, dict):
                    continue
                nid = str(item.get("id") or f"node_{len(nodes) + 1}").strip()
                lbl = str(item.get("label") or nid).strip()
                cat = str(item.get("category") or "CONCEPT").strip().upper()
                doc = str(item.get("document") or "")
                supp_papers = [str(p) for p in item.get("supporting_papers", []) if str(p)]
                if doc and doc not in supp_papers:
                    supp_papers.append(doc)

                ev = item.get("evidence")
                ev_list = [str(e) for e in ev] if isinstance(ev, list) else ([str(ev)] if ev else [])
                citations = item.get("citations")
                cit_list = citations if isinstance(citations, list) else []
                if not cit_list and (doc or item.get("chunk_id")):
                    cit_list = [{
                        "document": doc,
                        "page": item.get("page"),
                        "chunk_id": item.get("chunk_id", ""),
                        "passage": ev_list[0] if ev_list else "",
                    }]

                conf = float(item.get("confidence", 0.9))
                conf = max(0.0, min(1.0, conf))

                node = KnowledgeDNANode(
                    id=nid,
                    label=lbl,
                    category=cat,
                    explanation=str(item.get("explanation") or lbl),
                    evidence=ev_list,
                    confidence=conf,
                    document=doc,
                    supporting_papers=supp_papers,
                    page=item.get("page"),
                    chunk_id=str(item.get("chunk_id") or ""),
                    is_inferred=bool(item.get("is_inferred", False)),
                    quantitative_value=item.get("quantitative_value"),
                    citations=cit_list,
                )
                nodes.append(node)
                node_id_map[nid] = node

        # If payload only had signals (legacy format), adapt them to nodes
        if not nodes and raw_signals:
            for idx, sig in enumerate(raw_signals):
                if not isinstance(sig, dict):
                    continue
                lbl = str(sig.get("name") or f"Signal {idx + 1}")
                nid = str(sig.get("id") or lbl or f"sig_{idx + 1}")
                cat = str(sig.get("type") or "CONCEPT").upper()
                doc = str(sig.get("document") or "")
                ev = sig.get("evidence")
                ev_list = [str(e) for e in ev] if isinstance(ev, list) else ([str(ev)] if ev else [])
                conf = float(sig.get("confidence", 0.9))
                node = KnowledgeDNANode(
                    id=nid,
                    label=lbl,
                    category=cat,
                    explanation=str(sig.get("description") or lbl),
                    evidence=ev_list,
                    confidence=conf,
                    document=doc,
                    supporting_papers=[doc] if doc else [],
                    page=sig.get("page"),
                    chunk_id=str(sig.get("chunk_id") or ""),
                    is_inferred=False,
                    citations=[{
                        "document": doc,
                        "page": sig.get("page"),
                        "chunk_id": str(sig.get("chunk_id") or ""),
                        "passage": ev_list[0] if ev_list else "",
                    }],
                )
                nodes.append(node)
                node_id_map[nid] = node
                node_id_map[lbl.lower()] = node

        # Multi-document concept deduplication and merging
        nodes, edges = self.merge_duplicate_concepts(nodes, raw_edges)

        # Parse conflicts
        conflicts: list[KnowledgeDNAConflict] = []
        for c in raw_conflicts:
            if not isinstance(c, dict):
                continue
            topic = str(c.get("topic") or "").strip()
            pa = str(c.get("paper_a") or "").strip()
            pb = str(c.get("paper_b") or "").strip()
            fa = str(c.get("finding_a") or "").strip()
            fb = str(c.get("finding_b") or "").strip()
            if topic and pa and pb and fa and fb:
                conflicts.append(KnowledgeDNAConflict(
                    topic=topic,
                    paper_a=pa,
                    finding_a=fa,
                    paper_b=pb,
                    finding_b=fb,
                    explanation=str(c.get("explanation") or f"Contradiction between {pa} and {pb} regarding {topic}."),
                    evidence_chunks=[str(ch) for ch in c.get("evidence_chunks", []) if str(ch)],
                ))

        # Identify cross-paper relationships
        cross_paper_connections: list[KnowledgeRelationship] = []
        for e in edges:
            src_node = next((n for n in nodes if n.id == e.source), None)
            tgt_node = next((n for n in nodes if n.id == e.target), None)
            if src_node and tgt_node:
                src_docs = set(src_node.supporting_papers)
                tgt_docs = set(tgt_node.supporting_papers)
                # If they do not share the exact same papers, it's a cross-paper link
                if src_docs and tgt_docs and not src_docs.intersection(tgt_docs):
                    e.is_inferred = True  # Cross-paper syntheses are inferred
                    cross_paper_connections.append(e)

        # Sources
        parsed_sources: list[dict[str, Any]] = []
        seen_src = set()
        for s in raw_sources:
            if isinstance(s, dict):
                cid = str(s.get("chunk_id") or "")
                doc = str(s.get("document") or "")
                key = (doc, cid)
                if key not in seen_src:
                    seen_src.add(key)
                    parsed_sources.append({
                        "document": doc,
                        "page": s.get("page"),
                        "chunk_id": cid,
                        "passage": s.get("passage") or s.get("text") or "",
                    })

        # Add node citations to sources if missing
        for n in nodes:
            for cit in n.citations:
                cid = cit.get("chunk_id")
                doc = cit.get("document")
                key = (doc, cid)
                if key not in seen_src:
                    seen_src.add(key)
                    parsed_sources.append({
                        "document": doc,
                        "page": cit.get("page"),
                        "chunk_id": cid,
                        "passage": cit.get("passage") or (n.evidence[0] if n.evidence else ""),
                    })

        # Calculate rich statistics
        all_docs = set()
        for n in nodes:
            all_docs.update(n.supporting_papers)
        for s in parsed_sources:
            if s.get("document"):
                all_docs.add(s["document"])

        unique_methods = {n.label.lower() for n in nodes if "METHOD" in n.category.upper()}
        unique_datasets = {n.label.lower() for n in nodes if "DATASET" in n.category.upper() or n.label in datasets}
        unique_findings = [n for n in nodes if "RESULT" in n.category.upper() or "FINDING" in n.category.upper()]

        stats = {
            "total_concepts": len(nodes),
            "unique_methodologies": len(unique_methods) or len(methodologies),
            "datasets": len(unique_datasets) or len(datasets),
            "findings": len(unique_findings) or len(results),
            "relationships": len(edges),
            "explicit_relationships": len([e for e in edges if not e.is_inferred]),
            "inferred_relationships": len([e for e in edges if e.is_inferred]),
            "supporting_documents": len(all_docs),
        }

        # Legacy signals & relationships for backwards compatibility
        legacy_signals = [
            KnowledgeSignal(
                type=KnowledgeDNAReport._map_category_to_signal_type(n.category),
                name=n.label,
                description=n.explanation or n.label,
                evidence=n.evidence,
                confidence=n.confidence,
                document=n.document,
                page=n.page if n.page is not None else "",
                chunk_id=n.chunk_id or "",
            )
            for n in nodes
        ]

        return KnowledgeDNAReport(
            query=query,
            research_area=research_area,
            nodes=nodes,
            edges=edges,
            objectives=objectives,
            core_concepts=core_concepts,
            methodologies=methodologies,
            datasets=datasets,
            metrics=metrics,
            results=results,
            contributions=contributions,
            advantages=advantages,
            limitations=limitations,
            future_directions=future_directions,
            conflicting_findings=conflicts,
            cross_paper_connections=cross_paper_connections,
            statistics=stats,
            sources=parsed_sources,
            partial=False,
            notice=None,
            core_topics=core_topics or (objectives[:3] if objectives else [research_area]),
            key_concepts=core_concepts,
            methods=methodologies,
            findings=results,
            themes=themes,
            signals=legacy_signals,
            relationships=edges,
        )

    # ==========================================================================
    # MULTI-DOCUMENT DEDUPLICATION & CONCEPT MERGING
    # ==========================================================================

    def merge_duplicate_concepts(
        self,
        nodes: list[KnowledgeDNANode],
        raw_edges: list[dict[str, Any]],
    ) -> tuple[list[KnowledgeDNANode], list[KnowledgeRelationship]]:
        """
        Detects duplicate or synonymous concepts across documents, merges them,
        combines supporting papers & evidence, and redirects relationship edges.
        """
        if not nodes:
            return [], []

        merged_nodes: list[KnowledgeDNANode] = []
        canonical_map: dict[str, str] = {}  # alias/id -> canonical_id
        label_map: dict[str, KnowledgeDNANode] = {}  # normalized label -> node

        def normalize(text: str) -> str:
            t = text.lower().strip()
            t = re.sub(r"[^\w\s-]", "", t)
            return " ".join(t.split())

        for node in nodes:
            norm_lbl = normalize(node.label)
            # Check for existing match: exact norm label or high overlap
            existing = label_map.get(norm_lbl)
            if not existing:
                # Check for prefix or substring matches for multi-word technical concepts
                for elbl, enode in label_map.items():
                    if len(norm_lbl) > 5 and len(elbl) > 5:
                        if norm_lbl == elbl or norm_lbl in elbl or elbl in norm_lbl:
                            existing = enode
                            break

            if existing:
                # Merge into existing node
                canonical_map[node.id] = existing.id
                canonical_map[node.label.lower()] = existing.id
                canonical_map[normalize(node.label)] = existing.id

                # Combine supporting papers
                all_papers = set(existing.supporting_papers)
                all_papers.update(node.supporting_papers)
                if node.document:
                    all_papers.add(node.document)
                existing.supporting_papers = sorted(list(all_papers))

                # Combine evidence
                for ev in node.evidence:
                    if ev and ev not in existing.evidence:
                        existing.evidence.append(ev)

                # Combine citations
                existing_cids = {c.get("chunk_id") for c in existing.citations if c.get("chunk_id")}
                for cit in node.citations:
                    if cit.get("chunk_id") and cit["chunk_id"] not in existing_cids:
                        existing.citations.append(cit)
                        existing_cids.add(cit["chunk_id"])

                # Boost confidence from multiple papers
                if len(existing.supporting_papers) > 1:
                    existing.confidence = min(0.99, max(existing.confidence, node.confidence) + 0.05)

                # Keep longer, more detailed explanation
                if len(node.explanation) > len(existing.explanation):
                    existing.explanation = node.explanation
                if not existing.quantitative_value and node.quantitative_value:
                    existing.quantitative_value = node.quantitative_value
            else:
                canonical_map[node.id] = node.id
                canonical_map[node.label.lower()] = node.id
                canonical_map[norm_lbl] = node.id
                label_map[norm_lbl] = node
                merged_nodes.append(node)

        # Parse & redirect edges
        edges: list[KnowledgeRelationship] = []
        seen_edges = set()

        for item in raw_edges:
            if not isinstance(item, dict):
                continue
            raw_src = str(item.get("source") or "").strip()
            raw_tgt = str(item.get("target") or "").strip()
            rel = str(item.get("relationship") or "relates to").strip()
            ev = str(item.get("evidence") or rel).strip()

            src = canonical_map.get(raw_src) or canonical_map.get(normalize(raw_src)) or canonical_map.get(raw_src.lower()) or raw_src
            tgt = canonical_map.get(raw_tgt) or canonical_map.get(normalize(raw_tgt)) or canonical_map.get(raw_tgt.lower()) or raw_tgt

            if not src or not tgt or src == tgt:
                continue

            edge_key = (src, tgt, normalize(rel))
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)

            conf = float(item.get("confidence", 0.85))
            conf = max(0.0, min(1.0, conf))
            is_inf = bool(item.get("is_inferred", False))
            supp = [str(p) for p in item.get("supporting_papers", []) if str(p)]

            edges.append(KnowledgeRelationship(
                source=src,
                target=tgt,
                relationship=rel,
                evidence=ev,
                confidence=conf,
                is_inferred=is_inf,
                supporting_papers=supp,
            ))

        return merged_nodes, edges

    # ==========================================================================
    # DETERMINISTIC NO-LLM FALLBACK EXTRACTOR
    # ==========================================================================

    def build_no_llm_dna(
        self,
        *,
        query: str,
        evidence: list[dict[str, Any]],
        document_names: list[str] | None = None,
    ) -> KnowledgeDNAReport:
        """
        Deterministic, rule-based Knowledge DNA extractor when LLM providers fail.
        Parses actual evidence passages into the 10 research dimensions, creates
        nodes with exact chunk citations, links explicit relationships, and
        returns a valid partial report.
        """
        if not evidence:
            return KnowledgeDNAReport(
                query=query,
                research_area="Insufficient evidence",
                partial=False,
                notice="Not found in available sources. Insufficient evidence to extract Knowledge DNA for the specified query and documents.",
            )

        clean_research_area = self._extract_clean_topic(query)
        nodes: list[KnowledgeDNANode] = []
        node_id_map: dict[str, str] = {}  # category_token -> node_id

        objectives: list[str] = []
        core_concepts: list[str] = []
        methodologies: list[str] = []
        datasets: list[str] = []
        metrics: list[str] = []
        results: list[str] = []
        contributions: list[str] = []
        advantages: list[str] = []
        limitations: list[str] = []
        future_directions: list[str] = []

        seen_labels = set()
        seen_sentences = set()

        # Regular expressions for dimensional extraction
        objective_patterns = [r"\b(?:aim(?:s)? to|objective is to|in order to solve|problem of|we address|we focus on)\s+([^.;]+)", r"\b(?:propose|introduce|design)\s+([^.;]+)"]
        method_patterns = [r"\b(?:algorithm|architecture|framework|approach|technique|model|method|pipeline)\b"]
        metric_patterns = [r"\b(?:accuracy|precision|recall|f1(?:-score)?|bleu|rouge|latency|throughput|perplexity|error rate|fidelity|loss|density)\b"]
        dataset_patterns = [r"\b(?:dataset|benchmark|corpus|eval-set|test collection)\b"]
        quantitative_patterns = [r"(\b\d+(?:\.\d+)?\s*(?:%|bits?|nm|ms|seconds?|gb|tb|pb|eb|x|fold)\b|\b\d+\.\d+\b)"]
        contribution_patterns = [r"\b(?:key contribution|our contribution|we demonstrate|first to show|we present)\s+([^.;]+)"]
        advantage_patterns = [r"\b(?:advantage|benefit|outperforms?|superior|efficient|scalable|robust|high-density|zero-power)\b"]
        limitation_patterns = [r"\b(?:limitation|bottleneck|however|constrained by|trade-off|drawback|expensive|high cost|slow)\b"]
        future_patterns = [r"\b(?:future work|future research|open challenge|remains to be|promising direction)\b"]

        for c_idx, chunk in enumerate(evidence):
            raw_text = chunk.get("text", "")
            doc = chunk.get("document", "Document")
            page = chunk.get("page", 1)
            cid = chunk.get("chunk_id", f"chunk_{c_idx + 1}")

            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", raw_text) if len(s.strip()) > 20]

            for s in sentences:
                clean_s = " ".join(s.split())
                if clean_s.lower() in seen_sentences:
                    continue
                seen_sentences.add(clean_s.lower())

                # 1. Objectives
                if any(re.search(p, clean_s, re.IGNORECASE) for p in objective_patterns):
                    if len(objectives) < 4:
                        objectives.append(clean_s)
                        nid = f"obj_{len(objectives)}"
                        short_lbl = self._extract_short_title(clean_s, "Research Objective")
                        if short_lbl.lower() not in seen_labels:
                            seen_labels.add(short_lbl.lower())
                            nodes.append(KnowledgeDNANode(
                                id=nid,
                                label=short_lbl,
                                category="OBJECTIVE",
                                explanation=clean_s,
                                evidence=[clean_s],
                                confidence=0.88,
                                document=doc,
                                supporting_papers=[doc],
                                page=page,
                                chunk_id=cid,
                                citations=[{"document": doc, "page": page, "chunk_id": cid, "passage": clean_s}],
                            ))
                            node_id_map["OBJECTIVE"] = nid

                # 2. Methodologies
                if any(re.search(p, clean_s, re.IGNORECASE) for p in method_patterns):
                    if len(methodologies) < 6:
                        methodologies.append(clean_s)
                        nid = f"method_{len(methodologies)}"
                        short_lbl = self._extract_short_title(clean_s, "Methodology")
                        if short_lbl.lower() not in seen_labels:
                            seen_labels.add(short_lbl.lower())
                            nodes.append(KnowledgeDNANode(
                                id=nid,
                                label=short_lbl,
                                category="METHODOLOGY",
                                explanation=clean_s,
                                evidence=[clean_s],
                                confidence=0.90,
                                document=doc,
                                supporting_papers=[doc],
                                page=page,
                                chunk_id=cid,
                                citations=[{"document": doc, "page": page, "chunk_id": cid, "passage": clean_s}],
                            ))
                            node_id_map["METHODOLOGY"] = nid

                # 3. Metrics
                m_match = next((re.search(p, clean_s, re.IGNORECASE) for p in metric_patterns if re.search(p, clean_s, re.IGNORECASE)), None)
                if m_match and len(metrics) < 5:
                    metric_word = m_match.group(0).capitalize()
                    metrics.append(clean_s)
                    nid = f"metric_{len(metrics)}"
                    if metric_word.lower() not in seen_labels:
                        seen_labels.add(metric_word.lower())
                        nodes.append(KnowledgeDNANode(
                            id=nid,
                            label=metric_word,
                            category="METRIC",
                            explanation=clean_s,
                            evidence=[clean_s],
                            confidence=0.92,
                            document=doc,
                            supporting_papers=[doc],
                            page=page,
                            chunk_id=cid,
                            citations=[{"document": doc, "page": page, "chunk_id": cid, "passage": clean_s}],
                        ))
                        node_id_map["METRIC"] = nid

                # 4. Datasets
                if any(re.search(p, clean_s, re.IGNORECASE) for p in dataset_patterns):
                    if len(datasets) < 4:
                        datasets.append(clean_s)
                        nid = f"dataset_{len(datasets)}"
                        short_lbl = self._extract_short_title(clean_s, "Experimental Dataset")
                        if short_lbl.lower() not in seen_labels:
                            seen_labels.add(short_lbl.lower())
                            nodes.append(KnowledgeDNANode(
                                id=nid,
                                label=short_lbl,
                                category="DATASET",
                                explanation=clean_s,
                                evidence=[clean_s],
                                confidence=0.89,
                                document=doc,
                                supporting_papers=[doc],
                                page=page,
                                chunk_id=cid,
                                citations=[{"document": doc, "page": page, "chunk_id": cid, "passage": clean_s}],
                            ))
                            node_id_map["DATASET"] = nid

                # 5. Experimental Results (Quantitative)
                q_match = next((re.search(p, clean_s, re.IGNORECASE) for p in quantitative_patterns if re.search(p, clean_s, re.IGNORECASE)), None)
                if q_match and len(results) < 6:
                    results.append(clean_s)
                    nid = f"res_{len(results)}"
                    short_lbl = self._extract_short_title(clean_s, "Experimental Finding")
                    if short_lbl.lower() not in seen_labels:
                        seen_labels.add(short_lbl.lower())
                        nodes.append(KnowledgeDNANode(
                            id=nid,
                            label=short_lbl,
                            category="RESULT",
                            explanation=clean_s,
                            evidence=[clean_s],
                            confidence=0.91,
                            document=doc,
                            supporting_papers=[doc],
                            page=page,
                            chunk_id=cid,
                            quantitative_value=q_match.group(1),
                            citations=[{"document": doc, "page": page, "chunk_id": cid, "passage": clean_s}],
                        ))
                        node_id_map["RESULT"] = nid

                # 6. Key Contributions
                if any(re.search(p, clean_s, re.IGNORECASE) for p in contribution_patterns):
                    if len(contributions) < 4:
                        contributions.append(clean_s)
                        nid = f"contrib_{len(contributions)}"
                        short_lbl = self._extract_short_title(clean_s, "Key Contribution")
                        if short_lbl.lower() not in seen_labels:
                            seen_labels.add(short_lbl.lower())
                            nodes.append(KnowledgeDNANode(
                                id=nid,
                                label=short_lbl,
                                category="CONTRIBUTION",
                                explanation=clean_s,
                                evidence=[clean_s],
                                confidence=0.88,
                                document=doc,
                                supporting_papers=[doc],
                                page=page,
                                chunk_id=cid,
                                citations=[{"document": doc, "page": page, "chunk_id": cid, "passage": clean_s}],
                            ))
                            node_id_map["CONTRIBUTION"] = nid

                # 7. Advantages
                if any(re.search(p, clean_s, re.IGNORECASE) for p in advantage_patterns):
                    if len(advantages) < 4:
                        advantages.append(clean_s)
                        nid = f"adv_{len(advantages)}"
                        short_lbl = self._extract_short_title(clean_s, "Research Advantage")
                        if short_lbl.lower() not in seen_labels:
                            seen_labels.add(short_lbl.lower())
                            nodes.append(KnowledgeDNANode(
                                id=nid,
                                label=short_lbl,
                                category="ADVANTAGE",
                                explanation=clean_s,
                                evidence=[clean_s],
                                confidence=0.87,
                                document=doc,
                                supporting_papers=[doc],
                                page=page,
                                chunk_id=cid,
                                citations=[{"document": doc, "page": page, "chunk_id": cid, "passage": clean_s}],
                            ))

                # 8. Limitations
                if any(re.search(p, clean_s, re.IGNORECASE) for p in limitation_patterns):
                    if len(limitations) < 4:
                        limitations.append(clean_s)
                        nid = f"lim_{len(limitations)}"
                        short_lbl = self._extract_short_title(clean_s, "Identified Limitation")
                        if short_lbl.lower() not in seen_labels:
                            seen_labels.add(short_lbl.lower())
                            nodes.append(KnowledgeDNANode(
                                id=nid,
                                label=short_lbl,
                                category="LIMITATION",
                                explanation=clean_s,
                                evidence=[clean_s],
                                confidence=0.89,
                                document=doc,
                                supporting_papers=[doc],
                                page=page,
                                chunk_id=cid,
                                citations=[{"document": doc, "page": page, "chunk_id": cid, "passage": clean_s}],
                            ))
                            node_id_map["LIMITATION"] = nid

                # 9. Future Directions
                if any(re.search(p, clean_s, re.IGNORECASE) for p in future_patterns):
                    if len(future_directions) < 4:
                        future_directions.append(clean_s)
                        nid = f"fut_{len(future_directions)}"
                        short_lbl = self._extract_short_title(clean_s, "Future Direction")
                        if short_lbl.lower() not in seen_labels:
                            seen_labels.add(short_lbl.lower())
                            nodes.append(KnowledgeDNANode(
                                id=nid,
                                label=short_lbl,
                                category="FUTURE_DIRECTION",
                                explanation=clean_s,
                                evidence=[clean_s],
                                confidence=0.86,
                                document=doc,
                                supporting_papers=[doc],
                                page=page,
                                chunk_id=cid,
                                citations=[{"document": doc, "page": page, "chunk_id": cid, "passage": clean_s}],
                            ))
                            node_id_map["FUTURE_DIRECTION"] = nid

        # Always ensure central Core Concept node exists
        root_node = KnowledgeDNANode(
            id="concept_central",
            label=clean_research_area,
            category="CONCEPT",
            explanation=f"Core research domain: {clean_research_area}",
            evidence=[clean_research_area],
            confidence=0.98,
            document=evidence[0].get("document", "Document") if evidence else "",
            supporting_papers=[c.get("document", "") for c in evidence if c.get("document")],
            page=evidence[0].get("page", 1) if evidence else None,
            chunk_id=evidence[0].get("chunk_id", "") if evidence else None,
            citations=[{"document": evidence[0].get("document", ""), "page": evidence[0].get("page", 1), "chunk_id": evidence[0].get("chunk_id", ""), "passage": clean_research_area}] if evidence else [],
        )
        nodes.insert(0, root_node)
        core_concepts.append(clean_research_area)

        # Build grounded relationships between nodes
        edges: list[KnowledgeRelationship] = []
        for n in nodes[1:]:
            rel = "explores"
            if n.category == "OBJECTIVE":
                rel = "addresses"
            elif n.category == "METHODOLOGY":
                rel = "implements"
            elif n.category == "DATASET":
                rel = "evaluates on"
            elif n.category == "METRIC":
                rel = "measured by"
            elif n.category == "RESULT":
                rel = "produces"
            elif n.category == "LIMITATION":
                rel = "constrained by"
            elif n.category == "FUTURE_DIRECTION":
                rel = "motivates"
            elif n.category == "CONTRIBUTION":
                rel = "contributes"
            elif n.category == "ADVANTAGE":
                rel = "benefits from"

            edges.append(KnowledgeRelationship(
                source=root_node.id,
                target=n.id,
                relationship=rel,
                evidence=n.explanation[:120],
                confidence=n.confidence,
                is_inferred=False,
                supporting_papers=n.supporting_papers,
            ))

        # Cross-category relationships
        if "METHODOLOGY" in node_id_map and "METRIC" in node_id_map:
            edges.append(KnowledgeRelationship(
                source=node_id_map["METHODOLOGY"],
                target=node_id_map["METRIC"],
                relationship="evaluated using",
                evidence="Methodology evaluated using metric criteria.",
                confidence=0.88,
                is_inferred=True,
            ))
        if "METHODOLOGY" in node_id_map and "RESULT" in node_id_map:
            edges.append(KnowledgeRelationship(
                source=node_id_map["METHODOLOGY"],
                target=node_id_map["RESULT"],
                relationship="produces",
                evidence="Methodology yields experimental results.",
                confidence=0.90,
                is_inferred=True,
            ))
        if "DATASET" in node_id_map and "METHODOLOGY" in node_id_map:
            edges.append(KnowledgeRelationship(
                source=node_id_map["DATASET"],
                target=node_id_map["METHODOLOGY"],
                relationship="used for",
                evidence="Dataset used to validate methodology.",
                confidence=0.89,
                is_inferred=True,
            ))
        if "LIMITATION" in node_id_map and "FUTURE_DIRECTION" in node_id_map:
            edges.append(KnowledgeRelationship(
                source=node_id_map["LIMITATION"],
                target=node_id_map["FUTURE_DIRECTION"],
                relationship="motivates",
                evidence="Identified limitation motivates future research direction.",
                confidence=0.87,
                is_inferred=True,
            ))

        # Sources
        sources: list[dict[str, Any]] = []
        seen_src = set()
        for chunk in evidence:
            cid = chunk.get("chunk_id", "")
            doc = chunk.get("document", "")
            key = (doc, cid)
            if key not in seen_src:
                seen_src.add(key)
                sources.append({
                    "document": doc,
                    "page": chunk.get("page", 1),
                    "chunk_id": cid,
                    "passage": chunk.get("text", "")[:200],
                })

        all_papers = {n.document for n in nodes if n.document}
        stats = {
            "total_concepts": len(nodes),
            "unique_methodologies": len(methodologies) or len({n.label for n in nodes if n.category == "METHODOLOGY"}),
            "datasets": len(datasets) or len({n.label for n in nodes if n.category == "DATASET"}),
            "findings": len(results) or len({n.label for n in nodes if n.category == "RESULT"}),
            "relationships": len(edges),
            "explicit_relationships": len([e for e in edges if not e.is_inferred]),
            "inferred_relationships": len([e for e in edges if e.is_inferred]),
            "supporting_documents": len(all_papers) or len(document_names or []),
        }

        legacy_signals = [
            KnowledgeSignal(
                type=KnowledgeDNAReport._map_category_to_signal_type(n.category),
                name=n.label,
                description=n.explanation or n.label,
                evidence=n.evidence,
                confidence=n.confidence,
                document=n.document,
                page=n.page if n.page is not None else "",
                chunk_id=n.chunk_id or "",
            )
            for n in nodes
        ]

        return KnowledgeDNAReport(
            query=query,
            research_area=clean_research_area,
            nodes=nodes,
            edges=edges,
            objectives=objectives,
            core_concepts=core_concepts,
            methodologies=methodologies,
            datasets=datasets,
            metrics=metrics,
            results=results,
            contributions=contributions,
            advantages=advantages,
            limitations=limitations,
            future_directions=future_directions,
            conflicting_findings=[],
            cross_paper_connections=[],
            statistics=stats,
            sources=sources,
            partial=True,
            notice="Limited Knowledge DNA — generated from available evidence because AI providers were unavailable.",
            core_topics=objectives[:3] if objectives else [clean_research_area],
            key_concepts=core_concepts,
            methods=methodologies,
            findings=results,
            themes=["Empirical Research", clean_research_area],
            signals=legacy_signals,
            relationships=edges,
        )

    # ==========================================================================
    # HELPER UTILITIES
    # ==========================================================================

    @staticmethod
    def _extract_clean_topic(query: str) -> str:
        if not query or not query.strip():
            return "Research Knowledge"

        cleaned = query.strip()
        prefix_patterns = [
            r"^(?:please\s+)?(?:generate|create|extract|build|show(?:\s+me)?|give(?:\s+me)?|make|produce)\s+(?:the\s+)?(?:knowledge\s+dna|dna|profile|knowledge\s+graph|graph)\s+(?:of|for|on|about)\s+",
            r"^(?:what\s+is|explain|describe|explore|analyze|investigate)\s+",
        ]
        for pat in prefix_patterns:
            cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE).strip()

        cleaned = cleaned.strip(" \t\n\r?.!\"'`:,;")
        lower = cleaned.lower()
        if "dna" in lower and ("storage" in lower or "data" in lower):
            return "DNA Data Storage"
        if "rag" in lower and ("eval" in lower or "evaluation" in lower):
            return "RAG Evaluation"
        if "crispr" in lower:
            return "CRISPR Genome Editing"

        words = cleaned.split()
        if len(words) > 5:
            return " ".join(words[:4]).title()
        return cleaned.title()

    @staticmethod
    def _extract_short_title(sentence: str, fallback: str) -> str:
        s = " ".join(sentence.split())
        # Try finding quoted terms or specific capitalized phrases
        caps = re.findall(r"\b[A-Z][a-zA-Z0-9_-]+(?:\s+[A-Z][a-zA-Z0-9_-]+)*\b", s)
        for c in caps:
            if len(c.split()) in (1, 2, 3, 4) and c.lower() not in ("we", "the", "in", "this", "our", "figure", "table", "section"):
                return c

        words = s.split()
        if len(words) <= 5:
            return s
        return " ".join(words[:4])
