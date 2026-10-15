"""End-to-End integration tests for multi-paper collections, scoped retrieval, batch upload, and capacity enforcement."""

import io
from fastapi.testclient import TestClient

from app.main import app
from app.rag.config import settings

client = TestClient(app)


def test_documents_list_baseline():
    """Verify GET /documents returns active documents in the collection."""
    response = client.get("/documents")
    assert response.status_code == 200
    data = response.json()
    assert "documents" in data
    assert "total" in data
    assert data["total"] == len(data["documents"])
    for doc in data["documents"]:
        assert "name" in doc
        assert "title" in doc
        assert "chunks_count" in doc
        assert "total_pages" in doc
        assert "total_words" in doc


def test_single_document_upload_and_scoped_query():
    """Verify single document upload, chunking, indexing, retrieval, and detail viewing."""
    test_doc_name = "Synthetic_Quantum_Trap_Experiment_Alpha.txt"
    test_content = (
        "Quantum Trap Experiment Alpha Report\n\n"
        "Abstract: The experimental benchmark Alpha-99 achieves 99.4% quantum circuit fidelity "
        "using cryogenic resonant traps operating at 15 millikelvin. In comparison to silicon spin "
        "qubits, resonant RF trapping eliminates phase decoherence across 128 physical qubits.\n\n"
        "Results: Measured T1 relaxation time was 450 microseconds, exceeding conventional limits "
        "by a factor of four. Gate fidelity was verified through randomized benchmarking."
    )

    try:
        # 1. Upload document
        file_payload = {"file": (test_doc_name, io.BytesIO(test_content.encode("utf-8")), "text/plain")}
        upload_resp = client.post("/documents/upload", files=file_payload)
        assert upload_resp.status_code == 200, upload_resp.text
        upload_data = upload_resp.json()
        assert upload_data["status"] == "success"
        assert upload_data["filename"] == test_doc_name
        assert upload_data["chunks_count"] >= 1

        # 2. Check document detail
        detail_resp = client.get(f"/documents/{test_doc_name}")
        assert detail_resp.status_code == 200
        detail_data = detail_resp.json()
        assert detail_data["name"] == test_doc_name
        assert "Alpha-99" in (detail_data.get("preview") or "") or "Alpha-99" in (detail_data.get("content") or "")

        # 3. Query with document_names scope (Targeting the newly uploaded paper)
        scoped_query_resp = client.post(
            "/query",
            json={
                "query": "What quantum circuit fidelity does Alpha-99 achieve?",
                "document_names": [test_doc_name],
            },
        )
        assert scoped_query_resp.status_code == 200, scoped_query_resp.text
        query_result = scoped_query_resp.json()
        assert "answer" in query_result
        assert "sources" in query_result
        assert len(query_result["sources"]) > 0
        # All retrieved sources must come strictly from the scoped paper
        for source in query_result["sources"]:
            assert source["document"] == test_doc_name

        # 4. Cross-document isolation: Scope to another paper and verify the new paper is excluded
        docs_resp = client.get("/documents")
        other_docs = [d["name"] for d in docs_resp.json()["documents"] if d["name"] != test_doc_name]
        if other_docs:
            isolated_resp = client.post(
                "/query",
                json={
                    "query": "Alpha-99 quantum circuit fidelity",
                    "document_names": [other_docs[0]],
                },
            )
            assert isolated_resp.status_code == 200
            isolated_sources = isolated_resp.json().get("sources", [])
            for s in isolated_sources:
                assert s["document"] != test_doc_name

    finally:
        # Cleanup
        client.delete(f"/documents/{test_doc_name}")


def test_batch_upload_and_comparison():
    """Verify batch upload of multiple documents, multi-document comparison, and batch deletion."""
    doc_a_name = "Batch_Model_X.txt"
    doc_b_name = "Batch_Model_Y.txt"
    content_a = "Architecture Model X uses dense sparse matrix multiplication with 128 layers."
    content_b = "Architecture Model Y uses graph attention networks with 64 transformer heads."

    try:
        files = [
            ("files", (doc_a_name, io.BytesIO(content_a.encode("utf-8")), "text/plain")),
            ("files", (doc_b_name, io.BytesIO(content_b.encode("utf-8")), "text/plain")),
        ]

        batch_resp = client.post("/documents/upload-batch", files=files)
        assert batch_resp.status_code == 200, batch_resp.text
        batch_data = batch_resp.json()
        assert batch_data["total"] == 2
        assert batch_data["successful"] == 2
        assert batch_data["failed"] == 0

        # Run comparison with scoped document_names
        compare_resp = client.post(
            "/compare",
            json={
                "query": "Compare the architecture and layer configuration of Model X vs Model Y",
                "document_names": [doc_a_name, doc_b_name],
            },
        )
        assert compare_resp.status_code == 200, compare_resp.text
        compare_data = compare_resp.json()
        assert "comparison_table" in compare_data or "summary" in compare_data

    finally:
        client.delete(f"/documents/{doc_a_name}")
        client.delete(f"/documents/{doc_b_name}")


def test_capacity_limit_enforcement():
    """Verify that uploading beyond MAX_COLLECTION_PAPERS (25) is rejected with HTTP 400."""
    current_docs = client.get("/documents").json()["documents"]
    current_count = len(current_docs)
    needed_to_fill = settings.MAX_COLLECTION_PAPERS - current_count

    created_temp_docs = []
    try:
        # Fill up to capacity
        if needed_to_fill > 0:
            batch_fill = []
            for i in range(needed_to_fill):
                name = f"Temp_Cap_Paper_{i:02d}.txt"
                created_temp_docs.append(name)
                batch_fill.append(
                    ("files", (name, io.BytesIO(f"Paper content {i}".encode("utf-8")), "text/plain"))
                )
            fill_resp = client.post("/documents/upload-batch", files=batch_fill)
            assert fill_resp.status_code == 200, fill_resp.text

        # Verify collection is at capacity
        docs_at_cap = client.get("/documents").json()
        assert docs_at_cap["total"] == settings.MAX_COLLECTION_PAPERS

        # Attempt to upload 26th file via single upload -> MUST fail with 400
        overflow_single = {
            "file": ("Overflow_26th.txt", io.BytesIO(b"Excess file content"), "text/plain")
        }
        reject_single_resp = client.post("/documents/upload", files=overflow_single)
        assert reject_single_resp.status_code == 400
        assert "Collection limit" in reject_single_resp.json()["detail"] or "limit" in reject_single_resp.json()["detail"].lower()

        # Attempt to upload via batch upload -> MUST fail with 400
        overflow_batch = [
            ("files", ("Overflow_Batch_26.txt", io.BytesIO(b"Excess file"), "text/plain"))
        ]
        reject_batch_resp = client.post("/documents/upload-batch", files=overflow_batch)
        assert reject_batch_resp.status_code == 400
        assert "capacity" in reject_batch_resp.json()["detail"].lower() or "limit" in reject_batch_resp.json()["detail"].lower()

    finally:
        for temp_name in created_temp_docs:
            client.delete(f"/documents/{temp_name}")
