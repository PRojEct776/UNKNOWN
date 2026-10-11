from request_payload import (
    FEATURE_DEBATE,
    FEATURE_DISCOVER,
    FEATURE_VERIFY,
    EXAMPLE_QUERIES,
    build_request_payload,
    request_is_ready,
)


def test_verify_sends_claim_not_query():
    assert build_request_payload(FEATURE_VERIFY, "  the claim  ") == {
        "claim": "the claim",
    }


def test_discover_sends_description_not_query():
    assert build_request_payload(FEATURE_DISCOVER, "a concept") == {
        "description": "a concept",
    }


def test_debate_sends_query_and_positions():
    payload = build_request_payload(
        FEATURE_DEBATE,
        "Should we compress?",
        position_a="Yes",
        position_b="No",
    )
    assert payload == {
        "query": "Should we compress?",
        "position_a": "Yes",
        "position_b": "No",
    }


def test_query_tools_keep_query_field():
    assert build_request_payload("Research Assistant", "What is SAC-RAG?") == {
        "query": "What is SAC-RAG?",
    }
    assert build_request_payload("Knowledge DNA", "map it") == {"query": "map it"}
    assert build_request_payload("Knowledge Mind Map", "map it") == {
        "query": "map it",
    }


def test_debate_is_not_ready_without_positions():
    assert not request_is_ready(FEATURE_DEBATE, "topic")
    assert not request_is_ready(FEATURE_DEBATE, "topic", position_a="A")
    assert request_is_ready(FEATURE_DEBATE, "topic", position_a="A", position_b="B")


def test_examples_exist_for_every_mapped_tool():
    expected = {
        "Research Assistant",
        FEATURE_VERIFY,
        FEATURE_DISCOVER,
        "Contradictions",
        "Compare Research",
        "Research Gaps",
        FEATURE_DEBATE,
        "Knowledge DNA",
        "Knowledge Mind Map",
        "Adaptive Answer",
        "Visual Answer",
    }
    assert expected == set(EXAMPLE_QUERIES)
    debate = EXAMPLE_QUERIES[FEATURE_DEBATE][0]
    assert debate["position_a"] and debate["position_b"]
