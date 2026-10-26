"""Regression tests: numeric equivalence must not be blocked by the entity check."""

from app.rag.atomic_claims import (
    extract_named_entities,
    process_and_verify_claims,
    split_into_atomic_claims,
    verify_atomic_claim,
)


def _entails(premise: str, hypothesis: str) -> dict[str, float]:
    return {"entailment": 0.99, "neutral": 0.009, "contradiction": 0.001}


def test_percent_equals_decimal_is_supported():
    c = verify_atomic_claim("The threshold is 0.35.", "The threshold is 35%.", nli_fn=_entails)
    assert c.label == "supported"


def test_decimal_equals_percent_is_supported():
    c = verify_atomic_claim("Recall is 95%.", "Recall reached 0.95 on the test set.", nli_fn=_entails)
    assert c.label == "supported"


def test_wrong_number_is_contradicted():
    c = verify_atomic_claim("Recall is 0.95.", "Recall is 35%.", nli_fn=_entails)
    assert c.label == "contradicted"


def test_unit_mismatch_is_contradicted():
    c = verify_atomic_claim("The range is 5 km.", "The range is 5 m.", nli_fn=_entails)
    assert c.label == "contradicted"


def test_numeric_entities_are_ignored():
    ents = extract_named_entities("Recall is 0.95 and 35% at 500 kWh in 2021.")
    assert not any(ch.isdigit() for e in ents for ch in e)


def test_real_entity_still_required():
    c = verify_atomic_claim("NASA built the system.", "The system was built in a lab.", nli_fn=_entails)
    assert c.label != "supported"


def test_decimal_survives_splitter():
    claims = split_into_atomic_claims("Recall is 0.95 on the test set.")
    assert len(claims) == 1
    assert "0.95" in claims[0]["text"]


def test_sentence_boundary_after_decimal():
    claims = split_into_atomic_claims("Recall reached 0.95. Precision was lower.")
    assert len(claims) == 2
    assert claims[0]["text"].endswith("0.95.")


def test_mixed_valid_and_invalid_answer():
    passage = {"1": "Recall is 35%. Latency is 100 ms."}
    claims, refined = process_and_verify_claims(
        "Recall is 35%. Latency is 500 ms.", passage, llm=None, nli_fn=_entails
    )
    assert len(claims) == 1
    assert "35%" in refined
    assert "500" not in refined