"""Verdict decision, source independence, and four-signal confidence.

Confidence is ORDINAL (NONE/LOW/MODERATE/HIGH) on purpose: no invented percentages. It becomes a
probability only if you later calibrate it against a labelled evaluation set.
"""
from __future__ import annotations

import re
from typing import List, Optional, Sequence

from .evidence import (
    ConfidenceReport, Corroboration, DocumentEvidence, ExternalEvidence, Inspection, Level, Mode,
    SearchInfo, SideFinding, SourceType, Stance, Verdict,
)
from .numeric import NumericStatus

SOURCE_WEIGHT = {
    SourceType.PRIMARY_PAPER: 1.0, SourceType.OFFICIAL_DATA: 1.0, SourceType.GOVERNMENT: 0.95,
    SourceType.OFFICIAL_DOCS: 0.9, SourceType.PUBLISHER_RECORD: 0.9, SourceType.SCHOLARLY_SECONDARY: 0.7,
    SourceType.NEWS: 0.5, SourceType.BLOG_OR_FORUM: 0.3, SourceType.AI_SUMMARY: 0.2, SourceType.UNKNOWN: 0.3,
}
INSPECTION_FACTOR = {
    Inspection.FULL_TEXT: 1.0, Inspection.ABSTRACT_ONLY: 0.6,
    Inspection.SNIPPET_ONLY: 0.3, Inspection.INACCESSIBLE: 0.0,
}
MIN_DECISIVE = 0.5      # evidence lighter than this can never decide a verdict on its own


def external_weight(e: ExternalEvidence) -> float:
    return SOURCE_WEIGHT.get(e.source_type, 0.3) * INSPECTION_FACTOR.get(e.inspection, 0.0)


# ---------------------------------------------------------------- independence
def _norm_url(u: Optional[str]) -> str:
    u = (u or "").lower().split("#")[0]
    u = re.sub(r"^https?://(www\.)?", "", u)
    return u.rstrip("/")


def _shingles(text: str, k: int = 5) -> set:
    words = re.findall(r"[a-z0-9]+", text.lower())
    if len(words) <= k:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i:i + k]) for i in range(len(words) - k + 1)}


def cluster_external(items: Sequence[ExternalEvidence], threshold: float = 0.8) -> List[List[int]]:
    """Group sources that are copies/derivatives of one another. Returns clusters of indices."""
    n = len(items)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    sh = [_shingles(i.passage) for i in items]
    for a in range(n):
        for b in range(a + 1, n):
            derived = (
                (items[a].derived_from and _norm_url(items[a].derived_from) == _norm_url(items[b].url))
                or (items[b].derived_from and _norm_url(items[b].derived_from) == _norm_url(items[a].url))
                or (items[a].derived_from and _norm_url(items[a].derived_from) == _norm_url(items[b].derived_from))
            )
            union = sh[a] | sh[b]
            similar = bool(union) and len(sh[a] & sh[b]) / len(union) >= threshold
            if derived or similar:
                parent[find(a)] = find(b)
    groups: dict = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


# ---------------------------------------------------------------- verdict
def _decide(S: float, C: float, P: float, access_failed: bool):
    """Returns (verdict, conflict, weak_note)."""
    best = max(S, C, P)
    if best == 0:
        return (Verdict.UNVERIFIABLE if access_failed else Verdict.UNSUPPORTED), False, None
    eff_S, eff_C, eff_P = (w if w >= MIN_DECISIVE else 0.0 for w in (S, C, P))
    if max(eff_S, eff_C, eff_P) == 0:
        return Verdict.UNVERIFIABLE, False, "available evidence is too weak (e.g. snippets or low-authority sources)"
    weak = None
    if (C and not eff_C and (eff_S or eff_P)) or ((S or P) and not (eff_S or eff_P) and eff_C):
        weak = "weak evidence pointing the other way exists but was not inspected in full"
    pos, part, neg = eff_S, eff_P, eff_C
    if neg and (pos or part):
        share = min(neg, pos + part) / (neg + pos + part)
        if share >= 0.3:
            return Verdict.PARTIALLY_SUPPORTED, True, weak
        if neg > pos + part:
            return Verdict.CONTRADICTED, True, weak
        return (Verdict.SUPPORTED if pos >= part else Verdict.PARTIALLY_SUPPORTED), True, weak
    if neg:
        return Verdict.CONTRADICTED, False, weak
    if part or (pos and part):
        return Verdict.PARTIALLY_SUPPORTED, False, weak
    return Verdict.SUPPORTED, False, weak


def build_side(
    items: Sequence, *, kind: str, access_failed: bool = False, retrieved: Optional[int] = None,
    search: Optional[SearchInfo] = None,
) -> SideFinding:
    """Turn stance-labelled evidence into a verdict for one side (document or external)."""
    items = list(items)
    notes: List[str] = []
    if kind == "external":
        clusters = cluster_external(items)
        weights = [external_weight(i) for i in items]
        reps = []
        for c in clusters:
            top = max(c, key=lambda i: weights[i])
            reps.append((items[top], weights[top], len(c)))
        independent = len(clusters)
        for e, w, size in reps:
            if size > 1:
                notes.append(f"{size} sources share one origin and count as a single independent source")
    else:
        reps = [(i, 1.0, 1) for i in items]
        independent = len(items)

    S = max((w for e, w, _ in reps if e.stance == Stance.SUPPORTS), default=0.0)
    C = max((w for e, w, _ in reps if e.stance == Stance.CONTRADICTS), default=0.0)
    P = max((w for e, w, _ in reps if e.stance == Stance.PARTIAL), default=0.0)
    verdict, conflict, weak = _decide(S, C, P, access_failed)
    if weak:
        notes.append(weak)
    if conflict:
        notes.append("evidence conflicts; verdict is conservative")

    deciding_stances = {
        Verdict.SUPPORTED: (Stance.SUPPORTS,), Verdict.CONTRADICTED: (Stance.CONTRADICTS,),
        Verdict.PARTIALLY_SUPPORTED: (Stance.SUPPORTS, Stance.PARTIAL, Stance.CONTRADICTS),
    }.get(verdict, ())
    deciding = [(e, w) for e, w, _ in reps if e.stance in deciding_stances and w >= MIN_DECISIVE]
    covs = [e.numeric.coverage for e, _ in deciding if e.numeric is not None and e.numeric.coverage is not None]
    unresolved = any(
        e.numeric is not None and e.numeric.status in (NumericStatus.UNRESOLVED_CONDITIONS, NumericStatus.INCOMPATIBLE_UNITS)
        for e in items
    )
    if unresolved:
        notes.append("some passages use different conditions or incompatible units; discrepancy left unresolved")
    cond_unconfirmed = any(
        e.numeric is not None and any(c.outcome == "unconfirmed" for c in e.numeric.comparisons)
        for e, _ in deciding
    )
    return SideFinding(
        verdict=verdict, evidence=items, notes=notes, conflict=conflict,
        weak_opposition=weak is not None, unresolved=unresolved,
        abstract_only_deciding=bool(deciding) and all(
            getattr(e, "inspection", Inspection.FULL_TEXT) != Inspection.FULL_TEXT for e, _ in deciding
        ),
        condition_unconfirmed=cond_unconfirmed,
        deciding_weight=max((w for _, w in deciding), default=0.0),
        best_weight=max((w for _, w, _ in reps), default=0.0),
        coverage=max(covs) if covs else None,
        independent_clusters=independent,
        retrieved=len(items) if retrieved is None else retrieved,
        retrieval_failed=access_failed, search=search,
    )


def merge_verdicts(doc: Optional[Verdict], ext: Optional[Verdict]) -> Verdict:
    checked = [v for v in (doc, ext) if v is not None]
    if not checked:
        return Verdict.UNVERIFIABLE
    if Verdict.CONTRADICTED in checked:
        return Verdict.CONTRADICTED
    positives = [v for v in checked if v in (Verdict.SUPPORTED, Verdict.PARTIALLY_SUPPORTED)]
    if not positives:
        return Verdict.UNVERIFIABLE if Verdict.UNVERIFIABLE in checked else Verdict.UNSUPPORTED
    if all(v == Verdict.SUPPORTED for v in positives):
        return Verdict.SUPPORTED
    return Verdict.PARTIALLY_SUPPORTED


def corroboration_of(ext: Optional[SideFinding]) -> Corroboration:
    if ext is None:
        return Corroboration.NOT_CHECKED
    return {
        Verdict.SUPPORTED: Corroboration.CONFIRMED, Verdict.PARTIALLY_SUPPORTED: Corroboration.PARTIAL,
        Verdict.CONTRADICTED: Corroboration.CONTRADICTED,
    }.get(ext.verdict, Corroboration.NOT_FOUND)


# ---------------------------------------------------------------- confidence
def _level(x: float, hi: float, mid: float) -> Level:
    return Level.HIGH if x >= hi else Level.MODERATE if x >= mid else Level.LOW if x > 0 else Level.NONE


def _completeness(side: SideFinding, kind: str) -> Level:
    if side.retrieval_failed:
        return Level.NONE
    if kind == "document":
        return Level.HIGH if side.retrieved >= 1 else Level.MODERATE
    s = side.search or SearchInfo()
    if s.inspected >= 2 and s.failed == 0:
        return Level.HIGH
    if s.inspected >= 1:
        return Level.MODERATE
    return Level.LOW


def assess_confidence(
    verdict: Verdict, mode: Mode, doc: Optional[SideFinding], ext: Optional[SideFinding]
) -> ConfidenceReport:
    sides = [(s, k) for s, k in ((doc, "document"), (ext, "external")) if s is not None]
    reasons: List[str] = []
    absence = verdict in (Verdict.UNSUPPORTED, Verdict.UNVERIFIABLE)
    deciding = [(s, k) for s, k in sides if s.verdict == verdict] or (
        [(s, k) for s, k in sides if s.verdict in (Verdict.SUPPORTED, Verdict.PARTIALLY_SUPPORTED)]
        if verdict == Verdict.PARTIALLY_SUPPORTED else []
    )
    if not deciding:
        deciding = sides

    weight = max((s.best_weight if absence else s.deciding_weight) for s, _ in deciding) if deciding else 0.0
    quality = _level(weight, 0.8, 0.5)
    reasons.append({
        Level.HIGH: "deciding evidence comes from authoritative, inspected sources",
        Level.MODERATE: "deciding evidence is moderate in authority or only partly inspected",
        Level.LOW: "available evidence is weak (snippets, abstracts or low-authority sources)",
        Level.NONE: "no usable evidence was found",
    }[quality])

    covs = [s.coverage for s, _ in deciding if s.coverage is not None]
    if absence or not deciding:
        coverage = Level.NONE if not any(s.retrieved for s, _ in sides) else Level.LOW
    elif covs:
        coverage = _level(max(covs), 0.9, 0.5)
        reasons.append(f"{round(max(covs) * 100)}% of the claim's numbers/conditions were confirmed in the evidence")
    else:
        coverage = Level.MODERATE
        reasons.append("coverage of the claim's parts was not measured (no numeric check), so it is capped at moderate")

    comp_all = [_completeness(s, k) for s, k in sides]
    completeness = min(comp_all) if comp_all else Level.NONE
    comp_deciding = [_completeness(s, k) for s, k in deciding]
    comp_for_verdict = min(comp_all) if (absence or not comp_deciding) else max(comp_deciding)
    if ext is None:
        reasons.append("no external search was performed (document-only mode)")
    elif ext.search and ext.search.failed:
        reasons.append(f"{ext.search.failed} external source(s) could not be accessed")

    parts = [quality, coverage, comp_for_verdict]
    conf = min(parts)
    caps = []
    if any(s.conflict for s, _ in sides):
        caps.append((Level.LOW, "sources conflict"))
    if any(s.weak_opposition for s, _ in sides):
        caps.append((Level.MODERATE, "weaker evidence points the other way"))
    if any(s.unresolved for s, _ in sides):
        caps.append((Level.LOW if absence else Level.MODERATE, "conditions or units differ between passages and could not be reconciled"))
    if any(s.abstract_only_deciding for s, _ in deciding):
        caps.append((Level.MODERATE, "deciding evidence is not full-text inspected"))
    if any(s.condition_unconfirmed for s, _ in deciding):
        caps.append((Level.MODERATE, "some experimental conditions in the claim are not confirmed by the passage"))
    if any(k == "external" and s.independent_clusters < 2 for s, k in deciding) and not absence:
        caps.append((Level.MODERATE, "only one independent external source"))
    if verdict == Verdict.UNSUPPORTED:
        caps.append((Level.MODERATE, "absence of evidence is never conclusive"))
    for cap, why in caps:
        if conf > cap:
            conf = cap
        reasons.append(f"capped at {cap.name.lower()}: {why}")
    return ConfidenceReport(conf, quality, coverage, completeness, reasons)
