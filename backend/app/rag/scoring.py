"""
UNKNOWN X v2.0 - Document IQ Scoring Engine

Purpose:
- Calculate a 0-100 IQ score for every indexed document.
- Produce detailed quality metrics.
- Assign grades for dashboard, analytics, and IEEE evaluation.

Milestone 1 / Step 3 (transparency):
- The scoring FORMULA and WEIGHTS are unchanged, so existing scores do not move.
- Every component now reports its `basis`:
    measured    -> computed from a value the pipeline actually recorded
    assumed     -> a default was used because nothing was measured (points are still awarded
                   by the unchanged formula, but they are disclosed as assumption-based)
    unavailable -> the input was missing or could not be verified; the score uses the
                   formula's fallback value
- Every component explains how its score is calculated and what it does NOT measure.
"""

from typing import Any

# ==========================================================
# Helper
# ==========================================================


def clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    """Clamp a numeric value within a range."""
    return max(minimum, min(value, maximum))


def _component(
    score: float,
    max_score: float,
    basis: str,
    how_calculated: str,
    inputs: dict[str, Any],
    note: str | None = None,
) -> dict[str, Any]:
    """One entry of the per-component breakdown."""
    return {
        "score": round(score, 2),
        "max_score": max_score,
        "basis": basis,  # measured | assumed | unavailable
        "how_calculated": how_calculated,
        "inputs": inputs,
        "note": note,
    }


# ==========================================================
# Document IQ Calculator
# ==========================================================


def calculate_document_iq(metadata: dict) -> dict:
    """
    Calculate Document IQ Score from standardized metadata.

    Expected metadata comes from:
        app.services.document_service.build_document_metadata()
    """

    pages = metadata.get("pages", 0)
    chunks = metadata.get("chunks", 0)
    words = metadata.get("text_length", 0)

    embedding = metadata.get("embedding_status", False)
    embedding_detail = metadata.get("embedding_status_detail")
    completeness = metadata.get("metadata_completeness", 0.0)

    ocr_required = metadata.get("ocr_required", False)
    ocr_quality = metadata.get("ocr_quality", 1.0)
    ocr_basis = metadata.get("ocr_basis")

    # ------------------------------------------------------
    # Metric 1 — Text Extraction Quality (25)
    # ------------------------------------------------------

    extraction_score = clamp(min(words / 5000, 1.0) * 25, 0, 25)
    extraction_basis = "measured" if "text_length" in metadata else "unavailable"

    # ------------------------------------------------------
    # Metric 2 — Chunk Coverage / Density (20)
    # Ideal ≈ 2 chunks per page
    # ------------------------------------------------------

    chunk_density = chunks / max(pages, 1)
    chunk_score = clamp(min(chunk_density / 2, 1.0) * 20, 0, 20)
    chunk_basis = "measured" if ("chunks" in metadata and pages > 0) else "unavailable"

    # ------------------------------------------------------
    # Metric 3 — Embedding Availability (20)
    # ------------------------------------------------------

    embedding_score = 20 if embedding else 0
    if embedding:
        embedding_basis = "measured"
    elif embedding_detail in ("missing", "no_chunks", "inconsistent"):
        # The verification ran and found the index absent, empty or not matching the chunks.
        embedding_basis = "measured"
    else:
        # "unverified" (the check itself failed) or no detail recorded at all.
        embedding_basis = "unavailable"

    # ------------------------------------------------------
    # Metric 4 — OCR / Text Quality (20)
    # ------------------------------------------------------

    if ocr_required:
        ocr_score = clamp(ocr_quality * 20, 0, 20)
    else:
        # Documents whose pages all contain text receive full credit.
        ocr_score = 20

    if ocr_basis == "page_text_coverage":
        ocr_component_basis = "measured"
    elif ocr_basis == "assumed_no_page_data":
        ocr_component_basis = "assumed"
    elif ocr_required and "ocr_quality" in metadata:
        # Older metadata without ocr_basis: quality is only computed when pages were inspected.
        ocr_component_basis = "measured"
    else:
        # Older metadata, full credit by default: no evidence that pages were inspected.
        ocr_component_basis = "assumed"

    # ------------------------------------------------------
    # Metric 5 — Metadata Completeness (15)
    # ------------------------------------------------------

    metadata_score = clamp(completeness * 15, 0, 15)
    metadata_basis = "measured" if "metadata_completeness" in metadata else "unavailable"

    # ------------------------------------------------------
    # Final IQ Score
    # ------------------------------------------------------

    iq_score = round(
        extraction_score + chunk_score + embedding_score + ocr_score + metadata_score,
        2,
    )

    # ------------------------------------------------------
    # Grade
    # ------------------------------------------------------

    if iq_score >= 90:
        grade = "A+"
    elif iq_score >= 80:
        grade = "A"
    elif iq_score >= 70:
        grade = "B"
    elif iq_score >= 60:
        grade = "C"
    else:
        grade = "D"

    # ------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------

    if iq_score >= 90:
        health = "Excellent"
    elif iq_score >= 80:
        health = "Very Good"
    elif iq_score >= 70:
        health = "Good"
    elif iq_score >= 60:
        health = "Fair"
    else:
        health = "Poor"

    # ------------------------------------------------------
    # Transparent per-component breakdown
    # ------------------------------------------------------

    components = {
        "extraction": _component(
            extraction_score,
            25,
            extraction_basis,
            "Words extracted ÷ 5,000, capped at 1, × 25.",
            {"words": words},
            "Measures how much text was extracted (volume). It does not judge whether the text is "
            "correct, and short documents score lower regardless of quality.",
        ),
        "chunk_coverage": _component(
            chunk_score,
            20,
            chunk_basis,
            "Chunks per page ÷ 2 (target density), capped at 1, × 20.",
            {"pages": pages, "chunks": chunks, "chunks_per_page": round(chunk_density, 2)},
            None if chunk_basis == "measured"
            else "Page count or chunk count was not recorded; the score uses the formula's fallback value.",
        ),
        "embedding": _component(
            embedding_score,
            20,
            embedding_basis,
            "20 points only if the FAISS index covers every chunk of this document "
            "(verified chunk IDs match); otherwise 0.",
            {"embedding_status": bool(embedding), "verification": embedding_detail},
            None if embedding_basis == "measured"
            else "Embedding coverage could not be verified, so no points were awarded.",
        ),
        "ocr_text_quality": _component(
            ocr_score,
            20,
            ocr_component_basis,
            "If every page has extractable text: full 20 points. If some pages are empty: "
            "(share of pages with text) × 20.",
            {"ocr_required": bool(ocr_required), "text_coverage": ocr_quality, "ocr_basis": ocr_basis},
            "This is a text-coverage proxy, not an OCR confidence score."
            if ocr_component_basis == "measured"
            else "No page-level measurement was recorded; full credit was awarded by default.",
        ),
        "metadata_completeness": _component(
            metadata_score,
            15,
            metadata_basis,
            "Share of 7 pipeline checks present (title, source file, document hash, total pages, "
            "total words, read time, chunks exist) × 15.",
            {"completeness": completeness},
            "Counts pipeline fields only. It does not check authors, year or DOI.",
        ),
    }

    score_basis: dict[str, list[str]] = {"measured": [], "assumed": [], "unavailable": []}
    points_without_direct_measurement = 0.0
    for name, comp in components.items():
        score_basis[comp["basis"]].append(name)
        if comp["basis"] != "measured":
            points_without_direct_measurement += comp["score"]

    return {
        "document": metadata.get("document"),
        "title": metadata.get("title"),
        "iq_score": iq_score,
        "max_score": 100,
        "grade": grade,
        "health": health,
        "metrics": {
            "extraction_score": round(extraction_score, 2),
            "chunk_score": round(chunk_score, 2),
            "embedding_score": embedding_score,
            "ocr_score": round(ocr_score, 2),
            "metadata_score": round(metadata_score, 2),
        },
        "components": components,
        "score_basis": score_basis,
        "points_without_direct_measurement": round(points_without_direct_measurement, 2),
        "pipeline": {
            "pages": pages,
            "chunks": chunks,
            "text_length": words,
            "chunk_density": round(chunk_density, 2),
            "embedding_status": embedding,
            "embedding_status_detail": embedding_detail,
            "metadata_completeness": completeness,
            "ocr_required": ocr_required,
            "ocr_quality": ocr_quality,
            "ocr_basis": ocr_basis,
        },
    }