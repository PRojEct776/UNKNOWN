"""
Generation evaluation metrics: unsupported claim rate, citation precision, abstention accuracy.
"""
from __future__ import annotations

import re
import unicodedata


def _normalize(text: str) -> str:
    """Normalize text for quote matching: NFKC unicode, collapsed whitespace, lowercase."""
    t = unicodedata.normalize("NFKC", str(text))
    t = re.sub(r"\s+", " ", t)
    return t.strip().lower()


def unsupported_claim_rate(
    sentences: list[dict],
    passages: dict[str, str] | None = None,
) -> float:
    """
    Fraction of sentences whose quote is NOT a substring of any cited passage.
    sentences: list of {text, source_ids, quote, passages: dict[id, text]}
    Returns 0.0 if all supported, 1.0 if none supported.
    """
    if not sentences:
        return 0.0

    unsupported_count = 0
    for s in sentences:
        quote = _normalize(s.get("quote", ""))
        if not quote:
            unsupported_count += 1
            continue

        s_passages = s.get("passages") or passages or {}
        source_ids = s.get("source_ids", [])
        if not source_ids:
            unsupported_count += 1
            continue

        supported = False
        for sid in source_ids:
            p_text = None
            if isinstance(s_passages, dict):
                p_text = s_passages.get(sid)
                if p_text is None:
                    p_text = s_passages.get(str(sid))
            elif isinstance(s_passages, list):
                if isinstance(sid, int) and 1 <= sid <= len(s_passages):
                    item = s_passages[sid - 1]
                    p_text = item.get("text") if isinstance(item, dict) else str(item)
                else:
                    for item in s_passages:
                        if isinstance(item, dict) and item.get("chunk_id") == str(sid):
                            p_text = item.get("text")
                            break

            if p_text is not None and quote in _normalize(p_text):
                supported = True
                break

        if not supported:
            unsupported_count += 1

    return unsupported_count / len(sentences)


def citation_precision(sentences: list[dict], retrieved_ids: set[str]) -> float:
    """
    Fraction of cited source_ids that actually appear in retrieved_ids.
    """
    retrieved_set = {str(x) for x in retrieved_ids}
    total_citations = 0
    valid_citations = 0

    for s in sentences:
        sids = s.get("source_ids", [])
        for sid in sids:
            total_citations += 1
            if str(sid) in retrieved_set:
                valid_citations += 1

    if total_citations == 0:
        return 1.0
    return valid_citations / total_citations


def abstention_accuracy(
    responses: list[dict],
    NOT_FOUND: str = "Not found in available sources.",
) -> float:
    """
    For unanswerable queries (label='unanswerable'), fraction that correctly
    return the NOT_FOUND string (or contain it).
    responses: list of {label: str, answer: str}
    """
    unans = [r for r in responses if r.get("label") == "unanswerable"]
    if not unans:
        unans = responses
    if not unans:
        return 0.0

    target = NOT_FOUND.strip().lower()
    correct = sum(
        1 for r in unans
        if target in str(r.get("answer", "")).strip().lower()
    )
    return correct / len(unans)
