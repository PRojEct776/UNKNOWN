"""Instruction-aware claim extraction and categorisation.

Rule-based baseline: it keeps the author's original wording, removes request/instruction text
("verify this claim", "return supporting evidence"), and separates checkable assertions from
opinions, hypotheses, recommendations, questions and fragments. An LLM extractor can replace
`extract_statements`, but should keep the same `Statement` output so everything downstream works.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from .numeric import parse_quantities


class StatementKind(str, Enum):
    VERIFIABLE = "verifiable"
    INSTRUCTION = "instruction"
    QUESTION = "question"
    RECOMMENDATION = "recommendation"
    HYPOTHESIS = "hypothesis"
    OPINION = "opinion"
    FRAGMENT = "fragment"


class ClaimCategory(str, Enum):
    LIMITATION = "limitation"
    PRIOR_WORK = "prior_work"
    COMPARISON = "comparison"
    CAUSAL = "causal"
    DATASET = "dataset"
    EXPERIMENTAL = "experimental_result"
    QUANTITATIVE = "quantitative"
    METHODOLOGY = "methodology"
    FACTUAL = "factual"


@dataclass
class Statement:
    text: str
    kind: StatementKind
    category: Optional[ClaimCategory] = None
    numbers: List[str] = field(default_factory=list)
    citations: List[str] = field(default_factory=list)
    priority: int = 0                       # 3 = verify first
    doc_id: Optional[str] = None            # provenance, filled by the caller
    doc_name: Optional[str] = None
    page: Optional[int] = None
    chunk_id: Optional[str] = None


_INSTR_START = re.compile(
    r"^\s*(?:please\s+|kindly\s+)?(?:verify|check|confirm|validate|fact[- ]?check|return|provide|"
    r"show|give|find|search|cite|tell me|can you|could you|would you|i want you to|i need you to)\b",
    re.I,
)
_INSTR_PREFIX = re.compile(
    r"^\s*(?:please\s+)?(?:verify|check|confirm|validate|fact[- ]?check)\s+"
    r"(?:(?:this|the following)\s+(?:claim|statement|assertion|sentence)|whether|if|that)?\s*[:\-–,]?\s*",
    re.I,
)
_INSTR_TAIL = re.compile(
    r"(?:[,;.]|\band\b|\bthen\b)\s*(?:(?:and|then)\s+)?(?:please\s+)?(?:return|provide|give|show|cite|include|list|attach)\s+"
    r"[^.]*?(?:evidence|sources?|citations?|support|proof|references?|page)[^.]*\.?\s*$",
    re.I,
)
_QUOTED = re.compile(r"[\"“”']([^\"“”']{20,})[\"“”']")
_RECOMMEND = re.compile(r"\b(should|must|we recommend|recommend|ought to|it is advisable|need to)\b", re.I)
_HYPOTHESIS = re.compile(
    r"\b(we hypothesi[sz]e|hypothes[ie]s|may|might|could|potentially|possibly|we speculate|"
    r"we expect|is expected to|are expected to|likely to|would be)\b", re.I)
_OPINION = re.compile(
    r"\b(i think|i believe|we believe|in our opinion|arguably|elegant|exciting|amazing|"
    r"remarkable|beautiful|promising)\b", re.I)
_CITE = re.compile(r"\[\d+(?:\s*[,–-]\s*\d+)*\]|\b[A-Z][A-Za-z\-]+ et al\.?(?:,? \d{4})?|\([A-Z][A-Za-z\-]+,? \d{4}\)")

_ABBR = ["e.g.", "i.e.", "et al.", "Fig.", "Figs.", "Eq.", "Eqs.", "vs.", "approx.", "No.", "Sec.", "Tab."]

_CATEGORY_RULES = [
    (ClaimCategory.LIMITATION, re.compile(r"\b(limitation|future work|we leave|beyond the scope|not addressed)\b", re.I)),
    (ClaimCategory.PRIOR_WORK, re.compile(r"\b(previous(?:ly)?|prior|earlier|et al|\[\d+\]|state[- ]of[- ]the[- ]art|reported by)\b", re.I)),
    (ClaimCategory.COMPARISON, re.compile(r"\b(outperform\w*|compared (?:to|with)|versus|vs\.?|exceed\w*|baseline|better than|worse than|higher than|lower than|improv\w+)\b", re.I)),
    (ClaimCategory.CAUSAL, re.compile(r"\b(because|due to|caused?|leads? to|results? in|owing to|therefore|mechanism|drives?)\b", re.I)),
    (ClaimCategory.DATASET, re.compile(r"\b(dataset|corpus|cohort|participants|samples were|sample size|n\s*=)\b", re.I)),
    (ClaimCategory.EXPERIMENTAL, re.compile(r"\b(achiev\w+|observed|measured|accuracy|recovery|experiment\w*|simulat\w+|result\w*|found that|yield\w*)\b", re.I)),
    (ClaimCategory.METHODOLOGY, re.compile(r"\b(we (?:used|trained|simulated|implemented|measured|apply|applied)|protocol|setup|procedure|parameter\w*)\b", re.I)),
]


def split_sentences(text: str) -> List[str]:
    protected = text
    for i, a in enumerate(_ABBR):
        protected = protected.replace(a, a.replace(".", f"\x00{i}\x00"))
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\"“(\[])", protected.strip())
    out = []
    for p in parts:
        p = re.sub(r"\x00\d+\x00", ".", p).strip()
        if p:
            out.append(p)
    return out


def _clean_instruction_wrapping(text: str) -> str:
    """Remove 'verify this claim:' prefixes and 'and return supporting evidence' tails."""
    text = text.strip()
    quoted = _QUOTED.findall(text)
    if quoted and _INSTR_START.search(text.split(quoted[0])[0] or "") :
        return " ".join(q.strip() for q in quoted)
    if _INSTR_START.match(text):
        stripped = _INSTR_PREFIX.sub("", text, count=1).strip()
        if stripped and stripped != text and not _INSTR_START.match(stripped):
            text = stripped
    text = _INSTR_TAIL.sub("", text).strip()
    return text.strip(" \t\"“”")


def classify_statement(sentence: str) -> StatementKind:
    s = sentence.strip()
    if len(s.split()) < 4:
        return StatementKind.FRAGMENT
    if _INSTR_START.match(s):
        return StatementKind.INSTRUCTION
    if s.endswith("?"):
        return StatementKind.QUESTION
    if _RECOMMEND.search(s):
        return StatementKind.RECOMMENDATION
    if _HYPOTHESIS.search(s):
        return StatementKind.HYPOTHESIS
    if _OPINION.search(s):
        return StatementKind.OPINION
    return StatementKind.VERIFIABLE


def categorize(sentence: str) -> ClaimCategory:
    has_number = bool(parse_quantities(sentence))
    for cat, rx in _CATEGORY_RULES:
        if rx.search(sentence):
            if cat == ClaimCategory.EXPERIMENTAL and not has_number:
                continue
            return cat
    return ClaimCategory.QUANTITATIVE if has_number else ClaimCategory.FACTUAL


def _priority(cat: ClaimCategory, has_number: bool) -> int:
    if cat in (ClaimCategory.EXPERIMENTAL, ClaimCategory.COMPARISON, ClaimCategory.CAUSAL) or (
        cat == ClaimCategory.QUANTITATIVE
    ):
        return 3
    if has_number or cat in (ClaimCategory.DATASET, ClaimCategory.PRIOR_WORK):
        return 2
    return 1


def extract_statements(text: str) -> List[Statement]:
    """Split text into statements, remove instruction wrapping, classify each."""
    out: List[Statement] = []
    for raw in split_sentences(text):
        cleaned = _clean_instruction_wrapping(raw)
        for sentence in split_sentences(cleaned) if cleaned != raw else [cleaned]:
            if not sentence:
                continue
            kind = classify_statement(sentence)
            st = Statement(text=sentence, kind=kind)
            if kind == StatementKind.VERIFIABLE:
                st.category = categorize(sentence)
                st.numbers = [q.raw for q in parse_quantities(sentence)]
                st.citations = _CITE.findall(sentence)
                st.priority = _priority(st.category, bool(st.numbers))
            out.append(st)
    return out


def verifiable_claims(text: str) -> List[Statement]:
    return [s for s in extract_statements(text) if s.kind == StatementKind.VERIFIABLE]


def batched(items: List, size: int):
    """Controlled batches for long documents."""
    for i in range(0, len(items), size):
        yield items[i:i + size]
