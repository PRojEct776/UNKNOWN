import time
from types import SimpleNamespace as NS

import pytest  # type: ignore

from app.llm.llm_fallback import (
    Bench,
    bounded_model_chain,
    is_quota_error,
    run_fallback,
)

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
    r = run_fallback(
        ["slow", "groq"], call, lambda x: x.success, total_budget=25, slice_s=1.0
    )
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


@pytest.mark.parametrize(
    "fallback_name",
    ["groq", "cohere", "openrouter", "cloudflare"],
)
def test_grounded_generation_falls_back_to_each_registered_provider(
    fallback_name,
):
    from app.llm.base_provider import ErrorKind, LLMResponse
    from app.llm.orchestrator import LLMOrchestrator

    class FakeProvider:
        def __init__(self, name, should_succeed=False):
            self.provider_name = name
            self.model = "test-model"
            self.should_succeed = should_succeed
            self.calls = 0

        def _response(self):
            self.calls += 1

            if self.should_succeed:
                return LLMResponse(
                    answer=f"Answer from {self.provider_name}",
                    provider=self.provider_name,
                    model=self.model,
                    latency_ms=2.0,
                    success=True,
                )

            kind = (
                ErrorKind.RATE_LIMIT
                if self.provider_name == "gemini"
                else ErrorKind.TRANSIENT
            )

            return LLMResponse(
                answer="",
                provider=self.provider_name,
                model=self.model,
                latency_ms=1.0,
                success=False,
                error=(
                    "429 RESOURCE_EXHAUSTED quota exceeded"
                    if self.provider_name == "gemini"
                    else "Simulated provider failure"
                ),
                error_kind=kind,
            )

        def generate(self, prompt, system=None):
            return self._response()

    class FakeGeminiProvider(FakeProvider):
        def generate_at_zero_temperature(self, prompt):
            return self._response()

    alternative_names = ["groq", "cohere", "openrouter", "cloudflare"]

    providers = [
        FakeGeminiProvider("gemini"),
        *[
            FakeProvider(name, should_succeed=(name == fallback_name))
            for name in alternative_names
        ],
    ]

    orchestrator = LLMOrchestrator(
        providers,
        total_timeout_s=5.0,
    )

    result = orchestrator.generate_grounded("Verify this research claim")

    assert result.success
    assert result.provider == fallback_name
    assert result.answer == f"Answer from {fallback_name}"

    target_index = alternative_names.index(fallback_name) + 1

    assert all(provider.calls == 1 for provider in providers[: target_index + 1])
    assert all(provider.calls == 0 for provider in providers[target_index + 1 :])


def test_gemini_grounded_generation_uses_bounded_chain(monkeypatch):
    from app.llm.gemini_provider import GeminiProvider

    provider = object.__new__(GeminiProvider)
    provider.model = "gemini-test"
    provider._config_kwargs = {"temperature": 0.7}

    captured = {}

    def fake_run_chain(prompt, config):
        captured["prompt"] = prompt
        captured["temperature"] = config.temperature
        provider._answered_model = "gemini-fallback-model"
        return "  grounded answer  "

    monkeypatch.setattr(provider, "_run_chain", fake_run_chain)

    response = provider.generate_at_zero_temperature("verify this claim")

    assert response.success
    assert response.answer == "grounded answer"
    assert response.model == "gemini-fallback-model"
    assert captured["prompt"] == "verify this claim"
    assert captured["temperature"] == 0.0
