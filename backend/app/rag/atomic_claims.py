"""
UNKNOWN X – Atomic Claim Verification Layer (Task A5)

Pipeline:
1. Split generated answer into atomic claims (LLM JSON).
2. For each claim:
   (1) NLI entailment against its cited passage using a configurable Hugging Face NLI model.
   (2) Number/date match after normalization (5% = 0.05, units conversion, date matching).
   (3) Named-entity presence check (spaCy with pure-Python fallback).
   Label assigned: supported | partial | unsupported | contradicted.
3. If not supported:
   Regenerate once from the cited passage alone, re-check; else drop.
4. Construct and return claims[] in AnswerResponse.
"""

from __future__ import annotations

import json
import math
import os
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from app.api.schemas import AnswerResponse, Claim
from app.rag.logger import logger

# ---------------------------------------------------------------------------
# Configurable Environment Settings
# ---------------------------------------------------------------------------

NLI_MODEL: str = os.environ.get(
    "NLI_MODEL",
    "cross-encoder/nli-deberta-v3-small",
)

SPACY_MODEL: str = os.environ.get(
    "SPACY_MODEL",
    "en_core_web_sm",
)

# ---------------------------------------------------------------------------
# 1. Number & Date Normalization
# ---------------------------------------------------------------------------

# Unit scale mappings to base units (distance in meters, mass in grams, time in seconds)
_UNIT_SCALES: dict[str, tuple[float, str]] = {
    # Length / Distance -> meters (m)
    "km": (1000.0, "m"),
    "kilometer": (1000.0, "m"),
    "kilometers": (1000.0, "m"),
    "m": (1.0, "m"),
    "meter": (1.0, "m"),
    "meters": (1.0, "m"),
    "cm": (0.01, "m"),
    "centimeter": (0.01, "m"),
    "centimeters": (0.01, "m"),
    "mm": (0.001, "m"),
    "millimeter": (0.001, "m"),
    "millimeters": (0.001, "m"),
    "mi": (1609.344, "m"),
    "mile": (1609.344, "m"),
    "miles": (1609.344, "m"),
    # Mass / Weight -> grams (g)
    "kg": (1000.0, "g"),
    "kilogram": (1000.0, "g"),
    "kilograms": (1000.0, "g"),
    "g": (1.0, "g"),
    "gram": (1.0, "g"),
    "grams": (1.0, "g"),
    "mg": (0.001, "g"),
    "milligram": (0.001, "g"),
    "milligrams": (0.001, "g"),
    # Time -> seconds (s)
    "ms": (0.001, "s"),
    "millisecond": (0.001, "s"),
    "milliseconds": (0.001, "s"),
    "s": (1.0, "s"),
    "sec": (1.0, "s"),
    "second": (1.0, "s"),
    "seconds": (1.0, "s"),
    "min": (60.0, "s"),
    "minute": (60.0, "s"),
    "minutes": (60.0, "s"),
    "h": (3600.0, "s"),
    "hr": (3600.0, "s"),
    "hour": (3600.0, "s"),
    "hours": (3600.0, "s"),
    "day": (86400.0, "s"),
    "days": (86400.0, "s"),
    "year": (31536000.0, "s"),
    "years": (31536000.0, "s"),
}

_WORD_NUMBERS: dict[str, float] = {
    "zero": 0.0,
    "one": 1.0,
    "two": 2.0,
    "three": 3.0,
    "four": 4.0,
    "five": 5.0,
    "six": 6.0,
    "seven": 7.0,
    "eight": 8.0,
    "nine": 9.0,
    "ten": 10.0,
    "eleven": 11.0,
    "twelve": 12.0,
    "thirteen": 13.0,
    "fourteen": 14.0,
    "fifteen": 15.0,
    "sixteen": 16.0,
    "seventeen": 17.0,
    "eighteen": 18.0,
    "nineteen": 19.0,
    "twenty": 20.0,
    "thirty": 30.0,
    "forty": 40.0,
    "fifty": 50.0,
    "sixty": 60.0,
    "seventy": 70.0,
    "eighty": 80.0,
    "ninety": 90.0,
    "hundred": 100.0,
    "thousand": 1000.0,
    "million": 1000000.0,
    "billion": 1000000000.0,
}

_MONTHS: dict[str, int] = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}


@dataclass
class NormalizedQuantity:
    raw: str
    value: float
    base_unit: str  # "ratio" for percentages/fractions, "count" for scalars, or unit like "m", "g", "s"
    is_percentage: bool = False


@dataclass
class NormalizedDate:
    raw: str
    year: int
    month: int | None = None
    day: int | None = None


def extract_quantities(text: str) -> list[NormalizedQuantity]:
    """Extract and normalize numerical quantities, percentages, and units."""
    quantities: list[NormalizedQuantity] = []
    text_norm = unicodedata.normalize("NFKC", text)

    # 1. Percentages: "5%", "5.5 %", "5 percent", "five percent"
    matched_spans: list[tuple[int, int]] = []
    pct_pattern = re.compile(
        r"\b(?:(\d+(?:\.\d+)?)|(" + "|".join(_WORD_NUMBERS.keys()) + r"))\s*(?:%|percent\b|pct\b)",
        re.IGNORECASE,
    )
    for m in pct_pattern.finditer(text_norm):
        matched_spans.append(m.span())
        num_str = m.group(1) or str(_WORD_NUMBERS[m.group(2).lower()])
        val = float(num_str) / 100.0  # normalize 5% -> 0.05
        quantities.append(
            NormalizedQuantity(
                raw=m.group(0),
                value=round(val, 6),
                base_unit="ratio",
                is_percentage=True,
            )
        )

    # 2. Number + Unit: e.g. "5 km", "5000 meters", "10 kg", "2 hours"
    unit_keys = sorted(_UNIT_SCALES.keys(), key=len, reverse=True)
    unit_pattern = re.compile(
        r"\b(\d+(?:,\d+)*(?:\.\d+)?)\s*(" + "|".join(re.escape(u) for u in unit_keys) + r")\b",
        re.IGNORECASE,
    )
    for m in unit_pattern.finditer(text_norm):
        matched_spans.append(m.span())
        num_str = m.group(1).replace(",", "")
        unit_str = m.group(2).lower()
        scale, base_unit = _UNIT_SCALES[unit_str]
        val = float(num_str) * scale
        quantities.append(
            NormalizedQuantity(
                raw=m.group(0),
                value=round(val, 6),
                base_unit=base_unit,
                is_percentage=False,
            )
        )

    # 3. Standalone decimals or integers not already covered
    # (Exclude numbers that look like 4-digit years between 1900 and 2099)
    num_pattern = re.compile(r"\b(\d+(?:,\d+)*(?:\.\d+)?)\b")
    for m in num_pattern.finditer(text_norm):
        raw = m.group(0)
        start, end = m.span()
        # Skip if within an already matched percentage or unit span
        if any(s <= start and end <= e for s, e in matched_spans):
            continue
        cleaned = raw.replace(",", "")
        val = float(cleaned)
        # If integer in 1900..2099, treat as candidate year rather than scalar count
        if val.is_integer() and 1900 <= int(val) <= 2099:
            continue
        matched_spans.append((start, end))
        # If number is a decimal like 0.05, it could also represent 5%
        base_unit = "ratio" if 0.0 <= val <= 1.0 else "count"
        quantities.append(
            NormalizedQuantity(
                raw=raw,
                value=round(val, 6),
                base_unit=base_unit,
                is_percentage=(0.0 <= val <= 1.0),
            )
        )

    # 4. Standalone word numbers like "five", "twenty"
    word_pattern = re.compile(r"\b(" + "|".join(_WORD_NUMBERS.keys()) + r")\b", re.IGNORECASE)
    for m in word_pattern.finditer(text_norm):
        w = m.group(1).lower()
        start, end = m.span()
        if any(w in q.raw.lower() for q in quantities):
            continue
        val = _WORD_NUMBERS[w]
        quantities.append(
            NormalizedQuantity(
                raw=m.group(0),
                value=round(val, 6),
                base_unit="count",
                is_percentage=False,
            )
        )

    return quantities


def extract_dates(text: str) -> list[NormalizedDate]:
    """Extract and normalize calendar dates."""
    dates: list[NormalizedDate] = []
    text_norm = unicodedata.normalize("NFKC", text)

    # 1. YYYY-MM-DD or YYYY/MM/DD
    iso_pattern = re.compile(r"\b((?:19|20)\d{2})[-/](0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01])\b")
    for m in iso_pattern.finditer(text_norm):
        dates.append(
            NormalizedDate(
                raw=m.group(0),
                year=int(m.group(1)),
                month=int(m.group(2)),
                day=int(m.group(3)),
            )
        )

    # 2. Month DD, YYYY or DD Month YYYY
    month_names = "|".join(_MONTHS.keys())
    named_date_1 = re.compile(
        rf"\b({month_names})\s+([0-3]?\d)(?:st|nd|rd|th)?,?\s+((?:19|20)\d{{2}})\b",
        re.IGNORECASE,
    )
    for m in named_date_1.finditer(text_norm):
        dates.append(
            NormalizedDate(
                raw=m.group(0),
                year=int(m.group(3)),
                month=_MONTHS[m.group(1).lower()],
                day=int(m.group(2)),
            )
        )

    named_date_2 = re.compile(
        rf"\b([0-3]?\d)(?:st|nd|rd|th)?\s+({month_names}),?\s+((?:19|20)\d{{2}})\b",
        re.IGNORECASE,
    )
    for m in named_date_2.finditer(text_norm):
        dates.append(
            NormalizedDate(
                raw=m.group(0),
                year=int(m.group(3)),
                month=_MONTHS[m.group(2).lower()],
                day=int(m.group(1)),
            )
        )

    # 3. Month YYYY (e.g. "January 2021")
    month_year = re.compile(
        rf"\b({month_names})\s+((?:19|20)\d{{2}})\b",
        re.IGNORECASE,
    )
    for m in month_year.finditer(text_norm):
        start = m.start()
        # Skip if preceded by day digit
        if start > 2 and text_norm[start - 2 : start].strip().isdigit():
            continue
        dates.append(
            NormalizedDate(
                raw=m.group(0),
                year=int(m.group(2)),
                month=_MONTHS[m.group(1).lower()],
                day=None,
            )
        )

    # 4. Standalone Year (e.g. 2021, 1999)
    year_pattern = re.compile(r"\b((?:19|20)\d{2})\b")
    for m in year_pattern.finditer(text_norm):
        raw = m.group(1)
        if any(d.year == int(raw) and raw in d.raw for d in dates):
            continue
        dates.append(
            NormalizedDate(
                raw=raw,
                year=int(raw),
                month=None,
                day=None,
            )
        )

    return dates


def check_number_and_date_compatibility(claim: str, passage: str) -> tuple[bool, str]:
    """
    Check whether numbers and dates in the claim are compatible with the cited passage.

    Returns:
        (is_compatible, reason)
        where reason is one of "compatible", "wrong_number", "wrong_date", "missing_number"
    """
    claim_quantities = extract_quantities(claim)
    passage_quantities = extract_quantities(passage)

    claim_dates = extract_dates(claim)
    passage_dates = extract_dates(passage)

    # Check quantities / numbers
    for cq in claim_quantities:
        matched = False
        conflict = False
        for pq in passage_quantities:
            # Check unit compatibility or both are ratios/counts
            unit_match = (
                cq.base_unit == pq.base_unit
                or (cq.is_percentage and pq.is_percentage)
                or (cq.base_unit in ("ratio", "count") and pq.base_unit in ("ratio", "count"))
            )
            if unit_match:
                if math.isclose(cq.value, pq.value, rel_tol=1e-3, abs_tol=1e-4):
                    matched = True
                    break
                else:
                    # Non-trivial discrepancy in numbers across the same unit
                    conflict = True

        if not matched:
            if conflict:
                return False, "wrong_number"
            return False, "missing_number"

    # Check dates
    for cd in claim_dates:
        matched = False
        conflict = False
        for pd in passage_dates:
            if cd.year == pd.year:
                # If both specify month, they must match
                if cd.month is not None and pd.month is not None and cd.month != pd.month:
                    conflict = True
                    continue
                # If both specify day, they must match
                if cd.day is not None and pd.day is not None and cd.day != pd.day:
                    conflict = True
                    continue
                matched = True
                break
            else:
                conflict = True

        if not matched:
            if conflict:
                return False, "wrong_date"
            return False, "missing_date"

    return True, "compatible"


# ---------------------------------------------------------------------------
# 2. Named Entity Presence Check (spaCy with pure-Python fallback)
# ---------------------------------------------------------------------------

_spacy_nlp = None
_spacy_tried = False


def _get_spacy():
    global _spacy_nlp, _spacy_tried
    if _spacy_tried:
        return _spacy_nlp
    _spacy_tried = True
    try:
        import spacy  # type: ignore

        _spacy_nlp = spacy.load(SPACY_MODEL)
        logger.info("spaCy model loaded: %s", SPACY_MODEL)
    except Exception as exc:
        logger.info("spaCy unavailable (%s); using pure-Python entity extraction fallback.", exc)
        _spacy_nlp = None
    return _spacy_nlp


_STOP_ENTITIES = {
    "the", "a", "an", "this", "that", "these", "those", "it", "we", "they",
    "in", "on", "at", "to", "for", "of", "with", "by", "from", "as", "is",
    "are", "was", "were", "be", "been", "has", "have", "had", "method", "study",
    "paper", "author", "authors", "result", "results", "model", "approach",
}


def extract_named_entities(text: str) -> set[str]:
    """Extract named entities using spaCy if present, or regex-based fallback."""
    nlp = _get_spacy()
    if nlp is not None:
        try:
            doc = nlp(text)
            entities = set()
            for ent in doc.ents:
                clean = ent.text.strip().lower()
                if len(clean) > 1 and clean not in _STOP_ENTITIES:
                    entities.add(clean)
            return entities
        except Exception as exc:
            logger.warning("spaCy entity extraction failed: %s; falling back.", exc)

    # Pure-Python fallback for proper nouns, acronyms, and capitalized terms
    entities = set()
    # Acronyms (e.g. BERT, FAISS, ImageNet, DNA, COVID-19, SAC-RAG)
    for m in re.finditer(r"\b[A-Z]{2,}(?:[-_][A-Z0-9]+)*\b", text):
        entities.add(m.group(0).lower())

    # Capitalized Multi-word or Single Capitalized Names (excluding sentence starters)
    # Tokenize into sentences first
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for s in sentences:
        words = s.split()
        for idx, w in enumerate(words):
            # Clean punctuation
            w_clean = re.sub(r"^[^\w]+|[^\w]+$", "", w)
            if not w_clean:
                continue
            # If word is capitalized and not first word in sentence (or capitalized camelCase)
            is_camel = bool(re.search(r"[a-z][A-Z]", w_clean))
            if is_camel or (w_clean[0].isupper() and idx > 0 and w_clean.lower() not in _STOP_ENTITIES):
                entities.add(w_clean.lower())

    return entities


def check_named_entity_presence(claim: str, passage: str) -> tuple[bool, list[str]]:
    """Verify that all named entities in the claim are present in the cited passage."""
    claim_entities = extract_named_entities(claim)
    if not claim_entities:
        return True, []

    passage_lower = unicodedata.normalize("NFKC", passage).lower()
    missing = []
    for ent in claim_entities:
        # Check direct substring or word boundary
        if ent not in passage_lower:
            missing.append(ent)

    if missing:
        return False, missing
    return True, []


# ---------------------------------------------------------------------------
# 3. Hugging Face NLI Entailment Classifier (with Semantic Fallback)
# ---------------------------------------------------------------------------

_nli_pipeline = None
_nli_tried = False


def _get_nli_pipeline():
    global _nli_pipeline, _nli_tried
    if _nli_tried:
        return _nli_pipeline
    _nli_tried = True
    try:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline  # type: ignore

        try:
            tok = AutoTokenizer.from_pretrained(NLI_MODEL, local_files_only=True)
            mod = AutoModelForSequenceClassification.from_pretrained(NLI_MODEL, local_files_only=True)
            _nli_pipeline = pipeline("text-classification", model=mod, tokenizer=tok)
        except Exception:
            _nli_pipeline = pipeline("text-classification", model=NLI_MODEL)
        logger.info("HF NLI model loaded: %s", NLI_MODEL)
    except Exception as exc:
        logger.info("HF NLI unavailable (%s); using rule-based entailment fallback.", exc)
        _nli_pipeline = None
    return _nli_pipeline


_CONTRADICTION_PAIRS = [
    ("increased", "decreased"),
    ("increase", "decrease"),
    ("improved", "degraded"),
    ("improve", "degrade"),
    ("improved", "worsened"),
    ("higher", "lower"),
    ("succeeded", "failed"),
    ("success", "failure"),
    ("effective", "ineffective"),
    ("positive", "negative"),
    ("superior", "inferior"),
    ("converged", "failed to converge"),
    ("safe", "dangerous"),
    ("supported", "refuted"),
    ("supported", "contradicted"),
]


def _normalize_numbers_for_nli(text: str) -> str:
    """Normalize percentages and numbers so paraphrases like '95% recall' and '0.95 recall' match."""
    def _pct_to_dec(m):
        if m.group(1):
            val = float(m.group(1)) / 100.0
        elif m.group(2):
            val = _WORD_NUMBERS[m.group(2).lower()] / 100.0
        else:
            return m.group(0)
        return f"{val:g}"

    pct_pattern = re.compile(
        r"\b(?:(\d+(?:\.\d+)?)|(" + "|".join(_WORD_NUMBERS.keys()) + r"))\s*(?:%|percent\b|pct\b)",
        re.IGNORECASE,
    )
    return pct_pattern.sub(_pct_to_dec, text)


def classify_nli(
    premise: str,
    hypothesis: str,
    nli_fn: Callable[[str, str], dict[str, float]] | None = None,
) -> dict[str, float]:
    """
    Classify NLI relationship: premise (passage) -> hypothesis (claim).

    Returns:
        dict: {"entailment": float, "neutral": float, "contradiction": float}
    """
    if nli_fn is not None:
        return nli_fn(premise, hypothesis)

    p_norm_num = _normalize_numbers_for_nli(premise)
    h_norm_num = _normalize_numbers_for_nli(hypothesis)

    hf_pipe = _get_nli_pipeline()
    if hf_pipe is not None:
        try:
            out = hf_pipe({"text": p_norm_num, "text_pair": h_norm_num}, top_k=None)
            if isinstance(out, list) and out:
                scores = {"entailment": 0.0, "neutral": 0.0, "contradiction": 0.0}
                for item in out:
                    label = item.get("label", "").lower()
                    score = float(item.get("score", 0.0))
                    if "entail" in label:
                        scores["entailment"] = score
                    elif "contra" in label:
                        scores["contradiction"] = score
                    else:
                        scores["neutral"] = score
                return scores
        except Exception as exc:
            logger.warning("HF NLI pipeline inference failed: %s; falling back.", exc)

    # Pure-Python rule-based semantic NLI fallback
    p_norm = unicodedata.normalize("NFKC", p_norm_num).lower()
    h_norm = unicodedata.normalize("NFKC", h_norm_num).lower()

    # 1. Contradiction detection via antonyms and polarity reversal
    for pos, neg in _CONTRADICTION_PAIRS:
        if (pos in p_norm and neg in h_norm) or (neg in p_norm and pos in h_norm):
            return {"contradiction": 0.95, "neutral": 0.04, "entailment": 0.01}

    # Negation flips: e.g. "does not" vs "does", "not improve" vs "improves"
    neg_pattern = re.compile(r"\b(not|never|fails? to|cannot|no)\b")
    p_neg = bool(neg_pattern.search(p_norm))
    h_neg = bool(neg_pattern.search(h_norm))
    if p_neg != h_neg:
        # Check if they share the primary content words
        p_words = set(re.findall(r"\b\w{4,}\b", p_norm)) - _STOP_ENTITIES
        h_words = set(re.findall(r"\b\w{4,}\b", h_norm)) - _STOP_ENTITIES
        if len(p_words & h_words) >= 2:
            return {"contradiction": 0.90, "neutral": 0.08, "entailment": 0.02}

    # 2. Entailment / Paraphrase detection via token and n-gram overlap
    p_tokens = set(re.findall(r"\b\w+\b", p_norm)) - _STOP_ENTITIES
    h_tokens = set(re.findall(r"\b\w+\b", h_norm)) - _STOP_ENTITIES

    if not h_tokens:
        return {"entailment": 0.33, "neutral": 0.34, "contradiction": 0.33}

    overlap = len(p_tokens & h_tokens) / len(h_tokens)
    if overlap >= 0.5:
        entail_score = min(0.99, 0.6 + overlap * 0.39)
        return {"entailment": round(entail_score, 4), "neutral": round(1.0 - entail_score, 4), "contradiction": 0.01}

    return {"entailment": 0.15, "neutral": 0.80, "contradiction": 0.05}


# ---------------------------------------------------------------------------
# 4. Atomic Claim Splitter (LLM with Regex Fallback)
# ---------------------------------------------------------------------------

_SPLIT_CLAIMS_SYSTEM = """\
You are an expert NLP claim extraction engine.
Split the provided text into distinct atomic factual claims.
Each claim must be an independent, self-contained statement.
Return ONLY valid JSON matching this schema:
{
  "claims": [
    {
      "text": "<atomic claim>",
      "source_ids": ["<passage id if indicated>"],
      "quote": "<exact supporting excerpt if available>"
    }
  ]
}
""".strip()

_SPLIT_CLAIMS_USER = """\
Split this answer into atomic claims:

Answer:
{answer}
""".strip()


def split_into_atomic_claims(
    answer: str,
    passages: list[dict] | dict[str, str] | None = None,
    llm: Any = None,
) -> list[dict]:
    """Split generated text into atomic claims."""
    if not answer or not answer.strip():
        return []

    # Try LLM splitting first if available
    if llm is not None:
        try:
            prompt = _SPLIT_CLAIMS_USER.format(answer=answer)
            resp = llm.generate(prompt, _SPLIT_CLAIMS_SYSTEM)
            text = resp.answer if hasattr(resp, "answer") else str(resp)
            # Clean markdown code fences
            text = re.sub(r"```(?:json)?\s*", "", text).replace("```", "")
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                data = json.loads(match.group())
                raw_claims = data.get("claims", [])
                if isinstance(raw_claims, list) and raw_claims:
                    return [
                        {
                            "text": str(c.get("text", "")).strip(),
                            "source_ids": [str(s) for s in c.get("source_ids", [])],
                            "quote": str(c.get("quote", "")).strip() or None,
                        }
                        for c in raw_claims
                        if str(c.get("text", "")).strip()
                    ]
        except Exception as exc:
            logger.warning("LLM claim splitting failed (%s); falling back to sentence segmentation.", exc)

    # Pure-Python fallback: regex sentence segmentation
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", answer) if s.strip()]
    claims: list[dict] = []
    for s in sentences:
        claims.append({
            "text": s,
            "source_ids": [],
            "quote": None,
        })
    return claims


# ---------------------------------------------------------------------------
# 5. Core Atomic Claim Verifier & Labeler
# ---------------------------------------------------------------------------

def verify_atomic_claim(
    claim_text: str,
    passage_text: str,
    source_ids: list[str] | None = None,
    quote: str | None = None,
    nli_fn: Callable[[str, str], dict[str, float]] | None = None,
) -> Claim:
    """
    Verify an atomic claim against a cited passage.

    Applies:
      1. NLI entailment
      2. Number and date match with normalization
      3. Named entity presence check
    """
    source_ids = source_ids or []
    if not passage_text or not passage_text.strip():
        return Claim(text=claim_text, label="unsupported", source_ids=source_ids, quote=quote)

    # 1. NLI classification
    nli_scores = classify_nli(passage_text, claim_text, nli_fn=nli_fn)
    p_contra = nli_scores.get("contradiction", 0.0)
    p_entail = nli_scores.get("entailment", 0.0)

    # 2. Number & Date compatibility
    num_ok, num_reason = check_number_and_date_compatibility(claim_text, passage_text)

    # 3. Named Entity presence
    ent_ok, missing_ents = check_named_entity_presence(claim_text, passage_text)

    # Decision Matrix
    if p_contra >= 0.5 or num_reason in ("wrong_number", "wrong_date"):
        label = "contradicted"
    elif not num_ok or not ent_ok or p_entail < 0.5:
        # Check if partially supported (some entity overlap or moderate entailment)
        if p_entail >= 0.3 and num_reason != "wrong_number":
            label = "partial"
        else:
            label = "unsupported"
    else:
        label = "supported"

    return Claim(text=claim_text, label=label, source_ids=source_ids, quote=quote)


# ---------------------------------------------------------------------------
# 6. Single-Turn Regeneration from Passage Alone
# ---------------------------------------------------------------------------

_REGENERATE_PROMPT = """\
Using ONLY the following passage, generate ONE strictly factual, grounded sentence addressing the claim topic.
If the passage does not support any claim on this topic, return: NONE.

Passage:
{passage}

Claim topic:
{claim}
""".strip()


def regenerate_claim_from_passage(
    claim_text: str,
    passage_text: str,
    llm: Any,
) -> str | None:
    """Regenerate a claim once using only the cited passage."""
    if llm is None:
        return None
    try:
        prompt = _REGENERATE_PROMPT.format(passage=passage_text, claim=claim_text)
        resp = llm.generate(prompt, "You are a factual summarizer. Use only the provided passage.")
        answer = resp.answer if hasattr(resp, "answer") else str(resp)
        answer = answer.strip()
        if not answer or answer.upper() == "NONE" or "not found" in answer.lower():
            return None
        return answer
    except Exception as exc:
        logger.warning("Claim regeneration failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# 7. End-to-End Claim Processing & Answer Refinement
# ---------------------------------------------------------------------------

def process_and_verify_claims(
    answer: str,
    passages: list[dict] | dict[str, str],
    llm: Any = None,
    nli_fn: Callable[[str, str], dict[str, float]] | None = None,
) -> tuple[list[Claim], str]:
    """
    Split answer into claims, verify against cited passages, regenerate once if not supported,
    drop if still not supported, and reconstruct verified answer.

    Returns:
        (claims, refined_answer_text)
    """
    # Build fast passage lookup
    passage_lookup: dict[str, str] = {}
    combined_passage_text = ""
    if isinstance(passages, dict):
        passage_lookup = {str(k): str(v) for k, v in passages.items()}
        combined_passage_text = " ".join(passages.values())
    elif isinstance(passages, list):
        for idx, p in enumerate(passages, start=1):
            cid = str(p.get("chunk_id", p.get("id", idx)))
            text = str(p.get("text", ""))
            passage_lookup[cid] = text
            passage_lookup[str(idx)] = text
            combined_passage_text += " " + text

    raw_claims = split_into_atomic_claims(answer, passages, llm=llm)
    verified_claims: list[Claim] = []

    for raw in raw_claims:
        c_text = raw["text"]
        c_sources = raw.get("source_ids", [])
        c_quote = raw.get("quote")

        # Determine passage to verify against
        target_passage = ""
        for s in c_sources:
            if s in passage_lookup:
                target_passage += " " + passage_lookup[s]
        if not target_passage.strip():
            target_passage = combined_passage_text

        # First verification check
        claim_obj = verify_atomic_claim(
            claim_text=c_text,
            passage_text=target_passage,
            source_ids=c_sources,
            quote=c_quote,
            nli_fn=nli_fn,
        )

        # If not supported: regenerate once from the passage alone, re-check, else drop
        if claim_obj.label != "supported":
            logger.info("Claim %r is %s; attempting single-turn regeneration.", c_text[:60], claim_obj.label)
            regen_text = regenerate_claim_from_passage(c_text, target_passage, llm)
            if regen_text:
                rechecked = verify_atomic_claim(
                    claim_text=regen_text,
                    passage_text=target_passage,
                    source_ids=c_sources,
                    quote=c_quote,
                    nli_fn=nli_fn,
                )
                if rechecked.label == "supported":
                    logger.info("Regenerated claim verified as supported: %r", regen_text[:60])
                    verified_claims.append(rechecked)
                else:
                    logger.info("Regenerated claim failed verification (%s); dropping.", rechecked.label)
            else:
                logger.info("Regeneration yielded no claim; dropping original claim.")
        else:
            verified_claims.append(claim_obj)

    # Reconstruct refined answer from surviving claims
    if verified_claims:
        refined_answer = " ".join(c.text for c in verified_claims)
    else:
        refined_answer = "Not found in available sources."

    return verified_claims, refined_answer


def build_answer_response(
    query: str,
    answer: str,
    passages: list[dict] | dict[str, str],
    llm: Any = None,
    nli_fn: Callable[[str, str], dict[str, float]] | None = None,
    sources: list[dict[str, Any]] | None = None,
    gaps: list[str] | None = None,
    trace_id: str | None = None,
) -> AnswerResponse:
    """Run atomic claim verification pipeline and return a complete AnswerResponse."""
    claims, refined_answer = process_and_verify_claims(answer, passages, llm=llm, nli_fn=nli_fn)

    sources_list = []
    if sources is not None:
        sources_list = sources
    elif isinstance(passages, list):
        sources_list = passages

    return AnswerResponse(
        summary=refined_answer,
        detail=refined_answer,
        doc_section=refined_answer if "Not found" not in refined_answer else None,
        sources=sources_list,
        claims=claims,
        gaps=gaps or [],
        trace_id=trace_id,
    )


def final_answer_after_claim_filter(
    claims: list,
    refined_answer: str | None,
    not_found: str,
) -> str | None:
    """
    Decide what to show after atomic claim verification.

    Returns the refined answer, or None when nothing survived verification and
    the caller must abstain (never fall back to the unverified original text).
    """
    if not claims:
        return None
    text = (refined_answer or "").strip()
    if not text or text == not_found or text == "Not found in available sources.":
        return None
    return refined_answer
