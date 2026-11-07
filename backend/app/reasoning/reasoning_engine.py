"""
UNKNOWN Project - AI Reasoning Engine

Srinidhi's reasoning module.

Pipeline:
    Reasoning Query
        -> Query Analysis & Decomposition (Planning)
        -> Multi-Step Hybrid Retrieval with Step-Level Evidence Mapping
        -> Evidence Validation, Deduplication, and Scoring
        -> Step-by-Step Grounded Reasoning & Cross-Document Conflict Analysis
        -> Overarching Synthesis & Final Conclusion
        -> Accuracy Engine Integration (Confidence & Sources)
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.rag.confidence import build_sources, compute_confidence
from app.rag.context_builder import ContextBuilder
from app.rag.hybrid_search import HybridSearch
from app.rag.logger import logger
from app.rag.prompt_engine import PromptEngine, QueryType


INSUFFICIENT_EVIDENCE_MESSAGE = (
    "The retrieved context does not contain enough information."
)

GENERATION_FAILURE_MESSAGE = (
    "The answer could not be generated reliably from the "
    "retrieved context. Please try again."
)


class ReasoningEngine:
    """
    Evidence-grounded multi-step reasoning layer built on top of the existing RAG.

    Responsibilities:
    - Analyze and decompose simple vs. complex questions into an ordered plan.
    - Retrieve and map evidence for individual sub-questions.
    - Validate, score, and deduplicate retrieved evidence.
    - Execute step-by-step grounded reasoning without fabricating facts.
    - Detect conflicts and discrepancies across multiple documents.
    - Detect gaps and communicate uncertainty honestly.
    - Compute calibrated confidence scores and formatted source metadata.
    """

    def __init__(
        self,
        retriever: HybridSearch,
        context_builder: ContextBuilder,
        prompt_engine: PromptEngine,
        gemini: Any = None,
        llm: Any = None,
        max_subquestions: int = 3,
        top_k: int = 5,
    ) -> None:
        if max_subquestions < 1:
            raise ValueError(
                "max_subquestions must be at least 1."
            )

        if top_k < 1:
            raise ValueError(
                "top_k must be at least 1."
            )

        self.retriever = retriever
        self.context_builder = context_builder
        self.prompt_engine = prompt_engine
        self.gemini = gemini or llm
        self.llm = llm or gemini
        self.max_subquestions = max_subquestions
        self.top_k = top_k

        logger.info(
            "UNKNOWN Reasoning Engine initialized."
        )

    # =========================================================
    # LLM CALL HELPER (Supports GeminiEngine, Orchestrator, & Mock)
    # =========================================================

    def _call_llm(self, prompt: str, structured: bool = False) -> str:
        """
        Execute an LLM call using either LLMOrchestrator, GeminiEngine,
        or any compatible interface. Returns string content.
        """
        client = self.llm or self.gemini
        if client is None:
            return ""

        try:
            if structured and hasattr(client, "generate_structured"):
                resp = client.generate_structured(prompt)
                if hasattr(resp, "success") and not resp.success:
                    logger.warning(f"Structured generation error: {getattr(resp, 'error', '')}")
                    return ""
                return resp.answer if hasattr(resp, "answer") else str(resp)

            if hasattr(client, "generate"):
                resp = client.generate(prompt)
                if hasattr(resp, "success") and not resp.success:
                    logger.warning(f"Generation error: {getattr(resp, 'error', '')}")
                    return ""
                return resp.answer if hasattr(resp, "answer") else str(resp)

            if callable(client):
                return str(client(prompt))

        except Exception as error:
            logger.error(f"Reasoning LLM call failed: {error}")

        return ""

    # =========================================================
    # QUERY ANALYSIS & DECOMPOSITION (PLANNING)
    # =========================================================

    def analyze_and_plan(
        self,
        query: str,
    ) -> tuple[list[str], list[dict[str, Any]]]:
        """
        Analyze question complexity and generate an ordered reasoning plan.

        Returns:
            tuple of (subquestions_list, plan_list)
        """
        decomposition_prompt = f"""
You are the query analysis and decomposition component of UNKNOWN AI.
Analyze the user's question and determine the logical steps and sub-questions needed for evidence retrieval and reasoning.

Rules:
- For simple or single-objective questions, produce 1 or 2 focused sub-questions. Do not overcomplicate straightforward questions.
- For complex, multi-hop, or comparative questions, break the problem into at most {self.max_subquestions} sequential, non-circular sub-questions.
- Each sub-question must target verifiable evidence from documents.
- Order dependent steps logically so earlier steps establish facts needed by later steps.
- Provide a short title (2-6 words) for each step.
- Return ONLY valid JSON.

Required format:
{{
    "complexity": "simple" or "complex",
    "subquestions": [
        "question 1",
        "question 2"
    ],
    "plan": [
        {{
            "step_number": 1,
            "subquestion": "question 1",
            "title": "Step Title",
            "objective": "Objective of this step"
        }}
    ]
}}

Main question:
{query}
""".strip()

        try:
            response = self._call_llm(decomposition_prompt, structured=True)

            if isinstance(response, str) and response.strip():
                cleaned = self._clean_json(response)
                data = json.loads(cleaned)

                if isinstance(data, dict):
                    raw_questions = data.get("subquestions", [])
                    raw_plan = data.get("plan", [])

                    cleaned_questions: list[str] = []
                    if isinstance(raw_questions, list):
                        for q in raw_questions:
                            if isinstance(q, str) and q.strip():
                                cleaned_questions.append(q.strip())

                    cleaned_questions = self._deduplicate_questions(cleaned_questions)
                    if cleaned_questions:
                        cleaned_questions = cleaned_questions[: self.max_subquestions]

                        # Build or sanitize plan items
                        plan: list[dict[str, Any]] = []
                        if isinstance(raw_plan, list) and len(raw_plan) > 0:
                            for i, item in enumerate(raw_plan):
                                if isinstance(item, dict) and i < len(cleaned_questions):
                                    sq = cleaned_questions[i]
                                    title = item.get("title") or f"Step {i + 1}: Analyze Topic"
                                    obj = item.get("objective") or sq
                                    plan.append({
                                        "step_number": i + 1,
                                        "subquestion": sq,
                                        "title": str(title).strip(),
                                        "objective": str(obj).strip(),
                                    })

                        if len(plan) != len(cleaned_questions):
                            plan = [
                                {
                                    "step_number": i + 1,
                                    "subquestion": sq,
                                    "title": f"Step {i + 1}: {sq[:35].rstrip('?')}...",
                                    "objective": sq,
                                }
                                for i, sq in enumerate(cleaned_questions)
                            ]

                        return cleaned_questions, plan

            logger.warning(
                "Reasoning decomposition returned empty or invalid response. Using query fallback."
            )

        except (json.JSONDecodeError, ValueError, TypeError, AttributeError) as error:
            logger.warning(f"Reasoning decomposition parsing failed: {error}")
        except Exception as error:
            logger.error(f"Query decomposition failed: {error}")

        # Safe fallback: single-step plan using the original query.
        fallback_plan = [
            {
                "step_number": 1,
                "subquestion": query,
                "title": "Evidence Retrieval & Analysis",
                "objective": query,
            }
        ]
        return [query], fallback_plan

    def decompose_query(
        self,
        query: str,
    ) -> list[str]:
        """
        Break a complex reasoning query into smaller retrieval-oriented sub-questions.
        Preserved for backward compatibility.
        """
        subquestions, _ = self.analyze_and_plan(query)
        return subquestions

    # =========================================================
    # MULTI-QUERY RETRIEVAL WITH STEP MAPPING
    # =========================================================

    def retrieve_evidence_with_mapping(
        self,
        subquestions: list[str],
        doc_filter: list[str] | set[str] | None = None,
        user_id: str | None = None,
        exclude_test_docs: bool | None = None,
        document_names: list[str] | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
        """
        Retrieve evidence for each sub-question using HybridSearch.
        Returns:
            tuple of (all_ranked_evidence, mapping_of_subquestion_to_evidence_chunks)
        """
        if exclude_test_docs is None:
            exclude_test_docs = True if user_id is not None else False

        evidence_by_chunk: dict[str, dict[str, Any]] = {}
        step_evidence: dict[str, list[dict[str, Any]]] = {}

        effective_filter = doc_filter if doc_filter is not None else document_names
        allowed_docs = set(effective_filter) if effective_filter is not None else None

        for subquestion in subquestions:
            if not isinstance(subquestion, str) or not subquestion.strip():
                continue

            logger.info(f"Reasoning retrieval: {subquestion}")
            step_chunks: list[dict[str, Any]] = []

            try:
                results = self.retriever.search(
                    subquestion,
                    top_k=self.top_k,
                    doc_filter=doc_filter,
                    user_id=user_id,
                    exclude_test_docs=exclude_test_docs,
                )
            except TypeError:
                try:
                    results = self.retriever.search(
                        subquestion,
                        self.top_k,
                        document_names=list(allowed_docs) if allowed_docs else None,
                    )
                except TypeError:
                    results = self.retriever.search(subquestion, self.top_k)

            for result in results:
                if not isinstance(result, dict):
                    continue

                evidence_text = result.get("text")
                if not isinstance(evidence_text, str) or not evidence_text.strip():
                    continue

                chunk_id = result.get("chunk_id")
                if chunk_id is None:
                    continue

                if allowed_docs is not None:
                    doc_name = result.get("document", "")
                    if doc_name not in allowed_docs:
                        continue

                key = str(chunk_id)
                current_score = self._score(result.get("hybrid_score", 0.0))
                existing = evidence_by_chunk.get(key)

                if existing is None:
                    evidence_by_chunk[key] = result
                else:
                    existing_score = self._score(existing.get("hybrid_score", 0.0))
                    if current_score > existing_score:
                        evidence_by_chunk[key] = result

                step_chunks.append(result)

            step_evidence[subquestion] = step_chunks

        evidence = list(evidence_by_chunk.values())
        evidence.sort(
            key=lambda result: self._score(result.get("hybrid_score", 0.0)),
            reverse=True,
        )

        logger.info(
            f"Reasoning evidence validation retained {len(evidence)} unique chunks."
        )

        return evidence, step_evidence

    def retrieve_evidence(
        self,
        subquestions: list[str],
        doc_filter: list[str] | set[str] | None = None,
        user_id: str | None = None,
        exclude_test_docs: bool | None = None,
        document_names: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve deduplicated evidence chunks across all sub-questions.
        Preserved for backward compatibility.
        """
        evidence, _ = self.retrieve_evidence_with_mapping(
            subquestions,
            doc_filter=doc_filter,
            user_id=user_id,
            exclude_test_docs=exclude_test_docs,
            document_names=document_names,
        )
        return evidence

    # =========================================================
    # BUILD REASONING PROMPTS
    # =========================================================

    def build_reasoning_prompt(
        self,
        query: str,
        evidence: list[dict[str, Any]],
    ) -> str:
        """
        Reuse the existing ContextBuilder and PromptEngine
        to construct a grounded reasoning prompt.
        Preserved for backward compatibility.
        """
        context = self.context_builder.build(evidence)

        prompt = self.prompt_engine.build_prompt(
            query=query,
            context=context,
            query_type=QueryType.REASONING,
        )

        prompt += """

Additional reasoning requirements:
- Answer the main question, not the sub-questions separately.
- Connect the retrieved evidence logically.
- Use only information supported by the retrieved context.
- Do not introduce unsupported facts or assumptions.
- Do not fabricate sources, quotations, or citations.
- Do not reveal hidden chain-of-thought.
- Give a concise explanation of the reasoning outcome.
- If the evidence does not support an answer, explicitly state:
  "The retrieved context does not contain enough information."
""".strip()

        return prompt

    def build_multi_step_reasoning_prompt(
        self,
        query: str,
        plan: list[dict[str, Any]],
        step_evidence: dict[str, list[dict[str, Any]]],
        compact: bool = False,
    ) -> str:
        """
        Construct a multi-step evidence-grounded prompt that guides the model
        to analyze each step, identify cross-document conflicts, and synthesize
        a cohesive conclusion. Deduplicates evidence passages across steps to respect
        LLM token budgets (e.g. Groq TPM limits).
        """
        max_chunk_chars = 400 if compact else 800
        max_chunks_per_step = 2 if compact else self.top_k

        # 1. Collect and deduplicate unique evidence chunks across all steps
        unique_chunks: list[dict[str, Any]] = []
        seen_cids: set[str] = set()

        for item in plan:
            sq = item["subquestion"]
            chunks = step_evidence.get(sq, [])
            for c in chunks[:max_chunks_per_step]:
                cid = str(c.get("chunk_id", "")).strip()
                if cid and cid not in seen_cids:
                    seen_cids.add(cid)
                    unique_chunks.append(c)
                elif not cid and c not in unique_chunks:
                    unique_chunks.append(c)

        # 2. Build Deduplicated Evidence Catalog
        evidence_snippets: list[str] = []
        for c in unique_chunks:
            cid = c.get("chunk_id", "N/A")
            doc = c.get("document", "Unknown")
            page = c.get("page", "N/A")
            raw_text = str(c.get("text", "")).strip()
            if len(raw_text) > max_chunk_chars:
                text = raw_text[:max_chunk_chars] + "... [truncated for token budget]"
            else:
                text = raw_text
            evidence_snippets.append(
                f"[Chunk ID: {cid}] Document: {doc} (Page {page}):\n{text}"
            )

        if not evidence_snippets:
            evidence_catalog = "[No direct evidence chunks found]"
        else:
            evidence_catalog = "\n\n".join(evidence_snippets)

        # 3. Build Ordered Reasoning Steps referencing Chunk IDs
        steps_blocks: list[str] = []
        for item in plan:
            sq = item["subquestion"]
            title = item.get("title", sq)
            step_num = item.get("step_number", 1)
            chunks = step_evidence.get(sq, [])
            cids = [
                str(c.get("chunk_id", "N/A"))
                for c in chunks[:max_chunks_per_step]
                if c.get("chunk_id")
            ]

            if not cids:
                steps_blocks.append(
                    f"### STEP {step_num}: {title}\n"
                    f"Sub-question: {sq}\n"
                    f"Relevant Evidence Chunks: [No direct evidence chunks found for this sub-question]"
                )
            else:
                steps_blocks.append(
                    f"### STEP {step_num}: {title}\n"
                    f"Sub-question: {sq}\n"
                    f"Relevant Evidence Chunks: {', '.join(cids)}"
                )

        steps_section = "\n\n".join(steps_blocks)

        prompt = f"""
You are UNKNOWN's Evidence-Grounded Multi-Step AI Reasoning Engine.
Analyze the following user question by reasoning step-by-step across the retrieved document evidence.

MAIN QUESTION:
{query}

RETRIEVED EVIDENCE CATALOG:
{evidence_catalog}

ORDERED REASONING STEPS:
{steps_section}

STRICT GROUNDING & REASONING INSTRUCTIONS:
1. Grounding: Answer strictly using ONLY the retrieved evidence passages above. Never hallucinate facts, dates, numeric figures, or citations.
2. Inferences vs Established Facts: Clearly distinguish directly supported factual statements from reasonable deductive inferences. Never state an unsupported assumption as fact.
3. Unsupported Claims: If evidence is missing or insufficient for any sub-question, explicitly declare it as unknown or unverified.
4. Cross-Document Conflicts: If different documents disagree or report contrasting measurements or claims, explicitly explain the contradiction rather than arbitrarily picking one.
5. Intermediate Findings: For each sub-question, provide a grounded intermediate finding and list the chunk IDs supporting it.
6. Overarching Synthesis: Unify the step findings into a clear, cohesive explanation.
7. Final Conclusion: Answer the main user question directly and concisely based on the synthesized evidence.

Output strictly as a valid JSON object in the following format:
{{
    "intermediate_findings": [
        {{
            "subquestion": "text of sub-question 1",
            "synthesis": "grounded finding for step 1",
            "evidence_chunk_ids": ["chunk_id_1", "chunk_id_2"]
        }}
    ],
    "conflicts": [
        "Description of any contradiction found between sources (leave empty if none)"
    ],
    "uncertainty": "Explanation of any missing evidence or caveats (null or empty string if none)",
    "synthesis": "Cohesive overarching synthesis connecting all steps",
    "final_answer": "Definitive grounded answer to the main question"
}}
""".strip()

        return prompt

    # =========================================================
    # CONFLICT & DISCREPANCY DETECTION
    # =========================================================

    def detect_conflicts(
        self,
        evidence: list[dict[str, Any]],
    ) -> list[str]:
        """
        Scan retrieved evidence chunks across multiple documents to identify
        potential contradictions or discrepancies in reported figures or claims.
        """
        conflicts: list[str] = []
        if len(evidence) < 2:
            return conflicts

        docs_present = {c.get("document") for c in evidence if c.get("document")}
        if len(docs_present) < 2:
            return conflicts

        # Heuristic polarity checks across documents
        polarities = [
            (r"\b(?:increase|increases|increased|higher|growth|boost)\b",
             r"\b(?:decrease|decreases|decreased|lower|reduction|drop)\b"),
            (r"\b(?:effective|beneficial|superior|successful)\b",
             r"\b(?:ineffective|detrimental|inferior|failed)\b"),
            (r"\b(?:supported|confirmed|proven|valid)\b",
             r"\b(?:refuted|contradicted|disproven|invalid)\b"),
        ]

        doc_texts: dict[str, str] = {}
        for c in evidence:
            doc = c.get("document")
            if doc:
                doc_texts[doc] = doc_texts.get(doc, "") + " " + str(c.get("text", ""))

        docs = list(doc_texts.keys())
        for i in range(len(docs)):
            for j in range(i + 1, len(docs)):
                d1, d2 = docs[i], docs[j]
                t1, t2 = doc_texts[d1].lower(), doc_texts[d2].lower()

                for pos_pattern, neg_pattern in polarities:
                    if re.search(pos_pattern, t1) and re.search(neg_pattern, t2):
                        conflicts.append(
                            f"Differing findings between {d1} and {d2} regarding trend or efficacy."
                        )
                        break
                    elif re.search(neg_pattern, t1) and re.search(pos_pattern, t2):
                        conflicts.append(
                            f"Differing findings between {d1} and {d2} regarding trend or efficacy."
                        )
                        break

        return list(dict.fromkeys(conflicts))

    # =========================================================
    # SOURCE METADATA FORMATTING
    # =========================================================

    def format_sources(
        self,
        evidence: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Format ranked evidence into source dictionaries preserving scores and coordinates.
        """
        sources: list[dict[str, Any]] = []
        for rank, result in enumerate(evidence[: self.top_k], start=1):
            sources.append({
                "rank": rank,
                "document": result.get("document", "Unknown"),
                "page": result.get("page", "N/A"),
                "chunk_id": result.get("chunk_id", "N/A"),
                "hybrid_score": self._score(result.get("hybrid_score", 0.0)),
                "bm25_score": self._score(result.get("bm25_score", 0.0)),
                "faiss_score": self._score(result.get("faiss_score", 0.0)),
                "text": result.get("text", ""),
            })
        return sources

    # =========================================================
    # COMPLETE REASONING PIPELINE
    # =========================================================

    def reason(
        self,
        query: str,
        doc_filter: list[str] | set[str] | None = None,
        user_id: str | None = None,
        exclude_test_docs: bool | None = None,
        document_names: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Execute the complete multi-step reasoning pipeline.

        Pipeline:
            1. Validate query input
            2. Analyze complexity and generate ordered reasoning plan
            3. Retrieve evidence mapped to each sub-question
            4. Check for usable evidence (abstain if none)
            5. Execute grounded reasoning synthesis
            6. Parse structured findings, conflicts, and uncertainty
            7. Format sources and compute confidence
        """
        if exclude_test_docs is None:
            exclude_test_docs = True if user_id is not None else False

        if not isinstance(query, str):
            raise TypeError("query must be a string.")

        query = query.strip()
        if not query:
            raise ValueError("query cannot be empty.")

        logger.info(f"Starting reasoning query: {query}")

        # 1. Query Analysis & Ordered Plan
        subquestions, plan = self.analyze_and_plan(query)
        logger.info(f"Generated {len(subquestions)} reasoning subquestions.")

        # 2. Multi-Step Retrieval
        evidence, step_evidence = self.retrieve_evidence_with_mapping(
            subquestions,
            doc_filter=doc_filter,
            user_id=user_id,
            exclude_test_docs=exclude_test_docs,
            document_names=document_names,
        )

        # 3. Handle Missing Usable Evidence
        if not evidence:
            logger.warning("No usable evidence was retrieved. Skipping answer generation.")
            steps = [
                {
                    "id": f"step_{i + 1}",
                    "title": item.get("title", f"Step {i + 1}"),
                    "description": "No supporting evidence found in available documents.",
                    "status": "incomplete",
                }
                for i, item in enumerate(plan)
            ]
            sub_questions = [
                {
                    "id": f"subq_{i + 1}",
                    "question": sq,
                    "evidenceIds": [],
                    "synthesis": INSUFFICIENT_EVIDENCE_MESSAGE,
                }
                for i, sq in enumerate(subquestions)
            ]
            return {
                "query": query,
                "subquestions": subquestions,
                "answer": INSUFFICIENT_EVIDENCE_MESSAGE,
                "sources": [],
                "steps": steps,
                "sub_questions": sub_questions,
                "synthesis": INSUFFICIENT_EVIDENCE_MESSAGE,
                "final_answer": INSUFFICIENT_EVIDENCE_MESSAGE,
                "confidence": 0.0,
                "conflicts": [],
                "uncertainty": "The retrieved context does not contain enough information.",
            }

        # 4. Build Grounded Multi-Step Reasoning Prompt
        prompt = self.build_multi_step_reasoning_prompt(
            query=query,
            plan=plan,
            step_evidence=step_evidence,
        )

        # 5. Generate Reasoning Answer Safely
        answer = ""
        synthesis = ""
        final_answer = ""
        conflicts: list[str] = []
        uncertainty: str | None = None
        intermediate_map: dict[str, dict[str, Any]] = {}

        try:
            generated_response = self._call_llm(prompt)
            if not isinstance(generated_response, str) or not generated_response.strip():
                # Retry with compact multi-step prompt first if initial prompt was rejected or empty
                logger.warning("Multi-step prompt returned empty. Retrying with compact reasoning prompt.")
                compact_prompt = self.build_multi_step_reasoning_prompt(
                    query=query,
                    plan=plan,
                    step_evidence=step_evidence,
                    compact=True,
                )
                generated_response = self._call_llm(compact_prompt)

            if not isinstance(generated_response, str) or not generated_response.strip():
                # Fallback to standard prompt if compact multi-step call also returns empty
                logger.warning("Compact prompt returned empty. Falling back to build_reasoning_prompt.")
                fallback_prompt = self.build_reasoning_prompt(query=query, evidence=evidence)
                generated_response = self._call_llm(fallback_prompt)

            if isinstance(generated_response, str) and generated_response.strip():
                raw_text = generated_response.strip()
                cleaned = self._clean_json(raw_text)

                try:
                    data = json.loads(cleaned)
                    if isinstance(data, dict):
                        f_ans = data.get("final_answer") or data.get("answer")
                        synth = data.get("synthesis")
                        if isinstance(f_ans, str) and f_ans.strip():
                            final_answer = f_ans.strip()
                            answer = final_answer
                        if isinstance(synth, str) and synth.strip():
                            synthesis = synth.strip()
                        c_list = data.get("conflicts")
                        if isinstance(c_list, list):
                            conflicts.extend(str(c) for c in c_list if c)
                        unc = data.get("uncertainty")
                        if isinstance(unc, str) and unc.strip():
                            uncertainty = unc.strip()
                        findings = data.get("intermediate_findings")
                        if isinstance(findings, list):
                            for f in findings:
                                if isinstance(f, dict) and "subquestion" in f:
                                    intermediate_map[f["subquestion"].strip().lower()] = {
                                        "synthesis": f.get("synthesis", ""),
                                        "evidenceIds": f.get("evidence_chunk_ids", []),
                                    }
                except (json.JSONDecodeError, ValueError, TypeError):
                    # Plain string returned (e.g. from mock LLM generate())
                    answer = raw_text
                    synthesis = answer
                    final_answer = answer

            if not answer:
                logger.warning("Reasoning model returned an empty answer.")
                answer = GENERATION_FAILURE_MESSAGE
                synthesis = GENERATION_FAILURE_MESSAGE
                final_answer = GENERATION_FAILURE_MESSAGE

        except Exception as error:
            logger.error(f"Reasoning answer generation failed: {error}")
            answer = GENERATION_FAILURE_MESSAGE
            synthesis = GENERATION_FAILURE_MESSAGE
            final_answer = GENERATION_FAILURE_MESSAGE

        # 6. Build Structured Steps & Sub-Questions
        sub_questions: list[dict[str, Any]] = []
        steps: list[dict[str, Any]] = []
        statuses: list[str] = []

        for i, item in enumerate(plan):
            sq = item["subquestion"]
            sq_key = sq.strip().lower()
            step_chunks = step_evidence.get(sq, [])
            has_evidence = len(step_chunks) > 0
            statuses.append("sufficient" if has_evidence else "insufficient")

            evidence_ids = [str(c.get("chunk_id")) for c in step_chunks if c.get("chunk_id")]

            if sq_key in intermediate_map and intermediate_map[sq_key]["synthesis"]:
                step_synthesis = intermediate_map[sq_key]["synthesis"]
                if intermediate_map[sq_key]["evidenceIds"]:
                    evidence_ids = [str(eid) for eid in intermediate_map[sq_key]["evidenceIds"]]
            elif has_evidence:
                top_text = step_chunks[0].get("text", "").strip()
                step_synthesis = f"Grounded in {step_chunks[0].get('document', 'document')}: {top_text[:140]}..."
            else:
                step_synthesis = "No direct evidence found for this sub-question."

            sub_questions.append({
                "id": f"subq_{i + 1}",
                "question": sq,
                "evidenceIds": evidence_ids,
                "synthesis": step_synthesis,
            })

            steps.append({
                "id": f"step_{i + 1}",
                "title": item.get("title", f"Step {i + 1}: Analyze Sub-question"),
                "description": step_synthesis,
                "status": "complete" if has_evidence else "incomplete",
            })

        # Overarching final synthesis step
        steps.append({
            "id": f"step_{len(plan) + 1}",
            "title": "Synthesis & Conclusion",
            "description": "Synthesized evidence across all steps and derived final grounded conclusion.",
            "status": "complete" if any(st == "sufficient" for st in statuses) else "incomplete",
        })

        # 7. Format Sources & Detect Conflicts
        sources = self.format_sources(evidence[: self.top_k])
        detected_conflicts = self.detect_conflicts(evidence)
        for dc in detected_conflicts:
            if dc not in conflicts:
                conflicts.append(dc)

        # 8. Check Uncertainty
        if not uncertainty:
            unsupported = [sq for sq, st in zip(subquestions, statuses) if st == "insufficient"]
            if unsupported and len(unsupported) < len(subquestions):
                uncertainty = (
                    f"Partial evidence available: insufficient documents found for "
                    f"{len(unsupported)} of {len(subquestions)} sub-questions."
                )

        # 9. Unified Confidence Score
        confidence_obj = compute_confidence(
            statuses=statuses,
            sources=sources,
            conflicts=conflicts,
        )
        confidence_score = round(confidence_obj.score, 1)

        logger.info(
            f"Reasoning completed with {len(sources)} sources and {confidence_score}% confidence."
        )

        return {
            "query": query,
            "subquestions": subquestions,
            "answer": answer,
            "sources": sources,
            "steps": steps,
            "sub_questions": sub_questions,
            "synthesis": synthesis or answer,
            "final_answer": final_answer or answer,
            "confidence": confidence_score,
            "conflicts": conflicts,
            "uncertainty": uncertainty,
        }

    # =========================================================
    # HELPERS
    # =========================================================

    @staticmethod
    def _clean_json(
        response: str,
    ) -> str:
        """
        Remove Markdown code fences if the LLM returns JSON inside a fenced code block.
        """
        response = response.strip()
        response = re.sub(
            r"^```(?:json)?\s*",
            "",
            response,
            flags=re.IGNORECASE,
        )
        response = re.sub(
            r"\s*```$",
            "",
            response,
        )
        return response.strip()

    @staticmethod
    def _deduplicate_questions(
        questions: list[str],
    ) -> list[str]:
        """
        Remove duplicate sub-questions while preserving order.
        """
        seen = set()
        result = []
        for question in questions:
            normalized = question.lower().strip()
            if normalized not in seen:
                seen.add(normalized)
                result.append(question)
        return result

    @staticmethod
    def _score(
        value: Any,
    ) -> float:
        """
        Convert a retrieval score safely to float.
        Invalid or missing scores are treated as zero.
        """
        try:
            return float(value)
        except (TypeError, ValueError, OverflowError):
            return 0.0
