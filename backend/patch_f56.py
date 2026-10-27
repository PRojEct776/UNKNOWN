import os, shutil, sys

P = r"app\main.py"
T = r"tests\test_smart_query_honesty.py"

raw = open(P, "rb").read().decode("utf-8")
nl = "\r\n" if "\r\n" in raw else "\n"

def fx(s):
    return s.replace("\n", nl)

edits = [
    (
        '        target_doc = routing["matched_documents"][0] if routing["matched_documents"] else ""\n',
        '        if detected in ("mindmap", "dna", "summary", "overview") and len(routing["matched_documents"]) > 1:\n'
        '            return SmartQueryResponse(\n'
        '                original_query=routing["original_query"],\n'
        '                rewritten_query=routing["rewritten_query"],\n'
        '                matched_documents=routing["matched_documents"],\n'
        '                detected_feature=detected,\n'
        '                executed_feature=None,\n'
        '                run_all=routing["run_all"],\n'
        '                is_ambiguous=True,\n'
        '                clarification_options=[f"{detected} for {d}" for d in routing["matched_documents"]],\n'
        '                result={"error": "Multiple documents matched; choose one. Nothing was executed."},\n'
        '            )\n'
        '        target_doc = routing["matched_documents"][0] if routing["matched_documents"] else ""\n',
    ),
    (
        '            executed_result = {"status": "executed", "feature": detected, "target_documents": routing["matched_documents"]}\n',
        '            executed_result = {"status": "not_executed", "feature": detected, "detail": "This feature is not run by /smart-query.", "target_documents": routing["matched_documents"]}\n',
    ),
    (
        '        executed_feature=detected,\n',
        '        executed_feature=(None if isinstance(executed_result, dict) and executed_result.get("status") == "not_executed" else detected),\n',
    ),
]

src = raw
for old, new in edits:
    o = fx(old)
    if src.count(o) != 1:
        print("ABORT: anchor matched", src.count(o), "times:", old.strip()[:70])
        sys.exit(1)
    src = src.replace(o, fx(new))

shutil.copyfile(P, P + ".bak")
open(P, "wb").write(src.encode("utf-8"))
print("patched", P)

if os.path.exists(T):
    print("SKIP: test file exists:", T)
    sys.exit(0)

test = '''import asyncio
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
'''
open(T, "w", newline="\n").write(test)
print("created", T)