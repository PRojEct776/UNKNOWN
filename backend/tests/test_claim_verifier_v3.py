import pytest

from app.rag.claim_verifier import ClaimVerdict, ClaimVerificationResult, ClaimVerifier

KEY = "A single copy gives 0.767 after 3,000 generations."


def _chunk():
    prefix = ("filler words here. " * 80)[:1432]
    body = prefix + KEY
    body = body + (" filler words here." * 40)[: 2100 - len(body)]
    return {"chunk_id": "chunk_34", "text": body}


def _result(claim, verdict, quote):
    return ClaimVerificationResult(
        claim=claim,
        verdict=verdict,
        confidence=0.9,
        explanation="model explanation",
        supporting_evidence=[quote],
    )


def test_wrong_number_is_contradicted():
    claim = "A single copy gives 0.777 after 3,000 generations."
    result = _result(claim, ClaimVerdict.SUPPORTED, "A single copy gives 0.767 after 3,000 generations")
    out = ClaimVerifier().ground_result(result, [_chunk()], max_chars=1200)
    assert out.verdict == ClaimVerdict.CONTRADICTED
    assert out.contradicting_evidence
    assert "0.777" in out.explanation and "0.767" in out.explanation


def test_partially_with_wrong_number_is_contradicted():
    claim = "A single copy gives 0.777 after 3,000 generations."
    result = _result(claim, ClaimVerdict.PARTIALLY_SUPPORTED, "A single copy gives 0.767 after 3,000 generations")
    out = ClaimVerifier().ground_result(result, [_chunk()], max_chars=1200)
    assert out.verdict == ClaimVerdict.CONTRADICTED


def test_correct_number_stays_supported():
    claim = "A single copy gives 0.767 after 3,000 generations."
    result = _result(claim, ClaimVerdict.SUPPORTED, "A single copy gives 0.767 after 3,000 generations")
    out = ClaimVerifier().ground_result(result, [_chunk()], max_chars=1200)
    assert out.verdict == ClaimVerdict.SUPPORTED
    assert out.source_chunk_ids == ["chunk_34"]


def test_focus_text_finds_sentence_past_the_old_cut():
    chunk = _chunk()
    assert len(chunk["text"]) > 2000
    assert chunk["text"].index("0.767") > 1200
    window = ClaimVerifier.focus_text(chunk["text"], "single copy 0.767 after 3,000 generations", 1200)
    assert len(window) <= 1200
    assert KEY in window


def test_focus_text_without_claim_keeps_start():
    chunk = _chunk()
    assert ClaimVerifier.focus_text(chunk["text"], "", 1200) == chunk["text"][:1200]


def test_context_builder_shows_window_near_claim():
    module = pytest.importorskip("app.rag.context_builder")
    context = module.ContextBuilder(max_chars=1200).build(
        [dict(_chunk(), rank=1, document="paper.pdf", page=3)],
        claim="A single copy gives 0.777 after 3,000 generations.",
    )
    assert "0.767 after 3,000" in context
