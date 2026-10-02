"""
UNKNOWN X v2.0 - Document IQ Scoring Engine

Purpose:
- Calculate a 0-100 IQ score for every indexed document.
- Produce detailed quality metrics.
- Assign grades for dashboard, analytics, and IEEE evaluation.
"""

# ==========================================================
# Helper
# ==========================================================


def clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    """Clamp a numeric value within a range."""
    return max(minimum, min(value, maximum))


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
    completeness = metadata.get("metadata_completeness", 0.0)

    ocr_required = metadata.get("ocr_required", False)
    ocr_quality = metadata.get("ocr_quality", 1.0)

    # ------------------------------------------------------
    # Metric 1 — Text Extraction Quality (25)
    # ------------------------------------------------------

    extraction_score = clamp(min(words / 5000, 1.0) * 25, 0, 25)

    # ------------------------------------------------------
    # Metric 2 — Chunk Coverage / Density (20)
    # Ideal ≈ 2 chunks per page
    # ------------------------------------------------------

    chunk_density = chunks / max(pages, 1)
    chunk_score = clamp(min(chunk_density / 2, 1.0) * 20, 0, 20)

    # ------------------------------------------------------
    # Metric 3 — Embedding Availability (20)
    # ------------------------------------------------------

    embedding_score = 20 if embedding else 0

    # ------------------------------------------------------
    # Metric 4 — OCR / Text Quality (20)
    # ------------------------------------------------------

    if ocr_required:
        ocr_score = clamp(ocr_quality * 20, 0, 20)
    else:
        # Digital PDFs receive full OCR credit.
        ocr_score = 20

    # ------------------------------------------------------
    # Metric 5 — Metadata Completeness (15)
    # ------------------------------------------------------

    metadata_score = clamp(completeness * 15, 0, 15)

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

    return {
        "document": metadata.get("document"),
        "title": metadata.get("title"),
        "iq_score": iq_score,
        "grade": grade,
        "health": health,
        "metrics": {
            "extraction_score": round(extraction_score, 2),
            "chunk_score": round(chunk_score, 2),
            "embedding_score": embedding_score,
            "ocr_score": round(ocr_score, 2),
            "metadata_score": round(metadata_score, 2),
        },
        "pipeline": {
            "pages": pages,
            "chunks": chunks,
            "text_length": words,
            "chunk_density": round(chunk_density, 2),
            "embedding_status": embedding,
            "metadata_completeness": completeness,
        },
    }
