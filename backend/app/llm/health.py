"""
UNKNOWN X - Provider Health Tracker

A small circuit breaker so a failing provider is skipped instead of costing
every request a full timeout.

    RATE_LIMIT        -> benched immediately for `rate_limit_cooldown_s`
    FATAL             -> benched immediately for `fatal_cooldown_s`
    TRANSIENT/EMPTY/
    UNKNOWN           -> benched after `failure_threshold` failures in a row
    INVALID_REQUEST   -> ignored (the request was bad, not the provider)

When a cooldown ends the next request probes the provider; a success closes
the breaker, another failure re-opens it straight away.
Thread-safe: the orchestrator may be called from many worker threads.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.llm.base_provider import ErrorKind, LLMResponse

_EWMA_ALPHA = 0.2


@dataclass(frozen=True, slots=True)
class HealthPolicy:
    failure_threshold: int = 3
    transient_cooldown_s: float = 30.0
    rate_limit_cooldown_s: float = 60.0
    fatal_cooldown_s: float = 300.0


@dataclass(slots=True)
class _State:
    consecutive_failures: int = 0
    open_until: float = 0.0
    successes: int = 0
    failures: int = 0
    avg_latency_ms: float | None = None
    last_error: str | None = None
    last_error_kind: ErrorKind | None = None


class HealthTracker:
    """Tracks per-provider health from LLMResponse objects."""

    def __init__(
        self,
        policy: HealthPolicy | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.policy = policy or HealthPolicy()
        self._clock = clock
        self._lock = threading.Lock()
        self._states: dict[str, _State] = {}

    # ------------------------------------------------------
    # Queries
    # ------------------------------------------------------

    def is_available(self, name: str) -> bool:
        return self.seconds_until_available(name) <= 0.0

    def seconds_until_available(self, name: str) -> float:
        with self._lock:
            state = self._states.get(name)
            if state is None:
                return 0.0
            return max(0.0, state.open_until - self._clock())

    def snapshot(self) -> dict[str, dict[str, Any]]:
        """Plain-dict view of every provider seen so far (for a health endpoint)."""
        now = self._clock()
        with self._lock:
            return {
                name: {
                    "available": now >= s.open_until,
                    "cooldown_remaining_s": round(max(0.0, s.open_until - now), 1),
                    "consecutive_failures": s.consecutive_failures,
                    "successes": s.successes,
                    "failures": s.failures,
                    "avg_latency_ms": (
                        None if s.avg_latency_ms is None else round(s.avg_latency_ms, 1)
                    ),
                    "last_error": s.last_error,
                    "last_error_kind": (
                        s.last_error_kind.value if s.last_error_kind else None
                    ),
                }
                for name, s in self._states.items()
            }

    # ------------------------------------------------------
    # Updates
    # ------------------------------------------------------

    def record(self, response: LLMResponse) -> None:
        with self._lock:
            state = self._states.setdefault(response.provider, _State())

            if response.success:
                state.successes += 1
                state.consecutive_failures = 0
                state.open_until = 0.0
                state.last_error = None
                state.last_error_kind = None
                state.avg_latency_ms = (
                    response.latency_ms
                    if state.avg_latency_ms is None
                    else (1 - _EWMA_ALPHA) * state.avg_latency_ms
                    + _EWMA_ALPHA * response.latency_ms
                )
                return

            kind = response.error_kind or ErrorKind.UNKNOWN
            state.failures += 1
            state.last_error = response.error
            state.last_error_kind = kind

            if kind is ErrorKind.INVALID_REQUEST:
                return  # not the provider's fault

            state.consecutive_failures += 1
            cooldown = self._cooldown_for(kind, state.consecutive_failures)
            if cooldown > 0:
                state.open_until = self._clock() + cooldown

    def reset(self, name: str | None = None) -> None:
        """Clear one provider's state (or all of them)."""
        with self._lock:
            if name is None:
                self._states.clear()
            else:
                self._states.pop(name, None)

    def _cooldown_for(self, kind: ErrorKind, consecutive_failures: int) -> float:
        if kind is ErrorKind.FATAL:
            return self.policy.fatal_cooldown_s
        if kind is ErrorKind.RATE_LIMIT:
            return self.policy.rate_limit_cooldown_s
        if consecutive_failures >= self.policy.failure_threshold:
            return self.policy.transient_cooldown_s
        return 0.0
