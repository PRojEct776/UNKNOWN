"""
UNKNOWN X - Base LLM Provider

The shared contract for every provider (Gemini, Groq, Cerebras, OpenRouter):

    ErrorKind / LLMError - one error vocabulary for the whole LLM layer
    LLMResponse          - one response shape
    BaseProvider         - timing, error handling and validation, written once

A concrete provider implements `_call` and, if it can, `_classify`.
`generate()` never raises, so the orchestrator can always fall back.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from time import perf_counter
from typing import ClassVar

from app.rag.logger import logger

_MAX_ERROR_CHARS = 500


class ErrorKind(str, Enum):
    """Why a call failed - this is what the health tracker acts on."""

    RATE_LIMIT = "rate_limit"
    TRANSIENT = "transient"
    FATAL = "fatal"
    INVALID_REQUEST = "invalid_request"
    EMPTY = "empty"
    UNKNOWN = "unknown"


class LLMError(Exception):
    """Raise from `_call` when the provider already knows the error kind."""

    def __init__(self, kind: ErrorKind, message: str) -> None:
        super().__init__(message)
        self.kind = kind


def kind_from_http_status(status: int) -> ErrorKind:
    """Map an HTTP status code to an ErrorKind."""
    if status in (401, 402, 403, 404):
        return ErrorKind.FATAL
    if status == 429:
        return ErrorKind.RATE_LIMIT
    if status in (408, 499) or status >= 500:
        return ErrorKind.TRANSIENT
    if 400 <= status < 500:
        return ErrorKind.INVALID_REQUEST
    return ErrorKind.UNKNOWN


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """Standard response returned by every provider."""

    answer: str
    provider: str
    model: str
    latency_ms: float
    success: bool
    error: str | None = None
    error_kind: ErrorKind | None = None


class BaseProvider(ABC):
    """Base class: measures latency, catches errors, returns LLMResponse."""

    provider_name: ClassVar[str] = "base"

    def __init__(self, model: str) -> None:
        self.model = model

    @abstractmethod
    def _call(self, prompt: str, system: str | None = None) -> str:
        """Call the vendor API once and return the text. Raise on failure."""

    def _classify(self, exc: Exception) -> ErrorKind:
        """Map a vendor exception to an ErrorKind. Override per provider."""
        return ErrorKind.UNKNOWN

    def close(self) -> None:
        """Release network resources. Override if the client needs closing."""

    def generate(self, prompt: str, system: str | None = None) -> LLMResponse:
        """Run one call. Never raises; failures come back as success=False."""
        start = perf_counter()
        answer = ""
        error: str | None = None
        kind: ErrorKind | None = None

        try:
            if system is None:
                text = self._call(prompt)
            else:
                text = self._call(prompt, system)

            if text is None:
                raise ValueError("Provider returned None.")

            if not isinstance(text, str):
                raise ValueError("Provider returned an empty response.")  # noqa: TRY004

            answer = text.strip()

            if not answer:
                raise ValueError("Provider returned an empty response.")

        except Exception as exc:  # noqa: BLE001 - every failure must be reported
            answer = ""
            kind = self._kind_of(exc)
            error = f"{type(exc).__name__}: {str(exc)[:_MAX_ERROR_CHARS]}"

            logger.warning(
                "[%s/%s] %s failure: %s",
                self.provider_name,
                self.model,
                kind.value,
                error,
            )

        return LLMResponse(
            answer=answer,
            provider=self.provider_name,
            model=self.model,
            latency_ms=round((perf_counter() - start) * 1000, 2),
            success=error is None,
            error=error,
            error_kind=kind,
        )

    def generate_structured(
        self,
        prompt: str,
        system: str | None = None,
    ) -> LLMResponse:
        """Run one structured-output call with provider-specific JSON support."""
        start = perf_counter()
        answer = ""
        error: str | None = None
        kind: ErrorKind | None = None

        try:
            call = getattr(self, "_call_structured", None)

            if call is None:
                return self.generate(prompt, system)

            if system is None:
                text = call(prompt)
            else:
                text = call(prompt, system)

            if text is None:
                raise ValueError("Provider returned None.")

            if not isinstance(text, str):
                raise ValueError("Provider returned an empty response.")  # noqa: TRY004

            answer = text.strip()

            if not answer:
                raise ValueError("Provider returned an empty response.")

        except Exception as exc:  # noqa: BLE001
            answer = ""
            kind = self._kind_of(exc)
            error = f"{type(exc).__name__}: {str(exc)[:_MAX_ERROR_CHARS]}"

            logger.warning(
                "[%s/%s] structured %s failure: %s",
                self.provider_name,
                self.model,
                kind.value,
                error,
            )

        return LLMResponse(
            answer=answer,
            provider=self.provider_name,
            model=self.model,
            latency_ms=round((perf_counter() - start) * 1000, 2),
            success=error is None,
            error=error,
            error_kind=kind,
        )

    def _kind_of(self, exc: Exception) -> ErrorKind:
        if isinstance(exc, LLMError):
            return exc.kind

        if isinstance(exc, ValueError):
            message = str(exc).lower()
            if "provider returned none" in message:
                return ErrorKind.EMPTY
            if "provider returned an empty response" in message:
                return ErrorKind.EMPTY

        try:
            kind = self._classify(exc)
            if kind is None:
                return ErrorKind.UNKNOWN
            return kind
        except Exception:  # noqa: BLE001 - a broken classifier must not mask the error
            return ErrorKind.UNKNOWN
