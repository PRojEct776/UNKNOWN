from app.rag.context_builder import ContextBuilder

builder = ContextBuilder()

dummy_results = [
    {
        "rank": 1,
        "hybrid_score": 0.94,
        "bm25_score": 15.2,
        "faiss_score": 0.88,
        "document": "cloud_notes.pdf",
        "page": 12,
        "chunk_id": "cloud_12_01",
        "text": "Cloud computing provides on-demand access to computing resources over the internet.",
    },
    {
        "rank": 2,
        "hybrid_score": 0.91,
        "bm25_score": 14.7,
        "faiss_score": 0.83,
        "document": "os_notes.pdf",
        "page": 45,
        "chunk_id": "os_45_03",
        "text": "Virtualization creates virtual versions of hardware resources and operating systems.",
    },
]

context = builder.build(dummy_results)

print("\nGenerated Context:\n")
print(context)
```

Run:

```bash
python -m tests.test_context_builder
```

---

# 🔬 End-to-End Test (Required Before Module 3)

I agree with the reviewer's final point: **don't trust the builder in isolation.**

Before we move to Prompt Engineering, we should verify:

1. `HybridRetriever.search("What is cloud computing?")`
2. Pass its output directly into `ContextBuilder.build()`
3. Print the generated context.
4. Confirm the context contains:
   - Real document names.
   - Real chunk text.
   - Real scores.
   - Page numbers.

This is the first **integration test** between Sprint 2 and Sprint 3, and it's the right checkpoint before we connect Gemini to the retrieval pipeline.

## 🟢 Jarvis Decision

- **Replace the previous `context_builder.py`** with this version.
- **Do not continue to Module 3** until the end-to-end context print shows actual chunks from your ChromaDB/FAISS retrieval, not dummy data. That ensures the RAG pipeline is wired correctly before Gemini starts generating answers.