import json

import pytest

from app.rag.claim_verifier import ClaimVerdict, ClaimVerificationResult, ClaimVerifier

CHUNKS = [
    {"chunk_id": "c1", "document": "a.pdf", "page": 1,
     "text": "The model reached an accuracy of 0.85 on the test set."},
    {"chunk_id": "c2", "document": "a.pdf", "page": 2,
     "text": "Training used 10 epochs."},
    {"chunk_id": "c3", "document": "a.pdf", "page": 3,
     "text": "Inference takes 85 s per image on a CPU."},
]


def _res(verdict, supporting=(), contradicting=(), claim="The model reached 85% accuracy",
         explanation="e"):
    s, c = list(supporting), list(contradicting)
    return ClaimVerificationResult(
        claim=claim, verdict=verdict, confidence=0.9, explanation=explanation,
        evidence=s + c, supporting_evidence=s, contradicting_evidence=c,
        source_chunk_ids=[],
    )


def _ground(result):
    return ClaimVerifier().ground_result(result, CHUNKS)


def test_new_verdicts_exist_and_legacy_is_kept():
    assert ClaimVerdict("UNSUPPORTED") is ClaimVerdict.UNSUPPORTED
    assert ClaimVerdict("UNVERIFIABLE") is ClaimVerdict.UNVERIFIABLE
    assert ClaimVerdict("NOT_FOUND") is ClaimVerdict.NOT_FOUND


@pytest.mark.parametrize("label", ["UNSUPPORTED", "UNVERIFIABLE"])
def test_parse_accepts_new_verdicts(label):
    text = json.dumps({"verdict": label, "confidence": 0.4, "explanation": "x",
                       "supporting_evidence": [], "contradicting_evidence": [],
                       "source_chunk_ids": []})
    assert ClaimVerifier().parse_response("c", text).verdict.value == label


def test_parse_still_rejects_invalid_label():
    text = json.dumps({"verdict": "MAYBE", "confidence": 0.4, "explanation": "x"})
    with pytest.raises(ValueError):
        ClaimVerifier().parse_response("c", text)


def test_unsupported_passes_through_grounding():
    out = _ground(_res(ClaimVerdict.UNSUPPORTED, explanation="Nothing establishes this."))
    assert out.verdict == ClaimVerdict.UNSUPPORTED
    assert out.explanation == "Nothing establishes this."


def test_unverifiable_keeps_its_stated_limitation():
    out = _ground(_res(ClaimVerdict.UNVERIFIABLE, explanation="The source PDF is unreadable."))
    assert out.verdict == ClaimVerdict.UNVERIFIABLE
    assert out.explanation == "The source PDF is unreadable."


def test_unsupported_with_fabricated_quotes_has_them_stripped():
    out = _ground(_res(ClaimVerdict.UNSUPPORTED, supporting=["made up quote"]))
    assert out.verdict == ClaimVerdict.UNSUPPORTED
    assert out.supporting_evidence == [] and out.evidence == []


def test_irrelevant_supporting_quote_downgrades_to_unsupported():
    out = _ground(_res(ClaimVerdict.SUPPORTED, supporting=["Training used 10 epochs"],
                       claim="The model was trained with the AdamW optimizer"))
    assert out.verdict == ClaimVerdict.UNSUPPORTED
    assert out.supporting_evidence == []


def test_percent_and_decimal_are_equivalent():
    out = _ground(_res(ClaimVerdict.SUPPORTED, supporting=["accuracy of 0.85"]))
    assert out.verdict == ClaimVerdict.SUPPORTED


def test_different_number_is_still_not_equivalent():
    out = _ground(_res(ClaimVerdict.SUPPORTED, supporting=["accuracy of 0.85"],
                       claim="The model reached 95% accuracy"))
    assert out.verdict == ClaimVerdict.PARTIALLY_SUPPORTED


def test_unit_mismatch_downgrades_to_partial():
    out = _ground(_res(ClaimVerdict.SUPPORTED, supporting=["Inference takes 85 s per image"],
                       claim="Inference takes 85 ms per image"))
    assert out.verdict == ClaimVerdict.PARTIALLY_SUPPORTED


def test_matching_unit_keeps_supported():
    out = _ground(_res(ClaimVerdict.SUPPORTED, supporting=["Inference takes 85 s per image"],
                       claim="Inference takes 85 s per image"))
    assert out.verdict == ClaimVerdict.SUPPORTED