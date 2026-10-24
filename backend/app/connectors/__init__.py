"""
UNKNOWN – Web Connector Package

Exposes search(query, n) -> list[Chunk] for:
  - Wikipedia       (wikipedia.py)
  - OpenAlex        (openalex.py)
  - arXiv           (arxiv.py)
  - Crossref        (crossref.py)

Common infrastructure lives in _base.py (Chunk schema, HTTP client,
on-disk cache, rate limiter, deduplication).
"""
