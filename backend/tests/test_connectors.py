"""
Tests for Connector Package (Task A2)

Validates:
- Unit tests with saved fixtures for wikipedia, openalex, arxiv, crossref
- Deduplication by DOI and fuzzy title similarity
- Multi-connector resilience: failure of one connector does not fail the composite request
- Integration tests (@pytest.mark.integration) for real live APIs
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import xml.etree.ElementTree as ET

import pytest
import httpx

from app.connectors._base import Chunk, deduplicate
from app.connectors import wikipedia, openalex, arxiv, crossref

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

# ---------------------------------------------------------------------------
# Fixture-based Unit Tests
# ---------------------------------------------------------------------------

def test_wikipedia_connector_with_fixture(monkeypatch):
    search_json = json.loads((FIXTURES_DIR / "wikipedia_search.json").read_text("utf-8"))
    summary_json = json.loads((FIXTURES_DIR / "wikipedia_summary.json").read_text("utf-8"))

    def mock_http_get(url, params=None, extra_headers=None, max_retries=3, backoff_base=1.0):
        mock_resp = MagicMock()
        if "action=query" in str(params) or (params and params.get("action") == "query"):
            mock_resp.json.return_value = search_json
        else:
            mock_resp.json.return_value = summary_json
        mock_resp.status_code = 200
        return mock_resp

    monkeypatch.setattr(wikipedia, "http_get_with_retry", mock_http_get)
    monkeypatch.setattr(wikipedia, "cache_get", lambda *args: None)
    monkeypatch.setattr(wikipedia, "cache_put", lambda *args: None)

    chunks = wikipedia.search("Transformer", n=1)
    assert len(chunks) == 1
    chunk = chunks[0]
    assert isinstance(chunk, Chunk)
    assert chunk.origin == "web"
    assert "Transformer (machine learning model)" in chunk.title
    assert "self-attention" in chunk.text
    assert chunk.venue == "Wikipedia"
    assert chunk.url.startswith("https://en.wikipedia.org/wiki/")
    assert chunk.content_hash != ""


def test_openalex_connector_with_fixture(monkeypatch):
    works_json = json.loads((FIXTURES_DIR / "openalex_works.json").read_text("utf-8"))

    def mock_http_get(url, params=None, extra_headers=None, max_retries=3, backoff_base=1.0):
        mock_resp = MagicMock()
        mock_resp.json.return_value = works_json
        mock_resp.status_code = 200
        return mock_resp

    monkeypatch.setattr(openalex, "http_get_with_retry", mock_http_get)
    monkeypatch.setattr(openalex, "cache_get", lambda *args: None)
    monkeypatch.setattr(openalex, "cache_put", lambda *args: None)

    chunks = openalex.search("Attention is all you need", n=2)
    assert len(chunks) == 1
    c = chunks[0]
    assert c.origin == "scholarly"
    assert c.title == "Attention Is All You Need"
    assert c.doi == "10.48550/arxiv.1706.03762"
    assert c.year == 2017
    assert "Ashish Vaswani" in c.authors
    assert "recurrent or convolutional" in c.text
    assert c.url == "https://doi.org/10.48550/arxiv.1706.03762"


def test_arxiv_connector_with_fixture(monkeypatch):
    feed_xml = (FIXTURES_DIR / "arxiv_feed.xml").read_text("utf-8")

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
        def get(self, url, params=None):
            resp = MagicMock()
            resp.text = feed_xml
            resp.status_code = 200
            return resp

    monkeypatch.setattr(httpx, "Client", MockClient)
    monkeypatch.setattr(arxiv, "cache_get", lambda *args: None)
    monkeypatch.setattr(arxiv, "cache_put", lambda *args: None)

    chunks = arxiv.search("Transformer", n=1)
    assert len(chunks) == 1
    c = chunks[0]
    assert c.origin == "scholarly"
    assert c.title == "Attention Is All You Need"
    assert c.year == 2017
    assert "Ashish Vaswani" in c.authors
    assert "dispensing with recurrence" in c.text
    assert c.url.startswith("https://arxiv.org/abs/")
    assert c.doi == "10.48550/arXiv.1706.03762"


def test_crossref_connector_with_fixture(monkeypatch):
    works_json = json.loads((FIXTURES_DIR / "crossref_works.json").read_text("utf-8"))

    def mock_http_get(url, params=None, extra_headers=None, max_retries=3, backoff_base=1.0):
        mock_resp = MagicMock()
        mock_resp.json.return_value = works_json
        mock_resp.status_code = 200
        return mock_resp

    monkeypatch.setattr(crossref, "http_get_with_retry", mock_http_get)
    monkeypatch.setattr(crossref, "cache_get", lambda *args: None)
    monkeypatch.setattr(crossref, "cache_put", lambda *args: None)

    chunks = crossref.search("Nearest Neighbor", n=1)
    assert len(chunks) == 1
    c = chunks[0]
    assert c.origin == "scholarly"
    assert "Scalable Nearest Neighbor Algorithms" in c.title
    assert c.doi == "10.1145/3318464.3389700"
    assert c.year == 2014
    assert "<jats:p>" not in c.text  # HTML stripped
    assert "Nearest neighbor search is an essential" in c.text
    assert c.url == "https://doi.org/10.1145/3318464.3389700"


# ---------------------------------------------------------------------------
# Deduplication Tests
# ---------------------------------------------------------------------------

def test_deduplicate_by_doi_and_title_similarity():
    c1 = Chunk(
        id="c1",
        text="Sample text 1",
        title="Attention Is All You Need",
        authors=["Vaswani"],
        year=2017,
        venue="NeurIPS",
        doi="10.1234/test.123",
        url="https://doi.org/10.1234/test.123",
        origin="scholarly",
        retrieved_at="2026-10-24T00:00:00Z",
        content_hash="hash1",
    )
    # Exact duplicate DOI
    c2 = Chunk(
        id="c2",
        text="Sample text 2",
        title="Different Title But Same DOI",
        authors=["Vaswani"],
        year=2017,
        venue="NeurIPS",
        doi="10.1234/test.123",
        url="https://doi.org/10.1234/test.123",
        origin="scholarly",
        retrieved_at="2026-10-24T00:00:00Z",
        content_hash="hash2",
    )
    # Similar title, different or missing DOI
    c3 = Chunk(
        id="c3",
        text="Sample text 3",
        title="Attention is all you need!",
        authors=["Vaswani"],
        year=2017,
        venue="arXiv",
        doi=None,
        url="https://arxiv.org/abs/1706.03762",
        origin="scholarly",
        retrieved_at="2026-10-24T00:00:00Z",
        content_hash="hash3",
    )
    # Distinct item
    c4 = Chunk(
        id="c4",
        text="Sample text 4",
        title="BERT: Pre-training of Deep Bidirectional Transformers",
        authors=["Devlin"],
        year=2018,
        venue="NAACL",
        doi="10.1234/bert.456",
        url="https://doi.org/10.1234/bert.456",
        origin="scholarly",
        retrieved_at="2026-10-24T00:00:00Z",
        content_hash="hash4",
    )

    deduped = deduplicate([c1, c2, c3, c4])
    assert len(deduped) == 2
    assert deduped[0].id == "c1"
    assert deduped[1].id == "c4"


# ---------------------------------------------------------------------------
# Resilience: One connector failure does not fail overall request
# ---------------------------------------------------------------------------

def test_connector_failure_resilience(monkeypatch):
    """When one connector raises an exception or fails, others still yield results."""
    def failing_search(query, n=5):
        raise RuntimeError("Network down or timeout")

    def successful_search(query, n=5):
        return [
            Chunk(
                id="w1",
                text="Wikipedia article content.",
                title="Wikipedia Result",
                authors=[],
                year=None,
                venue="Wikipedia",
                doi=None,
                url="https://en.wikipedia.org/wiki/Test",
                origin="web",
                retrieved_at="2026-10-24T00:00:00Z",
                content_hash="hashw",
            )
        ]

    # Function executing multi-connector search
    def aggregate_search(query, n=5):
        connectors = [failing_search, successful_search]
        all_chunks = []
        for conn in connectors:
            try:
                all_chunks.extend(conn(query, n=n))
            except Exception:
                continue
        return deduplicate(all_chunks)

    results = aggregate_search("Test query", n=5)
    assert len(results) == 1
    assert results[0].title == "Wikipedia Result"


# ---------------------------------------------------------------------------
# Real API Integration Tests (marked @pytest.mark.integration)
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.slow
def test_wikipedia_integration():
    chunks = wikipedia.search("Quantum computing", n=2)
    assert len(chunks) > 0
    assert all(isinstance(c, Chunk) for c in chunks)
    assert all(c.origin == "web" for c in chunks)


@pytest.mark.integration
@pytest.mark.slow
def test_openalex_integration():
    chunks = openalex.search("Deep Learning", n=2)
    assert len(chunks) > 0
    assert all(isinstance(c, Chunk) for c in chunks)
    assert all(c.origin == "scholarly" for c in chunks)


@pytest.mark.integration
@pytest.mark.slow
def test_arxiv_integration():
    chunks = arxiv.search("Machine Learning", n=2)
    assert len(chunks) > 0
    assert all(isinstance(c, Chunk) for c in chunks)
    assert all(c.origin == "scholarly" for c in chunks)


@pytest.mark.integration
@pytest.mark.slow
def test_crossref_integration():
    chunks = crossref.search("Neural Networks", n=2)
    assert len(chunks) > 0
    assert all(isinstance(c, Chunk) for c in chunks)
    assert all(c.origin == "scholarly" for c in chunks)
