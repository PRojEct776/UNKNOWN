"""Query package exports."""

from app.llm.openai_compat import (
    OpenAICompatProvider as OpenAICompatProvider,
)

__all__ = ["OpenAICompatProvider"]
