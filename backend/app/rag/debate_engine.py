from __future__ import annotations

import json
import re
import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DebateSide(str, Enum):
    PRO = "POSITION_A"
    CON = "POSITION_B"
    POSITION_A = "POSITION_A"
    POSITION_B = "POSITION_B"

    @classmethod
    def from_str(cls, val: str) -> DebateSide:
        val_upper = str(val or "").strip().upper()
        if val_upper in ("POSITION_A", "PRO", "IN_FAVOUR", "AFFIRMATIVE"):
            return cls.POSITION_A
        if val_upper in ("POSITION_B", "CON", "AGAINST", "NEGATIVE"):
            return cls.POSITION_B
        return cls.POSITION_A


class EvidenceType(str, Enum):
    DIRECT_EVIDENCE = "DIRECT_EVIDENCE"
    REASONABLE_INFERENCE = "REASONABLE_INFERENCE"
    UNSUPPORTED = "UNSUPPORTED"


class EvidenceStrength(str, Enum):
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"
    NONE = "NONE"


class DebateArgument(BaseModel):
    id: str = Field(default_factory=lambda: f"arg_{uuid.uuid4().hex[:8]}")
    side: DebateSide
    title: str = ""
    argument: str = Field(..., min_length=1)
    evidence_type: str = "DIRECT_EVIDENCE"  # DIRECT_EVIDENCE | REASONABLE_INFERENCE | UNSUPPORTED
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    evidence_strength: str = "MODERATE"  # STRONG | MODERATE | WEAK | NONE
    document: str = ""
    page: int | str = ""
    chunk_id: str = ""

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if not self.title and self.argument:
            self.title = self.argument[:65] + "..." if len(self.argument) > 65 else self.argument
        if not self.evidence and not self.document:
            self.evidence_strength = "NONE"
            self.evidence_type = "UNSUPPORTED"


class DebateRebuttal(BaseModel):
    id: str = Field(default_factory=lambda: f"reb_{uuid.uuid4().hex[:8]}")
    side: DebateSide
    target_argument: str = Field(..., min_length=1)
    rebuttal: str = Field(..., min_length=1)
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.80, ge=0.0, le=1.0)
    document: str = ""
    page: int | str = ""
    chunk_id: str = ""


class DebateOpeningStatements(BaseModel):
    pro: str = ""
    con: str = ""


class DebateReport(BaseModel):
    query: str
    proposition: str = ""
    topic: str = ""
    position_a: str = ""
    position_b: str = ""
    opening_statements: DebateOpeningStatements = Field(default_factory=DebateOpeningStatements)
    arguments: list[DebateArgument] = Field(default_factory=list)
    rebuttals: list[DebateRebuttal] = Field(default_factory=list)
    agreements: list[str] = Field(default_factory=list)
    disagreements: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    neutral_assessment: str = ""
    conclusion: str = ""
    final_verdict: str = Field(..., min_length=1)
    verdict_confidence: float = Field(..., ge=0.0, le=1.0)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    partial: bool = False
    notice: str | None = None

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if not self.proposition:
            self.proposition = self.topic or self.query
        if not self.conclusion:
            self.conclusion = self.final_verdict
        if not self.final_verdict and self.conclusion:
            self.final_verdict = self.conclusion
        if not self.neutral_assessment and self.conclusion:
            self.neutral_assessment = self.conclusion


class DebateEngine:
    """
    Evidence-grounded AI debate engine.

    The model is strictly constrained to the supplied retrieval evidence.
    It constructs balanced Pro and Con positions, opening statements,
    counterarguments/rebuttals, and distinguishes evidence strength from certainty.
    """

    def build_debate_prompt(
        self,
        *,
        query: str,
        position_a: str,
        position_b: str,
        evidence: list[dict[str, Any]],
    ) -> str:
        compact_evidence = []
        for idx, item in enumerate(evidence[:8]):
            chunk_raw = str(item.get("text", "")).strip()
            compact_text = chunk_raw if len(chunk_raw) <= 450 else chunk_raw[:447] + "..."
            compact_evidence.append({
                "chunk_id": item.get("chunk_id", f"chunk_{idx+1}"),
                "document": item.get("document", "Document"),
                "page": item.get("page", 1),
                "text": compact_text,
            })

        evidence_json = json.dumps(compact_evidence, ensure_ascii=False, indent=1)

        return f"""You are the UNKNOWN Evidence-Based AI Debate Engine.
Analyze the research question by debating two opposing perspectives:
- Pro (POSITION_A): Arguments supporting the proposition.
- Con (POSITION_B): Arguments challenging, limiting, or opposing the proposition.

RESEARCH QUESTION:
{query}

PROPOSITION:
{query}

POSITION A (PRO):
{position_a}

POSITION B (CON):
{position_b}

RETRIEVED EVIDENCE:
{evidence_json}

STRICT EVIDENCE BOUNDARY RULES:
1. Base all arguments, rebuttals, and citations SOLELY on the supplied evidence. Do NOT invent facts, papers, benchmarks, numbers, or citations.
2. Represent both sides fairly; do not artificially force equal evidence strength.
3. For each argument, distinguish:
   - "DIRECT_EVIDENCE": Explicitly stated in the cited evidence.
   - "REASONABLE_INFERENCE": Directly deduced from empirical findings.
   - "UNSUPPORTED": Claims lacking direct empirical evidence in the supplied passages.
4. If the selected documents do not support one side, explicitly state that in the argument and set evidence_strength="NONE".
5. Rebuttals: Directly challenge the opposing arguments using evidence from the documents.
6. Provide opening arguments for both sides, identify shared agreements and core disagreements, and formulate unresolved research questions.
7. Neutral final assessment: Objectively evaluate which arguments have stronger empirical support without declaring an unearned absolute winner.
8. Conclusion: Synthesize the findings while carefully distinguishing evidence strength from certainty.
9. Keep text fields concise (1-2 sentences per field) to stay within token limits.
10. Return ONLY valid JSON with no markdown fences and no preamble.

EXPECTED JSON SCHEMA:
{{
  "query": "{query}",
  "proposition": "Clear, formal debate proposition",
  "topic": "Concise 3-6 word topic",
  "position_a": "{position_a}",
  "position_b": "{position_b}",
  "opening_statements": {{
    "pro": "1-2 sentence opening argument for Pro",
    "con": "1-2 sentence opening argument for Con"
  }},
  "arguments": [
    {{
      "side": "POSITION_A",
      "title": "Short headline of pro argument",
      "argument": "Evidence-grounded argument text",
      "evidence_type": "DIRECT_EVIDENCE|REASONABLE_INFERENCE|UNSUPPORTED",
      "evidence": ["Exact or near-exact quote from evidence"],
      "confidence": 0.88,
      "evidence_strength": "STRONG|MODERATE|WEAK|NONE",
      "document": "doc_name.pdf",
      "page": 1,
      "chunk_id": "chunk_001"
    }},
    {{
      "side": "POSITION_B",
      "title": "Short headline of con argument",
      "argument": "Evidence-grounded counterargument text",
      "evidence_type": "DIRECT_EVIDENCE|REASONABLE_INFERENCE|UNSUPPORTED",
      "evidence": ["Exact or near-exact quote from evidence"],
      "confidence": 0.84,
      "evidence_strength": "STRONG|MODERATE|WEAK|NONE",
      "document": "doc_name.pdf",
      "page": 2,
      "chunk_id": "chunk_002"
    }}
  ],
  "rebuttals": [
    {{
      "side": "POSITION_B",
      "target_argument": "Title or summary of Pro argument being challenged",
      "rebuttal": "Targeted rebuttal grounded in retrieved evidence",
      "evidence": ["Supporting quote"],
      "confidence": 0.82,
      "document": "doc_name.pdf",
      "page": 2,
      "chunk_id": "chunk_002"
    }},
    {{
      "side": "POSITION_A",
      "target_argument": "Title or summary of Con argument being challenged",
      "rebuttal": "Targeted response defending Pro position",
      "evidence": ["Supporting quote"],
      "confidence": 0.80,
      "document": "doc_name.pdf",
      "page": 1,
      "chunk_id": "chunk_001"
    }}
  ],
  "agreements": [
    "Common ground or shared fact accepted by both sides based on evidence"
  ],
  "disagreements": [
    "Core point of divergence or tension identified in the literature"
  ],
  "unresolved_questions": [
    "Key empirical question that remains open or untested"
  ],
  "neutral_assessment": "Objective comparison of which side has stronger empirical support in these sources",
  "conclusion": "Balanced synthesis distinguishing evidence strength from certainty",
  "final_verdict": "Clear summary verdict reflecting the relative strength of evidence",
  "verdict_confidence": 0.85,
  "sources": [
    {{
      "document": "doc_name.pdf",
      "page": 1,
      "chunk_id": "chunk_001"
    }}
  ]
}}
""".strip()

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        if not text or not text.strip():
            raise ValueError("Debate engine returned an empty response.")

        cleaned = text.strip()

        # Handle Markdown fences
        if "```" in cleaned:
            blocks = cleaned.split("```")
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

        try:
            value = json.loads(cleaned)
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            pass

        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end > start:
            try:
                value = json.loads(cleaned[start : end + 1])
                if isinstance(value, dict):
                    return value
            except json.JSONDecodeError as error:
                raise ValueError("Debate engine returned invalid JSON.") from error

        raise ValueError("Debate engine returned invalid JSON.")

    @staticmethod
    def _parse_argument(value: Any) -> DebateArgument:
        if not isinstance(value, dict):
            raise ValueError("Invalid debate argument.")

        raw_side = value.get("side", "POSITION_A")
        side = DebateSide.from_str(str(raw_side))
        arg_text = str(value.get("argument", "")).strip()
        title = str(value.get("title", "")).strip()
        ev_list = [str(e).strip() for e in value.get("evidence", []) if str(e).strip()]
        doc = str(value.get("document", "")).strip()

        ev_type = str(value.get("evidence_type", "DIRECT_EVIDENCE")).upper()
        if ev_type not in {e.value for e in EvidenceType}:
            ev_type = EvidenceType.DIRECT_EVIDENCE.value if ev_list else EvidenceType.UNSUPPORTED.value

        strength = str(value.get("evidence_strength", "MODERATE")).upper()
        if strength not in {s.value for s in EvidenceStrength}:
            strength = EvidenceStrength.STRONG.value if len(ev_list) >= 2 else (
                EvidenceStrength.MODERATE.value if ev_list else EvidenceStrength.NONE.value
            )

        try:
            conf = float(value.get("confidence", 0.85))
            conf = max(0.0, min(1.0, conf))
        except (ValueError, TypeError):
            conf = 0.85

        return DebateArgument(
            id=str(value.get("id") or f"arg_{uuid.uuid4().hex[:8]}"),
            side=side,
            title=title or arg_text[:65],
            argument=arg_text,
            evidence_type=ev_type,
            evidence=ev_list,
            confidence=conf,
            evidence_strength=strength,
            document=doc,
            page=value.get("page", 1),
            chunk_id=str(value.get("chunk_id", "")),
        )

    @staticmethod
    def _parse_rebuttal(value: Any) -> DebateRebuttal:
        if not isinstance(value, dict):
            raise ValueError("Invalid debate rebuttal.")

        raw_side = value.get("side", "POSITION_B")
        side = DebateSide.from_str(str(raw_side))
        target = str(value.get("target_argument", "")).strip()
        rebuttal_text = str(value.get("rebuttal", "")).strip()
        ev_list = [str(e).strip() for e in value.get("evidence", []) if str(e).strip()]

        try:
            conf = float(value.get("confidence", 0.80))
            conf = max(0.0, min(1.0, conf))
        except (ValueError, TypeError):
            conf = 0.80

        return DebateRebuttal(
            id=str(value.get("id") or f"reb_{uuid.uuid4().hex[:8]}"),
            side=side,
            target_argument=target,
            rebuttal=rebuttal_text,
            evidence=ev_list,
            confidence=conf,
            document=str(value.get("document", "")),
            page=value.get("page", 1),
            chunk_id=str(value.get("chunk_id", "")),
        )

    @staticmethod
    def _parse_sources(value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []

        sources: list[dict[str, Any]] = []
        seen = set()
        for source in value:
            if not isinstance(source, dict):
                continue
            doc = str(source.get("document", ""))
            cid = str(source.get("chunk_id", ""))
            key = (doc, cid)
            if key not in seen and (doc or cid):
                seen.add(key)
                sources.append({
                    "document": doc,
                    "page": source.get("page", 1),
                    "chunk_id": cid,
                    "text": str(source.get("text") or source.get("passage") or ""),
                })
        return sources

    def parse_response(
        self,
        *,
        query: str,
        position_a: str,
        position_b: str,
        response_text: str,
    ) -> DebateReport:
        payload = self._extract_json(response_text)

        raw_arguments = payload.get("arguments", [])
        if not isinstance(raw_arguments, list):
            raw_arguments = []

        arguments = []
        for item in raw_arguments:
            if isinstance(item, dict) and item.get("argument"):
                arguments.append(self._parse_argument(item))

        raw_rebuttals = payload.get("rebuttals", [])
        if not isinstance(raw_rebuttals, list):
            raw_rebuttals = []

        rebuttals = []
        for item in raw_rebuttals:
            if isinstance(item, dict) and item.get("rebuttal"):
                rebuttals.append(self._parse_rebuttal(item))

        raw_openings = payload.get("opening_statements", {})
        openings = DebateOpeningStatements(
            pro=str(raw_openings.get("pro") or f"Supporting arguments for {query}").strip(),
            con=str(raw_openings.get("con") or f"Counterarguments and limitations regarding {query}").strip(),
        )

        agreements = [
            str(a).strip() for a in payload.get("agreements", []) if str(a).strip()
        ]
        disagreements = [
            str(d).strip() for d in payload.get("disagreements", []) if str(d).strip()
        ]
        unresolved = [
            str(u).strip() for u in payload.get("unresolved_questions", []) if str(u).strip()
        ]

        neutral = str(payload.get("neutral_assessment", "")).strip()
        conclusion = str(payload.get("conclusion", "")).strip()
        verdict = str(payload.get("final_verdict", conclusion or "Debate completed based on available evidence.")).strip()

        try:
            v_conf = float(payload.get("verdict_confidence", 0.85))
            v_conf = max(0.0, min(1.0, v_conf))
        except (ValueError, TypeError):
            v_conf = 0.85

        parsed_sources = self._parse_sources(payload.get("sources", []))
        # Ensure arguments contribute to sources if missing
        seen_src = {(s["document"], s["chunk_id"]) for s in parsed_sources}
        for arg in arguments:
            key = (arg.document, arg.chunk_id)
            if key not in seen_src and (arg.document or arg.chunk_id):
                seen_src.add(key)
                parsed_sources.append({
                    "document": arg.document,
                    "page": arg.page,
                    "chunk_id": arg.chunk_id,
                    "text": arg.evidence[0] if arg.evidence else arg.argument,
                })

        return DebateReport(
            query=query,
            proposition=str(payload.get("proposition") or query),
            topic=str(payload.get("topic") or query),
            position_a=str(payload.get("position_a") or position_a),
            position_b=str(payload.get("position_b") or position_b),
            opening_statements=openings,
            arguments=arguments,
            rebuttals=rebuttals,
            agreements=agreements,
            disagreements=disagreements,
            unresolved_questions=unresolved,
            neutral_assessment=neutral or verdict,
            conclusion=conclusion or verdict,
            final_verdict=verdict,
            verdict_confidence=v_conf,
            sources=parsed_sources,
            partial=False,
            notice=None,
        )

    # --------------------------------------------------------------------------
    # DETERMINISTIC NO-LLM FALLBACK ENGINE
    # --------------------------------------------------------------------------

    def build_no_llm_debate(
        self,
        *,
        query: str,
        position_a: str,
        position_b: str,
        evidence: list[dict[str, Any]],
        document_names: list[str] | None = None,
    ) -> DebateReport:
        """
        Deterministic, evidence-grounded Debate generator when LLM providers fail.
        Scans retrieval passages for supportive vs cautionary/limitation findings,
        synthesizes structured Pro and Con positions, generates rebuttals,
        identifies agreements and open questions, and provides a neutral verdict.
        """
        if not evidence:
            return DebateReport(
                query=query,
                proposition=query,
                topic="Insufficient Evidence",
                position_a=position_a,
                position_b=position_b,
                opening_statements=DebateOpeningStatements(
                    pro="No evidence available in selected documents.",
                    con="No evidence available in selected documents.",
                ),
                arguments=[],
                rebuttals=[],
                agreements=[],
                disagreements=[],
                unresolved_questions=[
                    f"Does empirical literature directly address: '{query}'?",
                ],
                neutral_assessment="Not found in available sources. The selected documents do not contain evidence relevant to this proposition.",
                conclusion="Not found in available sources.",
                final_verdict="Not found in available sources. Insufficient evidence to establish a meaningful debate.",
                verdict_confidence=0.0,
                sources=[],
                partial=False,
                notice="Not found in available sources. Insufficient evidence in the selected document(s) to conduct an evidence-grounded debate.",
            )

        pro_arguments: list[DebateArgument] = []
        con_arguments: list[DebateArgument] = []
        sources: list[dict[str, Any]] = []
        seen_chunks = set()

        # Regular expressions for affirmative and critical/limitation signals
        pro_pattern = re.compile(
            r"\b(?:demonstrates?|proves?|superior|effective|advantages?|outperforms?|achieves?|improves?|significant|enhances?|enables?|benefits?|optimal|success|strengths?)\b",
            re.IGNORECASE,
        )
        con_pattern = re.compile(
            r"\b(?:limitation|bottleneck|overhead|cost|fails?|degrades?|disadvantages?|trade-offs?|vulnerability|risks?|drawbacks?|heavy|slow|error-prone|restricted|lacks?)\b",
            re.IGNORECASE,
        )

        for item in evidence:
            cid = str(item.get("chunk_id", ""))
            doc = str(item.get("document", "Document"))
            page = item.get("page", 1)
            text = str(item.get("text", "")).strip()

            if cid and cid not in seen_chunks:
                seen_chunks.add(cid)
                sources.append({
                    "document": doc,
                    "page": page,
                    "chunk_id": cid,
                    "text": text[:200] + "..." if len(text) > 200 else text,
                })

            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 35]

            for s in sentences:
                is_pro = bool(pro_pattern.search(s))
                is_con = bool(con_pattern.search(s))

                if is_pro and len(pro_arguments) < 3:
                    pro_arguments.append(DebateArgument(
                        id=f"arg_pro_{len(pro_arguments)+1}",
                        side=DebateSide.POSITION_A,
                        title=f"Affirmative Finding: {s[:55]}...",
                        argument=s,
                        evidence_type=EvidenceType.DIRECT_EVIDENCE.value,
                        evidence=[s],
                        confidence=0.86,
                        evidence_strength=EvidenceStrength.STRONG.value,
                        document=doc,
                        page=page,
                        chunk_id=cid,
                    ))
                elif is_con and len(con_arguments) < 3:
                    con_arguments.append(DebateArgument(
                        id=f"arg_con_{len(con_arguments)+1}",
                        side=DebateSide.POSITION_B,
                        title=f"Critical Constraint: {s[:55]}...",
                        argument=s,
                        evidence_type=EvidenceType.DIRECT_EVIDENCE.value,
                        evidence=[s],
                        confidence=0.83,
                        evidence_strength=EvidenceStrength.STRONG.value,
                        document=doc,
                        page=page,
                        chunk_id=cid,
                    ))

        # If one side has no direct evidence, state that explicitly per requirements
        if not pro_arguments and evidence:
            pro_arguments.append(DebateArgument(
                id="arg_pro_none",
                side=DebateSide.POSITION_A,
                title="Absence of Direct Pro Evidence",
                argument=f"The selected research documents do not report explicit empirical advantages supporting '{position_a}'.",
                evidence_type=EvidenceType.UNSUPPORTED.value,
                evidence=[],
                confidence=0.40,
                evidence_strength=EvidenceStrength.NONE.value,
                document=evidence[0].get("document", ""),
                page=evidence[0].get("page", 1),
                chunk_id=evidence[0].get("chunk_id", ""),
            ))

        if not con_arguments and evidence:
            con_arguments.append(DebateArgument(
                id="arg_con_none",
                side=DebateSide.POSITION_B,
                title="Absence of Direct Con Evidence",
                argument=f"The selected research documents do not report explicit limitations or counterarguments challenging '{position_b}'.",
                evidence_type=EvidenceType.UNSUPPORTED.value,
                evidence=[],
                confidence=0.40,
                evidence_strength=EvidenceStrength.NONE.value,
                document=evidence[0].get("document", ""),
                page=evidence[0].get("page", 1),
                chunk_id=evidence[0].get("chunk_id", ""),
            ))

        all_args = pro_arguments + con_arguments

        # Construct direct rebuttals between Pro and Con arguments
        rebuttals: list[DebateRebuttal] = []
        if pro_arguments and con_arguments:
            # Con rebuts Pro
            rebuttals.append(DebateRebuttal(
                id="reb_1",
                side=DebateSide.POSITION_B,
                target_argument=pro_arguments[0].title,
                rebuttal=f"While Pro highlights gains, empirical evidence identifies practical constraints: {con_arguments[0].argument}",
                evidence=con_arguments[0].evidence,
                confidence=0.82,
                document=con_arguments[0].document,
                page=con_arguments[0].page,
                chunk_id=con_arguments[0].chunk_id,
            ))
            # Pro rebuts Con
            rebuttals.append(DebateRebuttal(
                id="reb_2",
                side=DebateSide.POSITION_A,
                target_argument=con_arguments[0].title,
                rebuttal=f"Despite noted limitations, the literature documents verified capabilities: {pro_arguments[0].argument}",
                evidence=pro_arguments[0].evidence,
                confidence=0.81,
                document=pro_arguments[0].document,
                page=pro_arguments[0].page,
                chunk_id=pro_arguments[0].chunk_id,
            ))

        openings = DebateOpeningStatements(
            pro=f"The evidence demonstrates key capabilities supporting: '{position_a}'. Documented findings show measurable operational efficacy.",
            con=f"Critical evaluation reveals significant trade-offs and constraints regarding: '{position_b}'. Real-world adoption faces documented bottlenecks.",
        )

        agreements = [
            f"Both perspectives acknowledge that {query.lower()} involves complex system trade-offs.",
            "All cited literature confirms that performance is sensitive to implementation constraints.",
        ]

        disagreements = [
            "The primary dispute centers on whether performance gains outweigh associated operational overheads.",
            "Disagreement remains regarding generalizability across varied deployment environments.",
        ]

        unresolved = [
            f"What are the precise resource boundaries when scaling '{query}' in production?",
            "Are the documented trade-offs inherent to the architecture or solvable with optimized engineering?",
        ]

        # Neutral assessment identifying which arguments have stronger evidence
        pro_strong = sum(1 for a in pro_arguments if a.evidence_strength == "STRONG")
        con_strong = sum(1 for a in con_arguments if a.evidence_strength == "STRONG")

        if pro_strong > con_strong:
            neutral = f"Arguments in favor of '{position_a}' currently exhibit stronger empirical grounding ({pro_strong} direct findings vs {con_strong} constraints) in the analyzed literature."
        elif con_strong > pro_strong:
            neutral = f"Counterarguments highlighting limitations for '{position_b}' carry stronger empirical evidence ({con_strong} direct limitations vs {pro_strong} advantages) in the analyzed literature."
        else:
            neutral = "Both positions demonstrate comparable evidence strength across the reviewed passages, with affirmative findings balanced by documented limitations."

        conclusion = (
            f"Synthesizing retrieved findings for '{query}': while evidence establishes specific capabilities, "
            f"practical adoption requires balancing these gains against documented bottlenecks. "
            f"Evidence strength should not be conflated with certainty, as broader validation across unexamined domains remains necessary."
        )

        return DebateReport(
            query=query,
            proposition=query,
            topic=query,
            position_a=position_a,
            position_b=position_b,
            opening_statements=openings,
            arguments=all_args,
            rebuttals=rebuttals,
            agreements=agreements,
            disagreements=disagreements,
            unresolved_questions=unresolved,
            neutral_assessment=neutral,
            conclusion=conclusion,
            final_verdict=conclusion,
            verdict_confidence=0.82,
            sources=sources,
            partial=True,
            notice="This debate report was generated deterministically from extracted document evidence because external AI models were unavailable or exhausted.",
        )
