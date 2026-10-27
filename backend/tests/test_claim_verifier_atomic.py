import json
from types import SimpleNamespace

import pytest

import app.services.rag_service as rag_module
from app.rag.claim_verifier import ClaimVerdict, ClaimVerifier
from app.rag.context_builder import ContextBuilder

V = ClaimVerifier

ORIGINAL = "The model reached 85% accuracy and used 10 epochs."
PARTS = [{"text": "The model reached 85% accuracy"}, {"text": "The model used 10 epochs"}]


def _texts(parts):
    return [p["text"] for p in parts]


# ---- select_atomic_claims ----
def test_select_keeps_valid_parts():
    assert V.select_atomic_claims(ORIGINAL, PARTS) == _texts(PARTS)


def test_select_drops_invented_part_then_falls_back_when_too_few_remain():
    parts = PARTS[:1] + [{"text": "The model was trained on ImageNet"}]
    assert V.select_atomic_claims(ORIGINAL, parts) == [ORIGINAL]


def test_select_keeps_valid_parts_when_a_third_is_invented():
    parts = PARTS + [{"text": "The model was trained on ImageNet"}]
    assert V.select_atomic_claims(ORIGINAL, parts) == _texts(PARTS)


def test_select_removes_repeats_case_and_whitespace_insensitively():
    parts = PARTS + [{"text": "the  model reached 85% accuracy"}]
    assert V.select_atomic_claims(ORIGINAL, parts) == _texts(PARTS)


def test_select_falls_back_when_a_number_is_not_covered():
    parts = [{"text": "The model reached 85% accuracy"},
             {"text": "The model reached accuracy"}]
    assert V.select_atomic_claims(ORIGINAL, parts) == [ORIGINAL]


def test_select_rejects_part_with_number_not_in_original():
    parts = [{"text": "The model reached 95% accuracy"},
             {"text": "The model used 10 epochs"}]
    assert V.select_atomic_claims(ORIGINAL, parts) == [ORIGINAL]


def test_select_falls_back_over_the_cap_instead_of_truncating():
    words = "alpha bravo charlie delta echo foxtrot golf".split()
    original = " and ".join(words)
    assert V.select_atomic_claims(original, [{"text": w} for w in words]) == [original]


@pytest.mark.parametrize("parts", [None, [], [None, {"text": ""}, {"x": 1}, 5]])
def test_select_handles_malformed_input(parts):
    assert V.select_atomic_claims(ORIGINAL, parts) == [ORIGINAL]


# ---- aggregate_verdicts ----
@pytest.mark.parametrize("verdicts,expected", [
    (["SUPPORTED", "SUPPORTED"], "SUPPORTED"),
    (["SUPPORTED", "UNSUPPORTED"], "PARTIALLY_SUPPORTED"),
    (["SUPPORTED", "CONTRADICTED"], "CONTRADICTED"),
    (["PARTIALLY_SUPPORTED", "SUPPORTED"], "PARTIALLY_SUPPORTED"),
    (["UNSUPPORTED", "NOT_FOUND"], "UNSUPPORTED"),
    (["NOT_FOUND", "NOT_FOUND"], "NOT_FOUND"),
    (["UNVERIFIABLE", "UNVERIFIABLE"], "UNVERIFIABLE"),
    (["SUPPORTED", "UNVERIFIABLE"], "PARTIALLY_SUPPORTED"),
    (["UNSUPPORTED", "UNVERIFIABLE"], "UNSUPPORTED"),
    ([], "NOT_FOUND"),
])
def test_aggregate_verdicts(verdicts, expected):
    assert V.aggregate_verdicts(verdicts).value == expected


def test_aggregate_accepts_enum_members_and_rejects_unknown_labels():
    assert V.aggregate_verdicts([ClaimVerdict.SUPPORTED]) == ClaimVerdict.SUPPORTED
    with pytest.raises(ValueError):
        V.aggregate_verdicts(["MAYBE"])


# ---- service wiring (stub self; no models, no network) ----
CHUNKS = [
    {"chunk_id": "c1", "document": "a.pdf", "page": 1, "rank": 1,
     "text": "The model reached an accuracy of 85% on the test set."},
    {"chunk_id": "c2", "document": "a.pdf", "page": 2, "rank": 2,
     "text": "Training used 10 epochs."},
]


class _Resp:
    def __init__(self, answer):
        self.success, self.answer, self.error, self.error_kind = True, answer, None, None


def _answer(verdict, supporting=(), contradicting=(), ids=(), confidence=0.9):
    return json.dumps({"verdict": verdict, "confidence": confidence, "explanation": "e",
                       "supporting_evidence": list(supporting),
                       "contradicting_evidence": list(contradicting),
                       "source_chunk_ids": list(ids)})


def _service(chunks, split_reply, answers):
    cls = next(v for v in vars(rag_module).values()
               if isinstance(v, type) and v.__module__ == rag_module.__name__
               and hasattr(v, "verify_claim"))
    calls = SimpleNamespace(split=0, verify=0)

    def gen(prompt, system=None):
        if system and "claim extraction" in system:
            calls.split += 1
            return _Resp(split_reply)
        calls.verify += 1
        for text, reply in answers.items():
            if "CLAIM:\n" + text + "\n" in prompt:
                return _Resp(reply)
        raise AssertionError("unexpected verification prompt")

    stub = SimpleNamespace(
        _search=lambda claim, document_names=None: chunks,
        context_builder=ContextBuilder(),
        claim_verifier=ClaimVerifier(),
        llm=SimpleNamespace(generate=gen),
    )
    stub.verify_claim = lambda c, document_names=None, _split=True: cls.verify_claim(
        stub, c, document_names=document_names, _split=_split)
    return cls, stub, calls


SPLIT = json.dumps({"claims": PARTS})
SUPPORT_1 = _answer("SUPPORTED", ["accuracy of 85% on the test set"], ids=["c1"], confidence=0.9)
SUPPORT_2 = _answer("SUPPORTED", ["Training used 10 epochs"], ids=["c2"], confidence=0.6)


def test_service_all_parts_supported():
    answers = {PARTS[0]["text"]: SUPPORT_1, PARTS[1]["text"]: SUPPORT_2}
    cls, stub, calls = _service(CHUNKS, SPLIT, answers)
    resp = cls.verify_claim(stub, ORIGINAL)
    assert resp.claim == ORIGINAL and resp.verdict == "SUPPORTED"
    assert [a.verdict for a in resp.atomic_claims] == ["SUPPORTED", "SUPPORTED"]
    assert (calls.split, calls.verify) == (1, 2)
    assert resp.confidence == 0.6
    assert set(resp.source_chunk_ids) == {"c1", "c2"}


def test_service_unestablished_part_gives_partial():
    answers = {PARTS[0]["text"]: SUPPORT_1, PARTS[1]["text"]: _answer("UNSUPPORTED")}
    cls, stub, _ = _service(CHUNKS, SPLIT, answers)
    resp = cls.verify_claim(stub, ORIGINAL)
    assert resp.verdict == "PARTIALLY_SUPPORTED"
    assert [a.verdict for a in resp.atomic_claims] == ["SUPPORTED", "UNSUPPORTED"]


def test_service_contradicted_part_makes_whole_claim_contradicted():
    original = "The model reached 85% accuracy and used 20 epochs."
    parts = [{"text": "The model reached 85% accuracy"}, {"text": "The model used 20 epochs"}]
    answers = {parts[0]["text"]: SUPPORT_1,
               parts[1]["text"]: _answer("CONTRADICTED", contradicting=["Training used 10 epochs"],
                                         ids=["c2"])}
    cls, stub, _ = _service(CHUNKS, json.dumps({"claims": parts}), answers)
    resp = cls.verify_claim(stub, original)
    assert resp.verdict == "CONTRADICTED"
    assert resp.contradicting_evidence == ["Training used 10 epochs"]
    assert resp.atomic_claims[1].contradicting_evidence == ["Training used 10 epochs"]


def test_service_single_part_uses_the_legacy_path():
    claim = "The model reached 85% accuracy"
    cls, stub, calls = _service(CHUNKS, json.dumps({"claims": [{"text": claim}]}),
                                {claim: SUPPORT_1})
    resp = cls.verify_claim(stub, claim)
    assert resp.verdict == "SUPPORTED" and resp.atomic_claims == []
    assert calls.verify == 1


def test_service_malformed_split_output_falls_back_to_one_claim():
    cls, stub, calls = _service(CHUNKS, "not json at all", {ORIGINAL: SUPPORT_1})
    resp = cls.verify_claim(stub, ORIGINAL)
    assert resp.atomic_claims == [] and calls.verify == 1


def test_service_invented_parts_are_not_verified():
    split = json.dumps({"claims": PARTS + [{"text": "The model was trained on ImageNet"}]})
    answers = {PARTS[0]["text"]: SUPPORT_1, PARTS[1]["text"]: SUPPORT_2}
    cls, stub, calls = _service(CHUNKS, split, answers)
    resp = cls.verify_claim(stub, ORIGINAL)
    assert len(resp.atomic_claims) == 2 and calls.verify == 2


def test_service_empty_retrieval_skips_verification_calls():
    cls, stub, calls = _service([], SPLIT, {})
    resp = cls.verify_claim(stub, ORIGINAL)
    assert calls.verify == 0
    assert resp.verdict == "NOT_FOUND" and len(resp.atomic_claims) == 2