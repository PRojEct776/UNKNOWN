"""UNKNOWN X - Cohere provider."""

from __future__ import annotations

import cohere
import httpx

from app.llm.base_provider import BaseProvider, ErrorKind, kind_from_http_status
from app.rag.config import settings


class CohereProvider(BaseProvider):
    """Cohere Chat API provider."""

    provider_name = "cohere"

    def __init__(self) -> None:
        api_key = getattr(settings, "COHERE_API_KEY", None)
        model = getattr(settings, "COHERE_MODEL", None)

        if not api_key:
            raise ValueError("COHERE_API_KEY is not configured.")

        if not model:
            raise ValueError("COHERE_MODEL is not configured.")

        super().__init__(model)

        self.client = cohere.ClientV2(
            api_key=api_key,
            timeout=float(getattr(settings, "LLM_TIMEOUT_S", 10.0)),
        )

    def _call(self, prompt: str, system: str | None = None) -> str:
        messages = []

        if system:
            messages.append(
                {
                    "role": "system",
                    "content": system,
                }
            )

        messages.append(
            {
                "role": "user",
                "content": prompt,
            }
        )

        response = self.client.chat(
            model=self.model,
            messages=messages,
            temperature=settings.TEMPERATURE,
            max_tokens=settings.MAX_OUTPUT_TOKENS,
        )

        content = response.message.content

        if not content:
            raise ValueError("Provider returned an empty response.")

        # Cohere V2 returns content blocks.
        text = "".join(
            block.text
            for block in content
            if getattr(block, "type", None) == "text"
            and getattr(block, "text", None)
        )

        if not text:
            raise ValueError("Provider returned an empty response.")

        return text

    def _classify(self, exc: Exception) -> ErrorKind:
        status_code = getattr(exc, "status_code", None)

        if status_code is None:
            response = getattr(exc, "response", None)
            status_code = getattr(response, "status_code", None)

        if isinstance(status_code, int):
            return kind_from_http_status(status_code)

        if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
            return ErrorKind.TRANSIENT

        return ErrorKind.UNKNOWN