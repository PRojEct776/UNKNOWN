"""
UNKNOWN – arXiv Connector

Uses the arXiv API (free, no key required).
Returns abstracts of open-access preprints.

API docs: https://arxiv.org/help/api/
Endpoint: https://export.arxiv.org/api/query?search_query=...&max_results=n

Note: arXiv API is XML (Atom feed). We parse it with the stdlib xml.etree.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
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

_CONNECTOR = "arxiv"
_API_URL = "https://export.arxiv.org/api/query"
_RATE = RateLimiter(calls_per_second=0.34)   # arXiv asks max 3 req/s; we use ~0.34

_ATOM_NS = "http://www.w3.org/2005/Atom"
_ARXIV_NS = "http://arxiv.org/schemas/atom"


def _ns(tag: str) -> str:
    return f"{{{_ATOM_NS}}}{tag}"


def _extract_arxiv_id(entry_id: str) -> str:
    """Extract bare arXiv id from the full URL, e.g. http://arxiv.org/abs/2301.00001v1."""
    match = re.search(r"abs/([^v\s]+)", entry_id)
    return match.group(1) if match else entry_id


def _parse_entry(entry: ET.Element) -> Chunk | None:
    """Convert one Atom <entry> element to a Chunk."""
    # Title
    title_el = entry.find(_ns("title"))
    title = (title_el.text or "").strip().replace("\n", " ") if title_el is not None else ""
    if not title:
        return None

    # Abstract (summary)
    summary_el = entry.find(_ns("summary"))
    abstract = (summary_el.text or "").strip().replace("\n", " ") if summary_el is not None else ""
    if not abstract:
        return None

    # arXiv ID and landing URL
    id_el = entry.find(_ns("id"))
    raw_id = (id_el.text or "").strip() if id_el is not None else ""
    arxiv_id = _extract_arxiv_id(raw_id)
    url = f"https://arxiv.org/abs/{arxiv_id}"

    # DOI (arXiv may provide one)
    doi_el = entry.find(f"{{{_ARXIV_NS}}}doi")
    doi = (doi_el.text or "").strip() if (doi_el is not None and doi_el.text) else None

    # Authors
    authors: list[str] = []
    for author_el in entry.findall(_ns("author")):
        name_el = author_el.find(_ns("name"))
        if name_el is not None and name_el.text:
            authors.append(name_el.text.strip())

    # Published year
    published_el = entry.find(_ns("published"))
    year: int | None = None
    if published_el is not None and published_el.text:
        try:
            year = int(published_el.text[:4])
        except (ValueError, IndexError):
            pass

    # Venue
    journal_el = entry.find(f"{{{_ARXIV_NS}}}journal_ref")
    venue = (journal_el.text or "").strip() if (journal_el is not None and journal_el.text) else "arXiv"

    retrieved_at = datetime.now(timezone.utc).isoformat()

    return Chunk(
        id=make_chunk_id(_CONNECTOR, doi, title, year),
        text=abstract,
        title=title,
        authors=authors,
        year=year,
        venue=venue,
        doi=doi,
        url=url,
        origin="scholarly",
        retrieved_at=retrieved_at,
        content_hash=_sha256(abstract),
    )


def search(query: str, n: int = 5) -> list[Chunk]:
    """
    Search arXiv and return up to `n` Chunks.

    Uses arXiv all-field search. Returns abstract text exactly as fetched.

    Args:
        query: Free-text search query.
        n:     Maximum number of results to return.

    Returns:
        List of Chunk objects.
    """
    cached = cache_get(_CONNECTOR, query, n)
    if cached is not None:
        logger.debug("arXiv cache hit for %r (n=%d)", query, n)
        return [Chunk.from_dict(c) for c in cached]

    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": min(n, 25),
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    _RATE.wait()
    try:
        # arXiv API returns Atom XML (not JSON)
        import httpx as _httpx
        with _httpx.Client(
            timeout=_httpx.Timeout(10.0),
            headers={
                "User-Agent": (
                    "UNKNOWN-RAG/1.0 (academic research assistant; "
                    "contact: research@unknown.ai)"
                ),
                "Accept": "application/atom+xml, application/xml, */*",
            },
            follow_redirects=True,
        ) as client:
            resp = None
            import time as _time
            for attempt in range(1, 4):
                try:
                    resp = client.get(_API_URL, params=params)
                    resp.raise_for_status()
                    break
                except Exception as exc:
                    if attempt < 3:
                        _time.sleep(2 ** (attempt - 1))
                    else:
                        raise

        if resp is None:
            return []

        root = ET.fromstring(resp.text)
    except Exception as exc:
        from app.connectors._base import note_connector_failure
        note_connector_failure(type(exc).__name__)
        logger.warning("arXiv search failed for %r: %s", query, exc)
        return []

    entries = root.findall(_ns("entry"))
    chunks: list[Chunk] = []
    for entry in entries[:n]:
        chunk = _parse_entry(entry)
        if chunk:
            chunks.append(chunk)

    chunks = deduplicate(chunks)
    cache_put(_CONNECTOR, query, n, [c.to_dict() for c in chunks])
    return chunks
