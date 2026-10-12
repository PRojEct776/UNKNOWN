
import pytest

from app.services.universal_validator import (
    CheckStatus,
    validate_concept_consistency,
)


def test_valid_concepts_pass():
    concepts = [
        {"id": "c1", "name": "FAISS"},
        {"id": "c2", "name": "BM25"},
    ]

    result = validate_concept_consistency(concepts)

    assert result.status == CheckStatus.PASSED
    assert result.score == 100
    assert result.details["semantic_consistency_verified"] is False


def test_duplicate_names_are_detected_case_insensitively():
    concepts = [
        {"id": "c1", "name": "FAISS"},
        {"id": "c2", "name": " faiss "},
    ]

    result = validate_concept_consistency(concepts)

    assert result.status == CheckStatus.WARNING
    assert result.details["duplicate_name_indexes"] == [1]


def test_duplicate_ids_are_detected():
    concepts = [
        {"id": "c1", "name": "FAISS"},
        {"id": "c1", "name": "BM25"},
    ]

    result = validate_concept_consistency(concepts)

    assert result.status == CheckStatus.WARNING
    assert result.details["duplicate_id_indexes"] == [1]


@pytest.mark.parametrize(
    "concept",
    [
        {},
        {"id": "c1"},
        {"name": ""},
        {"name": "   "},
        "FAISS",
        None,
    ],
)
def test_malformed_concept_records_are_detected(concept):
    result = validate_concept_consistency([concept])

    assert result.status == CheckStatus.WARNING
    assert result.details["malformed_indexes"] == [0]


def test_missing_concepts_are_unavailable():
    result = validate_concept_consistency(None)

    assert result.status == CheckStatus.UNAVAILABLE
    assert result.score is None


def test_empty_concept_list_is_unavailable():
    result = validate_concept_consistency([])

    assert result.status == CheckStatus.UNAVAILABLE


def test_non_list_input_fails():
    result = validate_concept_consistency(
        {"name": "FAISS"}
    )

    assert result.status == CheckStatus.FAILED
    assert result.score == 0


def test_alternative_concept_name_fields_are_supported():
    concepts = [
        {"concept_id": "c1", "concept": "FAISS"},
        {"id": "c2", "label": "BM25"},
    ]

    result = validate_concept_consistency(concepts)

    assert result.status == CheckStatus.PASSED
    assert result.score == 100
