import pytest
from app.llm.gemini_provider import GeminiProvider


@pytest.mark.slow
def test_gemini_smoke():
    gemini = GeminiProvider()
    question = "Explain cloud computing in two lines."
    response = gemini.generate(question)
    assert response is not None
