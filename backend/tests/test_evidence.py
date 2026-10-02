"""
UNKNOWN X v2.0
Evidence Trail Integration Test

Uses the REAL HybridSearch pipeline.
"""

from app.rag.evidence import (
    build_evidence,
    evidence_markdown,
    format_citations,
)
from app.rag.hybrid_search import HybridSearch

QUERY = "What is Retrieval Augmented Generation?"


def main():
    print("=" * 60)
    print("UNKNOWN X v2.0 - Evidence Trail Test")
    print("=" * 60)

    retriever = HybridSearch()

    print("\nSearching...")
    results = retriever.search(query=QUERY, top_k=3)

    print(f"\nRetrieved {len(results)} chunks.\n")

    print("=" * 60)
    print("RAW HYBRID SEARCH OUTPUT")
    print("=" * 60)

    for result in results:
        print(result)
        print("-" * 60)

    evidence = build_evidence(results)

    print("\n")
    print("=" * 60)
    print("STANDARDIZED EVIDENCE OBJECTS")
    print("=" * 60)

    for item in evidence:
        print(item)
        print("-" * 60)

    print("\n")
    print("=" * 60)
    print("FORMATTED CITATIONS")
    print("=" * 60)

    for citation in format_citations(evidence):
        print(citation)

    print("\n")
    print("=" * 60)
    print("MARKDOWN EVIDENCE TRAIL")
    print("=" * 60)

    print(evidence_markdown(evidence))

    print("\n")
    print("=" * 60)
    print("RUNNING VALIDATIONS")
    print("=" * 60)

    assert len(evidence) > 0, "❌ No evidence generated."

    required_fields = [
        "rank",
        "document",
        "page",
        "chunk_id",
        "score",
        "hybrid_score",
        "bm25_score",
        "faiss_score",
        "snippet",
    ]

    for item in evidence:
        for field in required_fields:
            assert field in item, f"❌ Missing field: {field}"

        assert isinstance(item["document"], str)
        assert isinstance(item["chunk_id"], str)
        assert isinstance(item["snippet"], str)

        assert item["score"] >= 0
        assert item["hybrid_score"] >= 0

    print("\n✅ ALL TESTS PASSED!")
    print("Evidence Trail is compatible with HybridSearch.")


if __name__ == "__main__":
    main()
