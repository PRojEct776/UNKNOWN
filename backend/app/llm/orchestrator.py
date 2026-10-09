"""
UNKNOWN X - LLM Orchestrator

Tries providers in priority order and returns the first successful answer.

    * skips providers the health tracker has benched (no wasted timeouts)
    * stops starting new providers once the total time budget is spent
    * if every provider is benched, probes the one that reopens first
      instead of failing instantly
    * `generate()` never raises

Order comes from LLM_PROVIDER_ORDER (default: gemini,groq,cerebras,openrouter).
Providers whose key/model is missing are skipped with a warning, so the app
still starts with whichever providers are configured.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Sequence
from time import monotonic, perf_counter
from typing import Any

from app.llm.base_provider import BaseProvider, ErrorKind, LLMResponse
from app.llm.cloudflare_provider import CloudflareProvider
from app.llm.cohere_provider import CohereProvider
from app.llm.gemini_provider import GeminiProvider
from app.llm.groq_provider import GroqProvider
from app.llm.health import HealthTracker
from app.llm.openrouter_provider import OpenRouterProvider
from app.rag.config import settings
from app.rag.logger import logger

DEFAULT_ORDER = "gemini,groq,cerebras,openrouter"
DEFAULT_TOTAL_TIMEOUT_S = 25.0

_REGISTRY: dict[str, type[BaseProvider]] = {
    "gemini": GeminiProvider,
    "groq": GroqProvider,
    "cohere": CohereProvider,
    "openrouter": OpenRouterProvider,
    "cloudflare": CloudflareProvider,
}


class LLMOrchestrator:
    """Priority-ordered fallback across LLM providers."""

    def __init__(
        self,
        providers: Sequence[BaseProvider],
        health: HealthTracker | None = None,
        total_timeout_s: float = DEFAULT_TOTAL_TIMEOUT_S,
    ) -> None:
        if not providers:
            raise ValueError("LLMOrchestrator needs at least one provider.")
        self.providers: list[BaseProvider] = list(providers)
        self.health = health or HealthTracker()
        self.total_timeout_s = total_timeout_s

    # ------------------------------------------------------
    # Construction
    # ------------------------------------------------------

    @classmethod
    def from_settings(cls) -> LLMOrchestrator:
        raw = str(getattr(settings, "LLM_PROVIDER_ORDER", DEFAULT_ORDER))
        names = list(
            dict.fromkeys(n.strip().lower() for n in raw.split(",") if n.strip())
        )

        providers: list[BaseProvider] = []
        for name in names:
            factory = _REGISTRY.get(name)
            if factory is None:
                logger.warning(
                    "Unknown provider %r in LLM_PROVIDER_ORDER - skipped.", name
                )
                continue
            try:
                # One misconfigured provider must not stop the app from starting.
                providers.append(factory())  # type: ignore
            except Exception as exc:  # noqa: BLE001
                logger.warning("Provider %r disabled: %s", name, exc)

        if not providers:
            raise RuntimeError(
                "No LLM provider could be initialised. "
                "Check API keys and model names in backend/.env."
            )

        logger.info(
            "LLM providers active (in order): %s", [p.provider_name for p in providers]
        )
        return cls(
            providers,
            total_timeout_s=float(
                getattr(settings, "LLM_TOTAL_TIMEOUT_S", DEFAULT_TOTAL_TIMEOUT_S)
            ),
        )

    # ------------------------------------------------------
    # Generation
    # ------------------------------------------------------

    def generate(self, prompt: str, system: str | None = None) -> LLMResponse:
        start = perf_counter()

        if not prompt or not prompt.strip():
            return self._failure(start, "Prompt is empty.", ErrorKind.INVALID_REQUEST)

        deadline = monotonic() + self.total_timeout_s
        failures: list[str] = []
        last_kind: ErrorKind | None = None

        for provider in self._candidates():
            if failures and monotonic() >= deadline:
                logger.warning("LLM time budget spent; not trying further providers.")
                break

            response = provider.generate(prompt, system)
            self.health.record(response)

            if response.success:
                if failures:
                    logger.info(
                        "Answered by fallback provider %s after: %s",
                        response.provider,
                        "; ".join(failures),
                    )
                return response

            failures.append(f"{response.provider}: {response.error}")
            last_kind = response.error_kind

        return self._failure(start, " | ".join(failures), last_kind)

    def generate_structured(
        self,
        prompt: str,
        system: str | None = None,
    ) -> LLMResponse:
        """Generate structured JSON using provider-native support with fallback."""
        start = perf_counter()

        if not prompt or not prompt.strip():
            return self._failure(
                start,
                "Prompt is empty.",
                ErrorKind.INVALID_REQUEST,
            )

        deadline = monotonic() + self.total_timeout_s
        failures: list[str] = []
        last_kind: ErrorKind | None = None

        for provider in self._candidates():
            if failures and monotonic() >= deadline:
                logger.warning(
                    "LLM structured-output time budget spent; "
                    "not trying further providers."
                )
                break

            response = provider.generate_structured(prompt, system)
            self.health.record(response)

            if response.success:
                if failures:
                    logger.info(
                        "Structured answer supplied by fallback provider %s after: %s",
                        response.provider,
                        "; ".join(failures),
                    )
                return response

            failures.append(f"{response.provider}: {response.error}")
            last_kind = response.error_kind

        return self._failure(
            start,
            " | ".join(failures),
            last_kind,
        )

    async def agenerate(self, prompt: str, system: str | None = None) -> LLMResponse:
        """Async wrapper: runs the blocking call in a worker thread."""
        return await asyncio.to_thread(self.generate, prompt, system)

    def _candidates(self) -> list[BaseProvider]:
        available = [
            p for p in self.providers if self.health.is_available(p.provider_name)
        ]
        if available:
            return available
        # Everything is cooling down: probe whichever reopens first.
        soonest = min(
            self.providers,
            key=lambda p: self.health.seconds_until_available(p.provider_name),
        )
        logger.warning(
            "All providers are cooling down; probing %s.", soonest.provider_name
        )
        return [soonest]

    @staticmethod
    def _failure(start: float, error: str, kind: ErrorKind | None) -> LLMResponse:
        return LLMResponse(
            answer="",
            provider="orchestrator",
            model="",
            latency_ms=round((perf_counter() - start) * 1000, 2),
            success=False,
            error=error,
            error_kind=kind,
        )

    # ------------------------------------------------------
    # Introspection / lifecycle
    # ------------------------------------------------------

    def status(self) -> dict[str, Any]:
        """Provider order, models and live health - suitable for /health."""
        health = self.health.snapshot()
        return {
            "providers": [
                {
                    "name": p.provider_name,
                    "model": p.model,
                    **health.get(p.provider_name, {"available": True}),
                }
                for p in self.providers
            ]
        }

    def close(self) -> None:
        for provider in self.providers:
            try:
                provider.close()
            except Exception as exc:  # noqa: BLE001 - keep closing the rest
                logger.warning("Error closing %s: %s", provider.provider_name, exc)


# ----------------------------------------------------------
# Process-wide instance (build once, reuse connection pools)
# ----------------------------------------------------------

_instance: LLMOrchestrator | None = None
_instance_lock = threading.Lock()


def get_orchestrator() -> LLMOrchestrator:
    """Return the shared orchestrator, creating it on first use."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = LLMOrchestrator.from_settings()
    return _instance
