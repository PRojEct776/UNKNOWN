from app.rag.hybrid_search import HybridSearch

CASES = [
    {
        "query": "What problem does SAC-RAG solve?",
        "relevant": {"chunk_1", "chunk_6", "chunk_7"},
    },
    {
        "query": "What are the three question types?",
        "relevant": {"chunk_3", "chunk_7"},
    },
    {
        "query": "How does SAC-RAG perform adaptive retrieval?",
        "relevant": {"chunk_5", "chunk_6", "chunk_7", "chunk_10"},
    },
    {
        "query": "What is context compression?",
        "relevant": {"chunk_5", "chunk_8", "chunk_13"},
    },
    {
        "query": "What metrics are used to evaluate retrieval quality?",
        "relevant": {"chunk_8", "chunk_9", "chunk_10"},
    },
]


def test_retrieval_quality_top5():
    retriever = HybridSearch()

    hits = 0

    for case in CASES:
        results = retriever.search(case["query"], top_k=5)
        retrieved_ids = {result["chunk_id"] for result in results}

        if retrieved_ids & case["relevant"]:
            hits += 1

    recall_at_5 = hits / len(CASES)

    assert recall_at_5 >= 0.8
