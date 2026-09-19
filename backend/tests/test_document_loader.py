from app.rag.document_loader import DocumentLoader
from app.rag.config import settings

loader = DocumentLoader()


def test_extract_document():
    pages = loader.extract_document(
        settings.PAPERS_DIR / "sample_ieee.pdf"
    )

    assert isinstance(pages, list)
    assert len(pages) > 0


def test_create_document_json():
    document = loader.create_document_json(
        settings.PAPERS_DIR / "sample_ieee.pdf"
    )

    assert document["source_file"] == "sample_ieee.pdf"
    assert document["total_pages"] > 0
    assert document["total_words"] > 0
    assert len(document["pages"]) == document["total_pages"]


def test_save_document_json():
    document = loader.create_document_json(
        settings.PAPERS_DIR / "sample_ieee.pdf"
    )

    output_path = loader.save_document_json(document)

    assert output_path.exists()