from app.rag.llm_engine import GeminiEngine

engine = GeminiEngine()

question = "Explain cloud computing in two lines."

answer = engine.generate(question)

print("\nGemini Response:\n")
print(answer)