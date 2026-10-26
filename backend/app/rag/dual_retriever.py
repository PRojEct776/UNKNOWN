"""
UNKNOWN X – Dual Retriever with Comparison Layer (Task A8)

Retrieves evidence from two separate channels:
  - Document channel: user-uploaded documents (respects scope; never calls connectors
    when scope is "document only")
  - Web channel: live connector search (Wikipedia, OpenAlex, arXiv, Crossref), fetched
    live in this request so retrieved_at is current.

Then for each sub-question it runs NLI between the best doc passage and the best web
passage and produces:
  - doc_section  – grounded paragraph with page/chunk citations
  - web_section  – grounded paragraph with live URLs
  - comparison[] – per-sub-question pairs labelled agree / disagree / not_addressed
                   each with both verbatim quotes

Summary is max 3 sentences.  Detail is the full concatenation.

Public API
----------
    DualRetriever(retriever, llm, connectors=None)
    result = dual_retrieve(query, document_names=..., web_only=False, doc_only=False)
    # returns DualResult
"""

from __future__ import annotations

import concurrent.futures
import os
import re
import textwrap
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Sequence

from app.rag.logger import logger

# ---------------------------------------------------------------------------
# Config (env-overridable)
# ---------------------------------------------------------------------------

DUAL_DOC_TOP_K: int = int(os.environ.get("DUAL_DOC_TOP_K", "8"))
DUAL_WEB_PER_CONNECTOR: int = int(os.environ.get("DUAL_WEB_PER_CONNECTOR", "3"))
DUAL_WEB_TIMEOUT_S: float = float(os.environ.get("DUAL_WEB_TIMEOUT_S", "12.0"))
DUAL_NLI_ENTAIL_THRESHOLD: float = float(os.environ.get("DUAL_NLI_ENTAIL_THRESHOLD", "0.55"))
DUAL_NLI_CONTRA_THRESHOLD: float = float(os.environ.get("DUAL_NLI_CONTRA_THRESHOLD", "0.45"))
DUAL_SUMMARY_MAX_SENTENCES: int = 3

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ComparisonPair:
    """NLI-labelled pair comparing a doc passage against a web passage."""

    sub_question: str                     # the (sub-)question this pair addresses
    label: str                            # "agree" | "disagree" | "not_addressed"
    doc_quote: str                        # verbatim excerpt from doc channel
    web_quote: str                        # verbatim excerpt from web channel
    doc_source: str                       # document name + page/chunk
    web_source: str                       # URL from web channel
    nli_entail: float = 0.0
    nli_contra: float = 0.0


@dataclass
class DualResult:
    """Full output of a dual-retrieve call."""

    query: str
    doc_section: str | None               # grounded doc answer (with page/chunk)
    web_section: str | None               # grounded web answer (with URL)
    comparison: list[ComparisonPair] = field(default_factory=list)
    summary: str = ""                     # max 3 sentences
    detail: str = ""                      # full answer text
    doc_sources: list[dict] = field(default_factory=list)
    web_sources: list[dict] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Pure-Python NLI (keyword overlap fallback – no transformer required)
# ---------------------------------------------------------------------------

def _normalise_text(text: str) -> str:
    """Lowercase + NFKC + collapse whitespace."""
    text = unicodedata.normalize("NFKC", text).lower()
    return " ".join(text.split())


# Contradiction signal phrases
_CONTRA_PHRASES = frozenset([
    "however", "but", "although", "whereas", "while", "contrary",
    "despite", "instead", "unlike", "in contrast", "on the other hand",
    "not", "never", "neither", "nor", "false", "incorrect", "wrong",
    "disputed", "retracted", "disagree", "challenge", "refute",
])

_AGREE_PHRASES = frozenset([
    "similarly", "likewise", "also", "moreover", "furthermore",
    "consistent with", "confirms", "supports", "agrees",
    "in agreement", "corroborates", "replicates",
])


def _pure_python_nli(premise: str, hypothesis: str) -> dict[str, float]:
    """
    Pure-Python NLI approximation using keyword overlap and contradiction signals.

    Returns dict with keys: entailment, neutral, contradiction in [0, 1].
    """
    p_norm = _normalise_text(premise)
    h_norm = _normalise_text(hypothesis)

    p_tokens = set(re.findall(r"\b\w+\b", p_norm))
    h_tokens = set(re.findall(r"\b\w+\b", h_norm))

    # Remove stop words
    stops = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
              "being", "have", "has", "had", "do", "does", "did", "will",
              "would", "could", "should", "may", "might", "of", "in", "on",
              "at", "to", "for", "with", "by", "from", "this", "that",
              "and", "or", "but", "if", "as", "it", "its", "not"}
    p_tokens -= stops
    h_tokens -= stops

    if not h_tokens:
        return {"entailment": 0.15, "neutral": 0.80, "contradiction": 0.05}

    overlap = p_tokens & h_tokens
    overlap_ratio = len(overlap) / len(h_tokens)

    # Boost if agreeing phrases appear in premise
    agree_boost = 0.1 if any(ph in p_norm for ph in _AGREE_PHRASES) else 0.0
    # Contradiction penalty if contradiction signals appear in premise
    contra_signal = any(ph in p_norm for ph in _CONTRA_PHRASES)

    if contra_signal and overlap_ratio < 0.25:
        contradiction = min(0.80, 0.30 + (1.0 - overlap_ratio) * 0.4)
        entailment = max(0.05, overlap_ratio * 0.3)
        neutral = max(0.05, 1.0 - entailment - contradiction)
    elif overlap_ratio >= 0.55:
        entailment = min(0.85, overlap_ratio + agree_boost)
        contradiction = max(0.03, 0.15 - overlap_ratio * 0.1)
        neutral = max(0.05, 1.0 - entailment - contradiction)
    else:
        entailment = max(0.10, overlap_ratio * 0.7 + agree_boost)
        contradiction = max(0.03, 0.15 * (1.0 - overlap_ratio))
        neutral = max(0.05, 1.0 - entailment - contradiction)

    total = entailment + neutral + contradiction
    return {
        "entailment": round(entailment / total, 4),
        "neutral": round(neutral / total, 4),
        "contradiction": round(contradiction / total, 4),
    }


def classify_nli_pair(
    premise: str,
    hypothesis: str,
    nli_fn: Callable[[str, str], dict[str, float]] | None = None,
    entail_threshold: float = DUAL_NLI_ENTAIL_THRESHOLD,
    contra_threshold: float = DUAL_NLI_CONTRA_THRESHOLD,
) -> tuple[str, float, float]:
    """
    Run NLI and return (label, entail_score, contra_score).

    label is one of: "agree" | "disagree" | "not_addressed"
    """
    if nli_fn is not None:
        fn = nli_fn
    else:
        try:
            from app.rag.atomic_claims import classify_nli
            fn = classify_nli
        except Exception:
            fn = _pure_python_nli
    try:
        scores = fn(premise, hypothesis)
    except Exception as exc:
        logger.warning("NLI failed, falling back to pure-Python: %s", exc)
        scores = _pure_python_nli(premise, hypothesis)

    entail = float(scores.get("entailment", 0.0))
    contra = float(scores.get("contradiction", 0.0))

    if contra >= contra_threshold:
        label = "disagree"
    elif entail >= entail_threshold:
        label = "agree"
    else:
        label = "not_addressed"

    return label, entail, contra


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def _first_n_sentences(text: str, n: int) -> str:
    """Return up to n sentences from text (heuristic sentence splitter)."""
    if not text:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(sentences[:n]).strip()


_EXCERPT_STOPWORDS = frozenset({
    "the", "and", "for", "are", "was", "what", "which", "who", "how", "does",
    "did", "with", "from", "that", "this", "find", "exact", "tell", "give",
    "show", "about", "into", "has", "have", "can", "you", "your", "its",
})


def _query_focused_excerpt(text: str, query: str, max_chars: int = 320) -> str:
    """
    Return the part of ``text`` that best matches ``query``.

    Identifier-like query tokens (containing a digit, hyphen or underscore,
    e.g. BLP-204) win: the excerpt is a verbatim window around their first
    occurrence. Otherwise the sentence with the most query-word overlap is
    used. With no match at all, returns "" so callers can fall back.
    """
    text = (text or "").strip()
    if not text:
        return ""
    tokens = [tk.strip("-") for tk in re.findall(r"\w[\w\-]*", query or "")]
    identifiers = [
        tk for tk in tokens
        if len(tk) >= 3 and (any(ch.isdigit() for ch in tk) or "-" in tk or "_" in tk)
    ]
    low = text.lower()
    for ident in identifiers:
        idx = low.find(ident.lower())
        if idx < 0:
            continue
        start = max(0, idx - 80)
        end = min(len(text), idx + len(ident) + 160)
        if start > 0:
            sp = text.find(" ", start)
            if 0 <= sp < idx:
                start = sp + 1
        if end < len(text):
            sp = text.rfind(" ", idx + len(ident), end)
            if sp > idx:
                end = sp
        excerpt = text[start:end].strip()
        if start > 0:
            excerpt = "\u2026 " + excerpt
        if end < len(text):
            excerpt = excerpt + " \u2026"
        return excerpt
    keywords = [
        tk.lower() for tk in tokens
        if len(tk) > 2 and tk.lower() not in _EXCERPT_STOPWORDS
    ]
    if not keywords:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    best_i, best_score = -1, 0
    for i, sent in enumerate(sentences):
        s = sent.lower()
        score = sum(1 for kw in set(keywords) if kw in s)
        if score > best_score:
            best_i, best_score = i, score
    if best_score == 0:
        return ""
    return _extract_verbatim_quote(" ".join(sentences[best_i:best_i + 2]), max_chars)


def _best_passage_text(chunks: list[dict]) -> tuple[str, str, str]:
    """
    Return (text, citation_label, url) for the highest-scoring chunk.

    citation_label is e.g. "attention.pdf p.3 §chunk_42"
    """
    if not chunks:
        return "", "", ""
    best = chunks[0]
    text = str(best.get("text", "")).strip()
    doc = best.get("document", best.get("title", "Unknown"))
    page = best.get("page", "N/A")
    chunk_id = best.get("chunk_id", "N/A")
    citation = f"{doc} p.{page} §{chunk_id}"
    url = best.get("url", "") or ""
    return text, citation, url


def _extract_verbatim_quote(text: str, max_chars: int = 500) -> str:
    """Return a verbatim excerpt from text, ending cleanly on a sentence or word boundary."""
    if not text:
        return ""
    text = text.strip()
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    for sep in [". ", "! ", "? ", ".\n", "!\n", "?\n"]:
        idx = truncated.rfind(sep)
        if idx > 50:
            return truncated[: idx + 1].strip()
    last_space = truncated.rfind(" ")
    if last_space > 50:
        return truncated[:last_space].strip()
    return truncated.strip()


# ---------------------------------------------------------------------------
# Connector fan-out (live web fetch in this request)
# ---------------------------------------------------------------------------

def _load_connectors(names: list[str] | None = None) -> list[Any]:
    """
    Dynamically load connector modules.  Missing optional connectors are skipped
    so one failing connector never breaks the entire request.
    """
    all_names = names or ["wikipedia", "openalex", "arxiv", "crossref"]
    loaded = []
    for name in all_names:
        try:
            import importlib
            mod = importlib.import_module(f"app.connectors.{name}")
            loaded.append(mod)
        except Exception as exc:
            logger.warning("Connector %r failed to load (skipped): %s", name, exc)
    return loaded


_CONNECTOR_LABELS = {
    "wikipedia": "Wikipedia",
    "openalex": "OpenAlex",
    "arxiv": "arXiv",
    "crossref": "Crossref",
}


def _connector_key(connector_mod: Any) -> str:
    """Short connector name, e.g. arxiv for app.connectors.arxiv."""
    return str(getattr(connector_mod, "__name__", connector_mod)).rsplit(".", 1)[-1]


def _fetch_web_chunks(
    query: str,
    n_per: int = DUAL_WEB_PER_CONNECTOR,
    connector_names: list[str] | None = None,
    timeout_s: float = DUAL_WEB_TIMEOUT_S,
) -> tuple[list[dict], list[dict]]:
    """
    Fan out across connectors in parallel threads.  Results are stamped with
    retrieved_at = NOW (live fetch in this request).

    Returns (chunks, statuses).  chunks are plain dicts compatible with the
    Chunk.to_dict() schema.  statuses has one entry per requested connector:
    {"connector", "outcome", "count", "detail"} where outcome is one of
    ok, no_results, error, timeout, not_loaded.
    """
    requested = list(connector_names or ["wikipedia", "openalex", "arxiv", "crossref"])
    connectors = _load_connectors(connector_names)
    loaded_keys = {_connector_key(m) for m in connectors}
    statuses: list[dict] = [
        {"connector": name, "outcome": "not_loaded", "count": 0, "detail": ""}
        for name in requested
        if name not in loaded_keys
    ]
    if not connectors:
        logger.warning("No web connectors available; web_section will be empty.")
        return [], statuses

    fetched_now = datetime.now(timezone.utc).isoformat()
    all_chunks: list[dict] = []

    def _fetch_one(connector_mod: Any) -> tuple[list[dict], str | None]:
        from app.connectors._base import take_connector_failure

        take_connector_failure()  # clear any stale flag left on this pooled thread
        try:
            chunks = connector_mod.search(query, n_per)
            result = []
            for c in chunks:
                d = c.to_dict() if hasattr(c, "to_dict") else dict(c)
                d["retrieved_at"] = fetched_now   # overwrite with live timestamp
                d["origin"] = d.get("origin", "web")
                result.append(d)
            return result, take_connector_failure()
        except Exception as exc:
            logger.warning(
                "Connector %r.search() failed (skipped): %s",
                getattr(connector_mod, "__name__", connector_mod),
                exc,
            )
            take_connector_failure()
            return [], type(exc).__name__

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=len(connectors))
    try:
        futures = {pool.submit(_fetch_one, m): m for m in connectors}
        done, _still_running = concurrent.futures.wait(futures, timeout=timeout_s)
        for fut, mod in futures.items():
            key = _connector_key(mod)
            if fut not in done:
                statuses.append({
                    "connector": key,
                    "outcome": "timeout",
                    "count": 0,
                    "detail": "no response within %gs" % timeout_s,
                })
                continue
            try:
                chunks, failure = fut.result()
            except Exception as exc:
                chunks, failure = [], type(exc).__name__
            all_chunks.extend(chunks)
            if failure:
                outcome = "error"
            elif chunks:
                outcome = "ok"
            else:
                outcome = "no_results"
            statuses.append({
                "connector": key,
                "outcome": outcome,
                "count": len(chunks),
                "detail": failure or "",
            })
    except Exception as exc:
        logger.warning("Web connector fan-out failed: %s", exc)
    finally:
        # Never block the request on connectors that are still running.
        pool.shutdown(wait=False, cancel_futures=True)

    reported = {s["connector"] for s in statuses}
    for mod in connectors:
        key = _connector_key(mod)
        if key not in reported:
            statuses.append({"connector": key, "outcome": "error", "count": 0, "detail": "fan-out failed"})

    # Deduplicate by URL, then by title similarity (reuse connector _base logic)
    try:
        from app.connectors._base import deduplicate, Chunk
        chunk_objs = [Chunk.from_dict(d) for d in all_chunks if d.get("title")]
        chunk_objs = deduplicate(chunk_objs)
        all_chunks = [c.to_dict() for c in chunk_objs]
    except Exception as exc:
        logger.debug("Web chunk deduplication skipped: %s", exc)

    return all_chunks, statuses


def _web_gaps_from_statuses(statuses: list[dict]) -> list[str]:
    """Turn connector statuses into human-readable gap strings for /answer."""
    if not statuses:
        return ["Web retrieval was requested but no scholarly web source could be used."]

    def label(s: dict) -> str:
        return _CONNECTOR_LABELS.get(s["connector"], s["connector"])

    gaps: list[str] = []
    failed = [s for s in statuses if s["outcome"] in ("error", "timeout", "not_loaded")]
    reachable = [s for s in statuses if s["outcome"] in ("ok", "no_results")]

    for s in failed:
        if s["outcome"] == "timeout":
            reason = "timed out"
        elif s["outcome"] == "not_loaded":
            reason = "could not be loaded"
        elif s.get("detail"):
            reason = "failed (%s)" % s["detail"]
        else:
            reason = "failed"
        gaps.append("Web source unavailable: %s %s." % (label(s), reason))

    if not reachable:
        gaps.insert(0, "No scholarly web evidence was retrieved: every web source failed or timed out.")
    elif sum(s["count"] for s in statuses) == 0:
        gaps.append(
            "No scholarly web results found (checked: %s)."
            % ", ".join(label(s) for s in reachable)
        )
    return gaps


# ---------------------------------------------------------------------------
# Section builder
# ---------------------------------------------------------------------------

def _build_doc_section(doc_chunks: list[dict], query: str = "") -> str:
    """
    Render the doc_section string with page/chunk citations.

    Each sentence is labelled with its source.
    """
    if not doc_chunks:
        return ""
    parts: list[str] = []
    for c in doc_chunks[:3]:
        text = str(c.get("text", "")).strip()
        if not text:
            continue
        doc = c.get("document", "Unknown")
        page = c.get("page", "N/A")
        chunk_id = c.get("chunk_id", "N/A")
        excerpt = _query_focused_excerpt(text, query) or _first_n_sentences(text, 2)
        if excerpt:
            parts.append(f"{excerpt} [Source: {doc}, p.{page}, §{chunk_id}]")
    return "\n\n".join(parts)


def _build_web_section(web_chunks: list[dict], query: str = "") -> str:
    """
    Render the web_section string with live URL citations.
    """
    if not web_chunks:
        return ""
    parts: list[str] = []
    for c in web_chunks[:3]:
        text = str(c.get("text", "")).strip()
        if not text:
            continue
        title = c.get("title", c.get("document", "Unknown"))
        url = c.get("url", "")
        retrieved_at = c.get("retrieved_at", "")
        excerpt = _query_focused_excerpt(text, query) or _first_n_sentences(text, 2)
        if excerpt:
            citation = f"[{title}]({url})" if url else title
            if retrieved_at:
                citation += f" (fetched {retrieved_at[:10]})"
            parts.append(f"{excerpt} {citation}")
    return "\n\n".join(parts)


def _build_summary(doc_section: str | None, web_section: str | None) -> str:
    """Build a ≤3-sentence summary from doc and web sections."""
    combined = " ".join(filter(None, [doc_section, web_section]))
    return _first_n_sentences(combined, DUAL_SUMMARY_MAX_SENTENCES)


# ---------------------------------------------------------------------------
# Comparison matrix builder
# ---------------------------------------------------------------------------

def _build_comparison(
    sub_question: str,
    doc_chunks: list[dict],
    web_chunks: list[dict],
    nli_fn: Callable[[str, str], dict[str, float]] | None = None,
) -> ComparisonPair | None:
    """
    Compare the best doc passage against the best web passage for a given sub-question.

    Returns None if either channel has no usable text.
    """
    if not doc_chunks or not web_chunks:
        return None

    doc_text, doc_citation, _doc_url = _best_passage_text(doc_chunks)
    web_text, _web_citation, web_url = _best_passage_text(web_chunks)

    if not doc_text or not web_text:
        return None

    doc_quote = _extract_verbatim_quote(doc_text)
    web_quote = _extract_verbatim_quote(web_text)

    # Sentence-level alignment: check each doc sentence against web sentences
    doc_sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", doc_text.strip()) if s.strip()]
    web_sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", web_text.strip()) if s.strip()]

    best_entail = 0.0
    best_contra = 0.0
    best_agree_doc = doc_quote
    best_agree_web = web_quote
    best_contra_doc = doc_quote
    best_contra_web = web_quote

    for ds in (doc_sentences or [doc_text]):
        for ws in (web_sentences or [web_text]):
            _, entail, contra = classify_nli_pair(
                premise=ws,
                hypothesis=ds,
                nli_fn=nli_fn,
            )
            _, entail_rev, contra_rev = classify_nli_pair(
                premise=ds,
                hypothesis=ws,
                nli_fn=nli_fn,
            )
            eff_contra = max(contra, contra_rev)
            eff_entail = max(entail, entail_rev)

            if eff_entail >= DUAL_NLI_ENTAIL_THRESHOLD and eff_entail > best_entail:
                best_entail = eff_entail
                best_agree_doc = ds
                best_agree_web = ws
            if eff_contra >= DUAL_NLI_CONTRA_THRESHOLD and eff_contra > best_contra:
                best_contra = eff_contra
                best_contra_doc = ds
                best_contra_web = ws

    if best_entail >= DUAL_NLI_ENTAIL_THRESHOLD:
        best_label = "agree"
        best_doc_quote = best_agree_doc
        best_web_quote = best_agree_web
    elif best_contra >= DUAL_NLI_CONTRA_THRESHOLD:
        best_label = "disagree"
        best_doc_quote = best_contra_doc
        best_web_quote = best_contra_web
    else:
        _, p_entail, p_contra = classify_nli_pair(
            premise=web_text,
            hypothesis=doc_text,
            nli_fn=nli_fn,
        )
        if p_entail >= DUAL_NLI_ENTAIL_THRESHOLD:
            best_label = "agree"
            best_entail = p_entail
            best_contra = p_contra
            best_doc_quote = doc_quote
            best_web_quote = web_quote
        elif p_contra >= DUAL_NLI_CONTRA_THRESHOLD:
            best_label = "disagree"
            best_contra = p_contra
            best_entail = p_entail
            best_doc_quote = doc_quote
            best_web_quote = web_quote
        else:
            best_label = "not_addressed"
            best_doc_quote = doc_quote
            best_web_quote = web_quote

    web_source = web_url or web_chunks[0].get("title", "Unknown web source")

    return ComparisonPair(
        sub_question=sub_question,
        label=best_label,
        doc_quote=best_doc_quote,
        web_quote=best_web_quote,
        doc_source=doc_citation,
        web_source=web_source,
        nli_entail=best_entail,
        nli_contra=best_contra,
    )


# ---------------------------------------------------------------------------
# Main dual-retrieve entry point
# ---------------------------------------------------------------------------

class DualRetriever:
    """
    Orchestrates dual retrieval (document + web) for a query, respecting scope.

    Args:
        retriever:       Object with .search(query, top_k=N, document_names=...) -> list[dict].
        llm:             Optional LLM orchestrator (used for grounded generation).
        connector_names: Optional list of connector names to use.
                         Defaults to all four (wikipedia, openalex, arxiv, crossref).
        nli_fn:          Optional override for the NLI function.
    """

    def __init__(
        self,
        retriever: Any,
        llm: Any = None,
        connector_names: list[str] | None = None,
        nli_fn: Callable[[str, str], dict[str, float]] | None = None,
    ) -> None:
        self._retriever = retriever
        self._llm = llm
        self._connector_names = connector_names
        self._nli_fn = nli_fn

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def dual_retrieve(
        self,
        query: str,
        document_names: list[str] | None = None,
        doc_only: bool = False,
        scope: str | None = None,
        sub_questions: list[str] | None = None,
        top_k: int = DUAL_DOC_TOP_K,
        web_n_per: int = DUAL_WEB_PER_CONNECTOR,
    ) -> DualResult:
        """
        Retrieve from documents and (unless doc_only) from web connectors.

        Args:
            query:          The user query.
            document_names: Scope list.  When provided, only these docs are searched.
                            When None, all authorized docs are searched.
            doc_only:       If True, skip all connector/web retrieval (scope enforcement).
            sub_questions:  Optional list of sub-questions for per-question comparison.
                            If None, the main query is used as the single sub-question.
            top_k:          Number of doc chunks to retrieve.
            web_n_per:      Number of web results per connector.

        Returns:
            DualResult
        """
        if not query or not query.strip():
            raise ValueError("query must not be empty")

        if scope and "document only" in scope.lower():
            doc_only = True

        # 1. Document retrieval (always)
        doc_chunks = self._retrieve_doc(query, document_names, top_k)
        logger.info(
            "DualRetriever: %d doc chunks retrieved for %r", len(doc_chunks), query[:60]
        )

        # 2. Web retrieval (unless doc_only)
        web_chunks: list[dict] = []
        web_gaps: list[str] = []
        if not doc_only:
            web_chunks, web_statuses = _fetch_web_chunks(
                query,
                n_per=web_n_per,
                connector_names=self._connector_names,
            )
            web_gaps = _web_gaps_from_statuses(web_statuses)
            logger.info(
                "DualRetriever: %d web chunks retrieved for %r", len(web_chunks), query[:60]
            )
        else:
            logger.info("DualRetriever: doc_only=True – web connectors not called")

        # 3. Build sections
        doc_section = _build_doc_section(doc_chunks, query) or None
        web_section = _build_web_section(web_chunks, query) or None

        # 4. Build comparison pairs
        questions = sub_questions or [query]
        comparison: list[ComparisonPair] = []

        for sq in questions:
            # retrieve doc chunks for this sub-question
            sq_doc_chunks = self._retrieve_doc(sq, document_names, top_k) if sq != query else doc_chunks
            # retrieve web chunks for this sub-question (reuse main web results for perf)
            sq_web_chunks = web_chunks  # web chunks are query-level; OK to reuse

            pair = _build_comparison(sq, sq_doc_chunks, sq_web_chunks, nli_fn=self._nli_fn)
            if pair is not None:
                comparison.append(pair)

        # 5. Summary + detail
        summary = _build_summary(doc_section, web_section)
        detail = "\n\n".join(filter(None, [doc_section, web_section]))

        return DualResult(
            query=query,
            doc_section=doc_section,
            web_section=web_section,
            comparison=comparison,
            summary=summary,
            detail=detail,
            doc_sources=doc_chunks,
            web_sources=web_chunks,
            gaps=web_gaps,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _retrieve_doc(
        self, query: str, document_names: list[str] | None, top_k: int
    ) -> list[dict]:
        """Invoke the underlying retriever, catching all errors gracefully."""
        try:
            kwargs: dict[str, Any] = {"top_k": top_k}
            if document_names is not None:
                kwargs["document_names"] = document_names
            chunks = self._retriever.search(query, **kwargs)
            return list(chunks) if chunks else []
        except Exception as exc:
            logger.warning("DualRetriever doc retrieval failed (%s): %s", query[:40], exc)
            return []


# ---------------------------------------------------------------------------
# Convenience: chunk dict -> Source-compatible dict with connector metadata
# ---------------------------------------------------------------------------

def web_chunk_to_source_dict(chunk: dict) -> dict:
    """
    Convert a Chunk dict from a web connector into the shape expected by
    build_sources() so that web passages appear alongside doc passages in
    the canonical Source list.
    """
    return {
        "document": chunk.get("title", "Web Source"),
        "page": "N/A",
        "chunk_id": chunk.get("id", ""),
        "text": chunk.get("text", ""),
        "url": chunk.get("url", ""),
        "title": chunk.get("title"),
        "authors": chunk.get("authors", []),
        "year": chunk.get("year"),
        "venue": chunk.get("venue"),
        "doi": chunk.get("doi"),
        "origin": chunk.get("origin", "web"),
        "retrieved_at": chunk.get("retrieved_at"),
        "hybrid_score": 0.0,
        "bm25_score": 0.0,
        "faiss_score": 0.0,
    }
