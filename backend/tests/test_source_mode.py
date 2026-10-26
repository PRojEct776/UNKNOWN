import pytest
from app.rag.source_mode import resolve_source_mode


def test_no_mode_keeps_legacy_behaviour():
    assert resolve_source_mode(None, False, ["a.pdf"]) == (False, ["a.pdf"])
    assert resolve_source_mode(None, True, None) == (True, None)


def test_documents_mode_never_allows_web():
    assert resolve_source_mode("documents", False, ["a.pdf"]) == (True, ["a.pdf"])


def test_web_mode_skips_documents():
    assert resolve_source_mode("web", False, ["a.pdf"]) == (False, [])


def test_both_mode_keeps_documents_and_web():
    assert resolve_source_mode("both", False, ["a.pdf"]) == (False, ["a.pdf"])


@pytest.mark.parametrize("mode", ["web", "both"])
def test_contradiction_with_doc_only_is_rejected(mode):
    with pytest.raises(ValueError):
        resolve_source_mode(mode, True, None)


def test_invalid_mode_is_rejected():
    with pytest.raises(ValueError):
        resolve_source_mode("everything", False, None)
