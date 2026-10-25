import pytest


@pytest.mark.slow
def test_rag_context():
    from app.rag.context_builder import ContextBuilder
    from app.rag.hybrid_search import HybridSearch

    retriever = HybridSearch()
    builder = ContextBuilder(max_chunks=5)
    query = "What is cloud virtualization?"
    results = retriever.search(query)
    context = builder.build(results)
    assert context is not None
