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

        # Check figure / table count and thumbnails
        assert data1["figure_count"] >= 1
        assert data1["table_count"] >= 1
        assert len(data1["figures"]) >= 1
        assert len(data1["tables"]) >= 1
        assert data1["figures"][0]["thumbnail"].startswith("data:image/svg")
        assert data1["tables"][0]["thumbnail"].startswith("data:image/svg")

        # Check 5-sentence summary and PAGE REFERENCES on every summary sentence
        assert len(data1["summary_sentences"]) == 5, f"Expected 5 sentences, got {len(data1['summary_sentences'])}"
        for idx, sent in enumerate(data1["summary_sentences"]):
            assert sent["text"], f"Sentence {idx+1} must have non-empty text"
            assert sent["page_ref"], f"Sentence {idx+1} must carry a page reference"
            assert "Page" in sent["page_ref"], f"Sentence {idx+1} page_ref '{sent['page_ref']}' must specify page"
            assert sent["quote"], f"Sentence {idx+1} must carry a verified verbatim quote"

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
