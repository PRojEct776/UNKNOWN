"""Regression: exact identifiers must appear in the quoted document section."""
from app.rag.dual_retriever import (
    _build_doc_section,
    _build_summary,
    _query_focused_excerpt,
)

CHUNK_95 = (
    "UNKNOWN RAG test fixture \u2014 synthetic data Page 1 UNKNOWN \u2014 RAG Retrieval Test "
    "Document Purpose: a small, controlled document for testing document ingestion, "
    "chunking, keyword retrieval, semantic retrieval, hybrid ranking, context assembly, "
    "and answer grounding. Test-fixture note: The facts below are synthetic and created "
    "only for software testing. Do not treat them as real-world research findings. "
    "1. Project profile The fictional project is called Blue Lantern Pantry. Its goal is "
    "to monitor pantry supplies and warn a user when an item is running low. "
    "2. Exact facts for retrieval Field Synthetic value Project code BLP-204 Prototype "
    "location Lab Cedar, shelf 3 Controller ESP32-WROOM-32 Load-cell amplifier HX711 "
    "Low-stock threshold 250 grams Event collection pantry_events_v2 Notification retry "
    "limit 3 attempts Evaluation date 18 October 2026 Test batch identifier QZ-7319"
)
QUERY = "Find the exact project identifier BLP-204"
CHUNK = {"text": CHUNK_95, "document": "UNKNOWN_RAG_Test_Document.pdf", "page": 1, "chunk_id": "chunk_95"}


def test_identifier_appears_in_doc_section_and_summary():
    section = _build_doc_section([CHUNK], QUERY)
    assert "BLP-204" in section
    assert "UNKNOWN_RAG_Test_Document.pdf, p.1" in section
    assert "BLP-204" in _build_summary(section, None)


def test_excerpt_is_verbatim_from_the_chunk():
    excerpt = _query_focused_excerpt(CHUNK_95, QUERY)
    core = excerpt.replace("\u2026", "").strip()
    assert core in CHUNK_95


def test_other_identifier_is_found():
    assert "QZ-7319" in _query_focused_excerpt(CHUNK_95, "What is the test batch identifier QZ-7319?")


def test_word_query_picks_matching_sentence():
    text = "Alpha is first. The retry limit is three attempts. Gamma is last."
    assert "retry limit" in _query_focused_excerpt(text, "What is the retry limit?")


def test_no_match_returns_empty_and_section_falls_back_to_first_sentences():
    assert _query_focused_excerpt("Alpha is first. Beta is second.", "zebra giraffe") == ""
    section = _build_doc_section([{"text": "Alpha is first. Beta is second. Gamma.", "document": "d.pdf", "page": 2, "chunk_id": "c1"}], "zebra giraffe")
    assert "Alpha is first. Beta is second." in section


def test_default_query_keeps_old_behaviour():
    section = _build_doc_section([{"text": "One. Two. Three.", "document": "d.pdf", "page": 1, "chunk_id": "c1"}])
    assert section.startswith("One. Two.")
