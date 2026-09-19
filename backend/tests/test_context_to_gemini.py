"""
UNKNOWN Project - Sprint 3
End-to-End Adaptive RAG Integration Test

Pipeline:
User Query
    ↓
Hybrid Search
    ↓
Context Builder
    ↓
Prompt Engine
    ↓
Gemini
    ↓
Answer
"""

from app.rag.hybrid_search import HybridSearch
from app.rag.context_builder import ContextBuilder
from app.rag.prompt_engine import PromptEngine
from app.rag.llm_engine import GeminiEngine


# ============================================================
# INITIALIZE MODULES
# ============================================================

retriever = HybridSearch()
builder = ContextBuilder(max_chunks=5)
prompt_engine = PromptEngine()
gemini = GeminiEngine()


# ============================================================
# USER QUERY
# ============================================================

query = "Explain the SAC-RAG retrieval pipeline."


print("\n" + "=" * 70)
print("UNKNOWN ADAPTIVE RAG END-TO-END TEST")
print("=" * 70)
print(f"Query: {query}")


# ============================================================
# STEP 1: HYBRID RETRIEVAL
# ============================================================

results = retriever.search(query)

print("\n" + "=" * 70)
print("RETRIEVED SOURCES")
print("=" * 70)

for result in results[:3]:
    print(
        f"Rank {result['rank']} | "
        f"{result['document']} | "
        f"Page {result['page']} | "
        f"Hybrid Score {result['hybrid_score']}"
    )


# ============================================================
# STEP 2: CONTEXT BUILDING
# ============================================================

context = builder.build(results)

print("\n" + "=" * 70)
print("CONTEXT PREVIEW")
print("=" * 70)
print(context[:700] + "...")


# ============================================================
# STEP 3: QUERY INTENT DETECTION
# ============================================================

query_type = prompt_engine.detect_query_type(query)

print("\n" + "=" * 70)
print("QUERY INTENT")
print("=" * 70)
print(f"Detected Type: {query_type.value}")


# ============================================================
# STEP 4: ADAPTIVE PROMPT GENERATION
# ============================================================

prompt = prompt_engine.build_prompt(
    query=query,
    context=context,
    query_type=query_type
)

print("\n" + "=" * 70)
print("PROMPT PREVIEW")
print("=" * 70)
print(prompt[:1200] + "...")


# ============================================================
# STEP 5: GEMINI GENERATION
# ============================================================

answer = gemini.generate(prompt)

print("\n" + "=" * 70)
print("GEMINI ANSWER")
print("=" * 70)
print(answer)


# ============================================================
# TEST SUMMARY
# ============================================================

print("\n" + "=" * 70)
print("TEST SUMMARY")
print("=" * 70)
print(f"Retrieved Chunks : {len(results)}")
print(f"Context Length   : {len(context)} characters")
print(f"Query Type       : {query_type.value}")
print(f"Prompt Length    : {len(prompt)} characters")
print(f"Answer Length    : {len(answer)} characters")
print("=" * 70)