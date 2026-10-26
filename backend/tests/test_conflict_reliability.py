from app.api.schemas import QueryResponse
from app.rag.reliability import compute_reliability, detect_conflicts


def _contradict(premise: str, hypothesis: str) -> dict[str, float]:
    return {"entailment": 0.02, "neutral": 0.08, "contradiction": 0.90}


def _agree(premise: str, hypothesis: str) -> dict[str, float]:
    return {"entailment": 0.95, "neutral": 0.04, "contradiction": 0.01}


def test_query_response_defaults_are_empty():
    r = QueryResponse(query="q", query_type="x", answer="a", sources=[])
    assert r.conflicts == []
    assert r.source_reliability == []


def test_reliability_is_bounded():
    score = compute_reliability({"venue": "Nature", "year": 2020})
    assert 0.0 <= score <= 1.0


def test_contradicting_claims_produce_a_conflict():
    claims = [
        {"text": "Method A improves recall.", "source_ids": ["1"]},
        {"text": "Method A reduces recall.", "source_ids": ["2"]},
    ]
    assert len(detect_conflicts(claims, nli_fn=_contradict)) == 1


def test_agreeing_claims_produce_no_conflict():
    claims = [
        {"text": "Method A improves recall.", "source_ids": ["1"]},
        {"text": "Method A raises recall.", "source_ids": ["2"]},
    ]
    assert detect_conflicts(claims, nli_fn=_agree) == []