from app.api.schemas import ClaimVerificationResponse


def _response(confidence, **extra):
    return ClaimVerificationResponse(
        claim="c",
        verdict="SUPPORTED",
        confidence=confidence,
        explanation="e",
        evidence=[],
        source_chunk_ids=[],
        sources=[],
        **extra,
    )


def test_score_is_whole_number_percent():
    assert _response(0.95).confidence_score == 95
    assert _response(0.8).confidence_score == 80
    assert _response(0.0).confidence_score == 0
    assert _response(1.0).confidence_score == 100


def test_raw_confidence_is_unchanged():
    assert _response(0.95).confidence == 0.95


def test_explicit_score_is_kept():
    assert _response(0.95, confidence_score=42).confidence_score == 42


def test_score_is_in_serialized_output():
    assert _response(0.5).model_dump()["confidence_score"] == 50
