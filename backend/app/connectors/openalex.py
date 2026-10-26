"""
UNKNOWN – OpenAlex Connector

Uses the OpenAlex API (free, no key needed for ≤ 10 req/s with polite pool).
Returns abstracts of scholarly works.

API docs: https://docs.openalex.org/
Endpoint: https://api.openalex.org/works?search=...&per-page=n
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

_CONNECTOR = "openalex"
_WORKS_URL = "https://api.openalex.org/works"
_RATE = RateLimiter(calls_per_second=5.0)   # polite pool allows up to 10/s; we use 5

# Polite-pool header (adds your email → higher rate limit)
_POLITE_EMAIL = "research@unknown.ai"


def _reconstruct_abstract(inverted_index: dict | None) -> str:
    """
    OpenAlex stores abstracts as an inverted index {word: [positions]}.
    Reconstruct the plain text.
    """
    if not inverted_index:
        return ""
    # Build position→word mapping
    max_pos = 0
    pos_map: dict[int, str] = {}
    for word, positions in inverted_index.items():
        for p in positions:
            pos_map[p] = word
            if p > max_pos:
                max_pos = p
    return " ".join(pos_map.get(i, "") for i in range(max_pos + 1)).strip()


def _work_to_chunk(work: dict) -> Chunk | None:
    """Convert an OpenAlex Work object to a Chunk."""
    abstract = _reconstruct_abstract(work.get("abstract_inverted_index"))
    title = (work.get("title") or "").strip()

    if not title:
        return None

    text = abstract if abstract else title
    if not text.strip():
        return None

    # Authors
    authorships = work.get("authorships", []) or []
    authors = [
        a.get("author", {}).get("display_name", "")
        for a in authorships
        if a.get("author", {}).get("display_name")
    ]

    # Year
    year: int | None = work.get("publication_year")

    # DOI – strip URL prefix to get bare DOI
    doi_raw = work.get("doi") or ""
    doi = doi_raw.replace("https://doi.org/", "").strip() or None

    # Venue
    primary_location = work.get("primary_location") or {}
    source = primary_location.get("source") or {}
    venue = (source.get("display_name") or "").strip() or None

    # Landing URL – prefer DOI link, fall back to OpenAlex page
    if doi:
        url = f"https://doi.org/{doi}"
    else:
        url = work.get("id", "")  # OpenAlex record URL

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
    Search OpenAlex and return up to `n` Chunks with abstracts.

    Args:
        query: Free-text search query.
        n:     Maximum number of results to return.

    Returns:
        List of Chunk objects.
    """
    cached = cache_get(_CONNECTOR, query, n)
    if cached is not None:
        logger.debug("OpenAlex cache hit for %r (n=%d)", query, n)
        return [Chunk.from_dict(c) for c in cached]

    params = {
        "search": query,
        "per-page": min(n, 25),
        "select": "id,title,abstract_inverted_index,publication_year,doi,authorships,primary_location",
        "mailto": _POLITE_EMAIL,
    }
    _RATE.wait()
    try:
        resp = http_get_with_retry(_WORKS_URL, params=params)
        data = resp.json()
    except Exception as exc:
        from app.connectors._base import note_connector_failure
        note_connector_failure(type(exc).__name__)
        logger.warning("OpenAlex search failed for %r: %s", query, exc)
        return []

    works = data.get("results", [])
    chunks: list[Chunk] = []
    for work in works[:n]:
        chunk = _work_to_chunk(work)
        if chunk:
            chunks.append(chunk)

    chunks = deduplicate(chunks)
    cache_put(_CONNECTOR, query, n, [c.to_dict() for c in chunks])
    return chunks
