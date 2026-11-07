from __future__ import annotations

import json
import re
import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ==============================================================================
# ENUMS & MODELS
# ==============================================================================

class GapCategory(str, Enum):
    TECHNICAL = "TECHNICAL"
    METHODOLOGICAL = "METHODOLOGICAL"
    PERFORMANCE = "PERFORMANCE"
    DATASET = "DATASET"
    EVALUATION = "EVALUATION"
    IMPLEMENTATION = "IMPLEMENTATION"
    THEORETICAL = "THEORETICAL"
    APPLICATION = "APPLICATION"


class GapType(str, Enum):
    EXPLICIT = "EXPLICIT"
    DERIVED = "DERIVED"
    INFERRED = "INFERRED"  # Backward-compatible alias for DERIVED
    POTENTIAL = "POTENTIAL"


class GapPriority(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class FutureResearchRecommendation(BaseModel):
    id: str = Field(default_factory=lambda: f"rec_{uuid.uuid4().hex[:8]}")
    gap_id: str = ""
    title: str = Field(..., min_length=1)
    research_question: str = Field(..., min_length=1)
    problem_to_investigate: str = Field(..., min_length=1)
    suggested_approach: str = Field(..., min_length=1)
    expected_contribution: str = Field(..., min_length=1)
    supporting_evidence: list[str] = Field(default_factory=list)
    is_proposal: bool = True  # Clearly labeled as proposal, not established research finding


class GapConflict(BaseModel):
    topic: str = Field(..., min_length=1)
    paper_a: str = Field(..., min_length=1)
    finding_a: str = Field(..., min_length=1)
    paper_b: str = Field(..., min_length=1)
    finding_b: str = Field(..., min_length=1)
    explanation: str = ""
    evidence_chunks: list[str] = Field(default_factory=list)


class OpportunityMapNode(BaseModel):
    id: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    type: str = "LIMITATION"  # LIMITATION, UNRESOLVED_PROBLEM, CONCEPT, OPPORTUNITY
    category: str = "TECHNICAL"
    document: str = ""


class OpportunityMapLink(BaseModel):
    source: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)
    relationship: str = "leads_to"
    evidence: str = ""


class OpportunityMap(BaseModel):
    nodes: list[OpportunityMapNode] = Field(default_factory=list)
    links: list[OpportunityMapLink] = Field(default_factory=list)


class GapOverview(BaseModel):
    total_gaps: int = 0
    high_priority_gaps: int = 0
    medium_priority_gaps: int = 0
    low_priority_gaps: int = 0
    explicit_gaps: int = 0
    derived_gaps: int = 0
    potential_gaps: int = 0
    supporting_papers_count: int = 0
    categories_count: dict[str, int] = Field(default_factory=dict)


class ResearchGap(BaseModel):
    id: str = Field(default_factory=lambda: f"gap_{uuid.uuid4().hex[:8]}")
    gap: str = Field(..., min_length=1)
    title: str = ""
    category: GapCategory = GapCategory.TECHNICAL
    type: GapType = GapType.EXPLICIT
    priority: GapPriority = GapPriority.MEDIUM
    priority_reasoning: str = ""
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    rationale: str = Field(..., min_length=1)
    current_knowledge: str = ""
    missing_unresolved: str = ""
    limitation_evidence: str = ""
    why_it_matters: str = ""
    potential_direction: str = ""
    relevant_methods: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    document: str = ""
    page: int | str = ""
    chunk_id: str = ""
    supporting_papers: list[str] = Field(default_factory=list)
    is_shared: bool = False

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if not self.title:
            self.title = self.gap
        if not self.gap:
            self.gap = self.title
        if not self.current_knowledge and self.rationale:
            self.current_knowledge = self.rationale
        if not self.missing_unresolved and self.gap:
            self.missing_unresolved = self.gap
        if not self.limitation_evidence and self.evidence:
            self.limitation_evidence = self.evidence[0]
        if not self.supporting_papers and self.document:
            self.supporting_papers = [self.document]


class ResearchGapReport(BaseModel):
    query: str
    research_area: str
    existing_findings: list[str] = Field(default_factory=list)
    reported_limitations: list[str] = Field(default_factory=list)
    gaps: list[ResearchGap] = Field(default_factory=list)
    overview: GapOverview = Field(default_factory=GapOverview)
    recommendations: list[FutureResearchRecommendation] = Field(default_factory=list)
    opportunity_map: OpportunityMap = Field(default_factory=OpportunityMap)
    conflicts: list[GapConflict] = Field(default_factory=list)
    multi_doc_insights: dict[str, Any] = Field(default_factory=dict)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    partial: bool = False
    notice: str | None = None


# ==============================================================================
# RESEARCH GAP FINDER ENGINE
# ==============================================================================

class ResearchGapFinder:
    """Evidence-grounded research gap discovery engine."""

    # --------------------------------------------------------------------------
    # PROMPT BUILDER
    # --------------------------------------------------------------------------

    def build_gap_prompt(
        self,
        *,
        query: str,
        evidence: list[dict[str, Any]],
    ) -> str:
        # Build compact evidence representation to conserve token limits
        compact_evidence = []
        for idx, item in enumerate(evidence[:8]):
            chunk_raw = str(item.get("text", "")).strip()
            # truncate overly long chunks to conserve tokens while preserving crucial evidence
            compact_text = chunk_raw if len(chunk_raw) <= 450 else chunk_raw[:447] + "..."
            compact_evidence.append({
                "chunk_id": item.get("chunk_id", f"chunk_{idx+1}"),
                "document": item.get("document", "Document"),
                "page": item.get("page", 1),
                "text": compact_text,
            })

        evidence_json = json.dumps(compact_evidence, ensure_ascii=False, indent=1)

        return f"""You are the UNKNOWN Research Gap Discovery Engine.
Analyze the retrieved research evidence to identify evidence-grounded research gaps, multi-paper limitations, and future research opportunities.

RESEARCH QUERY:
{query}

RETRIEVED EVIDENCE:
{evidence_json}

STRICT EVIDENCE BOUNDARY RULES:
1. Base all findings, limitations, and gaps SOLELY on the supplied evidence. Do NOT invent papers, benchmarks, numbers, or citations.
2. Never claim an area has never been researched merely because it is not mentioned in these papers.
3. Identify 2 to 3 high-impact, evidence-grounded research gaps. Keep text values concise (1-2 sentences per field) to stay strictly within the token budget.
4. Categorize each gap into exactly one of: TECHNICAL, METHODOLOGICAL, PERFORMANCE, DATASET, EVALUATION, IMPLEMENTATION, THEORETICAL, APPLICATION.
4. Distinguish gap nature:
   - "EXPLICIT": Directly stated or acknowledged by the authors (e.g., explicit limitations, future work section).
   - "DERIVED": Reasonably deduced from empirical trade-offs or unaddressed assumptions across the evidence.
   - "POTENTIAL": Promising research opportunity warranting future investigation.
5. Prioritize gaps as "HIGH", "MEDIUM", or "LOW" based on:
   - Research significance, technical feasibility, potential impact, evidence strength, and practical relevance.
   - Provide a clear "priority_reasoning" explaining these criteria.
6. Multi-document intelligence:
   - If multiple documents are present, identify shared gaps across papers and unique limitations.
   - Detect conflicting findings between papers (do NOT interpret missing information as a contradiction).
7. Recommendations:
   - For each important gap, formulate a concrete proposal (research question, problem to investigate, suggested approach, expected contribution). Label them as proposals.
8. Return ONLY valid JSON with no markdown fences and no preamble.

JSON SCHEMA:
{{
  "query": "{query}",
  "research_area": "Concise 2-5 word research topic",
  "existing_findings": ["Established finding supported by evidence"],
  "reported_limitations": ["Reported limitation supported by evidence"],
  "gaps": [
    {{
      "gap": "Clear specific title of the research gap",
      "category": "TECHNICAL|METHODOLOGICAL|PERFORMANCE|DATASET|EVALUATION|IMPLEMENTATION|THEORETICAL|APPLICATION",
      "type": "EXPLICIT|DERIVED|POTENTIAL",
      "priority": "HIGH|MEDIUM|LOW",
      "priority_reasoning": "Reasoning based on significance, feasibility, impact, and evidence strength",
      "confidence": 0.85,
      "rationale": "Clear explanation of what is missing or unresolved",
      "current_knowledge": "What existing research has established",
      "missing_unresolved": "What remains unresolved",
      "limitation_evidence": "Passage or limitation statement revealing the gap",
      "why_it_matters": "Why addressing this gap matters",
      "potential_direction": "Suggested direction to address it",
      "relevant_methods": ["Method or research area"],
      "evidence": ["Exact or near-exact quote from evidence"],
      "document": "source_doc.pdf",
      "page": 1,
      "chunk_id": "chunk_001",
      "supporting_papers": ["source_doc.pdf"],
      "is_shared": false
    }}
  ],
  "recommendations": [
    {{
      "gap_title": "Associated gap title",
      "title": "Proposal title",
      "research_question": "Testable research question",
      "problem_to_investigate": "Specific problem",
      "suggested_approach": "Proposed methodology or experimental setup",
      "expected_contribution": "Expected scientific/practical contribution",
      "supporting_evidence": ["Evidence passage"]
    }}
  ],
  "conflicts": [
    {{
      "topic": "Conflicted topic or metric",
      "paper_a": "doc1.pdf",
      "finding_a": "Finding in doc1",
      "paper_b": "doc2.pdf",
      "finding_b": "Conflicting finding in doc2",
      "explanation": "Explanation of genuine contradiction",
      "evidence_chunks": ["chunk1", "chunk2"]
    }}
  ]
}}
""".strip()

    # --------------------------------------------------------------------------
    # JSON EXTRACTION & REPAIR
    # --------------------------------------------------------------------------

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        """Extract and parse a JSON object from a provider response with syntax repair."""
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Provider returned empty research gap output.")

        raw = text.strip()

        # Direct JSON parse
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

        # Markdown fenced JSON
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

        # Substring bounded JSON
        start = raw.find("{")
        if start != -1:
            end = raw.rfind("}")
            if end > start:
                candidate = raw[start : end + 1]
                try:
                    data = json.loads(candidate)
                    if isinstance(data, dict):
                        return data
                except json.JSONDecodeError:
                    pass

            # Truncated JSON repair using bracket stack
            sub = raw[start:]
            for cut in range(len(sub), max(0, len(sub) - 600), -1):
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
                            return candidate
                    except Exception:
                        continue

        raise ValueError("Provider returned invalid research gap JSON.")

    # --------------------------------------------------------------------------
    # GAP PRIORITIZATION & REASONING
    # --------------------------------------------------------------------------

    @staticmethod
    def calculate_gap_priority(
        gap: ResearchGap,
        evidence_count: int = 1,
        is_shared: bool = False,
    ) -> tuple[GapPriority, str]:
        """
        Calculates priority level (HIGH, MEDIUM, LOW) and explicit justification
        based on research significance, technical feasibility, potential impact,
        evidence strength, and practical relevance.
        """
        score = 0.0
        reasons = []

        # 1. Evidence Strength (up to 0.35)
        if gap.type == GapType.EXPLICIT:
            score += 0.25
            reasons.append("directly acknowledged by authors as a concrete limitation")
        elif gap.type == GapType.DERIVED:
            score += 0.15
            reasons.append("derived from empirical evidence and experimental trade-offs")
        else:
            score += 0.10
            reasons.append("identified as a potential exploratory area")

        if gap.confidence >= 0.85:
            score += 0.10
            reasons.append(f"high evidence grounding ({gap.confidence:.2f} confidence)")

        # 2. Research Significance & Category (up to 0.25)
        if gap.category in {GapCategory.THEORETICAL, GapCategory.METHODOLOGICAL}:
            score += 0.25
            reasons.append(f"high scientific significance in {gap.category.value.lower()} foundations")
        elif gap.category in {GapCategory.PERFORMANCE, GapCategory.TECHNICAL}:
            score += 0.20
            reasons.append(f"critical {gap.category.value.lower()} bottleneck affecting scalability")
        elif gap.category in {GapCategory.DATASET, GapCategory.EVALUATION}:
            score += 0.15
            reasons.append(f"essential {gap.category.value.lower()} baseline for empirical validation")
        else:
            score += 0.10
            reasons.append(f"practical {gap.category.value.lower()} relevance for domain adoption")

        # 3. Potential Impact & Cross-paper relevance (up to 0.25)
        if is_shared or len(gap.supporting_papers) > 1:
            score += 0.25
            reasons.append("cross-paper impact affecting multiple analyzed documents")
        elif evidence_count >= 2:
            score += 0.15
            reasons.append("supported by multiple distinct evidence passages")
        else:
            score += 0.05

        # 4. Technical Feasibility & Solution Direction (up to 0.15)
        if gap.potential_direction or gap.relevant_methods:
            score += 0.15
            reasons.append("concrete feasible methodologies and research directions identified")
        else:
            score += 0.05

        # Assign Level
        if score >= 0.70:
            priority = GapPriority.HIGH
            level_str = "High priority"
        elif score >= 0.45:
            priority = GapPriority.MEDIUM
            level_str = "Medium priority"
        else:
            priority = GapPriority.LOW
            level_str = "Low priority"

        reasoning = f"{level_str}: {'; '.join(reasons)}."
        return priority, reasoning

    # --------------------------------------------------------------------------
    # OPPORTUNITY MAP BUILDER
    # --------------------------------------------------------------------------

    @staticmethod
    def build_opportunity_map(
        gaps: list[ResearchGap],
        recommendations: list[FutureResearchRecommendation],
    ) -> OpportunityMap:
        """Constructs an interactive visual graph connecting limitations -> problems -> concepts -> opportunities."""
        nodes: list[OpportunityMapNode] = []
        links: list[OpportunityMapLink] = []
        seen_nodes = set()

        for g in gaps:
            # 1. Limitation node
            lim_id = f"lim_{g.id}"
            if lim_id not in seen_nodes:
                seen_nodes.add(lim_id)
                nodes.append(OpportunityMapNode(
                    id=lim_id,
                    label=g.title if len(g.title) <= 40 else g.title[:37] + "...",
                    type="LIMITATION",
                    category=g.category.value,
                    document=g.document,
                ))

            # 2. Unresolved problem node
            prob_id = f"prob_{g.id}"
            if prob_id not in seen_nodes:
                seen_nodes.add(prob_id)
                nodes.append(OpportunityMapNode(
                    id=prob_id,
                    label=g.missing_unresolved if len(g.missing_unresolved) <= 40 else g.missing_unresolved[:37] + "...",
                    type="UNRESOLVED_PROBLEM",
                    category=g.category.value,
                    document=g.document,
                ))
                links.append(OpportunityMapLink(
                    source=lim_id,
                    target=prob_id,
                    relationship="reveals_unresolved_problem",
                    evidence=g.limitation_evidence,
                ))

            # 3. Concept / Method nodes
            for m_idx, method in enumerate(g.relevant_methods[:2]):
                m_id = f"meth_{g.id}_{m_idx}"
                if m_id not in seen_nodes:
                    seen_nodes.add(m_id)
                    nodes.append(OpportunityMapNode(
                        id=m_id,
                        label=method if len(method) <= 35 else method[:32] + "...",
                        type="CONCEPT",
                        category=g.category.value,
                        document=g.document,
                    ))
                    links.append(OpportunityMapLink(
                        source=prob_id,
                        target=m_id,
                        relationship="addressable_by",
                        evidence=g.rationale,
                    ))

            # 4. Find matching recommendation
            matching_recs = [r for r in recommendations if r.gap_id == g.id or r.title.lower() in g.title.lower()]
            for r in matching_recs[:1]:
                opp_id = f"opp_{r.id}"
                if opp_id not in seen_nodes:
                    seen_nodes.add(opp_id)
                    nodes.append(OpportunityMapNode(
                        id=opp_id,
                        label=r.title if len(r.title) <= 40 else r.title[:37] + "...",
                        type="OPPORTUNITY",
                        category=g.category.value,
                        document=g.document,
                    ))
                    links.append(OpportunityMapLink(
                        source=prob_id,
                        target=opp_id,
                        relationship="leads_to_opportunity",
                        evidence=r.suggested_approach,
                    ))

        return OpportunityMap(nodes=nodes, links=links)

    # --------------------------------------------------------------------------
    # PARSE RESPONSE
    # --------------------------------------------------------------------------

    def parse_response(
        self,
        *,
        query: str,
        response_text: str,
    ) -> ResearchGapReport:
        data = self._extract_json(response_text)

        existing_findings = [
            str(item).strip() for item in data.get("existing_findings", []) if str(item).strip()
        ]
        reported_limitations = [
            str(item).strip() for item in data.get("reported_limitations", []) if str(item).strip()
        ]
        raw_gaps = data.get("gaps", [])
        if not isinstance(raw_gaps, list):
            raw_gaps = []

        gaps: list[ResearchGap] = []
        categories_count: dict[str, int] = {c.value: 0 for c in GapCategory}
        all_papers = set()

        for idx, item in enumerate(raw_gaps):
            if not isinstance(item, dict):
                continue
            gap_text = str(item.get("gap") or item.get("title") or "").strip()
            rationale_text = str(item.get("rationale") or item.get("missing_unresolved") or "").strip()
            if not gap_text:
                continue
            if not rationale_text:
                rationale_text = gap_text

            # Category resolution
            cat_str = str(item.get("category", GapCategory.TECHNICAL.value)).upper()
            try:
                category = GapCategory(cat_str)
            except ValueError:
                category = GapCategory.TECHNICAL

            # Type resolution
            type_str = str(item.get("type", GapType.EXPLICIT.value)).upper()
            if type_str == "INFERRED":
                gap_type = GapType.DERIVED
            else:
                try:
                    gap_type = GapType(type_str)
                except ValueError:
                    gap_type = GapType.EXPLICIT

            # Confidence
            conf = float(item.get("confidence", 0.85))
            confidence = max(0.0, min(1.0, conf))

            # Citations
            doc = str(item.get("document", "")).strip()
            if doc:
                all_papers.add(doc)
            page = item.get("page", 1)
            chunk_id = str(item.get("chunk_id", "")).strip()
            evidence_list = [str(e).strip() for e in item.get("evidence", []) if str(e).strip()]
            supporting_papers = [str(p).strip() for p in item.get("supporting_papers", []) if str(p).strip()]
            if doc and doc not in supporting_papers:
                supporting_papers.append(doc)
            for p in supporting_papers:
                all_papers.add(p)

            is_shared = bool(item.get("is_shared") or len(supporting_papers) > 1)

            # Extra rich fields
            current_k = str(item.get("current_knowledge") or "").strip() or "Identified from existing document literature."
            missing_u = str(item.get("missing_unresolved") or "").strip() or gap_text
            lim_ev = str(item.get("limitation_evidence") or (evidence_list[0] if evidence_list else "")).strip()
            why_m = str(item.get("why_it_matters") or "").strip() or f"Addresses critical {category.value.lower()} constraints in existing models."
            pot_dir = str(item.get("potential_direction") or "").strip() or "Develop empirical baselines and enhanced frameworks to address this limitation."
            rel_methods = [str(m).strip() for m in item.get("relevant_methods", []) if str(m).strip()]
            if not rel_methods:
                rel_methods = [f"{category.value.title()} evaluation", "Comparative benchmarking"]

            gap_obj = ResearchGap(
                id=f"gap_{idx+1}",
                gap=gap_text,
                title=gap_text,
                category=category,
                type=gap_type,
                confidence=confidence,
                rationale=rationale_text,
                current_knowledge=current_k,
                missing_unresolved=missing_u,
                limitation_evidence=lim_ev,
                why_it_matters=why_m,
                potential_direction=pot_dir,
                relevant_methods=rel_methods,
                evidence=evidence_list,
                document=doc,
                page=page,
                chunk_id=chunk_id,
                supporting_papers=supporting_papers,
                is_shared=is_shared,
            )

            # Prioritization calculation & reasoning
            req_priority = str(item.get("priority", "")).upper()
            if req_priority in {GapPriority.HIGH.value, GapPriority.MEDIUM.value, GapPriority.LOW.value}:
                gap_obj.priority = GapPriority(req_priority)
                gap_obj.priority_reasoning = str(item.get("priority_reasoning") or "").strip()
                if not gap_obj.priority_reasoning:
                    _, auto_reason = self.calculate_gap_priority(gap_obj, len(evidence_list), is_shared)
                    gap_obj.priority_reasoning = auto_reason
            else:
                p, r = self.calculate_gap_priority(gap_obj, len(evidence_list), is_shared)
                gap_obj.priority = p
                gap_obj.priority_reasoning = r

            gaps.append(gap_obj)
            categories_count[category.value] = categories_count.get(category.value, 0) + 1

        if not gaps:
            raise ValueError("No valid research gaps found in LLM response.")

        # Recommendations
        raw_recs = data.get("recommendations", [])
        recommendations: list[FutureResearchRecommendation] = []
        for r_idx, r in enumerate(raw_recs):
            if not isinstance(r, dict):
                continue
            title = str(r.get("title") or r.get("research_question") or "").strip()
            rq = str(r.get("research_question") or title).strip()
            prob = str(r.get("problem_to_investigate") or title).strip()
            appr = str(r.get("suggested_approach") or "Controlled experimental investigation with extended baselines.").strip()
            contr = str(r.get("expected_contribution") or "Definitive evidence resolving unaddressed trade-offs.").strip()
            ev_list = [str(e).strip() for e in r.get("supporting_evidence", []) if str(e).strip()]
            matching_gap = next((g for g in gaps if g.title.lower() in title.lower() or title.lower() in g.title.lower()), None)

            if title:
                recommendations.append(FutureResearchRecommendation(
                    id=f"rec_{r_idx+1}",
                    gap_id=matching_gap.id if matching_gap else (gaps[0].id if gaps else ""),
                    title=title,
                    research_question=rq,
                    problem_to_investigate=prob,
                    suggested_approach=appr,
                    expected_contribution=contr,
                    supporting_evidence=ev_list or (matching_gap.evidence if matching_gap else []),
                    is_proposal=True,
                ))

        # If LLM didn't produce recommendations, generate evidence-backed proposals for high/medium gaps
        if not recommendations and gaps:
            for g in gaps[:4]:
                recommendations.append(FutureResearchRecommendation(
                    id=f"rec_{g.id}",
                    gap_id=g.id,
                    title=f"Investigation into {g.title}",
                    research_question=f"How can {g.relevant_methods[0] if g.relevant_methods else 'systematic design'} mitigate {g.title.lower()}?",
                    problem_to_investigate=g.missing_unresolved,
                    suggested_approach=g.potential_direction or f"Empirically validate against {g.category.value.lower()} benchmarks.",
                    expected_contribution=f"Resolves {g.category.value.lower()} bottleneck and improves practical deployment viability.",
                    supporting_evidence=g.evidence,
                    is_proposal=True,
                ))

        # Conflicts
        conflicts: list[GapConflict] = []
        for c in data.get("conflicts", []):
            if isinstance(c, dict):
                topic = str(c.get("topic") or "").strip()
                pa = str(c.get("paper_a") or "").strip()
                fa = str(c.get("finding_a") or "").strip()
                pb = str(c.get("paper_b") or "").strip()
                fb = str(c.get("finding_b") or "").strip()
                if topic and pa and pb and fa and fb:
                    conflicts.append(GapConflict(
                        topic=topic,
                        paper_a=pa,
                        finding_a=fa,
                        paper_b=pb,
                        finding_b=fb,
                        explanation=str(c.get("explanation") or f"Conflicting findings between {pa} and {pb} regarding {topic}."),
                        evidence_chunks=[str(ch).strip() for ch in c.get("evidence_chunks", []) if str(ch).strip()],
                    ))

        # Multi-document insights
        shared_gaps_list = [g.title for g in gaps if g.is_shared]
        unique_limitations_map = {}
        for g in gaps:
            if g.document and not g.is_shared:
                unique_limitations_map.setdefault(g.document, []).append(g.title)

        underexplored_areas = [cat for cat, count in categories_count.items() if count == 0]

        multi_doc_insights = {
            "shared_gaps": shared_gaps_list,
            "unique_limitations": unique_limitations_map,
            "recurring_problems": [g.missing_unresolved for g in gaps if g.is_shared],
            "underexplored_areas": underexplored_areas,
        }

        # Overview
        high_gaps = len([g for g in gaps if g.priority == GapPriority.HIGH])
        med_gaps = len([g for g in gaps if g.priority == GapPriority.MEDIUM])
        low_gaps = len([g for g in gaps if g.priority == GapPriority.LOW])
        explicit_gaps = len([g for g in gaps if g.type == GapType.EXPLICIT])
        derived_gaps = len([g for g in gaps if g.type in {GapType.DERIVED, GapType.INFERRED}])
        potential_gaps = len([g for g in gaps if g.type == GapType.POTENTIAL])

        overview = GapOverview(
            total_gaps=len(gaps),
            high_priority_gaps=high_gaps,
            medium_priority_gaps=med_gaps,
            low_priority_gaps=low_gaps,
            explicit_gaps=explicit_gaps,
            derived_gaps=derived_gaps,
            potential_gaps=potential_gaps,
            supporting_papers_count=len(all_papers),
            categories_count=categories_count,
        )

        # Opportunity Map
        opportunity_map = self.build_opportunity_map(gaps, recommendations)

        # Sources
        parsed_sources: list[dict[str, Any]] = []
        seen_src = set()
        for s in data.get("sources", []):
            if isinstance(s, dict):
                cid = str(s.get("chunk_id") or "")
                doc = str(s.get("document") or "")
                key = (doc, cid)
                if key not in seen_src and (doc or cid):
                    seen_src.add(key)
                    parsed_sources.append({
                        "document": doc,
                        "page": s.get("page", 1),
                        "chunk_id": cid,
                        "passage": str(s.get("passage") or s.get("text") or ""),
                    })

        for g in gaps:
            key = (g.document, g.chunk_id)
            if key not in seen_src and (g.document or g.chunk_id):
                seen_src.add(key)
                parsed_sources.append({
                    "document": g.document,
                    "page": g.page,
                    "chunk_id": g.chunk_id,
                    "passage": g.limitation_evidence or (g.evidence[0] if g.evidence else ""),
                })

        return ResearchGapReport(
            query=str(data.get("query") or query),
            research_area=str(data.get("research_area", "General research")).strip(),
            existing_findings=existing_findings or ["Document evidence analyzed."],
            reported_limitations=reported_limitations or [g.title for g in gaps],
            gaps=gaps,
            overview=overview,
            recommendations=recommendations,
            opportunity_map=opportunity_map,
            conflicts=conflicts,
            multi_doc_insights=multi_doc_insights,
            sources=parsed_sources,
            partial=False,
            notice=None,
        )

    # --------------------------------------------------------------------------
    # DETERMINISTIC NO-LLM FALLBACK EXTRACTOR
    # --------------------------------------------------------------------------

    def build_no_llm_gaps(
        self,
        *,
        query: str,
        evidence: list[dict[str, Any]],
        document_names: list[str] | None = None,
    ) -> ResearchGapReport:
        """
        Deterministic, rule-based Research Gaps extractor when LLM providers fail.
        Scans actual evidence passages for limitation and bottleneck markers,
        classifies into the 8 gap categories, prioritizes gaps with concrete reasoning,
        constructs the opportunity map, and formulates future research proposals.
        """
        if not evidence:
            return ResearchGapReport(
                query=query,
                research_area="Insufficient evidence",
                existing_findings=[],
                reported_limitations=[],
                gaps=[],
                overview=GapOverview(),
                recommendations=[],
                opportunity_map=OpportunityMap(),
                conflicts=[],
                multi_doc_insights={},
                sources=[],
                partial=False,
                notice="Not found in available sources. Insufficient evidence to establish research gaps for the specified documents.",
            )

        gaps: list[ResearchGap] = []
        existing_findings: list[str] = []
        reported_limitations: list[str] = []
        categories_count: dict[str, int] = {c.value: 0 for c in GapCategory}
        all_papers = set()
        seen_sentences = set()

        # Regular expressions for category classification
        category_patterns = [
            (GapCategory.DATASET, re.compile(r"\b(?:dataset|sample size|corpus|annotation|imbalance|unlabeled|scarcity|underrepresented|diversity|data collection)\b", re.I)),
            (GapCategory.PERFORMANCE, re.compile(r"\b(?:latency|speed|throughput|memory|vram|gpu|compute|cost|scalability|overhead|resource-intensive|slow|bandwidth)\b", re.I)),
            (GapCategory.EVALUATION, re.compile(r"\b(?:benchmark|metric|baseline|evaluation|comparison|f1|accuracy|ablation|ground truth|untested against)\b", re.I)),
            (GapCategory.METHODOLOGICAL, re.compile(r"\b(?:assumption|heuristic|approximation|convergence|hyperparameter|optimization|variance|stability|generalization)\b", re.I)),
            (GapCategory.IMPLEMENTATION, re.compile(r"\b(?:deployment|hardware|real-world|engineering|production|integration|firmware|dependency|runtime)\b", re.I)),
            (GapCategory.THEORETICAL, re.compile(r"\b(?:proof|theoretical|bound|guarantee|understanding|formal|mathematical|tractability|unexplained)\b", re.I)),
            (GapCategory.APPLICATION, re.compile(r"\b(?:domain|clinical|industrial|real-time|multimodal|transfer|adaptation|commercial|field test)\b", re.I)),
        ]

        # Markers indicating limitations or unresolved challenges
        limitation_markers = [
            r"\b(?:limitation|drawback|bottleneck|however|fails to|unable to|constrained by|trade-off|expensive|slow|assumes|restricted to|unresolved|open problem|future work|remains to be|lack of|insufficient|does not support|vulnerable to|degrades?)\b"
        ]
        explicit_markers = re.compile(r"\b(?:our limitation|we leave|future work|we do not|authors acknowledge|limitation of this work|open question)\b", re.I)

        findings_markers = [
            r"\b(?:we show|we find|results demonstrate|outperforms|achieves?|we introduce|we propose|improves?)\b"
        ]

        parsed_sources: list[dict[str, Any]] = []
        seen_src = set()

        for c_idx, chunk in enumerate(evidence):
            raw_text = chunk.get("text", "")
            doc = chunk.get("document", "Document")
            page = chunk.get("page", 1)
            cid = chunk.get("chunk_id", f"chunk_{c_idx + 1}")
            all_papers.add(doc)

            # Record source
            src_key = (doc, cid)
            if src_key not in seen_src:
                seen_src.add(src_key)
                parsed_sources.append({
                    "document": doc,
                    "page": page,
                    "chunk_id": cid,
                    "passage": raw_text[:300],
                })

            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", raw_text) if len(s.strip()) > 25]

            for s in sentences:
                clean_s = " ".join(s.split())
                if clean_s.lower() in seen_sentences:
                    continue
                seen_sentences.add(clean_s.lower())

                # Check if it's an existing finding
                if any(re.search(p, clean_s, re.I) for p in findings_markers) and len(existing_findings) < 5:
                    existing_findings.append(clean_s)

                # Check if it indicates a limitation or gap
                is_limitation = any(re.search(p, clean_s, re.I) for p in limitation_markers)
                if is_limitation and len(gaps) < 8:
                    reported_limitations.append(clean_s)

                    # Determine category
                    matched_category = GapCategory.TECHNICAL
                    for cat, pat in category_patterns:
                        if pat.search(clean_s):
                            matched_category = cat
                            break

                    # Determine type
                    if explicit_markers.search(clean_s):
                        gap_type = GapType.EXPLICIT
                    elif any(w in clean_s.lower() for w in ["future", "promising", "opportunity", "could be"]):
                        gap_type = GapType.POTENTIAL
                    else:
                        gap_type = GapType.DERIVED

                    # Derive concise title
                    gap_title = self._clean_gap_title(clean_s, matched_category)

                    gap_obj = ResearchGap(
                        id=f"gap_{len(gaps)+1}",
                        gap=gap_title,
                        title=gap_title,
                        category=matched_category,
                        type=gap_type,
                        confidence=0.85 if gap_type == GapType.EXPLICIT else 0.80,
                        rationale=clean_s,
                        current_knowledge="Existing approach analyzed in literature.",
                        missing_unresolved=clean_s,
                        limitation_evidence=clean_s,
                        why_it_matters=f"Unresolved {matched_category.value.lower()} constraint that impedes robust broader deployment.",
                        potential_direction=f"Investigate enhanced {matched_category.value.lower()} formulations and comparative validation.",
                        relevant_methods=[f"{matched_category.value.title()} optimization", "Empirical benchmarking"],
                        evidence=[clean_s],
                        document=doc,
                        page=page,
                        chunk_id=cid,
                        supporting_papers=[doc],
                        is_shared=False,
                    )

                    # Prioritize
                    p, r = self.calculate_gap_priority(gap_obj, 1, False)
                    gap_obj.priority = p
                    gap_obj.priority_reasoning = r

                    gaps.append(gap_obj)
                    categories_count[matched_category.value] = categories_count.get(matched_category.value, 0) + 1

        # Check for shared gaps across multiple papers
        for g1 in gaps:
            for g2 in gaps:
                if g1.id != g2.id and g1.document != g2.document:
                    # check semantic category & keyword overlap
                    words1 = set(re.findall(r"\w{4,}", g1.title.lower()))
                    words2 = set(re.findall(r"\w{4,}", g2.title.lower()))
                    if (words1 & words2) or (g1.category == g2.category and g1.category != GapCategory.TECHNICAL):
                        g1.is_shared = True
                        if g2.document not in g1.supporting_papers:
                            g1.supporting_papers.append(g2.document)

        # Future Research Recommendations
        recommendations: list[FutureResearchRecommendation] = []
        for g in gaps[:4]:
            recommendations.append(FutureResearchRecommendation(
                id=f"rec_{g.id}",
                gap_id=g.id,
                title=f"Proposed Investigation: Addressing {g.title}",
                research_question=f"Can targeted methodological adaptations resolve the {g.title.lower()} constraint?",
                problem_to_investigate=g.missing_unresolved,
                suggested_approach=g.potential_direction,
                expected_contribution=f"Establishes rigorous empirical benchmarks and mitigates {g.category.value.lower()} bottlenecks.",
                supporting_evidence=g.evidence,
                is_proposal=True,
            ))

        # Multi-document insights
        shared_gaps_list = [g.title for g in gaps if g.is_shared]
        unique_limitations_map = {}
        for g in gaps:
            if g.document and not g.is_shared:
                unique_limitations_map.setdefault(g.document, []).append(g.title)

        underexplored_areas = [cat for cat, count in categories_count.items() if count == 0]

        multi_doc_insights = {
            "shared_gaps": shared_gaps_list,
            "unique_limitations": unique_limitations_map,
            "recurring_problems": [g.missing_unresolved for g in gaps if g.is_shared],
            "underexplored_areas": underexplored_areas,
        }

        # Overview
        high_gaps = len([g for g in gaps if g.priority == GapPriority.HIGH])
        med_gaps = len([g for g in gaps if g.priority == GapPriority.MEDIUM])
        low_gaps = len([g for g in gaps if g.priority == GapPriority.LOW])
        explicit_gaps = len([g for g in gaps if g.type == GapType.EXPLICIT])
        derived_gaps = len([g for g in gaps if g.type in {GapType.DERIVED, GapType.INFERRED}])
        potential_gaps = len([g for g in gaps if g.type == GapType.POTENTIAL])

        overview = GapOverview(
            total_gaps=len(gaps),
            high_priority_gaps=high_gaps,
            medium_priority_gaps=med_gaps,
            low_priority_gaps=low_gaps,
            explicit_gaps=explicit_gaps,
            derived_gaps=derived_gaps,
            potential_gaps=potential_gaps,
            supporting_papers_count=len(all_papers),
            categories_count=categories_count,
        )

        # Opportunity Map
        opportunity_map = self.build_opportunity_map(gaps, recommendations)

        # Clean topic from query
        words = [w for w in re.findall(r"[A-Za-z0-9\-]+", query) if len(w) > 3 and w.lower() not in {"what", "which", "find", "identify", "research", "gaps", "show"}]
        topic = " ".join(words[:4]).title() if words else "Document Research Domain"

        return ResearchGapReport(
            query=query,
            research_area=topic,
            existing_findings=existing_findings or ["Analyzed indexed passages."],
            reported_limitations=reported_limitations or [g.title for g in gaps],
            gaps=gaps,
            overview=overview,
            recommendations=recommendations,
            opportunity_map=opportunity_map,
            conflicts=[],
            multi_doc_insights=multi_doc_insights,
            sources=parsed_sources,
            partial=True,
            notice="Notice: Research gap report generated directly from available document evidence because AI providers were unavailable or timed out.",
        )

    @staticmethod
    def _clean_gap_title(sentence: str, category: GapCategory) -> str:
        """Derives a concise, readable title for an identified research gap."""
        # Clean leading words
        s = re.sub(r"^(?:however|furthermore|moreover|therefore|in addition|although|we find that|authors state that),?\s*", "", sentence, flags=re.I)
        # Match short clause
        match = re.search(r"([^,.;:]{15,65})", s)
        if match:
            candidate = match.group(1).strip()
            # Capitalize first letter
            return candidate[0].upper() + candidate[1:]
        return f"Unresolved {category.value.title()} Limitation"
