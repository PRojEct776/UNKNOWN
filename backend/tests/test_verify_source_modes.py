import json
from types import SimpleNamespace

import pytest

import app.services.rag_service as rag_module
from app.api.schemas import ClaimVerificationRequest
from app.rag.claim_verifier import ClaimVerifier
from app.rag.context_builder import ContextBuilder

CLAIM = "The model reached 85% accuracy"
ORIGINAL = "The model reached 85% accuracy and used 10 epochs."
PARTS = [{"text": "The model reached 85% accuracy"}, {"text": "The model used 10 epochs"}]

ACC_TEXT = "The model reached an accuracy of 85% on the test set."
DOC_OTHER = [{"chunk_id": "d1", "document": "a.pdf", "page": 1, "rank": 1,
              "text": "The dataset contains 500 images."}]
DOC_ACC = [{"chunk_id": "d1", "document": "a.pdf", "page": 1, "rank": 1, "text": ACC_TEXT}]
WEB_CHUNK = {"id": "arxiv:abc", "title": "Paper X", "text": ACC_TEXT,
             "url": "https://arxiv.org/abs/1", "origin": "web",
             "retrieved_at": "2026-01-01T00:00:00+00:00"}
OK_STATUS = [{"connector": "arxiv", "outcome": "ok", "count": 1, "detail": ""}]
EMPTY_STATUS = [{"connector": "arxiv", "outcome": "no_results", "count": 0, "detail": ""}]
ERR_STATUS = [
    {"connector": "arxiv", "outcome": "timeout", "count": 0, "detail": "no response within 8s"},
    {"connector": "crossref", "outcome": "error", "count": 0, "detail": "ConnectError"},
]


class _Resp:
    def __init__(self, answer):
        self.success, self.answer, self.error, self.error_kind = True, answer, None, None


def _reply(verdict, supporting=(), ids=()):
    return json.dumps({"verdict": verdict, "confidence": 0.9, "explanation": "e",
                       "supporting_evidence": list(supporting),
                       "contradicting_evidence": [],
                       "source_chunk_ids": list(ids)})


WEB_SUPPORT = _reply("SUPPORTED", ["accuracy of 85% on the test set"], ["arxiv:abc"])
DOC_SUPPORT = _reply("SUPPORTED", ["accuracy of 85% on the test set"], ["d1"])
SPLIT_ONE = json.dumps({"claims": [{"text": CLAIM}]})
SPLIT_TWO = json.dumps({"claims": PARTS})


def _service(monkeypatch, doc_chunks, web, verify_reply, split_reply=SPLIT_ONE):
    cls = next(v for v in vars(rag_module).values()
               if isinstance(v, type) and v.__module__ == rag_module.__name__
               and hasattr(v, "verify_claim"))
    calls = SimpleNamespace(split=0, verify=0, search=0, web_queries=[], prompts=[])

    def gen(prompt, system=None):
        if system and "claim extraction" in system:
            calls.split += 1
            return _Resp(split_reply)
        calls.verify += 1
        calls.prompts.append(prompt)
        return _Resp(verify_reply)

    def search(claim, document_names=None):
        calls.search += 1
        return doc_chunks

    def fake_fetch(query, *args, **kwargs):
        calls.web_queries.append(query)
        return web

    monkeypatch.setattr(rag_module, "_fetch_web_chunks", fake_fetch)
    stub = SimpleNamespace(
        _search=search,
        context_builder=ContextBuilder(),
        claim_verifier=ClaimVerifier(),
        llm=SimpleNamespace(generate=gen),
    )
    stub.verify_claim = (
        lambda c, document_names=None, _split=True, source_mode=None, _web=None:
        cls.verify_claim(stub, c, document_names=document_names, _split=_split,
                         source_mode=source_mode, _web=_web))
    return cls, stub, calls


# ---- schema ----
def test_request_source_mode_is_optional_and_defaults_to_none():
    assert ClaimVerificationRequest(claim="x").source_mode is None
    assert ClaimVerificationRequest(claim="x", source_mode="web").source_mode == "web"


# ---- documents mode and legacy default stay offline ----
@pytest.mark.parametrize("mode", ["documents", None])
def test_documents_and_default_never_touch_the_web(monkeypatch, mode):
    cls, stub, calls = _service(monkeypatch, DOC_ACC, ([WEB_CHUNK], OK_STATUS), DOC_SUPPORT)
    resp = cls.verify_claim(stub, CLAIM, source_mode=mode)
    assert calls.web_queries == []
    assert calls.search == 1
    assert resp.verdict == "SUPPORTED"


def test_invalid_source_mode_raises_and_does_not_fetch(monkeypatch):
    cls, stub, calls = _service(monkeypatch, DOC_ACC, ([WEB_CHUNK], OK_STATUS), DOC_SUPPORT)
    with pytest.raises(ValueError):
        cls.verify_claim(stub, CLAIM, source_mode="everything")
    assert calls.web_queries == [] and calls.search == 0


# ---- web mode ----
def test_web_mode_skips_documents_and_grounds_against_web_text(monkeypatch):
    cls, stub, calls = _service(monkeypatch, DOC_OTHER, ([WEB_CHUNK], OK_STATUS), WEB_SUPPORT)
    resp = cls.verify_claim(stub, CLAIM, source_mode="web")
    assert calls.search == 0
    assert calls.web_queries == [CLAIM]
    assert resp.verdict == "SUPPORTED"
    assert "arxiv:abc" in resp.source_chunk_ids
    assert resp.supporting_evidence == ["accuracy of 85% on the test set"]
    assert "500 images" not in calls.prompts[0]


def test_web_mode_all_connectors_failed_is_unverifiable(monkeypatch):
    cls, stub, calls = _service(monkeypatch, DOC_ACC, ([], ERR_STATUS), WEB_SUPPORT)
    resp = cls.verify_claim(stub, CLAIM, source_mode="web")
    assert resp.verdict == "UNVERIFIABLE"
    assert calls.verify == 0 and calls.search == 0
    text = resp.explanation.lower()
    assert "arxiv" in text and "timed out" in text


def test_web_mode_no_results_is_unverifiable_without_calling_llm(monkeypatch):
    cls, stub, calls = _service(monkeypatch, DOC_ACC, ([], EMPTY_STATUS), WEB_SUPPORT)
    resp = cls.verify_claim(stub, CLAIM, source_mode="web")
    assert resp.verdict == "UNVERIFIABLE"
    assert calls.verify == 0


def test_web_mode_compound_claim_fetches_web_once(monkeypatch):
    cls, stub, calls = _service(monkeypatch, [], ([WEB_CHUNK], OK_STATUS), WEB_SUPPORT,
                                split_reply=SPLIT_TWO)
    resp = cls.verify_claim(stub, ORIGINAL, source_mode="web")
    assert calls.web_queries == [ORIGINAL]
    assert calls.verify == 2
    assert len(resp.atomic_claims) == 2


# ---- both mode ----
def test_both_mode_merges_document_and_web_passages(monkeypatch):
    cls, stub, calls = _service(monkeypatch, DOC_OTHER, ([WEB_CHUNK], OK_STATUS), WEB_SUPPORT)
    resp = cls.verify_claim(stub, CLAIM, source_mode="both")
    assert calls.search == 1 and calls.web_queries == [CLAIM]
    assert "500 images" in calls.prompts[0] and "85%" in calls.prompts[0]
    assert resp.verdict == "SUPPORTED"
    assert "arxiv:abc" in resp.source_chunk_ids


def test_both_mode_web_failure_keeps_document_verdict_and_says_why(monkeypatch):
    cls, stub, calls = _service(monkeypatch, DOC_ACC, ([], ERR_STATUS), DOC_SUPPORT)
    resp = cls.verify_claim(stub, CLAIM, source_mode="both")
    assert resp.verdict == "SUPPORTED"
    assert "arxiv" in resp.explanation.lower()


def test_both_mode_nothing_from_docs_and_web_failed_is_unverifiable(monkeypatch):
    cls, stub, calls = _service(monkeypatch, [], ([], ERR_STATUS), DOC_SUPPORT)
    resp = cls.verify_claim(stub, CLAIM, source_mode="both")
    assert resp.verdict == "UNVERIFIABLE"
    assert calls.verify == 0
