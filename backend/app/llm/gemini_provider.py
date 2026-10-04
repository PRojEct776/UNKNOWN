"""
UNKNOWN X - Gemini provider

Google Gemini via the official google-genai SDK.
Single attempt, no hidden retries: fallback and cooldown belong to the
orchestrator. Thinking is capped because RAG answers rarely need it, and
thinking tokens count against max_output_tokens.
"""

from __future__ import annotations

from typing import Any

import httpx
from google import genai
from google.genai import errors, types

from app.llm.base_provider import (
    BaseProvider,
    ErrorKind,
    LLMError,
    kind_from_http_status,
)
from app.rag.config import settings
from app.rag.logger import logger

_LEVEL_TO_BUDGET = {"MINIMAL": 0, "LOW": 1024, "MEDIUM": 4096, "HIGH": 8192}
_PRO_MIN_BUDGET = 128  # 2.5 Pro cannot disable thinking
_BLOCKED_FINISH = frozenset(
    {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "RECITATION"}
)


def _model_name(model: str) -> str:
    return model.strip().lower().removeprefix("models/")


def resolve_thinking(model: str, level: str) -> types.ThinkingConfig | None:
    """Translate one LOW/MEDIUM/... setting into what this model family accepts.

    Returns None for unrecognised model names (API default is then used).
    """
    level = level.strip().upper()
    if level not in _LEVEL_TO_BUDGET:
        raise ValueError(
            f"Invalid GEMINI_THINKING_LEVEL: {level!r} "
            f"(use one of {sorted(_LEVEL_TO_BUDGET)})"
        )

    name = _model_name(model)

    if name.startswith("gemini-3"):
        if "pro" in name:  # 3 Pro accepts only LOW and HIGH
            level = "LOW" if level in ("MINIMAL", "LOW") else "HIGH"
        return types.ThinkingConfig(thinking_level=level)  # type: ignore

    if name.startswith("gemini-2.5"):
        budget = _LEVEL_TO_BUDGET[level]
        if "2.5-pro" in name:
            budget = max(budget, _PRO_MIN_BUDGET)
        return types.ThinkingConfig(thinking_budget=budget)

    return None


def _enum_name(value: Any) -> str:
    return str(getattr(value, "name", None) or value)


class GeminiProvider(BaseProvider):
    """Google Gemini provider."""

    provider_name = "gemini"

    def __init__(self) -> None:
        if not settings.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY not found in backend/.env")

        super().__init__(settings.GEMINI_MODEL)

        # One reusable client (connection pool). No retry_options => no SDK retries.
        self.client = genai.Client(
            api_key=settings.GOOGLE_API_KEY,
            http_options=types.HttpOptions(timeout=settings.GEMINI_TIMEOUT_MS),
        )

        self._config_kwargs = self._build_config_kwargs()
        self._config = types.GenerateContentConfig(**self._config_kwargs)

        logger.info("Gemini provider ready: model=%s", self.model)

    def _build_config_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"max_output_tokens": settings.MAX_OUTPUT_TOKENS}

        thinking = resolve_thinking(self.model, settings.GEMINI_THINKING_LEVEL)
        if thinking is None:
            logger.warning(
                "Unrecognised Gemini model %r: thinking left at the API default.",
                self.model,
            )
        else:
            kwargs["thinking_config"] = thinking

        # Google recommends leaving temperature at its default on Gemini 3.
        if _model_name(self.model).startswith("gemini-2.5"):
            kwargs["temperature"] = settings.TEMPERATURE

        return kwargs

    def _call(self, prompt: str, system: str | None = None) -> str:
        config = (
            types.GenerateContentConfig(
                **self._config_kwargs, system_instruction=system
            )
            if system
            else self._config
        )

        response = self.client.models.generate_content(  # type: ignore
            model=self.model,
            contents=prompt,
            config=config,
        )

        text = response.text
        if text and text.strip():
            return text
        raise self._empty_error(response)

    def _call_structured(
        self,
        prompt: str,
        system: str | None = None,
    ) -> str:
        """Call Gemini with native JSON output enabled."""
        config_kwargs = {
            **self._config_kwargs,
            "response_mime_type": "application/json",
        }

        if system:
            config_kwargs["system_instruction"] = system

        config = types.GenerateContentConfig(**config_kwargs)

        response = self.client.models.generate_content(  # type: ignore
            model=self.model,
            contents=prompt,
            config=config,
        )

        text = response.text
        if text and text.strip():
            return text

        raise self._empty_error(response)

    @staticmethod
    def _empty_error(response: Any) -> LLMError:
        block = getattr(
            getattr(response, "prompt_feedback", None), "block_reason", None
        )
        if block:
            return LLMError(
                ErrorKind.INVALID_REQUEST,
                f"Prompt blocked by Gemini (block_reason={_enum_name(block)}).",
            )

        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            return LLMError(ErrorKind.EMPTY, "Gemini returned no candidates.")

        finish = _enum_name(getattr(candidates[0], "finish_reason", None))
        if finish in _BLOCKED_FINISH:
            return LLMError(ErrorKind.INVALID_REQUEST, f"Response blocked ({finish}).")

        hint = (
            " (token limit hit; thinking shares the budget - raise "
            "MAX_OUTPUT_TOKENS or lower GEMINI_THINKING_LEVEL)"
            if finish == "MAX_TOKENS"
            else ""
        )
        return LLMError(
            ErrorKind.EMPTY, f"Empty Gemini response, finish_reason={finish}{hint}."
        )

    def _classify(self, exc: Exception) -> ErrorKind:
        if isinstance(exc, errors.APIError):
            code = exc.code
            # Gemini reports a bad API key as 400 INVALID_ARGUMENT.
            text = str(exc)
            if code == 400 and (
                "API_KEY_INVALID" in text or "API key not valid" in text
            ):
                return ErrorKind.FATAL
            if isinstance(code, int):
                return kind_from_http_status(code)
            return ErrorKind.UNKNOWN

        if isinstance(exc, (httpx.TransportError, TimeoutError, ConnectionError)):
            return ErrorKind.TRANSIENT
        return ErrorKind.UNKNOWN

    def close(self) -> None:
        close = getattr(self.client, "close", None)
        if callable(close):
            close()

    client = None
