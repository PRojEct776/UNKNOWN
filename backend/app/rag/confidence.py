"""
UNKNOWN X – Confidence & Canonical Source Module (Task A7)

Implements:
1. compute_confidence(statuses, claims, sources, conflicts) -> Confidence
   score = 100 * (w1*coverage + w2*claim_support + w3*agreement + w4*quality)
   with weights from config, breakdown, and formula_version.
2. build_sources(results) -> list[Source]
   Single canonical source builder used across all endpoints:
   - Stable ID: hash(url or doc_id+chunk)
   - Stable order: reliability desc, then id
   - Fully deterministic output
"""

from __future__ import annotations

import hashlib
import math
import os
from typing import Any

from app.api.schemas import (
    Claim,
    Confidence,
    ConfidenceBreakdown,
    Conflict,
    Source,
)
from app.rag.config import (
    CONFIDENCE_FORMULA_VERSION,
    CONFIDENCE_W_AGREEMENT,
    CONFIDENCE_W_CLAIM_SUPPORT,
    CONFIDENCE_W_COVERAGE,
    CONFIDENCE_W_QUALITY,
)
from app.rag.reliability import compute_reliability, get_source_warnings


# ---------------------------------------------------------------------------
# 1. Stable Source ID & Builder
# ---------------------------------------------------------------------------

def compute_stable_source_id(item: dict | Any) -> str:
    """
    Compute a deterministic stable ID for a source:
    hash(url or doc_id+chunk).
    """
    if isinstance(item, dict):
        url = item.get("url")
        if url and str(url).strip():
            key = str(url).strip()
        else:
            doc = item.get("document", item.get("doc_id", "unknown"))
            chunk = item.get("chunk_id", item.get("page", "0"))
            key = f"{doc}:{chunk}"
    else:
        url = getattr(item, "url", None)
        if url and str(url).strip():
            key = str(url).strip()
        else:
            doc = getattr(item, "document", getattr(item, "doc_id", "unknown"))
            chunk = getattr(item, "chunk_id", getattr(item, "page", "0"))
            key = f"{doc}:{chunk}"

    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def build_sources(results: list[dict | Any]) -> list[Source]:
    """
    Canonical source builder used by every endpoint.

    Guarantees:
      - Stable ID: hash(url or doc_id+chunk)
      - Stable order: reliability DESC, then id ASC
      - Deterministic ranking: rank 1, 2, 3...
    """
    if not results:
        return []

    sources: list[Source] = []
    for item in results:
        # Extract attributes handling dict or object
        if isinstance(item, dict):
            doc = str(item.get("document", item.get("doc_id", "Unknown")))
            page = item.get("page", "N/A")
            chunk_id = str(item.get("chunk_id", "N/A"))
            hybrid_score = float(item.get("hybrid_score", 0.0))
            bm25_score = float(item.get("bm25_score", 0.0))
            faiss_score = float(item.get("faiss_score", 0.0))
            title = item.get("title")
            authors = list(item.get("authors", []))
            year = item.get("year")
            venue = item.get("venue")
            doi = item.get("doi")
            url = item.get("url")
            origin = str(item.get("origin", "document"))
            passage = item.get("passage", item.get("text"))
            quote = item.get("quote")
            retrieved_at = item.get("retrieved_at")
        else:
            doc = str(getattr(item, "document", getattr(item, "doc_id", "Unknown")))
            page = getattr(item, "page", "N/A")
            chunk_id = str(getattr(item, "chunk_id", "N/A"))
            hybrid_score = float(getattr(item, "hybrid_score", 0.0))
            bm25_score = float(getattr(item, "bm25_score", 0.0))
            faiss_score = float(getattr(item, "faiss_score", 0.0))
            title = getattr(item, "title", None)
            authors = list(getattr(item, "authors", []))
            year = getattr(item, "year", None)
            venue = getattr(item, "venue", None)
            doi = getattr(item, "doi", None)
            url = getattr(item, "url", None)
            origin = str(getattr(item, "origin", "document"))
            passage = getattr(item, "passage", getattr(item, "text", None))
            quote = getattr(item, "quote", None)
            retrieved_at = getattr(item, "retrieved_at", None)

        stable_id = compute_stable_source_id(item)
        reliability = compute_reliability(item)
        warnings = get_source_warnings(item)

        source_obj = Source(
            id=stable_id,
            rank=0,  # assigned after sorting
            document=doc,
            page=page,
            chunk_id=chunk_id,
            hybrid_score=hybrid_score,
            bm25_score=bm25_score,
            faiss_score=faiss_score,
            title=title,
            authors=authors,
            year=year,
            venue=venue,
            doi=doi,
            url=url,
            origin=origin,
            passage=passage,
            quote=quote,
            retrieved_at=retrieved_at,
            reliability=reliability,
            warnings=warnings,
        )
        sources.append(source_obj)

    # Sort in stable order: reliability DESC, then id ASC
    sources.sort(key=lambda s: (-s.reliability, s.id))

    # Assign sequential 1-based ranks
    for rank, s in enumerate(sources, start=1):
        s.rank = rank

    return sources


# ---------------------------------------------------------------------------
# 2. Unified Confidence Calculator
# ---------------------------------------------------------------------------

def compute_confidence(
    statuses: list[str] | list[Any] | None = None,
    claims: list[Claim | dict] | None = None,
    sources: list[Source | dict] | None = None,
    conflicts: list[Conflict | dict] | None = None,
    *,
    w_coverage: float = CONFIDENCE_W_COVERAGE,
    w_claim_support: float = CONFIDENCE_W_CLAIM_SUPPORT,
    w_agreement: float = CONFIDENCE_W_AGREEMENT,
    w_quality: float = CONFIDENCE_W_QUALITY,
    formula_version: str = CONFIDENCE_FORMULA_VERSION,
) -> Confidence:
    """
    Single unified confidence scoring function.

    Formula:
      score = 100 * (w1*coverage + w2*claim_support + w3*agreement + w4*quality)

    Components:
      1. evidence_coverage: fraction of sub-questions satisfied (sufficient=1.0, weak=0.5)
      2. claim_support: fraction of atomic claims verified as supported
      3. source_agreement: 1.0 if zero conflicts, decays with detected conflicts
      4. source_quality: mean reliability w(s) of cited/retrieved sources

    Strictly deterministic and in [0, 100].
    """
    # 1. Normalize weights so they sum to 1.0
    total_w = w_coverage + w_claim_support + w_agreement + w_quality
    if not math.isclose(total_w, 1.0, rel_tol=1e-5):
        w_coverage /= total_w
        w_claim_support /= total_w
        w_agreement /= total_w
        w_quality /= total_w

    # 2. Evidence Coverage
    if statuses is not None and len(statuses) > 0:
        cov_points = 0.0
        for item in statuses:
            st = str(item.status if hasattr(item, "status") else (item.get("status") if isinstance(item, dict) else item)).lower()
            if "sufficient" in st and "in" not in st:
                cov_points += 1.0
            elif "weak" in st:
                cov_points += 0.5
        coverage = min(1.0, max(0.0, cov_points / len(statuses)))
    else:
        # If no sub-question statuses, coverage is 1.0 if sources/claims exist, else 0.0
        has_evidence = bool(sources) or bool(claims)
        coverage = 1.0 if has_evidence else 0.0

    # 3. Claim Support
    if claims is not None and len(claims) > 0:
        supp_count = 0.0
        for c in claims:
            lbl = str(c.label if hasattr(c, "label") else (c.get("label") if isinstance(c, dict) else "")).lower()
            if lbl == "supported":
                supp_count += 1.0
            elif lbl == "partial":
                supp_count += 0.5
        claim_support = min(1.0, max(0.0, supp_count / len(claims)))
    else:
        claim_support = 0.0

    # 4. Source Agreement
    num_conflicts = len(conflicts) if conflicts is not None else 0
    if num_conflicts == 0:
        agreement = 1.0
    else:
        agreement = max(0.0, 1.0 - (0.25 * num_conflicts))

    # 5. Source Quality
    if sources is not None and len(sources) > 0:
        rel_vals: list[float] = []
        for s in sources:
            r = getattr(s, "reliability", None)
            if r is None and isinstance(s, dict):
                r = s.get("reliability")
            if r is None:
                r = compute_reliability(s)
            rel_vals.append(max(0.0, min(1.0, float(r))))
        quality = sum(rel_vals) / len(rel_vals) if rel_vals else 0.0
    else:
        quality = 0.0

    # 6. Weighted sum in [0, 100]
    raw_score = 100.0 * (
        (w_coverage * coverage)
        + (w_claim_support * claim_support)
        + (w_agreement * agreement)
        + (w_quality * quality)
    )
    score = round(max(0.0, min(100.0, raw_score)), 2)

    breakdown = ConfidenceBreakdown(
        evidence_coverage=round(coverage, 4),
        claim_support=round(claim_support, 4),
        source_agreement=round(agreement, 4),
        source_quality=round(quality, 4),
    )

    return Confidence(
        score=score,
        breakdown=breakdown,
        formula_version=formula_version,
    )
