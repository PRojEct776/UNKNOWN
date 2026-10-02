from app.llm.gemini_provider import GeminiProvider

gemini = GeminiProvider()

question = "Explain cloud computing in two lines."

response = gemini.generate(question)

print("\nGemini Response:\n")
print(response.answer if response.success else response.error)