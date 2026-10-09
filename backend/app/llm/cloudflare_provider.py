
"""UNKNOWN X - Cloudflare Workers AI provider."""

from __future__ import annotations

from app.llm.openai_compat import OpenAICompatProvider
from app.rag.config import settings


class CloudflareProvider(OpenAICompatProvider):
    """Cloudflare Workers AI chat completions."""

    provider_name = "cloudflare"

    def __init__(self) -> None:
        account_id = getattr(settings, "CLOUDFLARE_ACCOUNT_ID", "").strip()

        if not account_id:
            raise ValueError("CLOUDFLARE_ACCOUNT_ID is not configured.")

        super().__init__(
            model=getattr(
                settings,
                "CLOUDFLARE_MODEL",
                "@cf/meta/llama-3.1-8b-instruct",
            ),
            api_key=getattr(settings, "CLOUDFLARE_API_TOKEN", None),
            base_url=(
                "https://api.cloudflare.com/client/v4/accounts/"
                f"{account_id}/ai/v1"
            ),
            timeout_s=float(getattr(settings, "LLM_TIMEOUT_S", 10.0)),
            temperature=settings.TEMPERATURE,
            max_tokens=settings.MAX_OUTPUT_TOKENS,
        )
