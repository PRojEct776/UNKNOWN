"""
UNKNOWN X – Grounded Generation Layer (Task A1)

Rules enforced here:
  1. The LLM receives ONLY the numbered retrieved passages – no outside knowledge.
  2. Temperature is forced to 0.
  3. The LLM must return JSON: {"sentences": [{"text": "...", "source_ids": [...], "quote": "..."}]}
  4. Each sentence is accepted only when its `quote` is a normalised substring of at
     least one of the cited passages.
  5. If no sentence survives verification, the public constant NOT_FOUND is returned.
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

NOT_FOUND = "Not found in available sources."

# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

_SYSTEM_INSTRUCTIONS = """\
You are UNKNOWN AI, a strictly grounded academic research assistant.

RULES – follow every rule exactly:
1. You may ONLY use information from the numbered passages provided below.
2. Do NOT use any outside knowledge, training data, common sense, or inference.
3. Return ONLY valid JSON – no markdown, no commentary, no extra keys.
4. For every sentence in your answer, copy an exact verbatim excerpt from the
   passage(s) you used into the "quote" field.  The quote must appear word-for-word
   in one of the cited passages.
5. If the passages do not contain enough information to answer the question,
   return:  {"sentences": []}

Required JSON schema:
{
  "sentences": [
    {
      "text": "<your answer sentence>",
      "source_ids": [<list of passage ids you used, e.g. 1, 3>],
      "quote": "<verbatim excerpt from the passage(s) that supports this sentence>"
    }
  ]
}

Violation of any rule means your response will be discarded entirely."""


def build_grounded_prompt(query: str, passages: list[dict]) -> str:
    """
    Build a grounded JSON prompt.

    Args:
        query:    User question.
        passages: List of retrieval dicts (must have at least a "text" key).
                  Each dict may also have "document", "chunk_id", "page".

    Returns:
        A complete prompt string to send to the LLM.
    """
    if not passages:
        # No passages – return special sentinel so caller can short-circuit.
        return ""

    # Number passages starting from 1
    passage_blocks: list[str] = []
    for idx, p in enumerate(passages, start=1):
        text = p.get("text", "").strip()
        doc = p.get("document", "Unknown")
        page = p.get("page", "N/A")
        chunk_id = p.get("chunk_id", "N/A")
        passage_blocks.append(
            f"[Passage {idx}] document={doc} page={page} chunk_id={chunk_id}\n{text}"
        )

    passages_text = "\n\n---\n\n".join(passage_blocks)

    return (
        f"{_SYSTEM_INSTRUCTIONS}\n\n"
        f"=== RETRIEVED PASSAGES ===\n\n"
        f"{passages_text}\n\n"
        f"=== USER QUESTION ===\n\n"
        f"{query}\n\n"
        f"=== YOUR JSON ANSWER ==="
    )


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def _normalise(text: str) -> str:
    """
    Collapse whitespace and apply NFKC unicode normalisation so that quote
    matching is robust to minor formatting differences.
    """
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().casefold()


def _quote_verified(quote: str, passages: list[dict], source_ids: list[int]) -> bool:
    """
    Return True when the normalised `quote` is a substring of at least one
    normalised passage referenced by `source_ids`.

    `source_ids` are 1-based indices into `passages`.
    """
    if not quote or not quote.strip():
        return False

    normalised_quote = _normalise(quote)

    for sid in source_ids:
        idx = int(sid) - 1  # convert 1-based to 0-based
        if idx < 0 or idx >= len(passages):
            continue
        passage_text = passages[idx].get("text", "")
        if normalised_quote in _normalise(passage_text):
            return True

    return False


# ---------------------------------------------------------------------------
# JSON parsing helpers
# ---------------------------------------------------------------------------

def _extract_json_object(text: str) -> dict[str, Any]:
    """
    Extract the first JSON object from an LLM response string, tolerating
    markdown code fences.
    """
    cleaned = text.strip()

    # Strip markdown code fences (```json ... ```)
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned).strip()

    # Try direct parse
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # Fallback: extract first {...} block
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        raise ValueError("LLM did not return a valid JSON object.")

    obj = json.loads(match.group(0))
    if not isinstance(obj, dict):
        raise TypeError("LLM response was not a JSON object.")
    return obj


# ---------------------------------------------------------------------------
# Main verification entry point
# ---------------------------------------------------------------------------

def verify_and_filter_sentences(
    llm_response_text: str,
    passages: list[dict],
) -> list[dict[str, Any]]:
    """
    Parse the LLM JSON response and retain only sentences whose quote is a
    verified substring of the cited passages.

    Returns a list of dicts with keys: text, source_ids, quote.
    Returns an empty list if parsing fails or no sentences survive.
    """
    try:
        data = _extract_json_object(llm_response_text)
    except (ValueError, TypeError, json.JSONDecodeError):
        return []

    raw_sentences = data.get("sentences", [])
    if not isinstance(raw_sentences, list):
        return []

    verified: list[dict[str, Any]] = []
    for item in raw_sentences:
        if not isinstance(item, dict):
            continue

        text = str(item.get("text", "")).strip()
        quote = str(item.get("quote", "")).strip()
        source_ids = item.get("source_ids", [])

        if not isinstance(source_ids, list):
            source_ids = []

        if not text:
            continue

        if _quote_verified(quote, passages, source_ids):
            verified.append(
                {
                    "text": text,
                    "source_ids": source_ids,
                    "quote": quote,
                }
            )
        # else: silently drop – fake / bad quote

    return verified


# ---------------------------------------------------------------------------
# High-level generate function called by RAGService
# ---------------------------------------------------------------------------

def grounded_generate(
    llm_generate_fn,  # callable(prompt: str, temperature: float) -> str
    query: str,
    passages: list[dict],
) -> tuple[str, list[dict[str, Any]]]:
    """
    Run the full grounded-generation pipeline:
      1. Build a passage-only prompt (temperature 0).
      2. Call `llm_generate_fn` with that prompt at temperature 0.
      3. Verify quotes.
      4. Return (answer_text, verified_sentences).

    `answer_text` is either a prose answer assembled from verified sentences
    or NOT_FOUND.

    Args:
        llm_generate_fn: A callable that accepts (prompt, temperature=0.0)
                         and returns a raw string from the LLM.
        query:           The user question.
        passages:        Retrieved passage dicts (must contain "text").

    Returns:
        (answer_text, verified_sentences)
    """
    if not passages:
        return NOT_FOUND, []

    prompt = build_grounded_prompt(query, passages)

    if not prompt:
        return NOT_FOUND, []

    raw_text: str = llm_generate_fn(prompt, temperature=0.0)

    verified = verify_and_filter_sentences(raw_text, passages)

    if not verified:
        return NOT_FOUND, []

    # Assemble prose answer from verified sentences
    answer = " ".join(s["text"] for s in verified)
    return answer, verified
