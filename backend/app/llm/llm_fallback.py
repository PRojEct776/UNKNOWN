"""Bounded, quota-aware LLM fallback helpers.

Fixes:
  * Gemini retried 429 quota errors and ran 3 models x 2 attempts, eating the 25 s budget.
  * One slow provider could consume the whole budget before others ran.
  * Quota-exhausted providers were benched for only 60 s.
"""
from __future__ import annotations

import time
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional

QUOTA_BENCH_SECONDS = 15 * 60   # quota 429 -> bench long
TRANSIENT_BENCH_SECONDS = 60


def is_quota_error(err: Any) -> bool:
    """True for quota exhaustion (retrying is pointless)."""
    text = str(err).lower()
    return (
        "resource_exhausted" in text
        or "quota" in text
        or ("429" in text and "exceeded" in text)
    )


def is_rate_limit(err: Any) -> bool:
    text = str(err).lower()
    return "429" in text or "rate limit" in text or "resource_exhausted" in text


class Bench:
    """Thread-safe provider bench with per-provider expiry."""

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._until: dict[str, float] = {}
        self._lock = threading.Lock()
        self._clock = clock

    def bench(self, name: str, seconds: float) -> None:
        with self._lock:
            self._until[name] = max(self._until.get(name, 0.0), self._clock() + seconds)

    def is_benched(self, name: str) -> bool:
        with self._lock:
            return self._clock() < self._until.get(name, 0.0)


# ---------------------------------------------------------------- Gemini chain
@dataclass
class ChainResult:
    ok: bool
    text: Optional[str] = None
    model: Optional[str] = None      # model that ACTUALLY answered
    error: Optional[str] = None
    quota: bool = False
    tried: list = field(default_factory=list)


def bounded_model_chain(
    models: Iterable[str],
    attempt: Callable[[str, float], str],
    budget_s: float,
    per_call_timeout: float = 10.0,
    clock: Callable[[], float] = time.monotonic,
) -> ChainResult:
    """One attempt per model. Quota error stops the chain immediately.
    Never exceeds budget_s. attempt(model, timeout) returns text or raises."""
    deadline = clock() + budget_s
    res = ChainResult(ok=False)
    for model in models:
        remaining = deadline - clock()
        if remaining <= 0.5:
            res.error = res.error or "chain budget exhausted"
            break
        try:
            text = attempt(model, min(per_call_timeout, remaining))
            res.ok, res.text, res.model = True, text, model
            res.tried.append((model, "ok"))
            return res
        except Exception as e:  # noqa: BLE001
            res.error = f"{type(e).__name__}: {e}"
            res.tried.append((model, res.error[:120]))
            if is_quota_error(e):
                res.quota = True
                break          # lite models share the quota; don't try them
    return res


# ---------------------------------------------------------------- Orchestrator
@dataclass
class FallbackResult:
    ok: bool
    provider: Optional[str] = None
    value: Any = None
    attempts: list = field(default_factory=list)   # (provider, status, seconds)
    budget_spent: bool = False


_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="llm")


def run_fallback(
    providers: list[str],
    call: Callable[[str, float], Any],
    is_success: Callable[[Any], bool],
    total_budget: float = 25.0,
    slice_s: float = 10.0,
    bench: Optional[Bench] = None,
    clock: Callable[[], float] = time.monotonic,
) -> FallbackResult:
    """Try providers in order. Each gets min(slice_s, remaining) seconds, so no
    single provider can starve the rest. call(provider, timeout) -> response;
    exceptions and is_success(resp)==False both advance to the next provider."""
    bench = bench or Bench()
    deadline = clock() + total_budget
    out = FallbackResult(ok=False)
    for name in providers:
        if bench.is_benched(name):
            out.attempts.append((name, "benched", 0.0))
            continue
        remaining = deadline - clock()
        if remaining <= 0.5:
            out.budget_spent = True
            break
        timeout = min(slice_s, remaining)
        t0 = clock()
        fut = _pool.submit(call, name, timeout)
        try:
            resp = fut.result(timeout=timeout + 1.0)
        except FutureTimeout:
            bench.bench(name, TRANSIENT_BENCH_SECONDS)
            out.attempts.append((name, "timeout", clock() - t0))
            continue
        except Exception as e:  # noqa: BLE001
            bench.bench(name, QUOTA_BENCH_SECONDS if is_quota_error(e) else TRANSIENT_BENCH_SECONDS)
            out.attempts.append((name, f"error:{type(e).__name__}", clock() - t0))
            continue
        if is_success(resp):
            out.ok, out.provider, out.value = True, name, resp
            out.attempts.append((name, "ok", clock() - t0))
            return out
        err = getattr(resp, "error", "") or ""
        bench.bench(name, QUOTA_BENCH_SECONDS if is_quota_error(err) else TRANSIENT_BENCH_SECONDS)
        out.attempts.append((name, "failed", clock() - t0))
    return out
