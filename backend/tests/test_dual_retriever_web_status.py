"""WEB-09: web connector failures must be reported in gaps, never silently dropped."""

from __future__ import annotations

import threading
import time
from types import SimpleNamespace

import pytest

from app.connectors._base import note_connector_failure, take_connector_failure
from app.rag import dual_retriever
from app.rag.dual_retriever import DualRetriever, _fetch_web_chunks, _web_gaps_from_statuses

_RETRIEVE = next(
    (getattr(DualRetriever, n) for n in ("retrieve", "dual_retrieve") if hasattr(DualRetriever, n)),
    None,
)


def _chunk(name: str) -> dict:
    return {
        "id": name,
        "title": name,
        "text": name + " passage",
        "url": "https://example.org/" + name,
        "origin": "web",
    }


def _fake(name, chunks=None, fail=None, release=None, calls=None):
    def search(query, n):
        if calls is not None:
            calls.append(name)
        if release is not None:
            release.wait(10)
            return []
        if fail:
            note_connector_failure(fail)
            return []
        return list(chunks or [])

    return SimpleNamespace(__name__="app.connectors." + name, search=search)


def _install(monkeypatch, mods):
    monkeypatch.setattr(dual_retriever, "_load_connectors", lambda names=None: mods)


def _outcomes(statuses):
    return {s["connector"]: s["outcome"] for s in statuses}


class _NoDocs:
    def search(self, query, **kwargs):
        return []


def _bare_retriever(connector_names):
    d = DualRetriever.__new__(DualRetriever)
    d._retriever = _NoDocs()
    d._connector_names = connector_names
    d._nli_fn = None
    return d


def test_failure_flag_is_per_thread_and_cleared():
    note_connector_failure("ConnectError")
    seen = []
    th = threading.Thread(target=lambda: seen.append(take_connector_failure()))
    th.start()
    th.join()
    assert seen == [None]
    assert take_connector_failure() == "ConnectError"
    assert take_connector_failure() is None


def test_all_connectors_failing_is_reported(monkeypatch):
    _install(monkeypatch, [_fake("arxiv", fail="ConnectError"), _fake("crossref", fail="ReadTimeout")])
    chunks, statuses = _fetch_web_chunks("q", connector_names=["arxiv", "crossref"], timeout_s=2)
    assert chunks == []
    assert _outcomes(statuses) == {"arxiv": "error", "crossref": "error"}
    gaps = _web_gaps_from_statuses(statuses)
    assert any("every web source failed" in g for g in gaps)
    assert any("arXiv" in g and "ConnectError" in g for g in gaps)
    assert any("Crossref" in g and "ReadTimeout" in g for g in gaps)


def test_one_connector_failing_is_reported(monkeypatch):
    _install(monkeypatch, [_fake("arxiv", fail="ConnectError"), _fake("crossref", chunks=[_chunk("paper")])])
    chunks, statuses = _fetch_web_chunks("q", connector_names=["arxiv", "crossref"], timeout_s=2)
    assert len(chunks) == 1
    assert _outcomes(statuses) == {"arxiv": "error", "crossref": "ok"}
    gaps = _web_gaps_from_statuses(statuses)
    assert len(gaps) == 1
    assert "arXiv" in gaps[0]


def test_hanging_connector_times_out_without_blocking(monkeypatch):
    release = threading.Event()
    _install(monkeypatch, [_fake("arxiv", chunks=[_chunk("fast")]), _fake("crossref", release=release)])
    try:
        started = time.perf_counter()
        chunks, statuses = _fetch_web_chunks("q", connector_names=["arxiv", "crossref"], timeout_s=0.3)
        elapsed = time.perf_counter() - started
    finally:
        release.set()
    assert elapsed < 3
    assert len(chunks) == 1
    assert _outcomes(statuses) == {"arxiv": "ok", "crossref": "timeout"}
    gaps = _web_gaps_from_statuses(statuses)
    assert any("Crossref" in g and "timed out" in g for g in gaps)


def test_connector_that_fails_to_load_is_reported(monkeypatch):
    _install(monkeypatch, [_fake("arxiv", chunks=[_chunk("paper")])])
    chunks, statuses = _fetch_web_chunks("q", connector_names=["arxiv", "crossref"], timeout_s=2)
    assert len(chunks) == 1
    assert _outcomes(statuses) == {"crossref": "not_loaded", "arxiv": "ok"}
    gaps = _web_gaps_from_statuses(statuses)
    assert any("Crossref" in g and "could not be loaded" in g for g in gaps)


def test_zero_results_without_failures_is_not_called_an_error(monkeypatch):
    _install(monkeypatch, [_fake("arxiv"), _fake("crossref")])
    chunks, statuses = _fetch_web_chunks("q", connector_names=["arxiv", "crossref"], timeout_s=2)
    assert chunks == []
    assert _outcomes(statuses) == {"arxiv": "no_results", "crossref": "no_results"}
    gaps = _web_gaps_from_statuses(statuses)
    assert len(gaps) == 1
    assert gaps[0].startswith("No scholarly web results found")
    assert "arXiv" in gaps[0] and "Crossref" in gaps[0]
    assert not any("unavailable" in g for g in gaps)


@pytest.mark.skipif(_RETRIEVE is None, reason="DualRetriever retrieve method not found")
def test_retrieve_puts_web_failures_in_gaps(monkeypatch):
    _install(monkeypatch, [_fake("arxiv", fail="ConnectError")])
    monkeypatch.setattr(dual_retriever, "_build_comparison", lambda *a, **k: None)
    result = _RETRIEVE(_bare_retriever(["arxiv"]), "some query", doc_only=False)
    assert any("every web source failed" in g for g in result.gaps)


@pytest.mark.skipif(_RETRIEVE is None, reason="DualRetriever retrieve method not found")
def test_doc_only_adds_no_web_gaps_and_calls_no_connector(monkeypatch):
    calls = []
    _install(monkeypatch, [_fake("arxiv", fail="ConnectError", calls=calls)])
    monkeypatch.setattr(dual_retriever, "_build_comparison", lambda *a, **k: None)
    result = _RETRIEVE(_bare_retriever(["arxiv"]), "some query", doc_only=True)
    assert not any("Web source" in g or "scholarly web" in g for g in result.gaps)
    assert calls == []
