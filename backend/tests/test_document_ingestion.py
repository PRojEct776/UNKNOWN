import pytest
from pathlib import Path
from app.rag.config import settings
from app.services.document_service import ingest_document, count_document_chunks
from app.rag.hybrid_search import HybridSearch


def test_ingest_txt_document(tmp_path):
    test_filename = "test_ingestion_doc.txt"
    test_file = settings.PAPERS_DIR / test_filename
    test_content = (
        "Quantum holographic storage enables unprecedented data density in crystalline substrates. "
        "The retrieval fidelity surpasses classic holographic optical discs by thirty percent. "
        "This experimental paper demonstrates crystal lattice data recording at nanometer resolution."
    )
    test_file.write_text(test_content, encoding="utf-8")

    try:
        result = ingest_document(test_file)
        assert result["status"] == "success"
        assert result["document"] == test_filename
        assert result["total_chunks"] > 0
        assert result["document_chunks"] > 0
        assert "document_iq" in result
        assert result["document_iq"]["iq_score"] > 0

        # Verify it can be retrieved via HybridSearch
        searcher = HybridSearch()
        results = searcher.search("quantum holographic storage")
        found = any(r.get("document") == test_filename for r in results)
        assert found, "Ingested document was not retrieved by hybrid search."

    finally:
        # Clean up created artifacts for the test document
        if test_file.exists():
            test_file.unlink()
        json_path = settings.JSON_DIR / "test_ingestion_doc.json"
        if json_path.exists():
            json_path.unlink()
        meta_path = settings.METADATA_DIR / "test_ingestion_doc_metadata.json"
        if meta_path.exists():
            meta_path.unlink()
        # Re-index the original dataset to restore baseline state
        from app.rag.chunker import DocumentChunker
        from app.rag.bm25_index_builder import BM25IndexBuilder
        from app.rag.faiss_index_builder import FAISSIndexBuilder
        DocumentChunker().create_chunks()
        BM25IndexBuilder().build_index()
        FAISSIndexBuilder().build_index()
