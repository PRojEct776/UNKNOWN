"""UNKNOWN X - Groq provider (OpenAI-compatible API)."""

from __future__ import annotations

from app.llm.openai_compat import OpenAICompatProvider
from app.rag.config import settings


class GroqProvider(OpenAICompatProvider):
    """Groq chat completions."""

    provider_name = "groq"

    def __init__(self) -> None:
        super().__init__(
            model=getattr(settings, "GROQ_MODEL", None),
            api_key=getattr(settings, "GROQ_API_KEY", None),
            base_url="https://api.groq.com/openai/v1",
            timeout_s=float(getattr(settings, "LLM_TIMEOUT_S", 10.0)),
            temperature=settings.TEMPERATURE,
            max_tokens=settings.MAX_OUTPUT_TOKENS,
        )
