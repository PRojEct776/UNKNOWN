import time
from types import SimpleNamespace as NS

from llm_fallback import (Bench, bounded_model_chain, is_quota_error, run_fallback)

QUOTA = RuntimeError("429 RESOURCE_EXHAUSTED You exceeded your current quota")


def test_quota_detection():
    assert is_quota_error(QUOTA)
    assert not is_quota_error(RuntimeError("504 deadline exceeded"))


def test_chain_stops_on_quota_one_attempt():
    calls = []

    def attempt(model, t):
        calls.append(model)
        raise QUOTA

    r = bounded_model_chain(["main", "lite1", "lite2"], attempt, budget_s=20)
    assert calls == ["main"] and r.quota and not r.ok


def test_chain_reports_actual_model():
    def attempt(model, t):
        if model == "main":
            raise RuntimeError("504")
        return "hi"

    r = bounded_model_chain(["main", "lite1"], attempt, budget_s=20)
    assert r.ok and r.model == "lite1"


def test_chain_respects_budget():
    def attempt(model, t):
        time.sleep(0.6)
        raise RuntimeError("504")

    t0 = time.monotonic()
    r = bounded_model_chain(["a", "b", "c", "d"], attempt, budget_s=1.0)
    assert time.monotonic() - t0 < 2.0 and not r.ok


def test_quota_gemini_moves_to_groq_fast():
    def call(name, timeout):
        if name == "gemini":
            raise QUOTA
        return NS(success=True, error="")

    t0 = time.monotonic()
    b = Bench()
    r = run_fallback(["gemini", "groq", "cohere"], call, lambda x: x.success, bench=b)
    assert r.ok and r.provider == "groq" and time.monotonic() - t0 < 2
    assert b.is_benched("gemini")


def test_slow_provider_cannot_starve_others():
    def call(name, timeout):
        if name == "slow":
            time.sleep(timeout + 3)
        return NS(success=True, error="")

    t0 = time.monotonic()
    r = run_fallback(["slow", "groq"], call, lambda x: x.success,
                     total_budget=25, slice_s=1.0)
    assert r.ok and r.provider == "groq" and time.monotonic() - t0 < 4


def test_failed_response_advances_and_never_raises():
    def call(name, timeout):
        return NS(success=False, error="boom")

    r = run_fallback(["a", "b"], call, lambda x: x.success)
    assert not r.ok and len(r.attempts) == 2


def test_benched_skipped():
    b = Bench()
    b.bench("gemini", 100)
    seen = []

    def call(name, timeout):
        seen.append(name)
        return NS(success=True, error="")

    run_fallback(["gemini", "groq"], call, lambda x: x.success, bench=b)
    assert seen == ["groq"]
