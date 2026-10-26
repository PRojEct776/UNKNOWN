"""/query must abstain when no atomic claim survives verification."""

from __future__ import annotations

from app.rag.atomic_claims import final_answer_after_claim_filter

NOT_FOUND = "Not found in the provided documents."


def test_no_surviving_claims_abstains():
    assert final_answer_after_claim_filter([], "Unverified original text.", NOT_FOUND) is None


def test_not_found_text_from_pipeline_abstains():
    claims = [object()]
    assert final_answer_after_claim_filter(claims, "Not found in available sources.", NOT_FOUND) is None
    assert final_answer_after_claim_filter(claims, NOT_FOUND, NOT_FOUND) is None


def test_empty_refined_answer_abstains():
    assert final_answer_after_claim_filter([object()], "   ", NOT_FOUND) is None
    assert final_answer_after_claim_filter([object()], None, NOT_FOUND) is None


def test_surviving_claims_return_refined_answer():
    refined = "Supported claim one. Supported claim two."
    assert final_answer_after_claim_filter([object(), object()], refined, NOT_FOUND) == refined
