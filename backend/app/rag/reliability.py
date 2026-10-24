"""
UNKNOWN X – Source Reliability & Conflict Detection Layer (Task A6)

1. Reliability w(s):
   w(s) = 0 if retracted (Crossref/OpenAlex flag)
   else:
     w(s) = alpha * V + beta * R + gamma * C
     with alpha + beta + gamma = 1.0:
       V: venue/source quality from config table (preprints lower)
       R = exp(-lambda * age_years)
       C = log(1 + cites) / log(1 + cites_max)
   Generates warnings on retracted or preprint sources.

2. Conflict Detection:
   For claims on the same sub-question, runs NLI.
   A contradiction becomes Conflict{topic, side_a, side_b, likely_reason}
   where likely_reason is deduced from year, dataset, or method metadata.
"""

from __future__ import annotations

import math
import os
import re
from datetime import datetime, timezone
from typing import Any, Callable

from app.api.schemas import Conflict
from app.rag.atomic_claims import classify_nli
from app.rag.logger import logger

# ---------------------------------------------------------------------------
# Configurable Weights & Parameters
# ---------------------------------------------------------------------------

RELIABILITY_ALPHA: float = float(os.environ.get("RELIABILITY_ALPHA", "0.40"))
RELIABILITY_BETA: float = float(os.environ.get("RELIABILITY_BETA", "0.30"))
RELIABILITY_GAMMA: float = float(os.environ.get("RELIABILITY_GAMMA", "0.30"))

RELIABILITY_LAMBDA: float = float(os.environ.get("RELIABILITY_LAMBDA", "0.05"))
RELIABILITY_CITES_MAX: float = float(os.environ.get("RELIABILITY_CITES_MAX", "1000.0"))

CURRENT_YEAR: int = 2026

# ---------------------------------------------------------------------------
# Venue / Source Quality Table (V)
# ---------------------------------------------------------------------------

VENUE_QUALITY_MAP: dict[str, float] = {
    # Top Tier Scientific Journals (1.00)
    "nature": 1.00,
    "science": 1.00,
    "cell": 1.00,
    "the lancet": 1.00,
    "lancet": 1.00,
    "new england journal of medicine": 1.00,
    "nejm": 1.00,
    "jama": 1.00,
    # Top Tier AI / ML Conferences (0.95)
    "neurips": 0.95,
    "icml": 0.95,
    "iclr": 0.95,
    "acl": 0.95,
    "emnlp": 0.95,
    "cvpr": 0.95,
    "iccv": 0.95,
    "pnas": 0.95,
    # High Impact Peer-Reviewed Publishers (0.80 - 0.85)
    "ieee": 0.85,
    "acm": 0.85,
    "springer": 0.80,
    "elsevier": 0.80,
    "wiley": 0.80,
    "oxford": 0.80,
    "cambridge": 0.80,
    "plos": 0.80,
    "plos one": 0.75,
    # General Scholarly / Peer-Reviewed Default (0.75)
    "scholarly": 0.75,
    "journal": 0.75,
    "conference": 0.75,
    # General Document / Web (0.50 - 0.60)
    "document": 0.60,
    "web": 0.50,
    "wikipedia": 0.50,
    # Preprints (Explicitly Lower: 0.40)
    "arxiv": 0.40,
    "biorxiv": 0.40,
    "medrxiv": 0.40,
    "chemrxiv": 0.40,
    "ssrn": 0.40,
    "preprint": 0.40,
    "preprints": 0.40,
}

_PREPRINT_KEYWORDS = {"arxiv", "biorxiv", "medrxiv", "chemrxiv", "ssrn", "preprint", "preprints"}


def is_preprint_source(venue: str | None, url: str | None = None, origin: str | None = None) -> bool:
    """Determine whether a source is a preprint."""
    text = f"{venue or ''} {url or ''} {origin or ''}".lower()
    return any(p in text for p in _PREPRINT_KEYWORDS)


def is_retracted_source(source: dict | Any) -> bool:
    """Check if a source is flagged as retracted."""
    if isinstance(source, dict):
        if source.get("is_retracted") or source.get("retracted"):
            return True
        status = str(source.get("status", "")).lower()
        if "retract" in status:
            return True
        # Check inside metadata dict if present
        meta = source.get("metadata", {})
        if isinstance(meta, dict):
            if meta.get("is_retracted") or meta.get("retracted"):
                return True
            if "retract" in str(meta.get("status", "")).lower():
                return True
    else:
        if getattr(source, "is_retracted", False) or getattr(source, "retracted", False):
            return True
    return False


def get_venue_quality(
    venue: str | None,
    origin: str | None = None,
    url: str | None = None,
    is_preprint: bool = False,
) -> float:
    """Determine quality score V in [0, 1] from the venue quality table."""
    if is_preprint or is_preprint_source(venue, url, origin):
        return VENUE_QUALITY_MAP["preprint"]

    v_str = (venue or "").strip().lower()
    if v_str:
        for k, score in VENUE_QUALITY_MAP.items():
            if k in v_str:
                return score

    # Fallback to origin
    orig = (origin or "").strip().lower()
    if orig in VENUE_QUALITY_MAP:
        return VENUE_QUALITY_MAP[orig]

    return 0.60  # Default document quality


# ---------------------------------------------------------------------------
# Reliability w(s)
# ---------------------------------------------------------------------------

def compute_reliability(
    source: dict | Any,
    alpha: float = RELIABILITY_ALPHA,
    beta: float = RELIABILITY_BETA,
    gamma: float = RELIABILITY_GAMMA,
    lambda_param: float = RELIABILITY_LAMBDA,
    cites_max: float = RELIABILITY_CITES_MAX,
    current_year: int = CURRENT_YEAR,
) -> float:
    """
    Compute reliability score w(s) for a source:
      - w(s) = 0 if retracted
      - else w(s) = alpha*V + beta*R + gamma*C
    Strictly deterministic and in [0, 1].
    """
    # 1. Retraction Check
    if is_retracted_source(source):
        return 0.0

    # Normalize weights so alpha + beta + gamma == 1.0
    total_w = alpha + beta + gamma
    if not math.isclose(total_w, 1.0, rel_tol=1e-5):
        alpha /= total_w
        beta /= total_w
        gamma /= total_w

    # Extract source attributes
    if isinstance(source, dict):
        venue = source.get("venue")
        url = source.get("url")
        origin = source.get("origin")
        year = source.get("year")
        cites = source.get("cites", source.get("cited_by_count", 0))
        is_pre = source.get("is_preprint", False)
    else:
        venue = getattr(source, "venue", None)
        url = getattr(source, "url", None)
        origin = getattr(source, "origin", None)
        year = getattr(source, "year", None)
        cites = getattr(source, "cites", getattr(source, "cited_by_count", 0))
        is_pre = getattr(source, "is_preprint", False)

    # V: Venue score
    V = get_venue_quality(venue=venue, origin=origin, url=url, is_preprint=is_pre)

    # R: Recency factor = exp(-lambda * age_years)
    if year is not None:
        try:
            y_int = int(year)
            age_years = max(0.0, float(current_year - y_int))
        except (ValueError, TypeError):
            age_years = 5.0
    else:
        age_years = 5.0
    R = math.exp(-lambda_param * age_years)

    # C: Citation impact factor = log(1 + cites) / log(1 + cites_max)
    try:
        c_val = max(0.0, float(cites or 0.0))
    except (ValueError, TypeError):
        c_val = 0.0
    denom = math.log(1.0 + max(1.0, cites_max))
    C = min(1.0, math.log(1.0 + c_val) / denom)

    # Weighted sum
    w = (alpha * V) + (beta * R) + (gamma * C)
    return round(max(0.0, min(1.0, w)), 4)


def get_source_warnings(source: dict | Any) -> list[str]:
    """Generate warnings for retracted or preprint sources."""
    warnings: list[str] = []

    if isinstance(source, dict):
        title = source.get("title", source.get("document", "Source"))
        venue = source.get("venue")
        url = source.get("url")
        origin = source.get("origin")
        is_pre = source.get("is_preprint", False)
    else:
        title = getattr(source, "title", getattr(source, "document", "Source"))
        venue = getattr(source, "venue", None)
        url = getattr(source, "url", None)
        origin = getattr(source, "origin", None)
        is_pre = getattr(source, "is_preprint", False)

    if is_retracted_source(source):
        warnings.append(f"WARNING: Source '{title}' has been RETRACTED.")

    if is_pre or is_preprint_source(venue, url, origin):
        warnings.append(f"WARNING: Source '{title}' is a PREPRINT and has not undergone formal peer review.")

    return warnings


def compute_reliability_breakdown(
    source: dict | Any,
    alpha: float = RELIABILITY_ALPHA,
    beta: float = RELIABILITY_BETA,
    gamma: float = RELIABILITY_GAMMA,
    lambda_param: float = RELIABILITY_LAMBDA,
    cites_max: float = RELIABILITY_CITES_MAX,
    current_year: int = CURRENT_YEAR,
) -> dict[str, Any]:
    """Detailed reliability breakdown with warnings."""
    retracted = is_retracted_source(source)
    score = compute_reliability(
        source,
        alpha=alpha,
        beta=beta,
        gamma=gamma,
        lambda_param=lambda_param,
        cites_max=cites_max,
        current_year=current_year,
    )
    warnings = get_source_warnings(source)

    if isinstance(source, dict):
        venue = source.get("venue")
        url = source.get("url")
        origin = source.get("origin")
        year = source.get("year")
        cites = source.get("cites", source.get("cited_by_count", 0))
        is_pre = source.get("is_preprint", False) or is_preprint_source(venue, url, origin)
    else:
        venue = getattr(source, "venue", None)
        url = getattr(source, "url", None)
        origin = getattr(source, "origin", None)
        year = getattr(source, "year", None)
        cites = getattr(source, "cites", getattr(source, "cited_by_count", 0))
        is_pre = getattr(source, "is_preprint", False) or is_preprint_source(venue, url, origin)

    V = get_venue_quality(venue=venue, origin=origin, url=url, is_preprint=is_pre)
    age = max(0.0, float(current_year - int(year))) if year else 5.0
    R = math.exp(-lambda_param * age)
    C = min(1.0, math.log(1.0 + float(cites or 0)) / math.log(1.0 + cites_max))

    return {
        "reliability": score,
        "is_retracted": retracted,
        "is_preprint": is_pre,
        "V": round(V, 4),
        "R": round(R, 4),
        "C": round(C, 4),
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Conflict Detection
# ---------------------------------------------------------------------------

def _deduce_likely_reason(meta_a: dict, meta_b: dict) -> str:
    """
    Deduce the likely reason for a factual conflict from metadata:
    (year differences, dataset differences, or method differences).
    """
    year_a = meta_a.get("year")
    year_b = meta_b.get("year")
    dataset_a = meta_a.get("dataset")
    dataset_b = meta_b.get("dataset")
    method_a = meta_a.get("method")
    method_b = meta_b.get("method")

    reasons: list[str] = []

    # 1. Temporal divergence
    if year_a and year_b and year_a != year_b:
        reasons.append(f"Temporal divergence (study A from {year_a} vs study B from {year_b})")

    # 2. Dataset / population divergence
    if dataset_a and dataset_b and str(dataset_a).lower() != str(dataset_b).lower():
        reasons.append(f"Evaluated on different datasets/cohorts ('{dataset_a}' vs '{dataset_b}')")

    # 3. Methodological difference
    if method_a and method_b and str(method_a).lower() != str(method_b).lower():
        reasons.append(f"Methodological difference in approaches ('{method_a}' vs '{method_b}')")

    if reasons:
        return "; ".join(reasons)
    return "Differing experimental conditions or evaluation metrics across studies"


def detect_conflicts(
    claims: list[dict | Any],
    topic: str = "Research Findings",
    nli_fn: Callable[[str, str], dict[str, float]] | None = None,
    source_metadata_lookup: dict[str, dict] | None = None,
) -> list[Conflict]:
    """
    Detect contradictions among top claims on the same sub-question / topic.

    For each pair of claims, runs NLI. A mutual contradiction becomes a Conflict:
      Conflict{topic, side_a, side_b, likely_reason}
    """
    source_metadata_lookup = source_metadata_lookup or {}
    conflicts: list[Conflict] = []
    seen_pairs: set[frozenset[str]] = set()

    for i in range(len(claims)):
        for j in range(i + 1, len(claims)):
            claim_a = claims[i]
            claim_b = claims[j]

            text_a = claim_a.get("text", "") if isinstance(claim_a, dict) else getattr(claim_a, "text", str(claim_a))
            text_b = claim_b.get("text", "") if isinstance(claim_b, dict) else getattr(claim_b, "text", str(claim_b))

            if not text_a or not text_b or text_a == text_b:
                continue

            pair_key = frozenset([text_a, text_b])
            if pair_key in seen_pairs:
                continue

            # Run NLI in both directions to verify mutual contradiction
            nli_ab = classify_nli(premise=text_a, hypothesis=text_b, nli_fn=nli_fn)
            nli_ba = classify_nli(premise=text_b, hypothesis=text_a, nli_fn=nli_fn)

            p_contra = max(nli_ab.get("contradiction", 0.0), nli_ba.get("contradiction", 0.0))

            if p_contra >= 0.5:
                seen_pairs.add(pair_key)

                # Extract metadata for both sides
                meta_a: dict = {}
                meta_b: dict = {}

                # Check if claims themselves carry metadata
                if isinstance(claim_a, dict):
                    meta_a = claim_a.get("metadata", {})
                    src_a = str(claim_a.get("source_ids", [""])[0] if claim_a.get("source_ids") else "")
                    if src_a in source_metadata_lookup:
                        meta_a = {**source_metadata_lookup[src_a], **meta_a}

                if isinstance(claim_b, dict):
                    meta_b = claim_b.get("metadata", {})
                    src_b = str(claim_b.get("source_ids", [""])[0] if claim_b.get("source_ids") else "")
                    if src_b in source_metadata_lookup:
                        meta_b = {**source_metadata_lookup[src_b], **meta_b}

                likely_reason = _deduce_likely_reason(meta_a, meta_b)

                conflict = Conflict(
                    topic=topic,
                    side_a=text_a,
                    side_b=text_b,
                    likely_reason=likely_reason,
                )
                conflicts.append(conflict)
                logger.info("Detected Conflict on topic %r: side_a=%r, side_b=%r", topic[:40], text_a[:40], text_b[:40])

    return conflicts
