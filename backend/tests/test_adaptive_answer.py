from app.rag.adaptive_answer import (
    AdaptiveAnswerDecision,
    AdaptiveAnswerEngine,
    AnswerMode,
)


def test_parse_plain_json():
    response = """
    {
        "mode": "TECHNICAL",
        "reasoning": "The query asks about system architecture."
    }
    """

    result = AdaptiveAnswerEngine.parse_response(response)

    assert isinstance(result, AdaptiveAnswerDecision)
    assert result.mode == AnswerMode.TECHNICAL


def test_parse_markdown_json():
    response = """
    ```json
    {
        "mode": "RESEARCH",
        "reasoning": "The query focuses on research findings."
    }
    ```
    """

    result = AdaptiveAnswerEngine.parse_response(response)

    assert result.mode == AnswerMode.RESEARCH


def test_parse_reason_alias():
    response = """
    {
        "mode": "SHORT",
        "reason": "The question requests a direct fact."
    }
    """

    result = AdaptiveAnswerEngine.parse_response(response)

    assert result.mode == AnswerMode.SHORT
    assert result.reasoning == "The question requests a direct fact."


def test_invalid_json_rejected():
    response = "This is not valid JSON."

    try:
        AdaptiveAnswerEngine.parse_response(response)
        assert False, "Expected ValueError"
    except ValueError:
        pass


def test_invalid_mode_rejected():
    response = """
    {
        "mode": "INVALID",
        "reasoning": "Invalid mode."
    }
    """

    try:
        AdaptiveAnswerEngine.parse_response(response)
        assert False, "Expected ValueError"
    except ValueError:
        pass


def test_local_classification_comparison():
    result = AdaptiveAnswerEngine.classify_query("Compare BM25 and FAISS")

    assert result == AnswerMode.COMPARATIVE


def test_local_classification_technical():
    result = AdaptiveAnswerEngine.classify_query(
        "Explain the architecture and implementation of a REST API"
    )

    assert result == AnswerMode.TECHNICAL


def test_local_classification_research():
    result = AdaptiveAnswerEngine.classify_query(
        "What are the limitations and findings of this research paper?"
    )

    assert result == AnswerMode.RESEARCH


def test_local_classification_detailed():
    result = AdaptiveAnswerEngine.classify_query(
        "Explain how hybrid retrieval works in detail"
    )

    assert result == AnswerMode.DETAILED


def test_local_classification_short():
    result = AdaptiveAnswerEngine.classify_query("What is FAISS?")

    assert result == AnswerMode.SHORT
