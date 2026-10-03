from app.rag.claim_verifier import (
    ClaimVerdict,
    ClaimVerifier,
)


def test_supported_claim():
    verifier = ClaimVerifier()

    response = """
    {
        "verdict": "SUPPORTED",
        "confidence": 0.9,
        "explanation": "The evidence supports the claim.",
        "evidence": ["The document directly supports the statement."],
        "source_chunk_ids": ["chunk_7"]
    }
    """

    result = verifier.parse_response(
        "Test claim",
        response,
    )

    assert result.verdict == ClaimVerdict.SUPPORTED
    assert result.confidence == 0.9
    assert result.source_chunk_ids == ["chunk_7"]


def test_partially_supported_claim():
    verifier = ClaimVerifier()

    response = """
    {
        "verdict": "PARTIALLY_SUPPORTED",
        "confidence": 0.7,
        "explanation": "Only part of the claim is supported.",
        "evidence": ["Partial evidence."],
        "source_chunk_ids": ["chunk_2"]
    }
    """

    result = verifier.parse_response(
        "Partial claim",
        response,
    )

    assert result.verdict == ClaimVerdict.PARTIALLY_SUPPORTED


def test_contradicted_claim():
    verifier = ClaimVerifier()

    response = """
    {
        "verdict": "CONTRADICTED",
        "confidence": 0.95,
        "explanation": "The evidence conflicts with the claim.",
        "evidence": ["Conflicting statement."],
        "source_chunk_ids": ["chunk_5"]
    }
    """

    result = verifier.parse_response(
        "Contradicted claim",
        response,
    )

    assert result.verdict == ClaimVerdict.CONTRADICTED


def test_not_found_claim():
    verifier = ClaimVerifier()

    response = """
    {
        "verdict": "NOT_FOUND",
        "confidence": 0.2,
        "explanation": "The retrieved evidence does not address the claim.",
        "evidence": [],
        "source_chunk_ids": []
    }
    """

    result = verifier.parse_response(
        "Unknown claim",
        response,
    )

    assert result.verdict == ClaimVerdict.NOT_FOUND
    assert result.evidence == []
    assert result.source_chunk_ids == []


def test_markdown_json_is_supported():
    verifier = ClaimVerifier()

    response = """
    ```json
    {
        "verdict": "SUPPORTED",
        "confidence": 0.8,
        "explanation": "Supported by the evidence.",
        "evidence": ["Evidence"],
        "source_chunk_ids": ["chunk_1"]
    }
    ```
    """

    result = verifier.parse_response(
        "Test claim",
        response,
    )

    assert result.verdict == ClaimVerdict.SUPPORTED


def test_invalid_verdict_is_rejected():
    verifier = ClaimVerifier()

    response = """
    {
        "verdict": "MAYBE",
        "confidence": 0.5,
        "explanation": "Unclear.",
        "evidence": [],
        "source_chunk_ids": []
    }
    """

    try:
        verifier.parse_response("Test claim", response)
        assert False, "Expected ValueError"
    except ValueError as error:
        assert "Invalid claim verification verdict" in str(error)


def test_invalid_json_is_rejected():
    verifier = ClaimVerifier()

    try:
        verifier.parse_response(
            "Test claim",
            "This is not JSON.",
        )
        assert False, "Expected ValueError"
    except ValueError as error:
        assert "invalid verification JSON" in str(error)