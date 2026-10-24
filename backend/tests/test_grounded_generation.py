"""
Tests for Task A1 – Grounded Generation.

ACCEPT criteria:
  1. Unanswerable query returns NOT_FOUND.
  2. A sentence with a fake quote is silently dropped.
  3. Across 20 sample queries zero sentences lack a verified quote.
"""

from __future__ import annotations

import json

import pytest

from app.rag.grounded_generation import (
    NOT_FOUND,
    _normalise,
    _quote_verified,
    build_grounded_prompt,
    grounded_generate,
    verify_and_filter_sentences,
)


# ---------------------------------------------------------------------------
# Unit: normalise helper
# ---------------------------------------------------------------------------

def test_normalise_collapses_whitespace():
    assert _normalise("hello   world") == "hello world"


def test_normalise_casefolds():
    assert _normalise("DNA Storage") == "dna storage"


# ---------------------------------------------------------------------------
# Unit: quote verification
# ---------------------------------------------------------------------------

PASSAGES = [
    {"text": "Microbial DNA can store large amounts of data reliably."},
    {"text": "FAISS is a library for efficient similarity search."},
]


def test_quote_verified_exact_match():
    assert _quote_verified("Microbial DNA can store", PASSAGES, [1]) is True


def test_quote_verified_case_insensitive():
    assert _quote_verified("microbial dna CAN STORE", PASSAGES, [1]) is True


def test_quote_verified_wrong_passage():
    # Source 1 (Microbial DNA) does NOT contain the FAISS text
    assert _quote_verified("FAISS is a library", PASSAGES, [1]) is False


def test_quote_verified_correct_passage():
    assert _quote_verified("FAISS is a library", PASSAGES, [2]) is True


def test_quote_verified_empty_quote():
    assert _quote_verified("", PASSAGES, [1]) is False


def test_quote_verified_out_of_range_source_id():
    assert _quote_verified("FAISS is a library", PASSAGES, [99]) is False


# ---------------------------------------------------------------------------
# Unit: verify_and_filter_sentences
# ---------------------------------------------------------------------------

def _make_llm_json(sentences: list[dict]) -> str:
    return json.dumps({"sentences": sentences})


def test_all_valid_sentences_pass():
    llm_output = _make_llm_json([
        {
            "text": "DNA storage is reliable.",
            "source_ids": [1],
            "quote": "Microbial DNA can store large amounts of data reliably.",
        },
        {
            "text": "FAISS enables fast search.",
            "source_ids": [2],
            "quote": "FAISS is a library for efficient similarity search.",
        },
    ])
    verified = verify_and_filter_sentences(llm_output, PASSAGES)
    assert len(verified) == 2


def test_fake_quote_is_dropped():
    """A sentence with a fabricated quote that does not appear in any passage
    must be silently dropped."""
    llm_output = _make_llm_json([
        {
            "text": "DNA can encode petabytes.",
            "source_ids": [1],
            "quote": "DNA encodes petabytes per gram of synthetic biology.",  # FAKE
        },
        {
            "text": "FAISS enables fast search.",
            "source_ids": [2],
            "quote": "FAISS is a library for efficient similarity search.",
        },
    ])
    verified = verify_and_filter_sentences(llm_output, PASSAGES)
    # Fake sentence dropped; real sentence kept
    assert len(verified) == 1
    assert "FAISS" in verified[0]["text"]


def test_all_fake_quotes_returns_empty():
    llm_output = _make_llm_json([
        {
            "text": "Quantum computers solve NP-hard problems instantly.",
            "source_ids": [1],
            "quote": "Quantum supremacy was achieved in 2019.",  # FAKE
        },
    ])
    verified = verify_and_filter_sentences(llm_output, PASSAGES)
    assert verified == []


def test_malformed_json_returns_empty():
    verified = verify_and_filter_sentences("not json at all", PASSAGES)
    assert verified == []


def test_missing_sentences_key_returns_empty():
    verified = verify_and_filter_sentences(json.dumps({"answer": "hello"}), PASSAGES)
    assert verified == []


def test_markdown_fenced_json_is_accepted():
    llm_output = (
        "```json\n"
        + json.dumps({
            "sentences": [{
                "text": "FAISS enables fast search.",
                "source_ids": [2],
                "quote": "FAISS is a library for efficient similarity search.",
            }]
        })
        + "\n```"
    )
    verified = verify_and_filter_sentences(llm_output, PASSAGES)
    assert len(verified) == 1


# ---------------------------------------------------------------------------
# Unit: build_grounded_prompt
# ---------------------------------------------------------------------------

def test_prompt_contains_passage_text():
    prompt = build_grounded_prompt("What is FAISS?", PASSAGES)
    assert "FAISS is a library" in prompt


def test_prompt_contains_query():
    prompt = build_grounded_prompt("What is FAISS?", PASSAGES)
    assert "What is FAISS?" in prompt


def test_prompt_forbids_outside_knowledge():
    prompt = build_grounded_prompt("What is FAISS?", PASSAGES)
    assert "outside knowledge" in prompt.lower() or "outside" in prompt.lower()


def test_prompt_empty_passages_returns_empty_string():
    prompt = build_grounded_prompt("anything", [])
    assert prompt == ""


# ---------------------------------------------------------------------------
# ACCEPT 1: Unanswerable question returns NOT_FOUND
# ---------------------------------------------------------------------------

def test_unanswerable_returns_not_found():
    """When LLM returns empty sentences (nothing grounded), return NOT_FOUND."""

    def _mock_llm(prompt: str, temperature: float = 0.0) -> str:  # noqa: ARG001
        return json.dumps({"sentences": []})  # LLM admits it cannot answer

    answer, verified = grounded_generate(_mock_llm, "What is the capital of the moon?", PASSAGES)
    assert answer == NOT_FOUND
    assert verified == []


def test_no_passages_returns_not_found():
    def _mock_llm(prompt: str, temperature: float = 0.0) -> str:
        return json.dumps({"sentences": []})

    answer, _ = grounded_generate(_mock_llm, "anything?", passages=[])
    assert answer == NOT_FOUND


# ---------------------------------------------------------------------------
# ACCEPT 2: Sentence with a fake quote is dropped
# ---------------------------------------------------------------------------

def test_fake_quote_sentence_dropped_in_pipeline():
    """grounded_generate must drop sentences whose quotes are fabricated."""

    def _mock_llm(prompt: str, temperature: float = 0.0) -> str:  # noqa: ARG001
        return json.dumps({
            "sentences": [
                {
                    "text": "Completely made-up claim.",
                    "source_ids": [1],
                    "quote": "This phrase does not exist in any passage.",  # FAKE
                },
                {
                    "text": "FAISS is efficient.",
                    "source_ids": [2],
                    "quote": "FAISS is a library for efficient similarity search.",
                },
            ]
        })

    answer, verified = grounded_generate(_mock_llm, "Tell me about FAISS.", PASSAGES)
    assert len(verified) == 1
    assert "FAISS" in verified[0]["text"]
    # The fabricated sentence must NOT appear in the answer
    assert "Completely made-up claim" not in answer


# ---------------------------------------------------------------------------
# ACCEPT 3: 20 sample queries – zero sentences lack a verified quote
# ---------------------------------------------------------------------------

SAMPLE_QUERIES_AND_PASSAGES = [
    # Each tuple: (query, passages, mock_llm_response)
    (
        f"Query {i}",
        [{"text": f"Evidence passage number {i} contains specific details about topic {i}."}],
        json.dumps({
            "sentences": [{
                "text": f"The evidence shows topic {i}.",
                "source_ids": [1],
                "quote": f"Evidence passage number {i} contains specific details about topic {i}.",
            }]
        }),
    )
    for i in range(1, 21)
]


@pytest.mark.parametrize("query,passages,llm_json", SAMPLE_QUERIES_AND_PASSAGES)
def test_20_queries_all_sentences_have_verified_quotes(query, passages, llm_json):
    """Across 20 sample queries, every sentence in the result must have a
    verified quote (none can be unverified or missing)."""

    def _mock_llm(prompt: str, temperature: float = 0.0) -> str:  # noqa: ARG001
        return llm_json

    answer, verified = grounded_generate(_mock_llm, query, passages)

    # If we got an answer, every sentence must have a non-empty verified quote
    if answer != NOT_FOUND:
        assert len(verified) > 0, f"Query '{query}': answer returned but no sentences."
        for sentence in verified:
            assert sentence.get("quote", "").strip(), (
                f"Sentence lacks a quote: {sentence['text']!r}"
            )
            # Re-verify the quote ourselves to be absolutely sure
            assert _quote_verified(
                sentence["quote"], passages, sentence["source_ids"]
            ), f"Quote not found in cited passage: {sentence['quote']!r}"
