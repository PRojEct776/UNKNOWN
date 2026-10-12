import pytest

from app.services.universal_validator import (
    CheckStatus,
    validate_contradictions,
)


def test_contradicted_claim_fails():
    result = validate_contradictions(
        [
            {"claim": "Claim A", "verdict": "CONTRADICTED"},
        ]
    )

    assert result.status == CheckStatus.FAILED
    assert result.details["contradicted_indexes"] == [0]


def test_supported_claim_passes():
    result = validate_contradictions(
        [
            {"claim": "Claim A", "verdict": "SUPPORTED"},
        ]
    )

    assert result.status == CheckStatus.PASSED
    assert result.score == 100


def test_partially_supported_claim_is_not_contradicted():
    result = validate_contradictions(
        [
            {"claim": "Claim A", "verdict": "PARTIALLY_SUPPORTED"},
        ]
    )

    assert result.status == CheckStatus.PASSED
    assert result.details["partially_supported_indexes"] == [0]


def test_not_found_claim_is_not_treated_as_contradicted():
    result = validate_contradictions(
        [
            {"claim": "Claim A", "verdict": "NOT_FOUND"},
        ]
    )

    assert result.status == CheckStatus.PASSED
    assert result.details["not_found_indexes"] == [0]


def test_verdict_is_case_insensitive():
    result = validate_contradictions(
        [
            {"claim": "Claim A", "verdict": "contradicted"},
        ]
    )

    assert result.status == CheckStatus.FAILED


def test_enum_verdict_is_supported():
    from app.rag.claim_verifier import ClaimVerdict

    result = validate_contradictions(
        [
            {"claim": "Claim A", "verdict": ClaimVerdict.CONTRADICTED},
        ]
    )

    assert result.status == CheckStatus.FAILED


def test_invalid_verdict_produces_warning():
    result = validate_contradictions(
        [
            {"claim": "Claim A", "verdict": "UNKNOWN_VERDICT"},
        ]
    )

    assert result.status == CheckStatus.ERROR
    assert result.details["invalid_result_indexes"] == [0]


def test_mixed_results_report_invalid_entries():
    result = validate_contradictions(
        [
            {"claim": "Claim A", "verdict": "SUPPORTED"},
            {"claim": "Claim B", "verdict": "CONTRADICTED"},
            {"claim": "Claim C", "verdict": "INVALID"},
        ]
    )

    assert result.status == CheckStatus.WARNING
    assert result.details["contradicted_indexes"] == [1]
    assert result.details["invalid_result_indexes"] == [2]


def test_missing_results_are_unavailable():
    result = validate_contradictions(None)

    assert result.status == CheckStatus.UNAVAILABLE
    assert result.score is None


def test_empty_results_are_unavailable():
    result = validate_contradictions([])

    assert result.status == CheckStatus.UNAVAILABLE


@pytest.mark.parametrize(
    "value",
    ["invalid", None],
)
def test_invalid_result_collection_entries(value):
    result = validate_contradictions([value])

    assert result.status == CheckStatus.ERROR
