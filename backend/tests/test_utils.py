from pathlib import Path

from app.rag.config import settings
from app.rag.utils import (
    clean_text,
    count_words,
    estimate_read_time,
    generate_hash,
    is_supported_document,
    list_supported_documents,
    normalize_unicode,
)


def test_unicode_normalization():
    assert isinstance(normalize_unicode("“UNKNOWN”"), str)


def test_clean_text():
    dirty = "Hello   World\n\nUNKNOWN-\nProject"
    assert clean_text(dirty) == "Hello World UNKNOWNProject"


def test_word_count():
    assert count_words("AETHER UNKNOWN Project") == 3


def test_reading_time():
    text = "word " * 400
    assert estimate_read_time(text) == 2.0


def test_hash_generation():
    assert len(generate_hash("UNKNOWN")) == 64


def test_supported_document():
    assert is_supported_document(Path("paper.pdf"))
    assert not is_supported_document(Path("image.png"))


def test_list_supported_documents():
    docs = list_supported_documents(settings.PAPERS_DIR)

    assert isinstance(docs, list)

    for file in docs:
        assert file.suffix.lower() in settings.SUPPORTED_EXTENSIONS