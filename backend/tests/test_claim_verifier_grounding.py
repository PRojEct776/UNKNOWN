import json
from types import SimpleNamespace

import pytest

import app.services.rag_service as rag_module
from app.rag.claim_verifier import ClaimVerdict, ClaimVerificationResult, ClaimVerifier
from app.rag.context_builder import ContextBuilder

CHUNKS = [
    {"chunk_id": "c1", "document": "a.pdf", "page": 1, "rank": 1,
     "text": "The model reached an accuracy of 85% on the test set."},
    {"chunk_id": "c2", "document": "a.pdf", "page": 2, "rank": 2,
     "text": "Training used 10 epochs."},
]
CLAIM = "The model reached 85% accuracy"


def _res(verdict, evidence, ids, claim=CLAIM):
    return ClaimVerificationResult(
        claim=claim, verdict=verdict, confidence=0.9, explanation="e",
        evidence=evidence, source_chunk_ids=ids,
    )


def test_no_chunks_gives_not_found():
    out = ClaimVerifier().ground_result(_res(ClaimVerdict.SUPPORTED, ["x"], ["c1"]), [])
    assert out.verdict == ClaimVerdict.NOT_FOUND
    assert out.evidence == [] and out.source_chunk_ids == []


def test_fabricated_evidence_is_stripped_and_matching_is_tolerant():
    ev = ["Accuracy of 85%  on the TEST set", "accuracy of 85% ... test set",
          "The model was trained on ImageNet"]
    out = ClaimVerifier().ground_result(_res(ClaimVerdict.SUPPORTED, ev, ["c1"]), CHUNKS)
    assert out.evidence == ev[:2]
    assert out.verdict == ClaimVerdict.SUPPORTED


def test_unknown_chunk_ids_are_dropped():
    out = ClaimVerifier().ground_result(
        _res(ClaimVerdict.SUPPORTED, ["accuracy of 85%"], ["c1", "zzz"]), CHUNKS)
    assert out.source_chunk_ids == ["c1"]


@pytest.mark.parametrize("verdict", [ClaimVerdict.SUPPORTED, ClaimVerdict.CONTRADICTED])
def test_verdict_without_grounded_evidence_becomes_not_found(verdict):
    for ev in ([], ["The model was trained on ImageNet"]):
        out = ClaimVerifier().ground_result(_res(verdict, ev, ["c1"]), CHUNKS)
        assert out.verdict == ClaimVerdict.NOT_FOUND


def test_numeric_mismatch_blocks_supported():
    out = ClaimVerifier().ground_result(
        _res(ClaimVerdict.SUPPORTED, ["accuracy of 85% on the test set"], ["c1"],
             claim="The model reached 95% accuracy"), CHUNKS)
    assert out.verdict == ClaimVerdict.PARTIALLY_SUPPORTED


def test_numeric_match_keeps_supported():
    out = ClaimVerifier().ground_result(
        _res(ClaimVerdict.SUPPORTED, ["accuracy of 85% on the test set"], ["c1"]), CHUNKS)
    assert out.verdict == ClaimVerdict.SUPPORTED


@pytest.mark.parametrize("raw", ['"high"', "null", "NaN", '"0.7abc"'])
def test_bad_confidence_defaults_to_zero(raw):
    text = ('{"verdict":"NOT_FOUND","confidence":%s,"explanation":"x",'
            '"evidence":[],"source_chunk_ids":[]}') % raw
    assert ClaimVerifier().parse_response("c", text).confidence == 0.0


def test_supporting_and_contradicting_lists_are_parsed():
    text = json.dumps({"verdict": "PARTIALLY_SUPPORTED", "confidence": 0.6,
                       "explanation": "x", "supporting_evidence": ["a"],
                       "contradicting_evidence": ["b"], "source_chunk_ids": ["c1"]})
    r = ClaimVerifier().parse_response("c", text)
    assert r.supporting_evidence == ["a"]
    assert r.contradicting_evidence == ["b"]
    assert r.evidence == ["a", "b"]


def test_legacy_evidence_is_split_by_verdict():
    text = json.dumps({"verdict": "CONTRADICTED", "confidence": 0.8, "explanation": "x",
                       "evidence": ["x"], "source_chunk_ids": []})
    r = ClaimVerifier().parse_response("c", text)
    assert r.contradicting_evidence == ["x"] and r.supporting_evidence == []


# ---- service wiring (stub self; no models, no network) ----
class _Resp:
    def __init__(self, answer):
        self.success, self.answer, self.error, self.error_kind = True, answer, None, None


def _service(chunks, answer):
    cls = next(v for v in vars(rag_module).values()
               if isinstance(v, type) and v.__module__ == rag_module.__name__
               and hasattr(v, "verify_claim"))
    llm = SimpleNamespace(calls=0)

    def gen(prompt):
        llm.calls += 1
        return _Resp(answer)

    llm.generate = gen
    stub = SimpleNamespace(_search=lambda claim, document_names=None: chunks,
                           context_builder=ContextBuilder(),
                           claim_verifier=ClaimVerifier(), llm=llm)
    return cls, stub, llm


def _answer(verdict, evidence, ids):
    return json.dumps({"verdict": verdict, "confidence": 0.9, "explanation": "e",
                       "evidence": evidence, "source_chunk_ids": ids})


def test_service_empty_retrieval_skips_llm():
    cls, stub, llm = _service([], _answer("SUPPORTED", ["made up"], ["c1"]))
    resp = cls.verify_claim(stub, CLAIM)
    assert llm.calls == 0
    assert resp.verdict == "NOT_FOUND" and resp.evidence == []


def test_service_strips_fabricated_evidence():
    cls, stub, llm = _service(CHUNKS, _answer("SUPPORTED", ["made up quote"], ["c1"]))
    resp = cls.verify_claim(stub, CLAIM)
    assert llm.calls == 1
    assert resp.verdict == "NOT_FOUND"


def test_service_keeps_grounded_result():
    cls, stub, _ = _service(CHUNKS, _answer(
        "SUPPORTED", ["accuracy of 85% on the test set"], ["c1"]))
    resp = cls.verify_claim(stub, CLAIM)
    assert resp.verdict == "SUPPORTED" and resp.source_chunk_ids == ["c1"]