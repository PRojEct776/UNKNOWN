"""
UNKNOWN – Wikipedia Connector

Uses the Wikipedia REST API (free, no key required).
Fetches the article summary (extract) for each search result.

API docs: https://en.wikipedia.org/api/rest_v1/
Search:   https://en.wikipedia.org/w/api.php?action=query&list=search
Summary:  https://en.wikipedia.org/api/rest_v1/page/summary/{title}
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.rag.logger import logger
from ._base import (
    Chunk,
    RateLimiter,
    _sha256,
    cache_get,
    cache_put,
    deduplicate,
    http_get_with_retry,
    make_chunk_id,
)

_CONNECTOR = "wikipedia"
_SEARCH_URL = "https://en.wikipedia.org/w/api.php"
_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
_RATE = RateLimiter(calls_per_second=1.0)  # Wikipedia asks ≤ 200/s but we stay polite


def _fetch_summary(page_title: str) -> dict | None:
    """Fetch the REST-API page summary for a single Wikipedia title."""
    url = _SUMMARY_URL.format(title=page_title.replace(" ", "_"))
    _RATE.wait()
    try:
        resp = http_get_with_retry(url)
        return resp.json()
    except Exception as exc:
        logger.warning("Wikipedia summary fetch failed for %r: %s", page_title, exc)
        return None


def _summary_to_chunk(data: dict) -> Chunk | None:
    """Convert a Wikipedia REST summary dict to a Chunk."""
    extract = data.get("extract", "").strip()
    if not extract:
        return None

    title = data.get("title", "")
    url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
    if not url:
        url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"

    retrieved_at = datetime.now(timezone.utc).isoformat()

    return Chunk(
        id=make_chunk_id(_CONNECTOR, doi=None, title=title, year=None),
        text=extract,
        title=title,
        authors=[],            # Wikipedia does not expose author lists via summary API
        year=None,
        venue="Wikipedia",
        doi=None,
        url=url,
        origin="web",
        retrieved_at=retrieved_at,
        content_hash=_sha256(extract),
    )


def search(query: str, n: int = 5) -> list[Chunk]:
    """
    Search Wikipedia and return up to `n` Chunks.

    Each Chunk contains the plain-text article summary (extract) exactly
    as returned by the REST API – no LLM rewriting.

    Args:
        query: Free-text search query.
        n:     Maximum number of results to return.

    Returns:
        List of Chunk objects (may be shorter than n if Wikipedia returns fewer).
    """
    # --- cache ---
    cached = cache_get(_CONNECTOR, query, n)
    if cached is not None:
        logger.debug("Wikipedia cache hit for %r (n=%d)", query, n)
        return [Chunk.from_dict(c) for c in cached]

    # --- search ---
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": min(n, 10),
        "format": "json",
        "utf8": 1,
    }
    _RATE.wait()
    try:
        resp = http_get_with_retry(_SEARCH_URL, params=params)
        data = resp.json()
    except Exception as exc:
        from app.connectors._base import note_connector_failure
        note_connector_failure(type(exc).__name__)
        logger.warning("Wikipedia search failed for %r: %s", query, exc)
        return []

    search_results = data.get("query", {}).get("search", [])
    chunks: list[Chunk] = []

    for hit in search_results[:n]:
        page_title = hit.get("title", "")
        if not page_title:
            continue
        summary = _fetch_summary(page_title)
        if summary is None:
            continue
        chunk = _summary_to_chunk(summary)
        if chunk:
            chunks.append(chunk)

    chunks = deduplicate(chunks)
    cache_put(_CONNECTOR, query, n, [c.to_dict() for c in chunks])
    return chunks
