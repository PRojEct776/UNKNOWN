import pytest

from app.rag.exceptions import (
    DocumentExtractionError,
    DocumentNotFoundError,
    EmptyDocumentError,
    UnsupportedDocumentError,
    UnknownProjectError,
)


def test_document_not_found():
    with pytest.raises(DocumentNotFoundError):
        raise DocumentNotFoundError("Document missing")


def test_unsupported_document():
    with pytest.raises(UnsupportedDocumentError):
        raise UnsupportedDocumentError("Unsupported format")


def test_empty_document():
    with pytest.raises(EmptyDocumentError):
        raise EmptyDocumentError("No text found")


def test_document_extraction():
    with pytest.raises(DocumentExtractionError):
        raise DocumentExtractionError("Extraction failed")


def test_base_exception():
    with pytest.raises(UnknownProjectError):
        raise UnknownProjectError("Base UNKNOWN exception")