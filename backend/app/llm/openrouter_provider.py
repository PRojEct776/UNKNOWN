"""UNKNOWN X - OpenRouter provider (OpenAI-compatible API)."""

from __future__ import annotations

from typing import ClassVar

from app.llm.openai_compat import OpenAICompatProvider
from app.rag.config import settings


class OpenRouterProvider(OpenAICompatProvider):
    """OpenRouter chat completions."""

    provider_name = "openrouter"
    max_tokens_param: ClassVar[str] = "max_tokens"

    def __init__(self) -> None:
        super().__init__(
            model=getattr(settings, "OPENROUTER_MODEL", None),
            api_key=getattr(settings, "OPENROUTER_API_KEY", None),
            base_url="https://openrouter.ai/api/v1",
            timeout_s=float(getattr(settings, "LLM_TIMEOUT_S", 10.0)),
            temperature=settings.TEMPERATURE,
            max_tokens=settings.MAX_OUTPUT_TOKENS,
        )
