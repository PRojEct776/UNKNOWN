
import pytest

from app.services.universal_validator import (
    CheckStatus,
    validate_relationship_integrity,
)


def test_valid_relationship_passes():
    nodes = [{"id": "A"}, {"id": "B"}]
    relationships = [{"source": "A", "target": "B"}]

    result = validate_relationship_integrity(nodes, relationships)

    assert result.status == CheckStatus.PASSED
    assert result.score == 100


def test_unknown_source_fails():
    nodes = [{"id": "B"}]
    relationships = [{"source": "A", "target": "B"}]

    result = validate_relationship_integrity(nodes, relationships)

    assert result.status == CheckStatus.FAILED
    assert result.details["unresolved_source_indexes"] == [0]


def test_unknown_target_fails():
    nodes = [{"id": "A"}]
    relationships = [{"source": "A", "target": "B"}]

    result = validate_relationship_integrity(nodes, relationships)

    assert result.status == CheckStatus.FAILED
    assert result.details["unresolved_target_indexes"] == [0]


def test_duplicate_node_ids_fail():
    nodes = [{"id": "A"}, {"id": "A"}]

    result = validate_relationship_integrity(nodes, [])

    assert result.status == CheckStatus.FAILED
    assert result.details["duplicate_node_indexes"] == [1]


@pytest.mark.parametrize(
    "nodes",
    [
        [{}],
        [{"id": ""}],
        [{"id": None}],
        ["A"],
    ],
)
def test_malformed_nodes_fail(nodes):
    result = validate_relationship_integrity(nodes, [])

    assert result.status == CheckStatus.FAILED
    assert result.details["malformed_node_indexes"] == [0]


@pytest.mark.parametrize(
    "relationship",
    [
        {},
        {"source": "A"},
        {"target": "B"},
        {"source": "", "target": "B"},
        "A -> B",
    ],
)
def test_malformed_relationships_fail(relationship):
    result = validate_relationship_integrity(
        [{"id": "A"}, {"id": "B"}],
        [relationship],
    )

    assert result.status == CheckStatus.FAILED


def test_missing_nodes_are_unavailable():
    result = validate_relationship_integrity(None, [])

    assert result.status == CheckStatus.UNAVAILABLE
    assert result.score is None


def test_non_list_inputs_fail():
    result = validate_relationship_integrity(
        {"id": "A"},
        [],
    )

    assert result.status == CheckStatus.FAILED


def test_relationships_without_nodes_fail():
    result = validate_relationship_integrity(
        [],
        [{"source": "A", "target": "B"}],
    )

    assert result.status == CheckStatus.FAILED


def test_self_reference_is_reported_separately():
    result = validate_relationship_integrity(
        [{"id": "A"}],
        [{"source": "A", "target": "A"}],
    )

    assert result.status == CheckStatus.PASSED
    assert result.details["self_reference_indexes"] == [0]


def test_empty_graph_is_structurally_valid():
    result = validate_relationship_integrity([], [])

    assert result.status == CheckStatus.PASSED
    assert result.score == 100
