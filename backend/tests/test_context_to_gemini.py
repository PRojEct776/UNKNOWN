import pytest


@pytest.mark.slow
def test_context_to_gemini():
    from app.rag.context_builder import ContextBuilder
    from app.rag.hybrid_search import HybridSearch
    from app.llm.gemini_provider import GeminiProvider
    from app.rag.prompt_engine import PromptEngine

    retriever = HybridSearch()
    builder = ContextBuilder(max_chunks=5)
    prompt_engine = PromptEngine()
    gemini = GeminiProvider()

    query = "Explain the SAC-RAG retrieval pipeline."
    results = retriever.search(query)
    context = builder.build(results)
    query_type = prompt_engine.detect_query_type(query)
    prompt = prompt_engine.build_prompt(query=query, context=context, query_type=query_type)
    response = gemini.generate(prompt)
    assert response is not None
