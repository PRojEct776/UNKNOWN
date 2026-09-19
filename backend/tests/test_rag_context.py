from app.rag.hybrid_search import HybridSearch
from app.rag.context_builder import ContextBuilder

# Initialize components
retriever = HybridSearch()
builder = ContextBuilder(max_chunks=5)

query = "What is cloud virtualization?"

print(f"\nQuery: {query}\n")

# Retrieve results
results = retriever.search(query)

print("=" * 60)
print("RAW HYBRID SEARCH RESULTS")
print("=" * 60)

for result in results[:3]:
    print(
        f"Rank {result['rank']} | "
        f"Document: {result['document']} | "
        f"Page: {result['page']} | "
        f"Hybrid Score: {result['hybrid_score']}"
    )
    print(result["text"][:200] + "...")
    print("-" * 60)

# Build Gemini context
context = builder.build(results)

print("\n" + "=" * 60)
print("GENERATED CONTEXT")
print("=" * 60)
print(context)

print("\n" + "=" * 60)
print(f"Context Length: {len(context)} characters")
print("=" * 60)