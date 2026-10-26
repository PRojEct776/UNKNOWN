import pytest
import app.rag.dual_retriever as dr


class FakeRetriever:
    def __init__(self, chunks):
        self.chunks = chunks

    def search(self, query, **kwargs):
        return self.chunks


def chunk(score):
    return {"text": "some text", "reranker_score": score}


@pytest.fixture(autouse=True)
def fixed_threshold(monkeypatch):
    monkeypatch.setattr(dr, "MIN_DOC_RELEVANCE", -8.0)


def test_low_score_is_off_topic():
    assert dr._is_off_topic("capital of Australia", [chunk(-11.1)]) is True


def test_high_score_is_on_topic():
    assert dr._is_off_topic("how does the model train", [chunk(-2.0)]) is False


def test_summarize_bypasses_gate():
    assert dr._is_off_topic("Summarize this document", [chunk(-11.1)]) is False


def test_missing_reranker_score_never_blocks():
    assert dr._is_off_topic("anything", [{"text": "x"}]) is False


def test_off_topic_returns_no_match_and_skips_web(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("web must not be called")

    monkeypatch.setattr(dr, "_fetch_web_chunks", boom)
    d = dr.DualRetriever(retriever=FakeRetriever([chunk(-11.1)]), llm=None)
    res = d.dual_retrieve("What is the capital of Australia?", doc_only=True)
    assert res.detail == dr.NO_MATCH_MESSAGE
    assert res.doc_sources == [] and res.web_sources == []


def test_exact_identifier_in_chunk_never_blocked():
    chunks = [{"text": "Project BLP-204 starts in May.", "reranker_score": -11.0}]
    assert dr._is_off_topic("Find the exact project identifier BLP-204", chunks) is False


def test_identifier_not_in_chunks_can_still_block():
    chunks = [{"text": "Unrelated text.", "reranker_score": -11.0}]
    assert dr._is_off_topic("Find the exact project identifier BLP-204", chunks) is True
