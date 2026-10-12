import pytest

from app.services.universal_validator import (
    VALIDATION_CHECKS,
    CheckStatus,
    ValidationCheck,
    ValidationReport,
)


def test_all_eleven_checks_are_defined():
    assert len(VALIDATION_CHECKS) == 11
    assert "overall_quality" in VALIDATION_CHECKS


def test_unavailable_check_does_not_affect_score():
    report = ValidationReport(input_type="txt")
    report.add_check(
        ValidationCheck(
            name="input_schema",
            status=CheckStatus.PASSED,
            score=80,
        )
    )
    report.add_check(
        ValidationCheck(
            name="evidence_traceability",
            status=CheckStatus.UNAVAILABLE,
            message="No evidence supplied.",
        )
    )

    result = report.to_dict()

    # A partial report must not expose a final quality score.
    assert result["summary"]["overall_score"] is None
    assert result["summary"]["overall_score_complete"] is False

    # The unavailable check is recorded, not counted as a failure.
    assert result["summary"]["checks_unavailable"] == 1
    assert result["summary"]["checks_failed"] == 0


def test_no_scored_checks_means_no_overall_score():
    report = ValidationReport(input_type="txt")
    report.add_check(
        ValidationCheck(
            name="metadata_completeness",
            status=CheckStatus.NOT_APPLICABLE,
        )
    )

    assert report.to_dict()["summary"]["overall_score"] is None


def test_duplicate_check_is_rejected():
    report = ValidationReport(input_type="pdf")
    check = ValidationCheck(
        name="input_schema",
        status=CheckStatus.PASSED,
        score=100,
    )
    report.add_check(check)

    with pytest.raises(ValueError, match="Duplicate"):
        report.add_check(check)


def test_invalid_score_is_rejected():
    with pytest.raises(ValueError):
        ValidationCheck(
            name="input_schema",
            status=CheckStatus.PASSED,
            score=101,
        )


def test_report_is_json_serializable():
    import json

    report = ValidationReport(input_type="json")
    report.add_check(
        ValidationCheck(
            name="input_schema",
            status=CheckStatus.PASSED,
            score=100,
        )
    )

    json.dumps(report.to_dict())


from app.services.universal_validator import (  # noqa: I001
    validate_input_schema,
    validate_metadata_completeness,
    validate_content_quality,
)


def test_input_schema_accepts_generic_text():
    result = validate_input_schema("A generic document.")
    assert result.status == CheckStatus.PASSED


def test_input_schema_rejects_empty_text():
    result = validate_input_schema("   ")
    assert result.status == CheckStatus.FAILED


def test_metadata_completeness_uses_requested_fields():
    result = validate_metadata_completeness(
        {"title": "Example"},
        required_fields=("title", "author"),
    )
    assert result.score == 50
    assert result.details["missing_fields"] == ["author"]


def test_empty_metadata_is_unavailable():
    result = validate_metadata_completeness({})
    assert result.status == CheckStatus.UNAVAILABLE
    assert result.score is None


def test_content_quality_accepts_plain_text():
    result = validate_content_quality("A plain text document.")
    assert result.status == CheckStatus.PASSED
    assert result.details["word_count"] == 4


def test_content_quality_detects_empty_text():
    result = validate_content_quality("")
    assert result.status == CheckStatus.FAILED
    assert result.score == 0


from app.services.universal_validator import validate_evidence_traceability


def test_evidence_traceability_accepts_matching_chunk_ids():
    result = validate_evidence_traceability(
        [
            {
                "chunk_id": "chunk-1",
                "document": "notes.txt",
                "page": 1,
                "snippet": "Example evidence",
            }
        ],
        cited_chunk_ids=["chunk-1"],
    )

    assert result.status == CheckStatus.PASSED
    assert result.score == 100


def test_evidence_traceability_detects_missing_citations():
    result = validate_evidence_traceability(
        [
            {
                "chunk_id": "chunk-1",
                "document": "notes.txt",
            }
        ],
        cited_chunk_ids=["chunk-404"],
    )

    assert result.status == CheckStatus.FAILED
    assert result.details["unresolved_chunk_ids"] == ["chunk-404"]


def test_evidence_traceability_without_evidence_is_unavailable():
    result = validate_evidence_traceability(None)

    assert result.status == CheckStatus.UNAVAILABLE
    assert result.score is None


def test_evidence_traceability_rejects_malformed_entries():
    result = validate_evidence_traceability(
        [{"chunk_id": "unknown", "document": "Unknown Document"}],
        cited_chunk_ids=["chunk-1"],
    )

    assert result.status == CheckStatus.FAILED
    assert result.details["malformed_evidence_indexes"] == [0]


from app.services.universal_validator import validate_semantic_relevance


def test_semantic_relevance_accepts_above_threshold_score():
    result = validate_semantic_relevance(
        "Explain hybrid retrieval",
        [{"chunk_id": "c1", "hybrid_score": 0.8}],
    )
    assert result.status == CheckStatus.PASSED
    assert result.score == 100


def test_semantic_relevance_rejects_below_threshold_results():
    result = validate_semantic_relevance(
        "Explain hybrid retrieval",
        [{"chunk_id": "c1", "hybrid_score": 0.1}],
    )
    assert result.status == CheckStatus.FAILED
    assert result.score == 0


def test_semantic_relevance_requires_query():
    result = validate_semantic_relevance(
        " ",
        [{"chunk_id": "c1", "hybrid_score": 0.8}],
    )
    assert result.status == CheckStatus.UNAVAILABLE


def test_semantic_relevance_requires_valid_scores():
    result = validate_semantic_relevance(
        "Explain retrieval",
        [{"chunk_id": "c1", "hybrid_score": None}],
    )
    assert result.status == CheckStatus.UNAVAILABLE


def test_semantic_relevance_reports_invalid_scores():
    result = validate_semantic_relevance(
        "Explain retrieval",
        [
            {"chunk_id": "c1", "hybrid_score": 0.8},
            {"chunk_id": "c2", "hybrid_score": 4.0},
        ],
    )
    assert result.status == CheckStatus.WARNING
    assert result.details["invalid_evidence_indexes"] == [1]
