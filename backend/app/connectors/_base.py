"""
UNKNOWN – Connector Base Infrastructure

Provides:
  Chunk              – canonical data model
  ConnectorHTTP      – httpx client with 10 s timeout, 3 retries, backoff, User-Agent
  DiskCache          – on-disk JSON cache with 24-hour TTL
  RateLimiter        – token-bucket rate limiter (per-connector)
  deduplicate        – remove near-duplicates by DOI then title similarity
"""

from __future__ import annotations

import difflib
import hashlib
import json
import threading
import time
import unicodedata
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx

from app.rag.config import settings
from app.rag.logger import logger

# ---------------------------------------------------------------------------
# Chunk schema
# ---------------------------------------------------------------------------

@dataclass
class Chunk:
    """Canonical unit returned by every connector."""

    id: str                         # connector-prefix + hash of (doi or title+year)
    text: str                       # abstract or open-access body text (as fetched)
    title: str
    authors: list[str]
    year: int | None
    venue: str | None               # journal / conference / repo name
    doi: str | None
    url: str                        # canonical landing page URL (not a PDF link)
    origin: str                     # "web" | "scholarly"
    retrieved_at: str               # ISO 8601 UTC
    content_hash: str               # SHA-256 of text

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Chunk":
        return cls(**d)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_chunk_id(prefix: str, doi: str | None, title: str, year: int | None) -> str:
    """Stable ID: prefer DOI, fall back to normalised title+year."""
    if doi and doi.strip():
        key = doi.strip().lower()
    else:
        norm = unicodedata.normalize("NFKC", title).lower().strip()
        key = f"{norm}_{year}"
    return f"{prefix}:{_sha256(key)[:16]}"


# ---------------------------------------------------------------------------
# HTTP client with retry + backoff
# ---------------------------------------------------------------------------

_USER_AGENT = (
    "UNKNOWN-RAG/1.0 (academic research assistant; "
    "contact: research@unknown.ai)"
)

_TRANSPORT = httpx.HTTPTransport(retries=0)  # we handle retries manually


def _build_client() -> httpx.Client:
    return httpx.Client(
        timeout=httpx.Timeout(10.0),
        headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
        follow_redirects=True,
    )


def http_get_with_retry(
    url: str,
    params: dict[str, Any] | None = None,
    extra_headers: dict[str, str] | None = None,
    max_retries: int = 3,
    backoff_base: float = 1.0,
) -> httpx.Response:
    """
    GET `url` with up to `max_retries` attempts, exponential backoff,
    polite User-Agent, and a 10-second timeout.

    Raises httpx.HTTPError on total failure.
    """
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            with _build_client() as client:
                resp = client.get(url, params=params, headers=extra_headers or {})
                resp.raise_for_status()
                return resp
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            last_exc = exc
            wait = backoff_base * (2 ** (attempt - 1))
            logger.warning(
                "Connector HTTP attempt %d/%d failed for %s: %s – retrying in %.1fs",
                attempt, max_retries, url, exc, wait,
            )
            if attempt < max_retries:
                time.sleep(wait)

    raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# On-disk cache (24-hour TTL)
# ---------------------------------------------------------------------------

_CACHE_DIR = settings.CACHE_DIR / "connectors"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)
_CACHE_TTL_S = 24 * 3600  # 24 hours

_cache_lock = threading.Lock()


def _cache_key(connector: str, query: str, n: int) -> str:
    raw = f"{connector}|{query.lower().strip()}|{n}"
    return hashlib.md5(raw.encode()).hexdigest()


def cache_get(connector: str, query: str, n: int) -> list[dict] | None:
    """Return cached result list or None if missing / expired."""
    key = _cache_key(connector, query, n)
    path = _CACHE_DIR / f"{key}.json"
    with _cache_lock:
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text("utf-8"))
            stored_at = payload.get("stored_at", 0)
            if time.time() - stored_at > _CACHE_TTL_S:
                path.unlink(missing_ok=True)
                return None
            return payload.get("chunks", [])
        except Exception:
            return None


def cache_put(connector: str, query: str, n: int, chunks: list[dict]) -> None:
    """Persist `chunks` to disk."""
    key = _cache_key(connector, query, n)
    path = _CACHE_DIR / f"{key}.json"
    payload = {"stored_at": time.time(), "chunks": chunks}
    with _cache_lock:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")


# ---------------------------------------------------------------------------
# Rate limiter (token-bucket, per-connector singleton)
# ---------------------------------------------------------------------------

class RateLimiter:
    """
    Token-bucket rate limiter.

    Args:
        calls_per_second: maximum sustained call rate.
    """

    def __init__(self, calls_per_second: float = 1.0) -> None:
        self._interval = 1.0 / calls_per_second
        self._last_call: float = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        """Block until a call is allowed, then mark the slot as used."""
        with self._lock:
            now = time.monotonic()
            gap = self._interval - (now - self._last_call)
            if gap > 0:
                time.sleep(gap)
            self._last_call = time.monotonic()


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _norm_title(title: str) -> str:
    t = unicodedata.normalize("NFKC", title).lower()
    # remove common filler words and punctuation for fuzzy compare
    import re
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    return " ".join(t.split())


def deduplicate(chunks: list[Chunk], title_sim_threshold: float = 0.85) -> list[Chunk]:
    """
    Remove near-duplicate Chunks.

    Deduplication order:
      1. Exact DOI match (keep first occurrence).
      2. Title similarity >= threshold (SequenceMatcher ratio).
    """
    seen_dois: set[str] = set()
    seen_titles: list[str] = []
    result: list[Chunk] = []

    for chunk in chunks:
        # --- DOI dedupe ---
        if chunk.doi and chunk.doi.strip():
            doi_key = chunk.doi.strip().lower()
            if doi_key in seen_dois:
                continue
            seen_dois.add(doi_key)

        # --- Title fuzzy dedupe ---
        nt = _norm_title(chunk.title)
        is_dup = False
        for existing_t in seen_titles:
            ratio = difflib.SequenceMatcher(None, nt, existing_t).ratio()
            if ratio >= title_sim_threshold:
                is_dup = True
                break
        if is_dup:
            continue

        seen_titles.append(nt)
        result.append(chunk)

    return result
