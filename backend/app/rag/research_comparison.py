"""
UNKNOWN X - Research Comparison Engine

Compares research entities using only retrieved document evidence.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field


# ============================================================
# MODELS
# ============================================================


class ComparisonValue(BaseModel):
    """Evidence-backed value for one entity and aspect."""

    entity: str = Field(..., min_length=1)
    value: str = Field(..., min_length=1)
    evidence: str = Field(..., min_length=1)
    document: str = Field(..., min_length=1)
    page: int | str
    chunk_id: str = Field(..., min_length=1)


class ComparisonAspect(BaseModel):
    """Comparison across entities for one research aspect."""

    aspect: str = Field(..., min_length=1)
    values: list[ComparisonValue] = Field(default_factory=list)


class ContradictionItem(BaseModel):
    """Contradiction or disagreement between documents."""

    topic: str = Field(..., min_length=1)
    claim_a: str = Field(default="")
    document_a: str = Field(default="")
    claim_b: str = Field(default="")
    document_b: str = Field(default="")
    explanation: str = Field(default="")
    evidence_chunks: list[str] = Field(default_factory=list)


class UniqueContribution(BaseModel):
    """Unique contribution of a document."""

    document: str = Field(..., min_length=1)
    contribution: str = Field(..., min_length=1)
    evidence: str = Field(default="")
    chunk_id: str = Field(default="")


class StrengthLimitation(BaseModel):
    """Strengths and limitations of a document."""

    document: str = Field(..., min_length=1)
    strengths: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ResearchComparisonReport(BaseModel):
    """Complete research comparison report."""

    query: str
    entities: list[str] = Field(default_factory=list)
    comparison: list[ComparisonAspect] = Field(
        default_factory=list
    )
    summary: str = Field(..., min_length=1)
    similarities: list[str] = Field(default_factory=list)
    differences: list[str] = Field(default_factory=list)
    contradictions: list[ContradictionItem] = Field(default_factory=list)
    unique_contributions: list[UniqueContribution] = Field(default_factory=list)
    strengths_and_limitations: list[StrengthLimitation] = Field(default_factory=list)
    synthesis: str = Field(default="")
    sources: list[dict] = Field(default_factory=list)
    partial: bool = False
    notice: str | None = None


# ============================================================
# ENGINE
# ============================================================


class ResearchComparisonEngine:
    """
    Build prompts and parse structured research
    comparison responses.
    """

    # ========================================================
    # PROMPT
    # ========================================================

    def build_comparison_prompt(
        self,
        query: str,
        evidence: list[dict],
    ) -> str:
        """
        Build a strict evidence-grounded comparison prompt.
        """

        evidence_blocks: list[str] = []

        for index, item in enumerate(evidence, start=1):
            cid = item.get("chunk_id", f"chunk_{index}")
            doc = item.get("document", "Unknown")
            page = item.get("page", "N/A")
            raw_t = item.get("text", "").strip()
            clean_t = " ".join(raw_t.split())
            evidence_blocks.append(f"[{cid}] doc: {doc} | page: {page}\n{clean_t}")

        evidence_text = "\n\n".join(evidence_blocks)

        return f"""You are the Research Comparison Engine of UNKNOWN.
Compare research systems/findings using ONLY the supplied document evidence catalog.

USER QUERY:
{query}

DOCUMENT EVIDENCE CATALOG:
{evidence_text}

INSTRUCTIONS:
1. Ground every claim strictly in the cited evidence catalog. Do not extrapolate or fabricate.
2. Provide:
   - 2-3 similarities (shared objectives, methods, or findings).
   - 2-3 differences (divergent approaches, results, or tradeoffs).
   - 2-3 key comparison aspects with values for each document (1-sentence excerpt quote citing document, page, chunk_id).
   - A brief 1-2 sentence executive summary and short final synthesis conclusion.
3. If an aspect or value is absent in a document, set value="NOT_REPORTED" and evidence="Not reported in available sources.".
4. If contradictions or unique contributions are not explicitly found in evidence, return empty arrays [].
5. Return ONLY a single valid JSON object adhering to this schema with NO markdown fences:

{{
  "entities": ["Document A", "Document B"],
  "summary": "Brief 1-2 sentence executive summary.",
  "similarities": ["Shared objective or methodology."],
  "differences": ["Key difference in approach or metric."],
  "comparison": [
    {{
      "aspect": "Core Methodology & Architecture",
      "values": [
        {{
          "entity": "Document A",
          "value": "Value for Document A",
          "evidence": "Brief excerpt quote.",
          "document": "document_a.pdf",
          "page": 1,
          "chunk_id": "chunk_1"
        }}
      ]
    }}
  ],
  "contradictions": [],
  "unique_contributions": [],
  "strengths_and_limitations": [],
  "synthesis": "Short 1-2 sentence synthesis conclusion.",
  "sources": [
    {{
      "document": "document_a.pdf",
      "page": 1,
      "chunk_id": "chunk_1"
    }}
  ]
}}""".strip()

    # ========================================================
    # NO-LLM DETERMINISTIC FALLBACK
    # ========================================================

    def build_no_llm_comparison(
        self,
        query: str,
        evidence: list[dict],
        document_names: list[str] | None = None,
    ) -> ResearchComparisonReport:
        """
        Build a deterministic, evidence-grounded comparison directly
        from retrieved document chunks when LLM providers are unavailable.
        Never fabricates findings, similarities, or contradictions.
        """
        if document_names:
            entities = list(document_names)
        else:
            seen_docs: list[str] = []
            for item in evidence:
                d = item.get("document", "Unknown")
                if d and d not in seen_docs:
                    seen_docs.append(d)
            entities = seen_docs or ["Document A", "Document B"]

        # Group evidence chunks by entity
        doc_chunks: dict[str, list[dict]] = {e: [] for e in entities}
        for item in evidence:
            doc = item.get("document", "")
            matched = False
            for e in entities:
                if doc == e or (doc and e and (doc in e or e in doc)):
                    doc_chunks[e].append(item)
                    matched = True
                    break
            if not matched and entities:
                doc_chunks[entities[0]].append(item)

        # Standard technical dimensions to search in retrieved evidence
        dimension_defs = [
            (
                "Encoding & Formatting",
                ["encod", "codec", "mapping", "algorithm", "format", "scheme", "compress", "representation"],
            ),
            (
                "Synthesis & Molecular Assembly",
                ["synthes", "chemical", "oligo", "assembly", "fabricat", "produce", "reaction", "photolithograph"],
            ),
            (
                "Data Storage & Density",
                ["stor", "density", "capacity", "retention", "durability", "bytes", "nucleotide", "physical", "volume"],
            ),
            (
                "Sequencing & Readout",
                ["sequenc", "read", "illumina", "nanopore", "sanger", "base call", "accuracy", "readout"],
            ),
            (
                "Retrieval & Random Access",
                ["retriev", "search", "query", "index", "random access", "primer", "pcr", "address", "access"],
            ),
            (
                "Reported Advantages",
                ["advantage", "benefit", "outperform", "superior", "high throughput", "robust", "low cost", "efficient", "gain"],
            ),
            (
                "Reported Limitations",
                ["limitation", "drawback", "bottleneck", "challenge", "error rate", "expensive", "slow", "trade-off", "decay"],
            ),
        ]

        aspects: list[ComparisonAspect] = []
        for dim_title, keywords in dimension_defs:
            values: list[ComparisonValue] = []
            has_evidence_any_doc = False

            for doc in entities:
                chunks = doc_chunks.get(doc, [])
                best_sent: str | None = None
                best_chunk: dict | None = None

                for c in chunks:
                    text = c.get("text", "")
                    sentences = re.split(r"(?<=[.!?])\s+", text)
                    for sent in sentences:
                        s = sent.strip()
                        if len(s) >= 25 and any(kw in s.lower() for kw in keywords):
                            best_sent = s
                            best_chunk = c
                            break
                    if best_sent:
                        break

                if best_sent and best_chunk:
                    has_evidence_any_doc = True
                    clean_val = " ".join(best_sent.split())
                    if len(clean_val) > 220:
                        clean_val = clean_val[:217] + "..."
                    values.append(
                        ComparisonValue(
                            entity=doc,
                            value=clean_val,
                            evidence=clean_val,
                            document=doc,
                            page=best_chunk.get("page", 1),
                            chunk_id=best_chunk.get("chunk_id", f"{doc}_chunk"),
                        )
                    )
                else:
                    first_cid = chunks[0].get("chunk_id", f"{doc}_chunk") if chunks else f"{doc}_chunk"
                    first_page = chunks[0].get("page", "N/A") if chunks else "N/A"
                    values.append(
                        ComparisonValue(
                            entity=doc,
                            value="Insufficient evidence in retrieved sources.",
                            evidence="Insufficient evidence in retrieved sources.",
                            document=doc,
                            page=first_page,
                            chunk_id=first_cid,
                        )
                    )

            if has_evidence_any_doc:
                aspects.append(ComparisonAspect(aspect=dim_title, values=values))

        # Fallback if no specific keyword matched: create general overview aspects
        if not aspects:
            for fallback_title in ["Document Overview & Methodology", "Experimental Findings"]:
                values = []
                for doc in entities:
                    chunks = doc_chunks.get(doc, [])
                    if chunks:
                        top_c = chunks[0]
                        text = top_c.get("text", "").strip()
                        clean_val = " ".join(text.split()[:30])
                        values.append(
                            ComparisonValue(
                                entity=doc,
                                value=clean_val or "Evidence available in retrieved sources.",
                                evidence=clean_val or "Evidence available in retrieved sources.",
                                document=doc,
                                page=top_c.get("page", 1),
                                chunk_id=top_c.get("chunk_id", f"{doc}_chunk"),
                            )
                        )
                    else:
                        values.append(
                            ComparisonValue(
                                entity=doc,
                                value="Insufficient evidence in retrieved sources.",
                                evidence="Insufficient evidence in retrieved sources.",
                                document=doc,
                                page="N/A",
                                chunk_id=f"{doc}_chunk",
                            )
                        )
                aspects.append(ComparisonAspect(aspect=fallback_title, values=values))

        # Evidence-grounded similarities
        similarities: list[str] = []
        concept_checks = [
            ("DNA data storage", ["dna", "storage", "molecular"]),
            ("error-correction coding", ["error-correct", "code", "redundancy"]),
            ("oligonucleotide synthesis", ["synthesis", "oligo"]),
            ("high-throughput sequencing", ["sequencing", "readout"]),
            ("random-access retrieval", ["random access", "retrieval", "primer"]),
        ]
        for concept_name, words in concept_checks:
            shared = True
            for doc in entities:
                chunks = doc_chunks.get(doc, [])
                if not any(any(w in c.get("text", "").lower() for w in words) for c in chunks):
                    shared = False
                    break
            if shared:
                similarities.append(f"All analyzed documents ({', '.join(entities)}) report evidence addressing {concept_name}.")
                if len(similarities) >= 3:
                    break

        if not similarities:
            similarities = ["No explicit shared methodologies supported by available evidence."]

        # Evidence-grounded differences
        differences: list[str] = []
        for asp in aspects:
            valid_vals = [v for v in asp.values if v.value != "Insufficient evidence in retrieved sources."]
            if len(valid_vals) >= 2:
                distinct_vals = {v.value for v in valid_vals}
                if len(distinct_vals) > 1:
                    differences.append(
                        f"Divergent reported findings on '{asp.aspect}': {valid_vals[0].entity} emphasizes '{valid_vals[0].value[:70]}...' whereas {valid_vals[1].entity} notes '{valid_vals[1].value[:70]}...'."
                    )
                    if len(differences) >= 3:
                        break

        if not differences:
            differences = ["No verified contradictory or divergent methodologies identified in available evidence."]

        # Contradictions: strictly empty without verified conflicting proof
        contradictions: list[ContradictionItem] = []

        # Unique contributions per document
        unique_contributions: list[UniqueContribution] = []
        for doc in entities:
            chunks = doc_chunks.get(doc, [])
            if chunks:
                top_c = chunks[0]
                text = top_c.get("text", "").strip()
                sentences = re.split(r"(?<=[.!?])\s+", text)
                best_s = next((s.strip() for s in sentences if len(s.strip()) > 30), text[:120])
                clean_s = " ".join(best_s.split())
                unique_contributions.append(
                    UniqueContribution(
                        document=doc,
                        contribution=f"Reported finding: {clean_s[:160]}",
                        evidence=clean_s[:160],
                        chunk_id=top_c.get("chunk_id", f"{doc}_chunk"),
                    )
                )

        # Strengths & limitations per document
        strengths_and_limitations: list[StrengthLimitation] = []
        for doc in entities:
            chunks = doc_chunks.get(doc, [])
            s_list: list[str] = []
            l_list: list[str] = []
            for c in chunks:
                text = c.get("text", "")
                sentences = re.split(r"(?<=[.!?])\s+", text)
                for sent in sentences:
                    s = sent.strip()
                    if any(kw in s.lower() for kw in ["advantage", "benefit", "outperform", "superior", "efficient"]) and len(s) > 20:
                        clean_s = " ".join(s.split())[:140]
                        if len(s_list) < 2 and clean_s not in s_list:
                            s_list.append(clean_s)
                    if any(kw in s.lower() for kw in ["limitation", "drawback", "bottleneck", "challenge", "error rate"]) and len(s) > 20:
                        clean_l = " ".join(s.split())[:140]
                        if len(l_list) < 2 and clean_l not in l_list:
                            l_list.append(clean_l)
            if not s_list:
                s_list = ["Insufficient evidence in retrieved sources."]
            if not l_list:
                l_list = ["Insufficient evidence in retrieved sources."]
            strengths_and_limitations.append(
                StrengthLimitation(
                    document=doc,
                    strengths=s_list,
                    limitations=l_list,
                )
            )

        # Sources preservation
        sources: list[dict] = []
        seen_src = set()
        for item in evidence:
            d = item.get("document", "Unknown")
            p = item.get("page", 1)
            cid = item.get("chunk_id", "")
            if cid and cid not in seen_src:
                seen_src.add(cid)
                sources.append({"document": d, "page": p, "chunk_id": cid})

        return ResearchComparisonReport(
            query=query,
            entities=entities,
            comparison=aspects,
            summary="Limited comparison — generated from available evidence because AI providers were unavailable.",
            similarities=similarities,
            differences=differences,
            contradictions=contradictions,
            unique_contributions=unique_contributions,
            strengths_and_limitations=strengths_and_limitations,
            synthesis="This comparison was compiled directly from retrieved evidence chunks without LLM synthesis. Unsupported dimensions are explicitly marked as Insufficient evidence.",
            sources=sources,
            partial=True,
            notice="Limited comparison — generated from available evidence because AI providers were unavailable.",
        )

    # ========================================================
    # BALANCED JSON EXTRACTION
    # ========================================================

    @staticmethod
    def _extract_balanced_json(
        text: str,
    ) -> str:
        """
        Extract the first complete JSON object.

        Handles:
        - nested objects
        - arrays
        - braces inside strings
        - escaped quotes
        """

        start = text.find("{")

        if start == -1:
            raise ValueError(
                "Provider returned no JSON object "
                "for research comparison."
            )

        depth = 0
        in_string = False
        escaped = False

        for index in range(
            start,
            len(text),
        ):
            char = text[index]

            if in_string:

                if escaped:
                    escaped = False

                elif char == "\\":
                    escaped = True

                elif char == '"':
                    in_string = False

                continue

            if char == '"':
                in_string = True
                continue

            if char == "{":
                depth += 1

            elif char == "}":
                depth -= 1

                if depth == 0:
                    return text[
                        start : index + 1
                    ]

        raise ValueError(
            "Provider returned incomplete "
            "research comparison JSON."
        )

    # ========================================================
    # JSON EXTRACTION
    # ========================================================

    @classmethod
    def _extract_json(
        cls,
        text: str,
    ) -> dict:
        """
        Extract JSON from an LLM response.

        Supports:
        - raw JSON
        - fenced JSON
        - JSON surrounded by text
        - nested JSON
        """

        if not isinstance(
            text,
            str,
        ):
            raise ValueError(
                "Provider returned a non-text "
                "research comparison response."
            )

        cleaned = text.strip()

        if not cleaned:
            raise ValueError(
                "Provider returned an empty "
                "research comparison response."
            )

        # ----------------------------------------------------
        # 1. Direct JSON
        # ----------------------------------------------------

        try:
            parsed = json.loads(cleaned)

            if isinstance(
                parsed,
                dict,
            ):
                return parsed

        except json.JSONDecodeError:
            pass

        # ----------------------------------------------------
        # 2. Markdown fenced JSON
        # ----------------------------------------------------

        fenced_match = re.search(
            r"```(?:json)?\s*(.*?)\s*```",
            cleaned,
            flags=re.IGNORECASE
            | re.DOTALL,
        )

        if fenced_match:

            fenced_content = (
                fenced_match
                .group(1)
                .strip()
            )

            try:
                parsed = json.loads(
                    fenced_content
                )

                if isinstance(
                    parsed,
                    dict,
                ):
                    return parsed

            except json.JSONDecodeError:
                pass

            try:
                candidate = (
                    cls._extract_balanced_json(
                        fenced_content
                    )
                )

                parsed = json.loads(
                    candidate
                )

                if isinstance(
                    parsed,
                    dict,
                ):
                    return parsed

            except (
                ValueError,
                json.JSONDecodeError,
            ):
                pass

        # ----------------------------------------------------
        # 3. Embedded JSON
        # ----------------------------------------------------

        try:
            candidate = (
                cls._extract_balanced_json(
                    cleaned
                )
            )

            parsed = json.loads(
                candidate
            )

            if isinstance(
                parsed,
                dict,
            ):
                return parsed

        except (
            ValueError,
            json.JSONDecodeError,
        ):
            pass

        raise ValueError(
            "Provider returned invalid "
            "research comparison JSON."
        )

    # ========================================================
    # VALUE PARSER
    # ========================================================

    @staticmethod
    def _parse_value(
        data: dict,
    ) -> ComparisonValue:
        """
        Parse and validate one comparison value.
        """

        if not isinstance(
            data,
            dict,
        ):
            raise ValueError(
                "Comparison value must be a JSON object."
            )

        entity = str(
            data.get(
                "entity",
                "",
            )
        ).strip()

        value = str(
            data.get(
                "value",
                "",
            )
        ).strip()

        evidence = str(
            data.get(
                "evidence",
                "",
            )
        ).strip()

        document = str(
            data.get(
                "document",
                "",
            )
        ).strip()

        page = data.get(
            "page",
            "",
        )

        chunk_id = str(
            data.get(
                "chunk_id",
                "",
            )
        ).strip()

        if not entity:
            raise ValueError(
                "Comparison value is missing entity."
            )

        if not value:
            raise ValueError(
                "Comparison value is missing "
                f"value for entity: {entity}"
            )

        if not evidence:
            evidence = f"Evidence traceable to chunk {chunk_id}." if chunk_id else "Evidence derived from document context."

        if not document:
            raise ValueError(
                "Comparison value contains "
                f"no document: {entity}"
            )

        if not chunk_id:
            raise ValueError(
                "Comparison value contains "
                f"no chunk_id: {entity}"
            )

        return ComparisonValue(
            entity=entity,
            value=value,
            evidence=evidence,
            document=document,
            page=page,
            chunk_id=chunk_id,
        )

    # ========================================================
    # ASPECT PARSER
    # ========================================================

    @staticmethod
    def _parse_aspect(
        data: dict,
    ) -> ComparisonAspect:
        """
        Parse and validate one comparison aspect.
        """

        if not isinstance(
            data,
            dict,
        ):
            raise ValueError(
                "Comparison aspect must be a JSON object."
            )

        aspect = str(
            data.get(
                "aspect",
                "",
            )
        ).strip()

        if not aspect:
            raise ValueError(
                "Comparison aspect is missing aspect name."
            )

        raw_values = data.get(
            "values",
            [],
        )

        if not isinstance(
            raw_values,
            list,
        ):
            raise ValueError(
                f"Comparison aspect '{aspect}' "
                "values must be a list."
            )

        values: list[ComparisonValue] = []

        for value in raw_values:

            if not isinstance(
                value,
                dict,
            ):
                continue

            values.append(
                ResearchComparisonEngine
                ._parse_value(value)
            )

        return ComparisonAspect(
            aspect=aspect,
            values=values,
        )

    # ========================================================
    # SOURCE PARSER
    # ========================================================

    @staticmethod
    def _parse_sources(
        raw_sources: Any,
    ) -> list[dict]:
        """
        Validate source metadata.
        """

        if raw_sources is None:
            return []

        if not isinstance(
            raw_sources,
            list,
        ):
            raise ValueError(
                "Comparison response "
                "'sources' must be a list."
            )

        sources: list[dict] = []

        for source in raw_sources:

            if not isinstance(
                source,
                dict,
            ):
                continue

            sources.append(source)

        return sources

    # ========================================================
    # RESPONSE PARSER
    # ========================================================

    def parse_response(
        self,
        query: str,
        response_text: str,
    ) -> ResearchComparisonReport:
        """
        Parse and validate the LLM comparison response.
        """

        data = self._extract_json(
            response_text
        )

        raw_entities = data.get(
            "entities",
            [],
        )

        raw_comparison = data.get(
            "comparison",
            [],
        )

        summary = str(
            data.get(
                "summary",
                "",
            )
        ).strip()

        # ----------------------------------------------------
        # Validate top-level fields
        # ----------------------------------------------------

        if not isinstance(
            raw_entities,
            list,
        ):
            raise ValueError(
                "Comparison response "
                "'entities' must be a list."
            )

        if not isinstance(
            raw_comparison,
            list,
        ):
            raise ValueError(
                "Comparison response "
                "'comparison' must be a list."
            )

        if not summary:
            raise ValueError(
                "Comparison response is "
                "missing summary."
            )

        # ----------------------------------------------------
        # Entities
        # ----------------------------------------------------

        entities: list[str] = []

        for entity in raw_entities:

            entity_text = str(
                entity
            ).strip()

            if (
                entity_text
                and entity_text not in entities
            ):
                entities.append(
                    entity_text
                )

        # ----------------------------------------------------
        # Comparison aspects
        # ----------------------------------------------------

        comparison: list[
            ComparisonAspect
        ] = []

        for item in raw_comparison:

            if not isinstance(
                item,
                dict,
            ):
                continue

            comparison.append(
                self._parse_aspect(item)
            )

        # ----------------------------------------------------
        # Sources
        # ----------------------------------------------------

        sources = self._parse_sources(
            data.get(
                "sources",
                [],
            )
        )

        # ----------------------------------------------------
        # Similarities & Differences
        # ----------------------------------------------------

        raw_similarities = data.get("similarities", [])
        similarities: list[str] = []
        if isinstance(raw_similarities, list):
            for item in raw_similarities:
                text = str(item).strip()
                if text and text not in similarities:
                    similarities.append(text)

        raw_differences = data.get("differences", [])
        differences: list[str] = []
        if isinstance(raw_differences, list):
            for item in raw_differences:
                text = str(item).strip()
                if text and text not in differences:
                    differences.append(text)

        # ----------------------------------------------------
        # Contradictions & Disagreements
        # ----------------------------------------------------

        raw_contradictions = data.get("contradictions", [])
        contradictions: list[ContradictionItem] = []
        if isinstance(raw_contradictions, list):
            for item in raw_contradictions:
                if isinstance(item, dict):
                    topic = str(item.get("topic", "")).strip() or "Disagreement"
                    claim_a = str(item.get("claim_a", "")).strip()
                    doc_a = str(item.get("document_a", "")).strip()
                    claim_b = str(item.get("claim_b", "")).strip()
                    doc_b = str(item.get("document_b", "")).strip()
                    explanation = str(item.get("explanation", "")).strip()
                    raw_chunks = item.get("evidence_chunks", [])
                    ev_chunks = [str(c).strip() for c in raw_chunks if str(c).strip()] if isinstance(raw_chunks, list) else []
                    contradictions.append(
                        ContradictionItem(
                            topic=topic,
                            claim_a=claim_a,
                            document_a=doc_a,
                            claim_b=claim_b,
                            document_b=doc_b,
                            explanation=explanation,
                            evidence_chunks=ev_chunks,
                        )
                    )
                elif isinstance(item, str) and item.strip():
                    contradictions.append(
                        ContradictionItem(
                            topic="Disagreement",
                            explanation=item.strip(),
                        )
                    )

        # ----------------------------------------------------
        # Unique Contributions
        # ----------------------------------------------------

        raw_contributions = data.get("unique_contributions", [])
        unique_contributions: list[UniqueContribution] = []
        if isinstance(raw_contributions, list):
            for item in raw_contributions:
                if isinstance(item, dict):
                    doc = str(item.get("document", "")).strip() or (entities[0] if entities else "Document")
                    contribution = str(item.get("contribution", "")).strip()
                    ev = str(item.get("evidence", "")).strip()
                    chunk_id = str(item.get("chunk_id", "")).strip()
                    if contribution:
                        unique_contributions.append(
                            UniqueContribution(
                                document=doc,
                                contribution=contribution,
                                evidence=ev,
                                chunk_id=chunk_id,
                            )
                        )
                elif isinstance(item, str) and item.strip():
                    unique_contributions.append(
                        UniqueContribution(
                            document=entities[0] if entities else "Document",
                            contribution=item.strip(),
                        )
                    )

        # ----------------------------------------------------
        # Strengths & Limitations
        # ----------------------------------------------------

        raw_sl = data.get("strengths_and_limitations", [])
        strengths_and_limitations: list[StrengthLimitation] = []
        if isinstance(raw_sl, list):
            for item in raw_sl:
                if isinstance(item, dict):
                    doc = str(item.get("document", "")).strip() or "Document"
                    raw_s = item.get("strengths", [])
                    raw_l = item.get("limitations", [])
                    s_list = [str(x).strip() for x in raw_s if str(x).strip()] if isinstance(raw_s, list) else []
                    l_list = [str(x).strip() for x in raw_l if str(x).strip()] if isinstance(raw_l, list) else []
                    strengths_and_limitations.append(
                        StrengthLimitation(
                            document=doc,
                            strengths=s_list,
                            limitations=l_list,
                        )
                    )

        # ----------------------------------------------------
        # Synthesis
        # ----------------------------------------------------

        synthesis = str(data.get("synthesis", "")).strip()

        # Fallback source gathering from comparison values and contributions if empty
        if not sources:
            seen_src = set()
            for aspect in comparison:
                for val in aspect.values:
                    if val.document and val.chunk_id:
                        src_key = (val.document, str(val.page), val.chunk_id)
                        if src_key not in seen_src:
                            seen_src.add(src_key)
                            sources.append({
                                "document": val.document,
                                "page": val.page,
                                "chunk_id": val.chunk_id,
                            })
            for uc in unique_contributions:
                if uc.document and uc.chunk_id:
                    src_key = (uc.document, "", uc.chunk_id)
                    if src_key not in seen_src:
                        seen_src.add(src_key)
                        sources.append({
                            "document": uc.document,
                            "page": "N/A",
                            "chunk_id": uc.chunk_id,
                        })

        # ----------------------------------------------------
        # Final validated report
        # ----------------------------------------------------

        return ResearchComparisonReport(
            query=query,
            entities=entities,
            comparison=comparison,
            summary=summary,
            similarities=similarities,
            differences=differences,
            contradictions=contradictions,
            unique_contributions=unique_contributions,
            strengths_and_limitations=strengths_and_limitations,
            synthesis=synthesis,
            sources=sources,
        )