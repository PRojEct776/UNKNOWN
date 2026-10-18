import pytest

from app.services.universal_validator import (
    CheckStatus,
    validate_confidence_calibration,
)


def test_missing_data_is_unavailable():
    result = validate_confidence_calibration(None)

    assert result.status == CheckStatus.UNAVAILABLE
    assert result.score is None


def test_empty_data_is_unavailable():
    result = validate_confidence_calibration([])

    assert result.status == CheckStatus.UNAVAILABLE


def test_invalid_collection_fails():
    result = validate_confidence_calibration("invalid")  # type: ignore

    assert result.status == CheckStatus.FAILED
    assert result.score == 0


def test_perfect_predictions_have_zero_brier_error():
    result = validate_confidence_calibration(
        [
            {"confidence": 1.0, "correct": True},
            {"confidence": 0.0, "correct": False},
        ]
    )

    assert result.status == CheckStatus.WARNING
    assert result.details["brier_score"] == 0.0
    assert result.details["ece"] == 0.0
    assert result.details["valid_result_count"] == 2


def test_confident_wrong_prediction_has_high_brier_error():
    result = validate_confidence_calibration(
        [
            {"confidence": 1.0, "correct": False},
        ]
    )

    assert result.status == CheckStatus.WARNING
    assert result.details["brier_score"] == 1.0


def test_half_confidence_and_half_accuracy_are_calibrated():
    result = validate_confidence_calibration(
        [
            {"confidence": 0.5, "correct": True},
            {"confidence": 0.5, "correct": False},
        ]
    )

    assert result.status == CheckStatus.WARNING
    assert result.details["brier_score"] == 0.25
    assert result.details["ece"] == 0.0
    assert result.details["valid_result_count"] == 2


def test_unbalanced_confidence_produces_calibration_error():
    result = validate_confidence_calibration(
        [
            {"confidence": 0.9, "correct": True},
            {"confidence": 0.9, "correct": False},
        ]
    )

    assert result.status == CheckStatus.WARNING
    assert result.details["ece"] == pytest.approx(0.4)


def test_confidence_outside_range_is_invalid():
    result = validate_confidence_calibration(
        [
            {"confidence": 1.5, "correct": True},
        ]
    )

    assert result.status == CheckStatus.FAILED
    assert result.details["invalid_result_indexes"] == [0]


def test_non_numeric_confidence_is_invalid():
    result = validate_confidence_calibration(
        [
            {"confidence": "high", "correct": True},
        ]
    )

    assert result.status == CheckStatus.FAILED


def test_missing_ground_truth_is_invalid():
    result = validate_confidence_calibration(
        [
            {"confidence": 0.8},
        ]
    )

    assert result.status == CheckStatus.FAILED


def test_boolean_confidence_is_invalid():
    result = validate_confidence_calibration(
        [
            {"confidence": True, "correct": True},
        ]
    )

    assert result.status == CheckStatus.FAILED


def test_string_boolean_is_not_accepted_as_ground_truth():
    result = validate_confidence_calibration(
        [
            {"confidence": 0.8, "correct": "true"},
        ]
    )

    assert result.status == CheckStatus.FAILED


def test_invalid_records_are_not_silently_ignored():
    result = validate_confidence_calibration(
        [
            {"confidence": 0.8, "correct": True},
            {"confidence": 1.2, "correct": False},
        ]
    )

    assert result.status == CheckStatus.WARNING
    assert result.details["invalid_result_indexes"] == [1]
    assert result.details["valid_result_count"] == 1


def test_calibration_metrics_are_not_claimed_without_labels():
    result = validate_confidence_calibration(
        [
            {"confidence": 0.8},
        ]
    )

    assert result.details.get("brier_score") is None


def test_details_disclose_evaluation_basis():
    result = validate_confidence_calibration(
        [
            {"confidence": 0.8, "correct": True},
        ]
    )

    assert result.details["evaluation_basis"] == "labeled_ground_truth"
    assert result.details["calibration_is_proven"] is False
