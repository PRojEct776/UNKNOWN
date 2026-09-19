"""
UNKNOWN Project - Sprint 3
Prompt Engine Test

Tests:
- Query intent detection
- Adaptive prompt generation
- Programming-language edge cases
"""

from app.rag.prompt_engine import PromptEngine, QueryType


engine = PromptEngine()


# ---------------------------------------------------------
# Query Intent Tests
# ---------------------------------------------------------

test_cases = [
    ("What is cloud computing?", QueryType.DEFINITION),
    ("When was Python created?", QueryType.FACT),
    ("Why is RAG better than fine tuning?", QueryType.REASONING),
    ("Compare Docker vs Kubernetes.", QueryType.COMPARISON),
    ("Write binary search in Java.", QueryType.CODE),
    ("Write Python code for binary search.", QueryType.CODE),
    ("What is Python?", QueryType.DEFINITION),
    ("Summarize this IEEE paper.", QueryType.SUMMARY),
    ("Tell me about virtualization.", QueryType.GENERAL),

    # Programming-language edge cases
    ("When was Java created?", QueryType.FACT),
    ("When was JavaScript created?", QueryType.FACT),
    ("When was Rust created?", QueryType.FACT),
    ("Implement quicksort using C++.", QueryType.CODE),
    ("How do I implement a stack in C#?", QueryType.CODE),
    ("Create a Java program for binary search.", QueryType.CODE),
]


print("=" * 70)
print("UNKNOWN PROMPT ENGINE TEST")
print("=" * 70)


for query, expected_type in test_cases:

    actual_type = engine.detect_query_type(query)

    print(f"\nQuery    : {query}")
    print(f"Expected : {expected_type.value}")
    print(f"Actual   : {actual_type.value}")

    assert actual_type == expected_type, (
        f"FAILED: '{query}' "
        f"expected '{expected_type.value}' "
        f"but got '{actual_type.value}'"
    )

    print("Status   : PASS")


# ---------------------------------------------------------
# Prompt Generation Test
# ---------------------------------------------------------

print("\n" + "=" * 70)
print("PROMPT GENERATION TEST")
print("=" * 70)


sample_context = """
Cloud computing provides on-demand computing resources
over the internet.
Virtualization allows multiple virtual machines to share
physical hardware.
"""

query = "What is virtualization?"

prompt = engine.build_prompt(
    query=query,
    context=sample_context
)

print("\nGenerated Prompt Preview:")
print("-" * 70)
print(prompt[:800])
print("-" * 70)


# Verify important prompt components
assert "UNKNOWN AI" in prompt
assert "Task Type: definition" in prompt
assert "Answer ONLY using the retrieved context." in prompt
assert (
    "The retrieved context does not contain enough information."
    in prompt
)
assert sample_context.strip() in prompt
assert query in prompt

print("Prompt structure : PASS")


# ---------------------------------------------------------
# Final Result
# ---------------------------------------------------------

print("\n" + "=" * 70)
print("ALL PROMPT ENGINE TESTS PASSED ✅")
print("=" * 70)