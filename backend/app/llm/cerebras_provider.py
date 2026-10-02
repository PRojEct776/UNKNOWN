"""UNKNOWN X - Cerebras provider (OpenAI-compatible API)."""

from __future__ import annotations

from app.llm.openai_compat import OpenAICompatProvider
from app.rag.config import settings


class CerebrasProvider(OpenAICompatProvider):
    """Cerebras chat completions."""

    provider_name = "cerebras"

    def __init__(self) -> None:
        super().__init__(
            model=getattr(settings, "CEREBRAS_MODEL", None),
            api_key=getattr(settings, "CEREBRAS_API_KEY", None),
            base_url="https://api.cerebras.ai/v1",
            timeout_s=float(getattr(settings, "LLM_TIMEOUT_S", 10.0)),
            temperature=settings.TEMPERATURE,
            max_tokens=settings.MAX_OUTPUT_TOKENS,
        )
