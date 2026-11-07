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

DEFAULT_ORDER = "gemini,groq,cohere,openrouter,cloudflare"
DEFAULT_TOTAL_TIMEOUT_S = 45.0

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

    @staticmethod
    def _compact_prompt(prompt: str, max_chars: int = 7000) -> str:
        """Compact prompt when payload size exceeds provider limits, preserving structure and instructions."""
        if len(prompt) <= max_chars:
            return prompt

        # If comparison prompt has an evidence catalog, compact evidence lines while preserving query & schema
        for marker in ("DOCUMENT EVIDENCE CATALOG:", "DOCUMENT EVIDENCE:"):
            if marker in prompt:
                idx = prompt.find(marker)
                prefix = prompt[: idx + len(marker)]
                rest = prompt[idx + len(marker) :]
                rule_marker = "STRICT RULES:"
                if rule_marker in rest:
                    ev_idx = rest.find(rule_marker)
                    ev_part = rest[:ev_idx]
                    suffix = rest[ev_idx:]
                    ev_lines = ev_part.strip().splitlines()
                    compacted_lines = []
                    total_len = 0
                    max_ev_len = max(800, max_chars - len(prefix) - len(suffix) - 150)
                    for line in ev_lines:
                        if total_len + len(line) < max_ev_len:
                            compacted_lines.append(line)
                            total_len += len(line)
                    compacted_ev = "\n".join(compacted_lines) + "\n[...evidence catalog compacted for model token budget...]\n"
                    return prefix + "\n" + compacted_ev + "\n" + suffix

        head = prompt[: int(max_chars * 0.6)]
        tail = prompt[-int(max_chars * 0.4) :]
        return head + "\n\n[...context compacted for model capacity...]\n\n" + tail

    def generate(self, prompt: str, system: str | None = None) -> LLMResponse:
        start = perf_counter()

        if not prompt or not prompt.strip():
            return self._failure(start, "Prompt is empty.", ErrorKind.INVALID_REQUEST)

        deadline = monotonic() + self.total_timeout_s
        failures: list[str] = []
        last_kind: ErrorKind | None = None
        current_prompt = prompt

        for provider in self._candidates():
            if failures and monotonic() >= deadline:
                logger.warning("LLM time budget spent; not trying further providers.")
                break

            response = provider.generate(current_prompt, system)
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
            if response.error_kind == ErrorKind.PAYLOAD_TOO_LARGE:
                current_prompt = self._compact_prompt(current_prompt)

        return self._failure(start, " | ".join(failures), last_kind)

    def generate_grounded(self, prompt: str) -> LLMResponse:
        """Like generate() but forces temperature=0 per Task A1."""
        start = perf_counter()

        if not prompt or not prompt.strip():
            return self._failure(start, "Prompt is empty.", ErrorKind.INVALID_REQUEST)

        deadline = monotonic() + self.total_timeout_s
        failures: list[str] = []
        last_kind: ErrorKind | None = None
        current_prompt = prompt

        for provider in self._candidates():
            if failures and monotonic() >= deadline:
                logger.warning("LLM grounded time budget spent.")
                break

            # Use temperature-override method when available (Task A1)
            _call_zero = getattr(provider, "generate_at_zero_temperature", None)
            if callable(_call_zero):
                response = _call_zero(current_prompt)
            else:
                response = provider.generate(current_prompt)

            self.health.record(response)

            if response.success:
                return response

            failures.append(f"{response.provider}: {response.error}")
            last_kind = response.error_kind
            if response.error_kind == ErrorKind.PAYLOAD_TOO_LARGE:
                current_prompt = self._compact_prompt(current_prompt)

        return self._failure(start, " | ".join(failures), last_kind)

    def generate_structured(
        self,
        prompt: str,
        system: str | None = None,
        max_attempts: int | None = None,
        time_budget_s: float | None = None,
    ) -> LLMResponse:
        """Generate structured JSON using provider-native support with fallback."""
        start = perf_counter()

        if not prompt or not prompt.strip():
            return self._failure(
                start,
                "Prompt is empty.",
                ErrorKind.INVALID_REQUEST,
            )

        effective_timeout = min(self.total_timeout_s, time_budget_s) if time_budget_s else self.total_timeout_s
        deadline = monotonic() + effective_timeout
        failures: list[str] = []
        last_kind: ErrorKind | None = None
        current_prompt = prompt
        attempts_count = 0

        retried_providers: set[str] = set()

        for provider in self._candidates():
            if failures and monotonic() >= deadline:
                logger.warning(
                    "LLM structured-output time budget spent (deadline exceeded); not trying further providers."
                )
                break

            if max_attempts is not None and attempts_count >= max_attempts:
                logger.warning(
                    "Reached maximum provider attempt limit (%d); stopping structured fallback.",
                    max_attempts,
                )
                break

            attempts_count += 1
            response = provider.generate_structured(current_prompt, system)
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

            # If payload exceeded provider limits, compact and retry at most once
            # Never repeatedly retry the same provider after payload / TPM failure
            if provider.provider_name not in retried_providers and (max_attempts is None or attempts_count < max_attempts):
                if response.error_kind == ErrorKind.PAYLOAD_TOO_LARGE or (response.error and "token limit hit" in response.error):
                    compacted = self._compact_prompt(current_prompt)
                    if compacted != current_prompt:
                        current_prompt = compacted
                        retried_providers.add(provider.provider_name)
                        logger.info("Retrying provider %s with compacted prompt...", provider.provider_name)
                        attempts_count += 1
                        retry_resp = provider.generate_structured(current_prompt, system)
                        self.health.record(retry_resp)
                        if retry_resp.success:
                            return retry_resp
                        failures.append(f"{provider.provider_name} (compacted retry): {retry_resp.error}")
                        last_kind = retry_resp.error_kind

        return self._failure(
            start,
            f"All configured LLM providers failed. Attempts: {'; '.join(failures)}",
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
