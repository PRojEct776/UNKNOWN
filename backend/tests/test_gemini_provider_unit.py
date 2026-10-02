"""
UNKNOWN X v2.3 - Gemini Provider Unit Tests

Run:
    python -m tests.test_gemini_provider_unit
"""

from app.llm.gemini_provider import GeminiProvider


class FakeResponse:
    def __init__(self, text):
        self.text = text
        self.prompt_feedback = None
        self.candidates = []


class FakeModels:
    def __init__(self, response):
        self.response = response

    def generate_content(self, **kwargs):
        return self.response


class FakeClient:
    def __init__(self, response):
        self.models = FakeModels(response)


def test_provider_metadata():
    provider = GeminiProvider()

    assert provider.provider_name == "gemini"
    assert provider.model.startswith("gemini-")

    print("✓ Provider metadata passed.")


def test_generate_success():
    provider = GeminiProvider()

    provider.client = FakeClient(FakeResponse(" Hello UNKNOWN X "))  # type: ignore

    response = provider.generate("Hello")

    assert response.success is True
    assert response.answer == "Hello UNKNOWN X"
    assert response.provider == "gemini"

    print("✓ Generate success passed.")


def test_generate_empty():
    provider = GeminiProvider()

    provider.client = FakeClient(FakeResponse(""))  # type: ignore

    response = provider.generate("Hello")

    assert response.success is False
    assert response.error is not None
    assert "gemini returned no candidates" in response.error.lower()

    print("✓ Empty response handled correctly.")


if __name__ == "__main__":
    print("=" * 60)
    print("UNKNOWN X v2.3 - GEMINI UNIT TESTS")
    print("=" * 60)

    test_provider_metadata()
    test_generate_success()
    test_generate_empty()

    print("=" * 60)
    print("ALL UNIT TESTS PASSED")
    print("=" * 60)
