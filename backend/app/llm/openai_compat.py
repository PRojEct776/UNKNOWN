"""
UNKNOWN X - OpenAI-compatible provider base

Groq, Cerebras and OpenRouter all speak the OpenAI chat-completions protocol,
so they share this one implementation (and one SDK) instead of three copies.
Subclasses only supply their name, base URL and settings.
"""

from __future__ import annotations

from typing import Any, ClassVar

import httpx
import openai
from openai import OpenAI

from app.llm.base_provider import (
    BaseProvider,
    ErrorKind,
    LLMError,
    kind_from_http_status,
)

_CONNECT_TIMEOUT_S = 5.0


def _error_from_body(body_error: Any) -> LLMError:
    """Some gateways (e.g. OpenRouter) return HTTP 200 with an error object."""
    if isinstance(body_error, dict):
        code = body_error.get("code")
        message = body_error.get("message") or str(body_error)
    else:
        code = getattr(body_error, "code", None)
        message = getattr(body_error, "message", None) or str(body_error)

    kind = (
        kind_from_http_status(code)
        if isinstance(code, int) and not isinstance(code, bool)
        else ErrorKind.TRANSIENT
    )
    return LLMError(kind, f"Upstream error in response body: {message}")


class OpenAICompatProvider(BaseProvider):
    """Single-attempt chat-completions call against an OpenAI-style API."""

    # Groq and Cerebras use max_completion_tokens; OpenRouter overrides this.
    max_tokens_param: ClassVar[str] = "max_completion_tokens"

    def __init__(
        self,
        *,
        model: str | None,
        api_key: str | None,
        base_url: str,
        timeout_s: float,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> None:
        if not model:
            raise ValueError(f"{self.provider_name}: model is not configured.")
        if not api_key:
            raise ValueError(f"{self.provider_name}: API key is not configured.")

        super().__init__(model)

        # max_retries=0: the SDK's hidden retries would break the latency
        # budget. Retry/fallback decisions belong to the orchestrator.
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=httpx.Timeout(
                timeout_s, connect=min(_CONNECT_TIMEOUT_S, timeout_s)
            ),  # type: ignore
            max_retries=0,
        )

        params = {"temperature": temperature, self.max_tokens_param: max_tokens}
        self._params = {k: v for k, v in params.items() if v is not None}

    def _call(self, prompt: str, system: str | None = None) -> str:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore
            **self._params,
        )  # type: ignore
        return self._extract_text(response)

    @staticmethod
    def _extract_text(response: Any) -> str:
        body_error = getattr(response, "error", None)
        if body_error:
            raise _error_from_body(body_error)

        choices = getattr(response, "choices", None) or []
        if not choices:
            raise LLMError(ErrorKind.EMPTY, "Response contained no choices.")

        choice = choices[0]
        text = getattr(getattr(choice, "message", None), "content", None)
        if isinstance(text, str) and text.strip():
            return text

        finish = getattr(choice, "finish_reason", None)
        hint = (
            " (token limit hit; raise MAX_OUTPUT_TOKENS)" if finish == "length" else ""
        )
        raise LLMError(
            ErrorKind.EMPTY, f"Empty response, finish_reason={finish}{hint}."
        )

    def _classify(self, exc: Exception) -> ErrorKind:
        if isinstance(exc, openai.APIStatusError):
            return kind_from_http_status(exc.status_code)  # type: ignore
        if isinstance(
            exc,
            (
                openai.APIConnectionError,
                httpx.TransportError,
                TimeoutError,
                ConnectionError,
            ),
        ):
            return ErrorKind.TRANSIENT
        return ErrorKind.UNKNOWN

    def close(self) -> None:
        self.client.close()
