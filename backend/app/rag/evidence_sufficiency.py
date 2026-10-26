"""Evidence sufficiency gate: decide whether retrieved passages cover the question.

Pure Python, no model calls. Checks what fraction of the question's content terms
appear in the retrieved passages. Used before generation so the system can abstain
and report gaps instead of guessing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_STOP = {
    "what", "which", "does", "with", "that", "this", "from", "have", "about",
    "their", "there", "where", "when", "into", "than", "then", "your", "been",
    "were", "will", "would", "could", "should", "these", "those", "tell",
    "explain", "describe", "give", "show", "paper", "study", "using", "used",
    "between", "other", "also", "more", "most", "some", "such", "they", "them",
}


@dataclass
class SufficiencyResult:
    sufficient: bool
    coverage: float
    covered_terms: list[str] = field(default_factory=list)
    uncovered_terms: list[str] = field(default_factory=list)
    reason: str = ""

    @property
    def gaps(self) -> list[str]:
        return [f"No evidence found for: {t}" for t in self.uncovered_terms]


def _stem(word: str) -> str:
    for suf in ("ing", "ed", "es", "s"):
        if word.endswith(suf) and len(word) - len(suf) >= 4:
            return word[: -len(suf)]
    return word


def query_terms(query: str) -> list[str]:
    seen: list[str] = []
    for w in re.findall(r"[a-z0-9][a-z0-9\-]{3,}", (query or "").lower()):
        if w not in _STOP and w not in seen:
            seen.append(w)
    return seen


def _passage_text(p) -> str:
    if isinstance(p, dict):
        return str(p.get("text", ""))
    return str(p)


def assess_sufficiency(
    query: str,
    passages: list,
    min_coverage: float = 0.5,
) -> SufficiencyResult:
    """Return whether the passages cover enough of the query's content terms."""
    blob = " ".join(_passage_text(p) for p in (passages or [])).lower()
    if not blob.strip():
        return SufficiencyResult(False, 0.0, [], query_terms(query), "no_passages")

    terms = query_terms(query)
    if not terms:
        return SufficiencyResult(True, 1.0, [], [], "no_content_terms")

    covered = [t for t in terms if _stem(t) in blob]
    uncovered = [t for t in terms if t not in covered]
    coverage = len(covered) / len(terms)
    ok = coverage >= min_coverage
    return SufficiencyResult(
        ok, round(coverage, 4), covered, uncovered, "ok" if ok else "low_coverage"
    )