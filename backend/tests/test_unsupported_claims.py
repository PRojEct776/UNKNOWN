
import pytest

from app.services.universal_validator import (
    CheckStatus,
    validate_unsupported_claims,
)


def test_missing_results_are_unavailable():
    result = validate_unsupported_claims(None)

    assert result.status == CheckStatus.UNAVAILABLE
    assert result.score is None


def test_empty_results_are_unavailable():
    result = validate_unsupported_claims([])

    assert result.status == CheckStatus.UNAVAILABLE


def test_non_list_input_fails():
    result = validate_unsupported_claims("invalid")

    assert result.status == CheckStatus.FAILED
    assert result.score == 0


def test_all_supported_claims_pass():
    result = validate_unsupported_claims([
        {"claim": "Claim A", "verdict": "SUPPORTED"},
        {"claim": "Claim B", "verdict": "SUPPORTED"},
    ])

    assert result.status == CheckStatus.PASSED
    assert result.score == 100


def test_not_found_claim_is_flagged():
    result = validate_unsupported_claims([
        {"claim": "Claim A", "verdict": "NOT_FOUND"},
    ])

    assert result.status == CheckStatus.WARNING
    assert result.score == 0
    assert result.details["not_found_indexes"] == [0]


def test_partial_support_is_flagged():
    result = validate_unsupported_claims([
        {"claim": "Claim A", "verdict": "PARTIALLY_SUPPORTED"},
    ])

    assert result.status == CheckStatus.WARNING
    assert result.details["flagged_insufficient_support_indexes"] == [0]


def test_contradicted_claim_is_reported_separately():
    result = validate_unsupported_claims([
        {"claim": "Claim A", "verdict": "CONTRADICTED"},
    ])

    assert result.status == CheckStatus.WARNING
    assert result.details["contradicted_indexes"] == [0]
    assert result.details["not_found_indexes"] == []


def test_verdict_strings_are_case_insensitive():
    result = validate_unsupported_claims([
        {"claim": "Claim A", "verdict": " supported "},
    ])

    assert result.status == CheckStatus.PASSED


def test_enum_verdict_is_accepted():
    from app.rag.claim_verifier import ClaimVerdict

    result = validate_unsupported_claims([
        {"claim": "Claim A", "verdict": ClaimVerdict.SUPPORTED},
    ])

    assert result.status == CheckStatus.PASSED


def test_invalid_entries_produce_warning_when_valid_results_exist():
    result = validate_unsupported_claims([
        {"claim": "Claim A", "verdict": "SUPPORTED"},
        {"claim": "Claim B", "verdict": "UNKNOWN"},
        None,
    ])

    assert result.status == CheckStatus.WARNING
    assert result.details["invalid_result_indexes"] == [1, 2]


def test_all_invalid_results_produce_error():
    result = validate_unsupported_claims([
        {"claim": "Claim A", "verdict": "UNKNOWN"},
        None,
    ])

    assert result.status == CheckStatus.ERROR
    assert result.score is None


def test_unsupported_claim_evidence_is_preserved():
    result = validate_unsupported_claims([
        {"claim": "Claim A", "verdict": "NOT_FOUND"},
        {"claim": "Claim B", "verdict": "SUPPORTED"},
    ])

    assert "Claim A" in result.evidence
    assert "Claim B" not in result.evidence


def test_result_discloses_verification_limitation():
    result = validate_unsupported_claims([
        {"claim": "Claim A", "verdict": "SUPPORTED"},
    ])

    assert result.details["independently_verified"] is False
    assert result.details["detection_source"] == "existing_claim_verifier"
