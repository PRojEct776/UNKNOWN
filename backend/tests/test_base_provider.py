"""
UNKNOWN X v2.2 - Base Provider Tests

Run using:

    python -m tests.test_base_provider

or

    pytest tests/test_base_provider.py
"""

from dataclasses import FrozenInstanceError

from app.llm.base_provider import BaseProvider, LLMResponse

# ==========================================================
# Dummy Providers
# ==========================================================


class DummyProvider(BaseProvider):
    provider_name = "dummy"

    def __init__(self):
        super().__init__("dummy-model")

    def _call(self, prompt: str) -> str:
        # Intentionally includes whitespace.
        return f"  Echo: {prompt}  "


class FailingProvider(BaseProvider):
    provider_name = "fail"

    def __init__(self):
        super().__init__("fail-model")

    def _call(self, prompt: str) -> str:
        raise RuntimeError("Provider unavailable")


class EmptyProvider(BaseProvider):
    provider_name = "empty"

    def __init__(self):
        super().__init__("empty-model")

    def _call(self, prompt: str) -> str:
        return "     "


class NoneProvider(BaseProvider):
    provider_name = "none"

    def __init__(self):
        super().__init__("none-model")

    def _call(self, prompt: str):
        return None


# ==========================================================
# Tests
# ==========================================================


def test_success():
    provider = DummyProvider()
    response = provider.generate("Hello UNKNOWN")

    assert response.success is True
    assert response.provider == "dummy"
    assert response.model == "dummy-model"
    assert response.answer == "Echo: Hello UNKNOWN"
    assert response.error is None
    assert response.latency_ms >= 0


def test_failure():
    provider = FailingProvider()
    response = provider.generate("Hello")

    assert response.success is False
    assert response.answer == ""
    assert response.error == "RuntimeError: Provider unavailable"


def test_empty_response():
    provider = EmptyProvider()
    response = provider.generate("Hello")

    assert response.success is False
    assert response.answer == ""
    assert response.error == ("ValueError: Provider returned an empty response.")


def test_none_response():
    provider = NoneProvider()
    response = provider.generate("Hello")

    assert response.success is False
    assert response.answer == ""
    assert response.error == ("ValueError: Provider returned None.")


def test_answer_is_stripped():
    provider = DummyProvider()
    response = provider.generate("Hello")

    assert response.answer == "Echo: Hello"


def test_immutable():
    response = LLMResponse(
        answer="Hi",
        provider="gemini",
        model="gemini-3.6-flash",
        latency_ms=100.0,
        success=True,
    )

    try:
        response.answer = "Changed"
    except FrozenInstanceError:
        return

    raise AssertionError("LLMResponse should be immutable.")


# ==========================================================
# Direct Execution
# ==========================================================

if __name__ == "__main__":

    test_success()
    test_failure()
    test_empty_response()
    test_none_response()
    test_answer_is_stripped()
    test_immutable()

    print("=" * 50)
    print("UNKNOWN X v2.2 - BASE PROVIDER TESTS PASSED")
    print("=" * 50)
