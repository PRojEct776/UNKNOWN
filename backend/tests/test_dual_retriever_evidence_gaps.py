"""Evidence-quality notes in /answer gaps."""

from __future__ import annotations

from app.rag.dual_retriever import _evidence_gaps

QUERY = "quantum entanglement thresholds"


def test_nothing_retrieved_is_reported():
    gaps = _evidence_gaps([], [], QUERY)
    assert gaps == ["No evidence was retrieved for this query."]


def test_matching_doc_passage_adds_no_note():
    doc = [{"text": "Quantum entanglement thresholds were measured in 2021."}]
    assert _evidence_gaps(doc, [], QUERY) == []


def test_matching_web_passage_adds_no_note():
    web = [{"text": "Entanglement thresholds depend on the quantum channel."}]
    assert _evidence_gaps([], web, QUERY) == []


def test_identifier_match_adds_no_note():
    doc = [{"text": "The release is tracked as project identifier BLP-204 in the plan."}]
    assert _evidence_gaps(doc, [], "Find the exact project identifier BLP-204") == []


def test_unrelated_passages_trigger_warning():
    doc = [{"text": "The weather is mild in spring."}]
    web = [{"text": "Bread is baked in ovens."}]
    gaps = _evidence_gaps(doc, web, QUERY)
    assert len(gaps) == 1
    assert "shares terms" in gaps[0]
