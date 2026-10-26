"""
UNKNOWN – Crossref Connector

Uses the Crossref REST API (free, no key required).
Returns abstracts and metadata for scholarly works.

API docs: https://api.crossref.org/swagger-ui/index.html
Endpoint: https://api.crossref.org/works?query=...&rows=n
"""

from __future__ import annotations

import re
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

_CONNECTOR = "crossref"
_WORKS_URL = "https://api.crossref.org/works"
_RATE = RateLimiter(calls_per_second=1.0)   # Crossref polite pool: up to 50/s; we stay safe

# Crossref polite pool requires identifying yourself in User-Agent
_CROSSREF_HEADERS = {
    "User-Agent": (
        "UNKNOWN-RAG/1.0 (academic research assistant; "
        "mailto:research@unknown.ai)"
    )
}


def _strip_html(text: str) -> str:
    """Remove HTML/JATS tags from Crossref abstract fields."""
    return re.sub(r"<[^>]+>", "", text).strip()


def _extract_year(date_parts: list | None) -> int | None:
    if not date_parts:
        return None
    try:
        parts = date_parts[0] if isinstance(date_parts[0], list) else date_parts
        return int(parts[0])
    except (IndexError, TypeError, ValueError):
        return None


def _work_to_chunk(work: dict) -> Chunk | None:
    """Convert a Crossref Work object to a Chunk."""
    # Title
    titles = work.get("title") or []
    title = titles[0].strip() if titles else ""
    if not title:
        return None

    # Abstract (often contains JATS/HTML markup)
    abstract_raw = work.get("abstract") or ""
    abstract = _strip_html(abstract_raw).strip()

    text = abstract if abstract else title
    if not text.strip():
        return None

    # Authors
    authors_raw = work.get("author") or []
    authors: list[str] = []
    for a in authors_raw:
        given = a.get("given", "")
        family = a.get("family", "")
        full = f"{given} {family}".strip()
        if full:
            authors.append(full)

    # Year
    published = (
        work.get("published-print")
        or work.get("published-online")
        or work.get("issued")
    )
    year = _extract_year((published or {}).get("date-parts"))

    # DOI
    doi = (work.get("DOI") or "").strip() or None

    # URL
    url = f"https://doi.org/{doi}" if doi else work.get("URL", "")

    # Venue
    container = work.get("container-title") or []
    venue = container[0].strip() if container else (work.get("publisher") or "").strip() or None

    retrieved_at = datetime.now(timezone.utc).isoformat()

    return Chunk(
        id=make_chunk_id(_CONNECTOR, doi, title, year),
        text=text,
        title=title,
        authors=authors,
        year=year,
        venue=venue,
        doi=doi,
        url=url,
        origin="scholarly",
        retrieved_at=retrieved_at,
        content_hash=_sha256(text),
    )


def search(query: str, n: int = 5) -> list[Chunk]:
    """
    Search Crossref and return up to `n` Chunks.

    Args:
        query: Free-text search query.
        n:     Maximum number of results to return.

    Returns:
        List of Chunk objects.
    """
    cached = cache_get(_CONNECTOR, query, n)
    if cached is not None:
        logger.debug("Crossref cache hit for %r (n=%d)", query, n)
        return [Chunk.from_dict(c) for c in cached]

    params = {
        "query": query,
        "rows": min(n, 20),
        "select": "title,abstract,author,published-print,published-online,issued,DOI,URL,container-title,publisher",
        "sort": "relevance",
        "order": "desc",
    }
    _RATE.wait()
    try:
        resp = http_get_with_retry(
            _WORKS_URL,
            params=params,
            extra_headers=_CROSSREF_HEADERS,
        )
        data = resp.json()
    except Exception as exc:
        from app.connectors._base import note_connector_failure
        note_connector_failure(type(exc).__name__)
        logger.warning("Crossref search failed for %r: %s", query, exc)
        return []

    items = (data.get("message") or {}).get("items") or []
    chunks: list[Chunk] = []
    for item in items[:n]:
        chunk = _work_to_chunk(item)
        if chunk:
            chunks.append(chunk)

    chunks = deduplicate(chunks)
    cache_put(_CONNECTOR, query, n, [c.to_dict() for c in chunks])
    return chunks
