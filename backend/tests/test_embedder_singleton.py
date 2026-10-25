import pytest
from app.rag.embedder import embed_text


@pytest.mark.slow
def test_embedder_singleton():
    queries = [
        "What is virtualization?",
        "Explain cloud computing.",
        "Difference between VM and Docker.",
    ]
    for query in queries:
        embedding = embed_text(query)
        assert embedding.shape[0] > 0
