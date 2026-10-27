"""Small text helpers shared by claim extraction, numeric checks and judging."""
from __future__ import annotations

import re

_STOP = set(
    "the a an and or of in on at to for with by from is are was were be been being as that this "
    "these those it its their there which who whom whose than then also after before under over "
    "into between among we our us they he she you not but if so such can will would should could "
    "may might has have had do does did using used use via per each both all any more most less "
    "other when while where what how why".split()
)
_WORD = re.compile(r"[A-Za-z][A-Za-z\-]{2,}")


def _stem(word: str) -> str:
    w = word.lower()
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def content_tokens(text: str) -> set[str]:
    return {_stem(t) for t in _WORD.findall(text) if t.lower() not in _STOP}


def overlap(claim: str, passage: str) -> float:
    """Share of the claim's content words that also appear in the passage (0..1)."""
    c = content_tokens(claim)
    if not c:
        return 0.0
    return len(c & content_tokens(passage)) / len(c)


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()
