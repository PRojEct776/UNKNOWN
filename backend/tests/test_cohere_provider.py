from types import SimpleNamespace

import httpx

from app.llm.base_provider import ErrorKind
from app.llm.cohere_provider import CohereProvider


def test_cohere_success_with_system_prompt():
    provider = object.__new__(CohereProvider)
    provider.model = "command-a-03-2025"

    class FakeClient:
        def chat(self, **kwargs):
            assert kwargs["model"] == "command-a-03-2025"
            assert kwargs["messages"][0] == {
                "role": "system",
                "content": "Be concise.",
            }
            assert kwargs["messages"][1] == {
                "role": "user",
                "content": "What is RAG?",
            }

            return SimpleNamespace(
                message=SimpleNamespace(
                    content=[
                        SimpleNamespace(type="text", text="RAG retrieves context.")
                    ]
                )
            )

    provider.client = FakeClient()

    response = provider.generate("What is RAG?", "Be concise.")

    assert response.success
    assert response.answer == "RAG retrieves context."
    assert response.provider == "cohere"
    assert response.model == "command-a-03-2025"


def test_cohere_empty_response():
    provider = object.__new__(CohereProvider)
    provider.model = "command-a-03-2025"

    class FakeClient:
        def chat(self, **kwargs):
            return SimpleNamespace(
                message=SimpleNamespace(content=[])
            )

    provider.client = FakeClient()

    response = provider.generate("test")

    assert not response.success
    assert response.error_kind is ErrorKind.EMPTY


def test_cohere_timeout_is_transient():
    provider = object.__new__(CohereProvider)
    provider.model = "command-a-03-2025"

    class FakeClient:
        def chat(self, **kwargs):
            raise httpx.ReadTimeout(
                "request timed out",
                request=httpx.Request("POST", "https://example.test"),
            )

    provider.client = FakeClient()

    response = provider.generate("test")

    assert not response.success
    assert response.error_kind is ErrorKind.TRANSIENT


def test_cohere_rate_limit_is_classified():
    provider = object.__new__(CohereProvider)

    class FakeClient:
        def chat(self, **kwargs):
            error = RuntimeError("rate limited")
            error.status_code = 429
            raise error

    provider.client = FakeClient()
    provider.model = "command-a-03-2025"

    response = provider.generate("test")

    assert not response.success
    assert response.error_kind is ErrorKind.RATE_LIMIT