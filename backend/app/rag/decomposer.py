"""
UNKNOWN X – Query Decomposer with Sufficiency Checking (Task A4)

Pipeline
--------
1. decompose(query, llm)  →  up to 5 sub-questions  (LLM JSON call)
2. For each sub-question:
     a. retrieve top-k chunks via the caller-supplied retriever
     b. compute n  = # independent source papers (deduped by DOI / title hash)
        compute r  = mean reranker_score in [0,1] (fallback: hybrid_score)
     c. classify status:
          sufficient   if n >= DECOMPOSE_MIN_PAPERS   and r >= TAU_R
          weak         if n >= 1                       and r >= TAU_R / 2
          insufficient otherwise
     d. if insufficient → reformulate, search again, repeat ≤ DECOMPOSE_MAX_ROUNDS
        if still insufficient → add to gaps[], generate nothing for it
3. All rounds are captured in a DecompositionTrace object.

Config (env-overridable, all have sensible defaults):
    DECOMPOSE_MAX_SUBQS      max sub-questions to generate (default 5)
    DECOMPOSE_TOP_K          top-k per retrieval (default 10)
    DECOMPOSE_MIN_PAPERS     min independent sources for "sufficient" (default 2)
    DECOMPOSE_TAU_R          rerank threshold τ_r (default 0.50)
    DECOMPOSE_MAX_ROUNDS     max reformulation rounds per sub-question (default 2)
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from app.rag.logger import logger

# ---------------------------------------------------------------------------
# Config (read once at import time; tests can override via env before import)
# ---------------------------------------------------------------------------

DECOMPOSE_MAX_SUBQS: int = int(os.environ.get("DECOMPOSE_MAX_SUBQS", "5"))
DECOMPOSE_TOP_K: int = int(os.environ.get("DECOMPOSE_TOP_K", "10"))
DECOMPOSE_MIN_PAPERS: int = int(os.environ.get("DECOMPOSE_MIN_PAPERS", "2"))
DECOMPOSE_TAU_R: float = float(os.environ.get("DECOMPOSE_TAU_R", "0.50"))
DECOMPOSE_MAX_ROUNDS: int = int(os.environ.get("DECOMPOSE_MAX_ROUNDS", "2"))


# ---------------------------------------------------------------------------
# Protocols – keeps the decomposer independent of real LLM / retriever impls
# ---------------------------------------------------------------------------

class LLMCallable(Protocol):
    """Minimal interface the decomposer needs from any LLM provider."""
    def generate(self, prompt: str, system: str | None = None) -> Any:
        """Return an object with `.answer: str` and `.success: bool`."""
        ...


class RetrieverCallable(Protocol):
    """Minimal interface for any retriever."""
    def search(self, query: str, top_k: int = DECOMPOSE_TOP_K) -> list[dict]:
        """Return chunks ordered best-first. Each chunk is a dict."""
        ...


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class RetrievalRound:
    """One retrieval attempt for a sub-question."""
    round_number: int          # 1-based
    query_used: str            # the (possibly reformulated) query
    chunks_retrieved: int
    n: int                     # # independent source papers
    r: float                   # mean rerank score [0,1]
    status: str                # "sufficient" | "weak" | "insufficient"


@dataclass
class SubQuestionResult:
    """Outcome for a single sub-question."""
    sub_question: str
    final_status: str          # "sufficient" | "weak" | "insufficient"
    rounds: list[RetrievalRound] = field(default_factory=list)
    chunks: list[dict] = field(default_factory=list)   # best chunks available
    added_to_gaps: bool = False


@dataclass
class DecompositionTrace:
    """Full trace of the decomposition + sufficiency pipeline."""
    original_query: str
    sub_questions: list[str] = field(default_factory=list)
    results: list[SubQuestionResult] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)   # sub-questions with no evidence

    @property
    def total_rounds(self) -> int:
        return sum(len(r.rounds) for r in self.results)

    def to_dict(self) -> dict:
        return {
            "original_query": self.original_query,
            "sub_questions": self.sub_questions,
            "gaps": self.gaps,
            "total_rounds": self.total_rounds,
            "results": [
                {
                    "sub_question": r.sub_question,
                    "final_status": r.final_status,
                    "added_to_gaps": r.added_to_gaps,
                    "rounds": [
                        {
                            "round_number": rd.round_number,
                            "query_used": rd.query_used,
                            "chunks_retrieved": rd.chunks_retrieved,
                            "n": rd.n,
                            "r": round(rd.r, 4),
                            "status": rd.status,
                        }
                        for rd in r.rounds
                    ],
                }
                for r in self.results
            ],
        }


# ---------------------------------------------------------------------------
# LLM prompts
# ---------------------------------------------------------------------------

_DECOMPOSE_SYSTEM = """\
You are a research query decomposer.
Return ONLY valid JSON — no markdown, no commentary.
Schema: {{"sub_questions": ["<question 1>", "<question 2>", ...]}}
Rules:
- Each sub-question must be answerable independently.
- Maximum {max_subqs} sub-questions.
- If the query is already atomic, return one sub-question.
""".strip()

_DECOMPOSE_USER = """\
Decompose this research query into up to {max_subqs} independent sub-questions:

Query: {query}
""".strip()

_REFORMULATE_SYSTEM = """\
You are a search query reformulator.
Return ONLY valid JSON — no markdown, no commentary.
Schema: {{"reformulated": "<improved query>"}}
Make the query more specific, use synonyms, add domain context.
""".strip()

_REFORMULATE_USER = """\
The following sub-question retrieved insufficient evidence.
Reformulate it to be more likely to match academic passages.

Original sub-question: {sub_question}
Previous attempt query: {prev_query}
""".strip()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _norm_text(text: str) -> str:
    """NFKC-normalise and lower-case."""
    return unicodedata.normalize("NFKC", text).lower().strip()


def _extract_json(text: str) -> dict:
    """
    Robustly extract the first JSON object from LLM output.
    Handles markdown fences and surrounding prose.
    """
    # Strip ```json ... ``` fences
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = text.replace("```", "")
    # Find first { ... }
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in: {text!r}")
    return json.loads(match.group())


def _paper_key(chunk: dict) -> str:
    """
    Return a deduplication key for a chunk's source paper.

    Priority:
      1. DOI (lowercased, stripped)
      2. title hash (normalised title, first 80 chars)
      3. document filename
    """
    doi = (chunk.get("doi") or chunk.get("metadata", {}).get("doi") or "").strip().lower()
    if doi:
        return f"doi:{doi}"
    title = (chunk.get("title") or chunk.get("metadata", {}).get("title") or "").strip()
    if title:
        return f"title:{_norm_text(title)[:80]}"
    return f"doc:{chunk.get('document', chunk.get('chunk_id', '?'))}"


def _compute_n_r(chunks: list[dict]) -> tuple[int, float]:
    """
    n = number of independent source papers (deduped by DOI / title).
    r = mean reranker_score in [0,1]; falls back to hybrid_score, then rrf_score, then rank-based.
    """
    seen_papers: set[str] = set()
    scores: list[float] = []

    for chunk in chunks:
        seen_papers.add(_paper_key(chunk))

        # Best available score proxy → clamp to [0,1]
        score: float
        if "reranker_score" in chunk:
            # CrossEncoder logit → sigmoid to map to [0,1]
            import math
            raw = float(chunk["reranker_score"])
            score = 1.0 / (1.0 + math.exp(-raw))
        elif "hybrid_score" in chunk:
            score = float(chunk["hybrid_score"])
        elif "rrf_score" in chunk:
            # RRF scores are small (≈ 0.016); normalise by max possible 1/61
            raw = float(chunk["rrf_score"])
            score = min(raw / (1.0 / 61), 1.0)
        else:
            # Fall back: rank-based decay (rank 1 → 1.0, rank 10 → 0.1)
            rank = int(chunk.get("rank", len(scores) + 1))
            score = max(0.0, 1.0 - (rank - 1) * 0.1)

        scores.append(max(0.0, min(1.0, score)))

    n = len(seen_papers)
    r = sum(scores) / len(scores) if scores else 0.0
    return n, r


def _classify_status(n: int, r: float) -> str:
    """Classify retrieval sufficiency."""
    if n >= DECOMPOSE_MIN_PAPERS and r >= DECOMPOSE_TAU_R:
        return "sufficient"
    if n >= 1 and r >= DECOMPOSE_TAU_R / 2:
        return "weak"
    return "insufficient"


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def decompose(query: str, llm: LLMCallable) -> list[str]:
    """
    Call the LLM to decompose `query` into up to DECOMPOSE_MAX_SUBQS sub-questions.

    Returns a list of sub-question strings (never empty; falls back to [query]).
    """
    system = _DECOMPOSE_SYSTEM.format(max_subqs=DECOMPOSE_MAX_SUBQS)
    prompt = _DECOMPOSE_USER.format(max_subqs=DECOMPOSE_MAX_SUBQS, query=query)

    response = llm.generate(prompt, system)
    if not response.success or not response.answer:
        logger.warning("decompose: LLM call failed (%s); using original query.", response.error)
        return [query]

    try:
        data = _extract_json(response.answer)
        sub_questions = data.get("sub_questions", [])
        if not isinstance(sub_questions, list) or not sub_questions:
            raise ValueError("Empty sub_questions list")
        # Sanitise: strings only, max items, non-empty
        sub_questions = [
            str(q).strip()
            for q in sub_questions
            if str(q).strip()
        ][:DECOMPOSE_MAX_SUBQS]
        if not sub_questions:
            raise ValueError("All sub_questions empty after sanitisation")
        logger.info("decompose: %d sub-question(s) from %r", len(sub_questions), query)
        return sub_questions
    except Exception as exc:
        logger.warning("decompose: JSON parse failed (%s); using original query.", exc)
        return [query]


def _reformulate(sub_question: str, prev_query: str, llm: LLMCallable) -> str:
    """Ask the LLM to reformulate an insufficient sub-question."""
    system = _REFORMULATE_SYSTEM
    prompt = _REFORMULATE_USER.format(
        sub_question=sub_question, prev_query=prev_query
    )
    response = llm.generate(prompt, system)
    if not response.success or not response.answer:
        logger.warning("_reformulate: LLM call failed; keeping original query.")
        return prev_query

    try:
        data = _extract_json(response.answer)
        reformulated = str(data.get("reformulated", "")).strip()
        if not reformulated:
            raise ValueError("Empty reformulated field")
        return reformulated
    except Exception as exc:
        logger.warning("_reformulate: parse failed (%s); keeping original.", exc)
        return prev_query


def solve_sub_question(
    sub_question: str,
    retriever: RetrieverCallable,
    llm: LLMCallable,
    top_k: int = DECOMPOSE_TOP_K,
    max_rounds: int = DECOMPOSE_MAX_ROUNDS,
    connector_search: Callable[[str, int], list[dict]] | None = None,
) -> SubQuestionResult:
    """
    Retrieve evidence for one sub-question, reformulating if insufficient.

    Returns a SubQuestionResult with a full round trace.
    """
    result = SubQuestionResult(sub_question=sub_question, final_status="insufficient")
    current_query = sub_question

    for round_num in range(1, max_rounds + 1):
        chunks = retriever.search(current_query, top_k=top_k)
        n, r = _compute_n_r(chunks)
        status = _classify_status(n, r)

        # If insufficient, search more connectors if available
        if status == "insufficient" and connector_search is not None:
            try:
                conn_chunks = connector_search(current_query, top_k)
                if conn_chunks:
                    chunks = chunks + conn_chunks
                    n, r = _compute_n_r(chunks)
                    status = _classify_status(n, r)
            except Exception as exc:
                logger.warning("connector search failed: %s", exc)

        rnd = RetrievalRound(
            round_number=round_num,
            query_used=current_query,
            chunks_retrieved=len(chunks),
            n=n,
            r=r,
            status=status,
        )
        result.rounds.append(rnd)

        logger.info(
            "sub-question %r round %d: n=%d r=%.3f status=%s",
            sub_question[:60], round_num, n, r, status,
        )

        if status in ("sufficient", "weak"):
            result.final_status = status
            result.chunks = chunks
            return result

        # Insufficient — reformulate (only if more rounds remain)
        if round_num < max_rounds:
            logger.info(
                "sub-question %r insufficient; reformulating (round %d/%d).",
                sub_question[:60], round_num, max_rounds,
            )
            current_query = _reformulate(sub_question, current_query, llm)

    # All rounds exhausted — still insufficient
    result.final_status = "insufficient"
    result.added_to_gaps = True
    logger.info(
        "sub-question %r → gaps (no sufficient evidence after %d round(s)).",
        sub_question[:60], max_rounds,
    )
    return result


def run_decomposition(
    query: str,
    retriever: RetrieverCallable,
    llm: LLMCallable,
    top_k: int = DECOMPOSE_TOP_K,
    max_rounds: int = DECOMPOSE_MAX_ROUNDS,
    connector_search: Callable[[str, int], list[dict]] | None = None,
) -> DecompositionTrace:
    """
    Full decomposition pipeline:
      1. LLM → sub-questions
      2. For each: retrieve → check sufficiency → reformulate if needed
      3. Collect gaps

    Returns a DecompositionTrace capturing every round.
    """
    trace = DecompositionTrace(original_query=query)
    trace.sub_questions = decompose(query, llm)

    for sub_q in trace.sub_questions:
        sqr = solve_sub_question(
            sub_q,
            retriever,
            llm,
            top_k=top_k,
            max_rounds=max_rounds,
            connector_search=connector_search,
        )
        trace.results.append(sqr)
        if sqr.added_to_gaps:
            trace.gaps.append(sub_q)

    logger.info(
        "Decomposition done: %d sub-questions, %d gaps, %d total rounds.",
        len(trace.sub_questions), len(trace.gaps), trace.total_rounds,
    )
    return trace
