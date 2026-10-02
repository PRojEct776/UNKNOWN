"""
UNKNOWN X v2.0
Real Document IQ Integration Test
"""

from pprint import pprint

from app.rag.scoring import calculate_document_iq
from app.services.document_service import (
    build_document_metadata,
    save_document_metadata,
)

DOCUMENT = "sample_ieee.pdf"


def main():
    print("=" * 65)
    print("UNKNOWN X v2.0 - DOCUMENT IQ TEST")
    print("=" * 65)

    # Build metadata from real pipeline.
    metadata = build_document_metadata(DOCUMENT)

    print("\nDOCUMENT METADATA")
    print("-" * 65)
    pprint(metadata)

    # Calculate IQ report.
    report = calculate_document_iq(metadata)

    print("\nDOCUMENT IQ REPORT")
    print("-" * 65)
    pprint(report)

    # Merge IQ report into metadata.
    metadata.update({"document_iq": report})

    saved_path = save_document_metadata(metadata)

    print("\nMETADATA SAVED")
    print("-" * 65)
    print(saved_path)

    # ----------------------
    # Validation
    # ----------------------

    assert report["iq_score"] >= 80, "IQ score unexpectedly low."
    assert report["grade"] in ["A+", "A", "B", "C", "D"]
    assert report["pipeline"]["chunks"] == metadata["chunks"]

    print("\n✅ DOCUMENT IQ ENGINE PASSED ALL TESTS.")


if __name__ == "__main__":
    main()
