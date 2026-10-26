"""Tavily connector: request shape, failure reporting, default connector list."""

from __future__ import annotations

import httpx
import pytest

import app.rag.config  # noqa: F401  (load_dotenv runs now, before tests clear the env)
from app.connectors import tavily
from app.connectors._base import take_connector_failure
from app.rag import dual_retriever


class _FakeResponse:
    def __init__(self, status=200, body=None):
        self.status_code = status
        self._body = body if body is not None else {"results": []}

    def raise_for_status(self):
        if self.status_code >= 400:
            req = httpx.Request("POST", tavily._API_URL)
            raise httpx.HTTPStatusError(
                "error", request=req, response=httpx.Response(self.status_code, request=req)
            )

    def json(self):
        return self._body


def _install_client(monkeypatch, response=None, error=None, calls=None):
    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, json=None, headers=None):
            if calls is not None:
                calls.append({"url": url, "json": json, "headers": headers})
            if error is not None:
                raise error
            return response

    monkeypatch.setattr(httpx, "Client", _Client)


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    monkeypatch.setattr(tavily, "cache_get", lambda *a, **k: None)
    monkeypatch.setattr(tavily, "cache_put", lambda *a, **k: None)
    monkeypatch.setattr(tavily._RATE, "wait", lambda: None)
    take_connector_failure()
    yield
    take_connector_failure()


def test_missing_key_returns_nothing_and_reports_not_configured(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    assert tavily.search("anything", 3) == []
    assert take_connector_failure() == "NotConfigured"


def test_successful_search_builds_chunks_and_sends_bearer_key(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    body = {
        "results": [
            {"title": "Page A", "url": "https://www.example.org/a", "content": "Alpha text", "score": 0.9},
            {"title": "Page B", "url": "https://docs.example.com/b", "content": "Beta text", "score": 0.8},
        ]
    }
    calls = []
    _install_client(monkeypatch, response=_FakeResponse(200, body), calls=calls)

    chunks = tavily.search("some query", 5)

    assert [c.title for c in chunks] == ["Page A", "Page B"]
    assert chunks[0].url == "https://www.example.org/a"
    assert chunks[0].venue == "example.org"
    assert chunks[0].origin == "web"
    assert chunks[0].text == "Alpha text"
    assert take_connector_failure() is None
    assert calls[0]["url"] == "https://api.tavily.com/search"
    assert calls[0]["headers"]["Authorization"] == "Bearer tvly-test"
    assert calls[0]["json"]["query"] == "some query"
    assert calls[0]["json"]["max_results"] == 5


def test_results_without_content_or_url_are_skipped(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    body = {
        "results": [
            {"title": "No text", "url": "https://a.example/x", "content": ""},
            {"title": "No url", "url": "", "content": "text"},
            {"title": "Good", "url": "https://a.example/y", "content": "ok"},
        ]
    }
    _install_client(monkeypatch, response=_FakeResponse(200, body))
    chunks = tavily.search("q", 5)
    assert [c.title for c in chunks] == ["Good"]


def test_max_results_is_clamped(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    calls = []
    _install_client(monkeypatch, response=_FakeResponse(200, {"results": []}), calls=calls)
    tavily.search("q", 50)
    assert calls[0]["json"]["max_results"] == 10


def test_http_error_is_reported_with_status(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    _install_client(monkeypatch, response=_FakeResponse(429))
    assert tavily.search("q", 3) == []
    assert take_connector_failure() == "HTTP429"


def test_network_error_is_reported_by_type(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    _install_client(monkeypatch, error=httpx.ConnectError("boom"))
    assert tavily.search("q", 3) == []
    assert take_connector_failure() == "ConnectError"


def test_zero_results_is_not_a_failure(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    _install_client(monkeypatch, response=_FakeResponse(200, {"results": []}))
    assert tavily.search("q", 3) == []
    assert take_connector_failure() is None


def test_default_connectors_include_tavily_only_when_key_is_set(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    with_key = dual_retriever._default_connector_names()
    assert with_key[0] == "tavily"
    assert {"wikipedia", "openalex", "arxiv", "crossref"} <= set(with_key)

    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    without_key = dual_retriever._default_connector_names()
    assert "tavily" not in without_key
    assert {"wikipedia", "openalex", "arxiv", "crossref"} <= set(without_key)
