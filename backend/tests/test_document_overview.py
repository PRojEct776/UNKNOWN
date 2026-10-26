import io
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app, rag_service
from app.rag.config import settings


@pytest.fixture
def client():
    return TestClient(app)


def test_document_overview_generation_and_caching_by_hash(client, monkeypatch):
    """
    ACCEPT criteria:
    1. Second open makes zero LLM calls (verified with call counter).
    2. Page references exist on every summary sentence.
    3. Title, authors, year, page count, language, 5-sentence summary, key topics,
       figure/table count with thumbnails, Document IQ, and 5 suggested questions are present.
    """
    doc_name = "Quantum_Cryogenic_Resonance_Overview_Test.txt"
    content = (
        "Quantum Cryogenic Resonant Trapping of Atomic Superconductors\n\n"
        "Abstract: We introduce cryogenic resonant trapping for superconducting qubits operating at 10 millikelvin. "
        "The experimental framework achieves 99.8% two-qubit gate fidelity across 64 physical resonators.\n\n"
        "Methodology: Cryogenic dilution refrigeration stabilizes thermal decoherence. "
        "Radio-frequency resonant pulses modulate flux-tunable transmon couplers without stray crosstalk.\n\n"
        "Results: Relaxation time T1 reached 520 microseconds, outperforming baseline planar topologies by 3.8x. "
        "Randomized benchmarking demonstrates average gate infidelity below 0.002 across all 128 microwave channels.\n\n"
        "Discussion: Scalable multiplexed readout enables real-time error syndrome measurement without heating. "
        "Future investigations will explore topological surface codes using 3D cavity integration."
    )

    try:
        # Ingest document
        payload = {"file": (doc_name, io.BytesIO(content.encode("utf-8")), "text/plain")}
        up_resp = client.post("/documents/upload", files=payload)
        assert up_resp.status_code == 200, up_resp.text

        # Track LLM calls with a call counter
        call_counter = {"grounded": 0, "standard": 0}

        real_generate_grounded = rag_service.llm.generate_grounded
        real_generate = rag_service.llm.generate

        def counted_generate_grounded(prompt, **kwargs):
            call_counter["grounded"] += 1
            return real_generate_grounded(prompt, **kwargs)

        def counted_generate(prompt, **kwargs):
            call_counter["standard"] += 1
            return real_generate(prompt, **kwargs)

        monkeypatch.setattr(rag_service.llm, "generate_grounded", counted_generate_grounded)
        monkeypatch.setattr(rag_service.llm, "generate", counted_generate)

        # Clear overview cache for this test document so we measure first open
        from app.services.document_service import load_document_json
        doc_json = load_document_json(doc_name)
        doc_hash = doc_json.get("document_hash")
        assert doc_hash, "Document must have a valid hash"

        overview_cache_file = settings.BASE_DIR / "app" / "data" / "cache" / "overviews" / f"{doc_hash}.json"
        if overview_cache_file.exists():
            overview_cache_file.unlink()

        # Reset call counter
        call_counter["grounded"] = 0
        call_counter["standard"] = 0

        # --- FIRST OPEN ---
        resp1 = client.get(f"/documents/{doc_name}/overview")
        assert resp1.status_code == 200, resp1.text
        data1 = resp1.json()

        # Check required fields
        assert data1["document_name"] == doc_name
        assert data1["document_hash"] == doc_hash
        assert data1["title"]
        assert isinstance(data1["authors"], list)
        assert data1["page_count"] >= 1
        assert data1["language"] == "en"
        assert "iq_score" in data1["document_iq"]

        # Check 5 suggested questions
        assert len(data1["suggested_questions"]) == 5
        for q in data1["suggested_questions"]:
            assert isinstance(q, str) and len(q) > 5

        # M1-05: every question carries provenance; text view matches the detailed view
        assert len(data1["question_details"]) == 5
        assert [q["text"] for q in data1["question_details"]] == data1["suggested_questions"]
        for q in data1["question_details"]:
            assert q["type"] in ("grounded", "exploratory")

        # M1-07: every section reports a status
        for name in (
            "metadata",
            "figures_tables",
            "key_topics",
            "document_iq",
            "retrieval",
            "summary",
            "suggested_questions",
        ):
            assert name in data1["section_status"], f"missing section status: {name}"
            assert data1["section_status"][name]["status"] in (
                "ok", "partial", "empty", "unavailable", "failed",
            )

        # M1-01 / OV-05: this text-only document has no figure/table captions,
        # so nothing may be invented: zero counts and empty collections.
        assert data1["figure_count"] == 0
        assert data1["table_count"] == 0
        assert data1["figures"] == []
        assert data1["tables"] == []

        # Check 5-sentence summary and PAGE REFERENCES on every summary sentence
        assert len(data1["summary_sentences"]) == 5, f"Expected 5 sentences, got {len(data1['summary_sentences'])}"
        for idx, sent in enumerate(data1["summary_sentences"]):
            assert sent["text"], f"Sentence {idx+1} must have non-empty text"
            assert sent["page_ref"], f"Sentence {idx+1} must carry a page reference"
            assert "Page" in sent["page_ref"], f"Sentence {idx+1} page_ref '{sent['page_ref']}' must specify page"
            assert sent["quote"], f"Sentence {idx+1} must carry a verified verbatim quote"
            assert sent["support"] in ("grounded", "extractive")

        # Verify LLM was called during first open
        first_open_calls = call_counter["grounded"] + call_counter["standard"]
        assert first_open_calls > 0, "First open should invoke LLM generation"

        # Verify cache file was written to disk
        assert overview_cache_file.exists(), f"Cache file {overview_cache_file} must exist after first open"

        # --- SECOND OPEN ---
        calls_before_second_open = call_counter["grounded"] + call_counter["standard"]

        resp2 = client.get(f"/documents/{doc_name}/overview")
        assert resp2.status_code == 200, resp2.text
        data2 = resp2.json()

        calls_after_second_open = call_counter["grounded"] + call_counter["standard"]

        # ACCEPT CRITERION: Second open makes ZERO LLM calls
        new_llm_calls = calls_after_second_open - calls_before_second_open
        assert new_llm_calls == 0, f"Second open made {new_llm_calls} LLM calls; expected exactly 0"
        assert data2["from_cache"] is True, "Second open must be served from cache"

        # Confirm identical data
        assert data2["title"] == data1["title"]
        assert len(data2["summary_sentences"]) == 5
        assert data2["suggested_questions"] == data1["suggested_questions"]

    finally:
        # Cleanup
        client.delete(f"/documents/{doc_name}?undo_window=0")


# ---------------------------------------------------------------------------
# Milestone 1 / Step 1 unit tests (pure functions, no server or LLM needed)
# ---------------------------------------------------------------------------

def test_m1_01_no_captions_means_no_figures_or_tables():
    from app.services.overview_service import _extract_figures_tables

    pages = [{"page": 1, "text": "Plain prose with no captions at all."}]
    figures, tables = _extract_figures_tables(pages)
    assert figures == []
    assert tables == []


def test_m1_01b_in_text_mentions_are_not_counted():
    from app.services.overview_service import _extract_figures_tables

    pages = [{"page": 1, "text": "As shown in Figure 3 and Table 2, results improve."}]
    figures, tables = _extract_figures_tables(pages)
    assert figures == []
    assert tables == []


def test_m1_02_real_captions_are_reported_with_real_pages():
    from app.services.overview_service import _extract_figures_tables

    pages = [
        {"page": 1, "text": "Intro text.\nFigure 1: System architecture overview\nMore text."},
        {"page": 4, "text": "Table 2. Benchmark results on dataset X\nFig. 3 - Loss curves\n"},
        {"page": 5, "text": "Figure 1: Duplicate caption that must be ignored"},
    ]
    figures, tables = _extract_figures_tables(pages)

    assert [f["label"] for f in figures] == ["Figure 1", "Figure 3"]
    assert figures[0]["page"] == 1
    assert figures[0]["caption"] == "System architecture overview"
    assert figures[1]["page"] == 4
    assert [t["label"] for t in tables] == ["Table 2"]
    assert tables[0]["page"] == 4
    assert tables[0]["caption"] == "Benchmark results on dataset X"
    assert all(f["thumbnail_is_placeholder"] for f in figures + tables)


def test_m1_03_summary_page_refs_come_from_passage_metadata():
    from app.services.overview_service import _generate_summary

    passages = [
        {"page": 3, "text": "Cryogenic dilution refrigeration stabilizes thermal decoherence in the device."},
        {"page": 7, "text": "Relaxation time T1 reached 520 microseconds across the tested resonators."},
    ]
    summary = _generate_summary(lambda prompt, temperature=0.0: "", "doc.txt", passages)

    assert summary, "Real passages should yield extractive sentences"
    pages_by_quote = {p["text"].split(".")[0]: str(p["page"]) for p in passages}
    for sent in summary:
        assert sent["support"] == "extractive"
        assert sent["quote"] in sent["text"] or sent["quote"] == sent["text"]
        expected = next(pg for key, pg in pages_by_quote.items() if sent["quote"].startswith(key))
        assert sent["page_ref"] == f"Page {expected}"


def test_m1_04_passages_without_real_page_produce_no_invented_citation():
    from app.services.overview_service import _generate_summary

    passages = [
        {"text": "This sentence is long enough but its passage has no page metadata at all."},
        {"page": "N/A", "text": "Another sufficiently long sentence whose page is explicitly unknown."},
    ]
    summary = _generate_summary(lambda prompt, temperature=0.0: "", "doc.txt", passages)
    assert summary == []


def test_m1_10_old_cache_entry_is_ignored(tmp_path, monkeypatch):
    import json as _json
    from app.services import overview_service as svc

    monkeypatch.setattr(svc, "OVERVIEW_CACHE_DIR", tmp_path)

    (tmp_path / "oldhash.json").write_text(
        _json.dumps({"title": "old", "figure_count": 1, "from_cache": True}), encoding="utf-8"
    )
    assert svc._load_cached("oldhash") is None

    svc._save_cache("newhash", {"schema_version": svc.OVERVIEW_SCHEMA_VERSION, "title": "new"})
    assert svc._load_cached("newhash")["title"] == "new"


# ---------------------------------------------------------------------------
# Milestone 1 / Step 2 unit tests: provenance, section status, partial failures
# ---------------------------------------------------------------------------

_GOOD_PASSAGES = [
    {"page": 2, "text": "Relaxation time T1 reached 520 microseconds across the tested resonators."},
]


def _patch_document(monkeypatch, tmp_path, doc_json=None, metadata=None, iq_boom=False):
    """Patch the document store and cache dir so generate_document_overview runs offline."""
    from app.services import document_service as ds
    from app.services import overview_service as svc

    monkeypatch.setattr(svc, "OVERVIEW_CACHE_DIR", tmp_path)
    doc = doc_json or {
        "document_hash": "h" * 64,
        "title": "Real Title",
        "authors": ["A. Author"],
        "year": 2024,
        "total_pages": 1,
        "pages": [{"page": 1, "text": "Figure 1: A real caption\nSome words here."}],
    }
    monkeypatch.setattr(ds, "load_document_json", lambda name: doc)

    def fake_metadata(name):
        if iq_boom:
            raise RuntimeError("metadata store offline")
        return metadata or {
            "document": name, "title": "Real Title", "pages": 1, "chunks": 2,
            "text_length": 6000, "embedding_status": True, "metadata_completeness": 1.0,
        }

    monkeypatch.setattr(ds, "build_document_metadata", fake_metadata)
    return doc


class _Retriever:
    def __init__(self, passages=None, error=None):
        self.passages, self.error = passages, error

    def search(self, *args, **kwargs):
        if self.error:
            raise RuntimeError(self.error)
        return self.passages


def test_m1_05_question_provenance_labels():
    from app.services.overview_service import _generate_suggested_question_details

    passages = [{"page": 1, "text": "Some passage text about resonators."}]

    # All five from the LLM -> all grounded
    llm_five = lambda prompt, temperature=0.3: (
        '["Q one about resonators?", "Q two about T1?", "Q three here?", "Q four here?", "Q five here?"]'
    )
    status = {}
    details = _generate_suggested_question_details(llm_five, "doc", passages, status)
    assert len(details) == 5 and all(d["type"] == "grounded" for d in details)
    assert status["status"] == "ok"

    # Only two from the LLM -> two grounded, three exploratory templates
    llm_two = lambda prompt, temperature=0.3: '["A real question?", "Another real question?"]'
    status = {}
    details = _generate_suggested_question_details(llm_two, "doc", passages, status)
    assert [d["type"] for d in details] == ["grounded"] * 2 + ["exploratory"] * 3
    assert status["status"] == "partial"
    assert status["detail"] == {"grounded": 2, "exploratory": 3}

    # Unparseable LLM output -> everything exploratory, reported as failed
    llm_bad = lambda prompt, temperature=0.3: "not json at all"
    status = {}
    details = _generate_suggested_question_details(llm_bad, "doc", passages, status)
    assert len(details) == 5 and all(d["type"] == "exploratory" for d in details)
    assert status["status"] == "failed" and status["error"]

    # No passages -> nothing was attempted, all exploratory, unavailable
    status = {}
    details = _generate_suggested_question_details(llm_five, "doc", [], status)
    assert all(d["type"] == "exploratory" for d in details)
    assert status["status"] == "unavailable"


def test_m1_07_summary_llm_failure_is_reported_and_extractive_kept():
    from app.services.overview_service import _generate_summary

    def boom(prompt, temperature=0.0):
        raise RuntimeError("llm down")

    status = {}
    summary = _generate_summary(boom, "d.txt", _GOOD_PASSAGES, status)
    assert summary, "Verbatim passage sentences should survive an LLM failure"
    assert status["status"] == "partial"
    assert "llm down" in status["error"]


def test_m1_06_retrieval_failure_keeps_other_sections(tmp_path, monkeypatch):
    from app.services import overview_service as svc

    _patch_document(monkeypatch, tmp_path)
    ov = svc.generate_document_overview(
        "x.txt", lambda p, temperature=0.0: "", _Retriever(error="index offline")
    )

    status = ov["section_status"]
    assert status["retrieval"]["status"] == "failed"
    assert "index offline" in status["retrieval"]["error"]
    assert status["summary"]["status"] == "unavailable"
    assert "index offline" in status["summary"]["error"]
    # Everything that did not depend on retrieval is still there
    assert ov["title"] == "Real Title"
    assert ov["authors"] == ["A. Author"]
    assert ov["figure_count"] == 1
    assert status["document_iq"]["status"] == "ok"
    assert "iq_score" in ov["document_iq"]
    assert len(ov["suggested_questions"]) == 5
    assert all(q["type"] == "exploratory" for q in ov["question_details"])
    # A retrieval failure must not be frozen into the cache
    assert not (tmp_path / f"{'h' * 64}.json").exists()


def test_m1_07_iq_failure_keeps_other_sections(tmp_path, monkeypatch):
    from app.services import overview_service as svc

    _patch_document(monkeypatch, tmp_path, iq_boom=True)
    ov = svc.generate_document_overview(
        "x.txt", lambda p, temperature=0.0: "", _Retriever(passages=_GOOD_PASSAGES)
    )

    status = ov["section_status"]
    assert status["document_iq"]["status"] == "failed"
    assert "metadata store offline" in status["document_iq"]["error"]
    assert ov["document_iq"] == {}
    assert status["retrieval"]["status"] == "ok"
    assert ov["summary_sentences"], "Summary must survive an IQ failure"
    assert ov["figure_count"] == 1
    assert not (tmp_path / f"{'h' * 64}.json").exists()


def test_ov_03_missing_metadata_is_disclosed_not_invented(tmp_path, monkeypatch):
    from app.services import overview_service as svc

    bare = {
        "document_hash": "b" * 64,
        "total_pages": 1,
        "pages": [{"page": 1, "text": "Plain text with no captions."}],
    }
    _patch_document(monkeypatch, tmp_path, doc_json=bare)
    ov = svc.generate_document_overview("bare_doc.txt", lambda p, temperature=0.0: "", _Retriever(passages=[]))

    meta = ov["section_status"]["metadata"]
    assert meta["status"] == "partial"
    assert set(meta["detail"]["missing"]) == {"title", "authors", "year"}
    assert meta["detail"]["title_source"] == "filename"
    assert ov["authors"] == []
    assert ov["year"] is None
    assert ov["section_status"]["figures_tables"]["status"] == "empty"
    assert ov["section_status"]["retrieval"]["status"] == "empty"


def test_m1_09_healthy_overview_is_cached_and_reused(tmp_path, monkeypatch):
    from app.services import overview_service as svc

    _patch_document(monkeypatch, tmp_path)
    calls = {"n": 0}

    def llm(prompt, temperature=0.0):
        calls["n"] += 1
        return ""

    retriever = _Retriever(passages=_GOOD_PASSAGES)
    first = svc.generate_document_overview("x.txt", llm, retriever)
    assert first["from_cache"] is False
    assert (tmp_path / f"{'h' * 64}.json").exists()
    calls_after_first = calls["n"]

    second = svc.generate_document_overview("x.txt", llm, retriever)
    assert second["from_cache"] is True
    assert calls["n"] == calls_after_first, "Second request must make zero LLM calls"
    assert second["section_status"] == first["section_status"]