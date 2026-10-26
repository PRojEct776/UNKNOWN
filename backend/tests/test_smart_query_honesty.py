import asyncio
from types import SimpleNamespace

import app.main as m
import app.rag.document_eligibility as elig
import app.rag.utils as rutils
import app.services.smart_router_service as sr


def _run(monkeypatch, routing):
    monkeypatch.setattr(m, "resolve_authenticated_workspace", lambda *a, **k: ("u", None))
    monkeypatch.setattr(elig, "get_user_authorized_documents", lambda *a, **k: {"a.txt", "b.txt"})
    monkeypatch.setattr(rutils, "list_supported_documents",
                        lambda *_: [SimpleNamespace(name="a.txt"), SimpleNamespace(name="b.txt")])
    monkeypatch.setattr(sr, "smart_route_query", lambda **k: routing)

    def boom(*a, **k):
        raise AssertionError("feature must not run")

    monkeypatch.setattr(sr, "extract_concept_graph", boom)
    req = SimpleNamespace(text="x", document_ids=None, run_all=False, stream=False)
    return asyncio.run(m.post_smart_query(
        request=req, http_request=None, authorization=None,
        x_session_token=None, x_user_id=None))


def _routing(feature, docs):
    return {"original_query": "x", "rewritten_query": "x", "matched_documents": docs,
            "detected_feature": feature, "run_all": False, "is_ambiguous": False,
            "clarification_options": []}


def test_multi_match_is_ambiguous_and_runs_nothing(monkeypatch):
    r = _run(monkeypatch, _routing("mindmap", ["a.txt", "b.txt"]))
    assert r.is_ambiguous is True
    assert r.executed_feature is None
    assert len(r.clarification_options) == 2


def test_unrun_feature_not_reported_executed(monkeypatch):
    r = _run(monkeypatch, _routing("gaps", ["a.txt"]))
    assert r.executed_feature is None
    assert r.result["status"] == "not_executed"
