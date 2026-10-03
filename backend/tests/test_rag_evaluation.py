from app.rag.context_builder import ContextBuilder
from app.rag.hybrid_search import HybridSearch
from app.rag.prompt_engine import PromptEngine

CASES = [
    {
        "query": "What problem does SAC-RAG solve?",
        "expected_chunks": {"chunk_1", "chunk_6", "chunk_7"},
        "expected_type": "general",
    },
    {
        "query": "What are the three question types?",
        "expected_chunks": {"chunk_3", "chunk_7"},
        "expected_type": "definition",
    },
    {
        "query": "How does SAC-RAG perform adaptive retrieval?",
        "expected_chunks": {"chunk_5", "chunk_6", "chunk_7", "chunk_10"},
        "expected_type": "reasoning",
    },
    {
        "query": "What metrics are used to evaluate retrieval quality?",
        "expected_chunks": {"chunk_8", "chunk_9", "chunk_10"},
        "expected_type": "general",
    },
]


def test_rag_retrieval_context_and_prompt_pipeline():
    retriever = HybridSearch()
    builder = ContextBuilder(max_chunks=5)
    prompt_engine = PromptEngine()

    for case in CASES:
        results = retriever.search(case["query"], top_k=5)

        assert results, f"No retrieval results for: {case['query']}"

        retrieved_ids = {result["chunk_id"] for result in results}

        assert (
            retrieved_ids & case["expected_chunks"]
        ), f"No expected evidence retrieved for: {case['query']}"

        context = builder.build(results)

        assert context
        assert "Evidence:" in context

        query_type = prompt_engine.detect_query_type(case["query"])

        assert query_type.value == case["expected_type"]

        prompt = prompt_engine.build_prompt(
            query=case["query"],
            context=context,
            query_type=query_type,
        )

        assert "Answer ONLY using the retrieved context." in prompt
        assert "Do not use outside knowledge." in prompt
        assert "Do not fabricate facts or citations." in prompt

        for result in results:
            assert result["text"].strip()[:1200] in context


def test_rag_context_contains_source_metadata():
    retriever = HybridSearch()
    builder = ContextBuilder(max_chunks=5)

    results = retriever.search("What are the three question types?", top_k=5)

    context = builder.build(results)

    for result in results:
        assert result["document"] in context
        assert str(result["page"]) in context
        assert result["chunk_id"] in context
