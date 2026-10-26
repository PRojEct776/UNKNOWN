from app.rag.evidence_sufficiency import assess_sufficiency, query_terms


def test_full_coverage_is_sufficient():
    r = assess_sufficiency(
        "What is the recall of BERT on SQuAD?",
        [{"text": "BERT reaches recall of 0.91 on SQuAD."}],
    )
    assert r.sufficient and r.coverage == 1.0 and r.gaps == []


def test_empty_passages_insufficient():
    r = assess_sufficiency("recall of BERT", [])
    assert not r.sufficient and r.reason == "no_passages"


def test_unrelated_passages_insufficient_with_gaps():
    r = assess_sufficiency(
        "quantum entanglement teleportation",
        [{"text": "BERT is a language model."}],
    )
    assert not r.sufficient
    assert "No evidence found for: quantum" in r.gaps[0] or len(r.gaps) == 3


def test_partial_coverage_lists_uncovered_term():
    r = assess_sufficiency("recall of BERT on ImageNet", [{"text": "BERT recall is high."}])
    assert r.sufficient
    assert r.uncovered_terms == ["imagenet"]


def test_threshold_can_force_insufficient():
    r = assess_sufficiency(
        "recall of BERT on ImageNet", [{"text": "BERT recall is high."}], min_coverage=0.9
    )
    assert not r.sufficient


def test_accepts_plain_strings():
    r = assess_sufficiency("BERT recall", ["BERT recall is high."])
    assert r.sufficient


def test_no_content_terms_with_passages_is_sufficient():
    assert assess_sufficiency("Is it?", ["anything"]).sufficient
    assert query_terms("Is it?") == []