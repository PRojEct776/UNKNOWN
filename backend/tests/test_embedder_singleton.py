from app.rag.embedder import embed_text

print("=" * 60)
print("EMBEDDER SINGLETON TEST")
print("=" * 60)

queries = [
    "What is virtualization?",
    "Explain cloud computing.",
    "Difference between VM and Docker."
]

for i, query in enumerate(queries, start=1):
    print(f"\nQuery {i}: {query}")
    embedding = embed_text(query)
    print(f"Embedding Shape: {embedding.shape}")

print("\nTest Completed Successfully!")
