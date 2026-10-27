"""verify_claim(): runs one claim through the selected mode.

Plug-in points (all injected, so your BM25+FAISS retriever, Tavily client and LLM stay yours):
  retrieve_document(claim) -> list[DocumentEvidence]      (stance/numeric left empty)
  research_external(claim) -> ExternalResearch            (fetched pages, not just snippets)
  judge(claim, passage)    -> Stance                      (LLM/NLI judge; default is a lexical baseline)
  chunk_lookup(doc_id, chunk_id) -> str | None            (to validate cited passages)

Mode guarantees: DOCUMENT_ONLY never calls research_external; EXTERNAL_ONLY never calls retrieve_document.
A failing retriever/researcher never aborts the result: it is recorded as a limitation.
"""
from __future__ import annotations

import dataclasses
from typing import Callable, List, Optional, Tuple

from .evidence import (
    DocumentEvidence, ExternalEvidence, ExternalResearch, Mode, SearchInfo, SideFinding, Stance,
    Verdict, VerificationResult, validate_document_evidence, validate_external_evidence,
)
from .numeric import NumericCheck, NumericStatus, check_numeric
from .textutil import overlap
from .verdict import assess_confidence, build_side, corroboration_of, merge_verdicts

Judge = Callable[[str, str], Stance]


def lexical_judge(claim: str, passage: str) -> Stance:
    """Baseline only: word overlap cannot detect negation. Replace with an LLM/NLI judge in production."""
    o = overlap(claim, passage)
    return Stance.SUPPORTS if o >= 0.7 else Stance.PARTIAL if o >= 0.4 else Stance.CONTEXT


def assess_passage(claim: str, text: str, judge: Judge) -> Tuple[Stance, Optional[NumericCheck]]:
    nc = check_numeric(claim, text)
    st = nc.status
    if st == NumericStatus.NO_NUMBERS:
        return judge(claim, text), None
    if st == NumericStatus.MISMATCH:
        return Stance.CONTRADICTS, nc
    if st in (NumericStatus.UNRESOLVED_CONDITIONS, NumericStatus.INCOMPATIBLE_UNITS, NumericStatus.NOT_FOUND):
        return Stance.CONTEXT, nc
    j = judge(claim, text)
    if j == Stance.CONTRADICTS:
        return Stance.CONTRADICTS, nc
    if st == NumericStatus.MATCH and j == Stance.SUPPORTS:
        return Stance.SUPPORTS, nc
    return Stance.PARTIAL, nc


def _document_side(claim, retrieve_document, judge, chunk_lookup, problems, limitations) -> SideFinding:
    if retrieve_document is None:
        limitations.append("document retrieval is not configured")
        return build_side([], kind="document", access_failed=True)
    try:
        raw = retrieve_document(claim)
    except Exception as exc:  # noqa: BLE001 - preserve partial results
        limitations.append(f"document retrieval failed: {type(exc).__name__}")
        return build_side([], kind="document", access_failed=True)
    items: List[DocumentEvidence] = []
    for e in list(raw or []):
        if not isinstance(e, DocumentEvidence):
            problems.append("malformed document evidence ignored")
            continue
        bad = validate_document_evidence(e, chunk_lookup)
        if bad:
            problems.extend(bad)
            continue
        stance, nc = assess_passage(claim, e.passage, judge)
        items.append(dataclasses.replace(e, stance=stance, numeric=nc))
    return build_side(items, kind="document")


def _external_side(claim, research_external, judge, problems, limitations) -> SideFinding:
    if research_external is None:
        limitations.append("external research is not configured")
        return build_side([], kind="external", access_failed=True, search=SearchInfo(failures=["not configured"]))
    try:
        res = research_external(claim)
    except Exception as exc:  # noqa: BLE001
        info = SearchInfo(failed=1, failures=[type(exc).__name__])
        limitations.append(f"external research failed: {type(exc).__name__}")
        return build_side([], kind="external", access_failed=True, search=info)
    if not isinstance(res, ExternalResearch):
        problems.append("malformed external research result ignored")
        return build_side([], kind="external", access_failed=True, search=SearchInfo())
    items: List[ExternalEvidence] = []
    for e in res.items:
        if not isinstance(e, ExternalEvidence):
            problems.append("malformed external evidence ignored")
            continue
        bad = validate_external_evidence(e)
        if bad:
            problems.extend(bad)
            continue
        stance, nc = assess_passage(claim, e.passage, judge)
        items.append(dataclasses.replace(e, stance=stance, numeric=nc))
    if res.search.failed:
        limitations.append(f"{res.search.failed} external source(s) could not be inspected")
    return build_side(items, kind="external", access_failed=(not items and res.search.failed > 0), search=res.search)


def verify_claim(
    claim_text: str,
    mode: Mode,
    *,
    retrieve_document: Optional[Callable[[str], List[DocumentEvidence]]] = None,
    research_external: Optional[Callable[[str], ExternalResearch]] = None,
    judge: Optional[Judge] = None,
    chunk_lookup: Optional[Callable[[str, str], Optional[str]]] = None,
    claim_id: Optional[str] = None,
) -> VerificationResult:
    judge = judge or lexical_judge
    problems: List[str] = []
    limitations: List[str] = []
    doc = ext = None
    if mode in (Mode.DOCUMENT_ONLY, Mode.DOCUMENT_AND_EXTERNAL):
        doc = _document_side(claim_text, retrieve_document, judge, chunk_lookup, problems, limitations)
    if mode in (Mode.EXTERNAL_ONLY, Mode.DOCUMENT_AND_EXTERNAL):
        ext = _external_side(claim_text, research_external, judge, problems, limitations)

    verdict = merge_verdicts(doc.verdict if doc else None, ext.verdict if ext else None)
    if ext is None:
        limitations.append("No independent external verification was performed; findings are author-reported.")
    if doc is not None and doc.verdict == Verdict.SUPPORTED and ext is not None and ext.verdict != Verdict.SUPPORTED:
        limitations.append("Supported by the document but not independently corroborated.")
    return VerificationResult(
        claim_id=claim_id, claim_text=claim_text, mode=mode, verdict=verdict, document=doc, external=ext,
        corroboration=corroboration_of(ext), confidence=assess_confidence(verdict, mode, doc, ext),
        limitations=limitations, citation_problems=problems,
    )
