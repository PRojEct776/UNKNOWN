"""
UNKNOWN - Tavily web search connector (live web, free tier).

Needs TAVILY_API_KEY in backend/.env. Without a key the connector is not part of
the default connector list (see dual_retriever._default_connector_names).

API: POST https://api.tavily.com/search with a bearer key and a JSON body.
Each basic search costs 1 credit; the free plan gives 1,000 credits per month.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from app.rag.logger import logger
from ._base import (
    Chunk,
    RateLimiter,
    _sha256,
    cache_get,
    cache_put,
    deduplicate,
    make_chunk_id,
    note_connector_failure,
)

_CONNECTOR = "tavily"
_API_URL = "https://api.tavily.com/search"
_MAX_RESULTS = 10
_RATE = RateLimiter(calls_per_second=0.3)  # stay under the documented 20 requests/minute


def api_key() -> str:
    """Return the configured key ('' when missing). Never logged."""
    try:
        import app.rag.config  # noqa: F401  (loads backend/.env)
    except Exception:
        pass
    return (os.getenv("TAVILY_API_KEY") or "").strip()


def is_configured() -> bool:
    return bool(api_key())


def _result_to_chunk(result: dict, retrieved_at: str) -> Chunk | None:
    text = str(result.get("content") or "").strip()
    url = str(result.get("url") or "").strip()
    if not text or not url:
        return None
    title = str(result.get("title") or "").strip() or url
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return Chunk(
        id=make_chunk_id(_CONNECTOR, doi=None, title=url, year=None),
        text=text,
        title=title,
        authors=[],
        year=None,
        venue=host or "Web",
        doi=None,
        url=url,
        origin="web",
        retrieved_at=retrieved_at,
        content_hash=_sha256(text),
    )


def search(query: str, n: int = 5) -> list[Chunk]:
    """Search the live web through Tavily and return up to n Chunks."""
    key = api_key()
    if not key:
        note_connector_failure("NotConfigured")
        logger.warning("Tavily search skipped: TAVILY_API_KEY is not set.")
        return []

    cached = cache_get(_CONNECTOR, query, n)
    if cached is not None:
        logger.debug("Tavily cache hit for %r (n=%d)", query, n)
        return [Chunk.from_dict(c) for c in cached]

    payload = {
        "query": query,
        "search_depth": "basic",
        "max_results": max(1, min(int(n), _MAX_RESULTS)),
        "include_answer": False,
        "include_raw_content": False,
    }
    headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}

    _RATE.wait()
    try:
        with httpx.Client(timeout=httpx.Timeout(10.0)) as client:
            resp = client.post(_API_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        if isinstance(exc, httpx.HTTPStatusError):
            kind = "HTTP%d" % exc.response.status_code
        else:
            kind = type(exc).__name__
        note_connector_failure(kind)
        logger.warning("Tavily search failed for %r: %s", query, kind)
        return []

    retrieved_at = datetime.now(timezone.utc).isoformat()
    chunks: list[Chunk] = []
    for item in (data.get("results") or [])[:n]:
        if not isinstance(item, dict):
            continue
        chunk = _result_to_chunk(item, retrieved_at)
        if chunk:
            chunks.append(chunk)

    chunks = deduplicate(chunks)
    cache_put(_CONNECTOR, query, n, [c.to_dict() for c in chunks])
    return chunks
