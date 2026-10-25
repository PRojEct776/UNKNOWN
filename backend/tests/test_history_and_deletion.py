import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app, rag_service
from app.rag.config import settings
from app.services import history_service


@pytest.fixture
def client():
    return TestClient(app)


def test_history_crud_and_endpoints(client):
    """Verify history table schema, filtering, open, delete one, clear all, and rerun."""
    # 1. Clear any pre-existing test history
    history_service.clear_history_entries(user="test_runner")

    # 2. Insert records with different scopes and features
    h1 = history_service.create_history_entry(
        user="test_runner",
        workspace="workspace_alpha",
        document_ids=["doc_a.pdf"],
        scope="document",
        query="What is transformer architecture?",
        feature="query",
        result_snapshot={"answer": "Transformers use self-attention."},
    )
    h2 = history_service.create_history_entry(
        user="test_runner",
        workspace="workspace_alpha",
        document_ids=["doc_b.pdf"],
        scope="document",
        query="What is diffusion?",
        feature="knowledge-dna",
        result_snapshot={"core_topics": ["denoising", "score matching"]},
    )
    h3 = history_service.create_history_entry(
        user="test_runner",
        workspace="workspace_beta",
        document_ids=["doc_a.pdf", "doc_b.pdf"],
        scope="collection",
        query="Compare transformers and diffusion",
        feature="query",
        result_snapshot={"comparison": "Different modalities."},
    )

    # 3. Test list / filter endpoint
    resp = client.get("/history?user=test_runner")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 3

    # Filter by workspace
    resp_alpha = client.get("/history?user=test_runner&workspace=workspace_alpha")
    assert resp_alpha.status_code == 200
    assert len(resp_alpha.json()) == 2

    # Filter by feature
    resp_dna = client.get("/history?user=test_runner&feature=knowledge-dna")
    assert resp_dna.status_code == 200
    assert len(resp_dna.json()) == 1
    assert resp_dna.json()[0]["id"] == h2["id"]

    # Filter by document_id
    resp_doc_b = client.get("/history?user=test_runner&document_id=doc_b.pdf")
    assert resp_doc_b.status_code == 200
    assert len(resp_doc_b.json()) == 2

    # 4. Test open endpoint (GET /history/{id})
    resp_open = client.get(f"/history/{h1['id']}")
    assert resp_open.status_code == 200
    assert resp_open.json()["id"] == h1["id"]
    assert resp_open.json()["query"] == "What is transformer architecture?"
    assert resp_open.json()["result_snapshot"]["answer"] == "Transformers use self-attention."

    # 5. Test rerun endpoint (POST /history/{id}/rerun)
    resp_rerun = client.post(f"/history/{h1['id']}/rerun")
    assert resp_rerun.status_code == 200
    rerun_data = resp_rerun.json()
    assert rerun_data["id"] != h1["id"]
    assert rerun_data["query"] == h1["query"]
    assert "result_snapshot" in rerun_data

    # 6. Test delete one (DELETE /history/{id})
    del_resp = client.delete(f"/history/{h2['id']}")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "deleted"

    not_found_resp = client.get(f"/history/{h2['id']}")
    assert not_found_resp.status_code == 404

    # 7. Test clear all for user (DELETE /history?user=...)
    clear_resp = client.delete("/history?user=test_runner")
    assert clear_resp.status_code == 200
    assert clear_resp.json()["status"] == "cleared"

    remaining = client.get("/history?user=test_runner").json()
    assert len(remaining) == 0


def test_soft_delete_undo_and_hard_delete_orphan_purge(client):
    """
    ACCEPT criteria test:
    1. Ingest document with unique phrase.
    2. Confirm search returns unique phrase and record vector count.
    3. Soft delete: search returns nothing, vector count drops.
    4. Undo within 10s: everything restored, search finds phrase again, vector count restored.
    5. Hard delete: vector count drops, search returns nothing, history item tied only to that doc is purged.
    6. Data dir walk finds NO orphan files anywhere.
    """
    doc_name = "Unique_Orphan_Test_Doc.txt"
    unique_phrase = "PHRASE_ZEBRA_QUANTUM_789_UNIQUE"
    content = (
        f"Experimental Findings Report.\n\n"
        f"This research proves that {unique_phrase} achieves remarkable stability "
        f"at ultra-low cryogenic temperatures under resonant electromagnetic confinement."
    )

    try:
        # 1. Ingest test document
        payload = {"file": (doc_name, io.BytesIO(content.encode("utf-8")), "text/plain")}
        up_resp = client.post("/documents/upload", files=payload)
        assert up_resp.status_code == 200, up_resp.text
        assert up_resp.json()["status"] == "success"

        v_count_initial = rag_service.retriever.faiss.index.ntotal
        assert v_count_initial > 0

        # Verify unique phrase is indexed in search
        search_results_before = rag_service.retriever.search(unique_phrase, top_k=5)
        doc_matches_before = [c for c in search_results_before if c.get("document") == doc_name]
        assert len(doc_matches_before) > 0, "Unique phrase should be found before deletion"

        # Create history record tied ONLY to this document
        h_sole = history_service.create_history_entry(
            user="deletion_tester",
            document_ids=[doc_name],
            query=f"Query solely for {unique_phrase}",
            feature="query",
            result_snapshot={"found": True},
        )
        # Create history record tied to MULTIPLE documents
        h_multi = history_service.create_history_entry(
            user="deletion_tester",
            document_ids=[doc_name, "sample_ieee.pdf"],
            query="Query spanning multiple documents",
            feature="query",
            result_snapshot={"found": True},
        )

        # Create a mock derived artifact in cache
        cache_dir = settings.BASE_DIR / "app" / "data" / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        derived_dna_file = cache_dir / "Unique_Orphan_Test_Doc_dna.json"
        derived_dna_file.write_text('{"derived": "dna"}', encoding="utf-8")

        # 2. Perform Soft Delete with 10-second undo window
        del_resp = client.delete(f"/documents/{doc_name}?undo_window=10.0")
        assert del_resp.status_code == 200
        del_data = del_resp.json()
        assert del_data["status"] == "soft_deleted"
        assert del_data["document_name"] == doc_name
        assert del_data["undo_window_seconds"] == 10.0

        # Vector count drops
        v_count_after_delete = rag_service.retriever.faiss.index.ntotal
        assert v_count_after_delete < v_count_initial, "Vector count must drop after soft delete"

        # Search for unique phrase returns NOTHING
        search_results_deleted = rag_service.retriever.search(unique_phrase, top_k=5)
        doc_matches_deleted = [c for c in search_results_deleted if c.get("document") == doc_name]
        assert len(doc_matches_deleted) == 0, "Deleted document chunks must not appear in search"

        # 3. Undo within 10 seconds restores everything
        undo_resp = client.post(f"/documents/{doc_name}/undo")
        assert undo_resp.status_code == 200
        assert undo_resp.json()["status"] == "restored"

        # Vector count is restored
        assert rag_service.retriever.faiss.index.ntotal == v_count_initial, "Vector count must be restored after undo"

        # Search for unique phrase succeeds again
        search_results_restored = rag_service.retriever.search(unique_phrase, top_k=5)
        doc_matches_restored = [c for c in search_results_restored if c.get("document") == doc_name]
        assert len(doc_matches_restored) > 0, "Document chunks must be searchable again after undo"

        # 4. Perform Hard Delete (undo_window=0)
        hard_del_resp = client.delete(f"/documents/{doc_name}?undo_window=0")
        assert hard_del_resp.status_code == 200

        # Vector count drops again
        assert rag_service.retriever.faiss.index.ntotal < v_count_initial

        # Search returns nothing
        search_after_hard = rag_service.retriever.search(unique_phrase, top_k=5)
        assert len([c for c in search_after_hard if c.get("document") == doc_name]) == 0

        # History tied ONLY to this document was deleted
        assert history_service.get_history_entry(h_sole["id"]) is None, "Sole document history must be deleted"
        # History tied to multiple documents remains intact
        assert history_service.get_history_entry(h_multi["id"]) is not None, "Multi-doc history must be preserved"

        # 5. Walk data directory and ensure NO orphan files exist for this document
        stem = Path(doc_name).stem
        directories_to_walk = [
            settings.PAPERS_DIR,
            settings.JSON_DIR,
            settings.BASE_DIR / "app" / "data" / "metadata",
            settings.BASE_DIR / "app" / "data" / "cache",
            settings.BASE_DIR / "app" / "data" / "trash",
        ]

        orphan_files = []
        for d in directories_to_walk:
            if d.exists():
                for f in d.rglob("*"):
                    if f.is_file() and (stem in f.name or doc_name in f.name):
                        orphan_files.append(str(f))

        assert len(orphan_files) == 0, f"Found orphan files after complete deletion: {orphan_files}"

    finally:
        # Cleanup history
        history_service.clear_history_entries(user="deletion_tester")
