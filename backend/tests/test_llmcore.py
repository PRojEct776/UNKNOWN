"""
UNKNOWN X - offline tests for the LLM layer (no network, no API keys).

Run:  python -m tests.test_llm_core      (or: pytest tests/test_llm_core.py)
"""

from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import httpx
import openai
from google.genai import errors as genai_errors
from google.genai import types

from app.llm.base_provider import (
    BaseProvider,
    ErrorKind,
    LLMError,
    LLMResponse,
    kind_from_http_status,
)
from app.llm.gemini_provider import GeminiProvider, resolve_thinking
from app.llm.groq_provider import GroqProvider
from app.llm.health import HealthPolicy, HealthTracker
from app.llm.openai_compat import OpenAICompatProvider
from app.llm.orchestrator import LLMOrchestrator

_REQ = httpx.Request("POST", "https://example.test/v1/chat/completions")


# ==========================================================
# Helpers
# ==========================================================


class ScriptedProvider(BaseProvider):
    """Plays back a script of return values / exceptions (last item repeats)."""

    def __init__(self, name: str, *script):
        self.provider_name = name  # type: ignore
        super().__init__(f"{name}-model")
        self.script = list(script)
        self.calls = 0
        self.last_args = None

    def _call(self, prompt, system=None):
        self.calls += 1
        self.last_args = (prompt, system)
        item = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(item, Exception):
            raise item
        return item


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def ok(name="p", latency=100.0):
    return LLMResponse("hi", name, "m", latency, True)


def fail(name="p", kind=ErrorKind.TRANSIENT):
    return LLMResponse("", name, "m", 1.0, False, "boom", kind)


def bare(cls):
    """Instance without running __init__ (no keys/settings needed)."""
    return object.__new__(cls)


# ==========================================================
# base_provider
# ==========================================================


def test_response_is_immutable():
    r = ok()
    try:
        r.answer = "changed"  # type: ignore
    except FrozenInstanceError:
        return
    raise AssertionError("LLMResponse should be immutable")


def test_generate_success_strips_and_forwards_system():
    p = ScriptedProvider("a", "  hello \n")
    r = p.generate("q", "be brief")
    assert r.success and r.answer == "hello" and r.error is None
    assert r.error_kind is None and r.provider == "a" and r.latency_ms >= 0
    assert p.last_args == ("q", "be brief")


def test_generate_keeps_llm_error_kind():
    r = ScriptedProvider("a", LLMError(ErrorKind.RATE_LIMIT, "slow down")).generate("q")
    assert not r.success and r.answer == ""
    assert r.error_kind is ErrorKind.RATE_LIMIT
    assert r.error == "LLMError: slow down"


def test_empty_and_non_text_are_empty_kind():
    for reply in ("", "   ", None, 123):
        r = ScriptedProvider("a", reply).generate("q")
        assert not r.success and r.error_kind is ErrorKind.EMPTY, reply


def test_unclassified_exception_is_unknown_and_broken_classifier_is_safe():
    r = ScriptedProvider("a", RuntimeError("x")).generate("q")
    assert r.error is not None
    assert r.error_kind is ErrorKind.UNKNOWN and r.error.startswith("RuntimeError")

    class Broken(ScriptedProvider):
        def _classify(self, exc):
            raise ValueError("classifier bug")

    assert Broken("b", RuntimeError("x")).generate("q").error_kind is ErrorKind.UNKNOWN


def test_error_text_is_truncated():
    r = ScriptedProvider("a", RuntimeError("x" * 5000)).generate("q")
    assert len(r.error) < 600  # type: ignore


def test_kind_from_http_status():
    table = {
        401: ErrorKind.FATAL, 402: ErrorKind.FATAL, 403: ErrorKind.FATAL,
        404: ErrorKind.FATAL, 429: ErrorKind.RATE_LIMIT, 408: ErrorKind.TRANSIENT,
        499: ErrorKind.TRANSIENT, 500: ErrorKind.TRANSIENT, 503: ErrorKind.TRANSIENT,
        400: ErrorKind.INVALID_REQUEST, 413: ErrorKind.INVALID_REQUEST,
        422: ErrorKind.INVALID_REQUEST, 200: ErrorKind.UNKNOWN,
    }  # fmt: skip
    for status, kind in table.items():
        assert kind_from_http_status(status) is kind, status


# ==========================================================
# health
# ==========================================================


def test_transient_failures_bench_after_threshold_then_probe():
    clock = FakeClock()
    h = HealthTracker(HealthPolicy(failure_threshold=3, transient_cooldown_s=30), clock)
    for _ in range(2):
        h.record(fail())
    assert h.is_available("p")
    h.record(fail())
    assert not h.is_available("p")
    assert 29 < h.seconds_until_available("p") <= 30

    clock.t += 31
    assert h.is_available("p")  # cooldown over: next request probes
    h.record(fail())  # probe fails -> benched again immediately
    assert not h.is_available("p")

    clock.t += 31
    h.record(ok())  # probe succeeds -> breaker closes
    assert h.is_available("p")
    assert h.snapshot()["p"]["consecutive_failures"] == 0


def test_rate_limit_and_fatal_bench_immediately():
    clock = FakeClock()
    h = HealthTracker(
        HealthPolicy(rate_limit_cooldown_s=60, fatal_cooldown_s=300), clock
    )
    h.record(fail("rl", ErrorKind.RATE_LIMIT))
    h.record(fail("dead", ErrorKind.FATAL))
    assert not h.is_available("rl") and not h.is_available("dead")
    clock.t += 61
    assert h.is_available("rl") and not h.is_available("dead")
    clock.t += 300
    assert h.is_available("dead")


def test_success_closes_breaker_even_during_cooldown():
    h = HealthTracker(HealthPolicy(rate_limit_cooldown_s=60), FakeClock())
    h.record(fail("p", ErrorKind.RATE_LIMIT))
    assert not h.is_available("p")
    h.record(ok("p"))  # e.g. a probe made while everything was cooling down
    assert h.is_available("p")


def test_invalid_request_never_benches_but_empty_counts():
    h = HealthTracker(HealthPolicy(failure_threshold=3), FakeClock())
    for _ in range(10):
        h.record(fail("p", ErrorKind.INVALID_REQUEST))
    assert h.is_available("p")
    for _ in range(3):
        h.record(fail("q", ErrorKind.EMPTY))
    assert not h.is_available("q")


def test_snapshot_shape_and_reset():
    h = HealthTracker(clock=FakeClock())
    h.record(ok("a", 100.0))
    h.record(ok("a", 200.0))
    snap = h.snapshot()["a"]
    assert snap["available"] and snap["successes"] == 2
    assert snap["avg_latency_ms"] == 120.0  # EWMA: 0.8*100 + 0.2*200
    h.reset("a")
    assert h.snapshot() == {}


# ==========================================================
# orchestrator
# ==========================================================


def make(*providers, **kw):
    return LLMOrchestrator(list(providers), HealthTracker(clock=FakeClock()), **kw)


def test_falls_back_in_order_and_forwards_system():
    a = ScriptedProvider("a", LLMError(ErrorKind.TRANSIENT, "down"))
    b = ScriptedProvider("b", "from b")
    r = make(a, b).generate("q", "sys")
    assert r.success and r.provider == "b" and r.answer == "from b"
    assert a.calls == 1 and b.last_args == ("q", "sys")


def test_benched_provider_is_skipped_on_next_request():
    a = ScriptedProvider("a", LLMError(ErrorKind.RATE_LIMIT, "429"))
    b = ScriptedProvider("b", "ok")
    orch = make(a, b)
    orch.generate("q1")
    orch.generate("q2")
    assert a.calls == 1 and b.calls == 2


def test_all_fail_returns_aggregate_failure():
    orch = make(
        ScriptedProvider("a", LLMError(ErrorKind.TRANSIENT, "x")),
        ScriptedProvider("b", LLMError(ErrorKind.EMPTY, "y")),
    )
    r = orch.generate("q")
    assert not r.success and r.provider == "orchestrator" and r.answer == ""
    assert "a:" in r.error and "b:" in r.error  # type: ignore
    assert r.error_kind is ErrorKind.EMPTY


def test_empty_prompt_short_circuits():
    a = ScriptedProvider("a", "ok")
    r = make(a).generate("   ")
    assert not r.success and r.error_kind is ErrorKind.INVALID_REQUEST and a.calls == 0


def test_all_cooling_down_probes_only_the_soonest():
    clock = FakeClock()
    a = ScriptedProvider("a", "A")
    b = ScriptedProvider("b", "B")
    h = HealthTracker(
        HealthPolicy(rate_limit_cooldown_s=60, fatal_cooldown_s=300), clock
    )
    h.record(fail("a", ErrorKind.FATAL))
    h.record(fail("b", ErrorKind.RATE_LIMIT))
    r = LLMOrchestrator([a, b], h).generate("q")
    assert r.provider == "b" and a.calls == 0 and b.calls == 1
    assert h.is_available("b") and not h.is_available("a")  # successful probe reopens b


def test_time_budget_stops_further_providers():
    a = ScriptedProvider("a", LLMError(ErrorKind.TRANSIENT, "x"))
    b = ScriptedProvider("b", "ok")
    r = make(a, b, total_timeout_s=0.0).generate("q")
    assert not r.success and a.calls == 1 and b.calls == 0


def test_constructor_and_status_and_async():
    try:
        LLMOrchestrator([])
    except ValueError:
        pass
    else:
        raise AssertionError("empty provider list must be rejected")

    orch = make(ScriptedProvider("a", "hi"))
    r = asyncio.run(orch.agenerate("q"))
    assert r.success
    status = orch.status()["providers"][0]
    assert status["name"] == "a" and status["available"] is True


# ==========================================================
# OpenAI-compatible providers (real SDK objects, mocked transport)
# ==========================================================


class _P(OpenAICompatProvider):
    provider_name = "p"


def _provider_with_transport(handler, **kw):
    p = _P(
        model="m", api_key="k", base_url="http://127.0.0.1:9/v1", timeout_s=1.0, **kw
    )
    p.client = openai.OpenAI(
        api_key="k",
        base_url="http://test/v1",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),  # type: ignore
    )
    return p


def _completion(content, finish="stop"):
    return {
        "id": "x", "object": "chat.completion", "created": 0, "model": "m",
        "choices": [{"index": 0, "finish_reason": finish,
                     "message": {"role": "assistant", "content": content}}],
    }  # fmt: skip


def test_compat_success_sends_system_and_params():
    seen = {}

    def handler(request):
        seen["body"] = __import__("json").loads(request.content)
        return httpx.Response(200, json=_completion("  hello "))

    p = _provider_with_transport(handler, temperature=0.2, max_tokens=50)
    r = p.generate("question", "be brief")
    assert r.success and r.answer == "hello"
    body = seen["body"]
    assert body["messages"][0] == {"role": "system", "content": "be brief"}
    assert body["messages"][1] == {"role": "user", "content": "question"}
    assert body["max_completion_tokens"] == 50 and body["temperature"] == 0.2


def test_compat_http_errors_are_classified():
    for status, kind in [(429, ErrorKind.RATE_LIMIT), (401, ErrorKind.FATAL),
                         (400, ErrorKind.INVALID_REQUEST), (503, ErrorKind.TRANSIENT)]:  # fmt: skip
        p = _provider_with_transport(
            lambda request, s=status: httpx.Response(
                s, json={"error": {"message": "e"}}
            )
        )
        r = p.generate("q")
        assert not r.success and r.error_kind is kind, (status, r.error_kind)


def test_compat_timeout_is_transient():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    assert (
        _provider_with_transport(handler).generate("q").error_kind
        is ErrorKind.TRANSIENT
    )


def test_compat_empty_body_error_and_length_hint():
    r = _provider_with_transport(
        lambda req: httpx.Response(200, json=_completion(""))
    ).generate("q")
    assert r.error_kind is ErrorKind.EMPTY

    r = _provider_with_transport(
        lambda req: httpx.Response(200, json=_completion(None, "length"))
    ).generate("q")
    assert r.error_kind is ErrorKind.EMPTY and "MAX_OUTPUT_TOKENS" in r.error  # type: ignore

    r = _provider_with_transport(
        lambda req: httpx.Response(
            200, json={"error": {"code": 429, "message": "upstream"}}
        )
    ).generate("q")
    assert r.error_kind is ErrorKind.RATE_LIMIT

    r = _provider_with_transport(
        lambda req: httpx.Response(200, json={"error": {"message": "weird"}})
    ).generate("q")
    assert r.error_kind is ErrorKind.TRANSIENT


def test_compat_constructor_validation_and_token_param_override():
    for kwargs in ({"model": "", "api_key": "k"}, {"model": "m", "api_key": None}):
        try:
            _P(base_url="http://x", timeout_s=1.0, **kwargs)  # type: ignore
        except ValueError:
            continue
        raise AssertionError(f"should reject {kwargs}")

    p = _P(model="m", api_key="k", base_url="http://127.0.0.1:9/v1", timeout_s=10.0)
    assert p.client.max_retries == 0  # hidden SDK retries would break the time budget
    assert p.client.timeout is not None
    assert p.client.timeout.read == 10.0 and p.client.timeout.connect == 5.0  # type: ignore
    assert (
        _P(
            model="m", api_key="k", base_url="http://x/v1", timeout_s=2.0
        ).client.timeout.connect  # type: ignore
        == 2.0
    )

    from app.llm.openrouter_provider import OpenRouterProvider

    assert OpenRouterProvider.max_tokens_param == "max_tokens"
    assert OpenAICompatProvider.max_tokens_param == "max_completion_tokens"
    assert GroqProvider.provider_name == "groq"


def test_compat_sdk_exception_classes():
    p = bare(_P)
    resp = lambda s: httpx.Response(s, request=_REQ)
    assert (
        p._classify(openai.RateLimitError("x", response=resp(429), body=None))  # type: ignore
        is ErrorKind.RATE_LIMIT
    )
    assert (
        p._classify(openai.AuthenticationError("x", response=resp(401), body=None))  # type: ignore
        is ErrorKind.FATAL
    )
    assert (
        p._classify(openai.InternalServerError("x", response=resp(500), body=None))  # type: ignore
        is ErrorKind.TRANSIENT
    )
    assert p._classify(openai.APITimeoutError(request=_REQ)) is ErrorKind.TRANSIENT  # type: ignore
    assert p._classify(openai.APIConnectionError(request=_REQ)) is ErrorKind.TRANSIENT  # type: ignore
    assert p._classify(ValueError("x")) is ErrorKind.UNKNOWN


# ==========================================================
# Gemini
# ==========================================================


def _level(cfg):
    return getattr(cfg.thinking_level, "name", cfg.thinking_level)


def test_resolve_thinking_per_model_family():
    assert resolve_thinking("gemini-2.5-flash", "minimal").thinking_budget == 0  # type: ignore
    assert resolve_thinking("gemini-2.5-pro", "MINIMAL").thinking_budget == 128  # type: ignore
    assert resolve_thinking("gemini-2.5-pro", "HIGH").thinking_budget == 8192  # type: ignore
    assert resolve_thinking("models/gemini-2.5-flash", "LOW").thinking_budget == 1024  # type: ignore
    assert _level(resolve_thinking("gemini-3-flash", "MEDIUM")) == "MEDIUM"
    assert _level(resolve_thinking("gemini-3-flash", "MINIMAL")) == "MINIMAL"
    assert _level(resolve_thinking("gemini-3.1-pro-preview", "MINIMAL")) == "LOW"
    assert _level(resolve_thinking("gemini-3-pro", "MEDIUM")) == "HIGH"
    assert resolve_thinking("gemini-flash-latest", "LOW") is None
    try:
        resolve_thinking("gemini-3-flash", "ULTRA")
    except ValueError:
        pass
    else:
        raise AssertionError("invalid level must raise")


def _api_error(cls, code, message="e", status="X"):
    return cls(code, {"error": {"code": code, "message": message, "status": status}})


def test_gemini_error_classification():
    g = bare(GeminiProvider)
    C, S = genai_errors.ClientError, genai_errors.ServerError
    assert (
        g._classify(_api_error(C, 429, status="RESOURCE_EXHAUSTED"))
        is ErrorKind.RATE_LIMIT
    )
    assert g._classify(_api_error(S, 503, status="UNAVAILABLE")) is ErrorKind.TRANSIENT
    assert (
        g._classify(_api_error(C, 403, status="PERMISSION_DENIED")) is ErrorKind.FATAL
    )
    assert g._classify(_api_error(C, 404, status="NOT_FOUND")) is ErrorKind.FATAL
    assert (
        g._classify(_api_error(C, 400, "API key not valid.", "INVALID_ARGUMENT"))
        is ErrorKind.FATAL
    )
    assert (
        g._classify(_api_error(C, 400, "prompt too long", "INVALID_ARGUMENT"))
        is ErrorKind.INVALID_REQUEST
    )
    assert g._classify(httpx.ReadTimeout("t", request=_REQ)) is ErrorKind.TRANSIENT
    assert g._classify(RuntimeError("?")) is ErrorKind.UNKNOWN


def test_gemini_empty_response_diagnostics():
    e = GeminiProvider._empty_error
    blocked = SimpleNamespace(
        prompt_feedback=SimpleNamespace(block_reason=SimpleNamespace(name="SAFETY"))
    )
    assert e(blocked).kind is ErrorKind.INVALID_REQUEST
    assert (
        e(SimpleNamespace(prompt_feedback=None, candidates=[])).kind is ErrorKind.EMPTY
    )

    def with_finish(name):
        cand = SimpleNamespace(finish_reason=SimpleNamespace(name=name))
        return SimpleNamespace(prompt_feedback=None, candidates=[cand])

    err = e(with_finish("MAX_TOKENS"))
    assert err.kind is ErrorKind.EMPTY and "MAX_OUTPUT_TOKENS" in str(err)
    assert e(with_finish("SAFETY")).kind is ErrorKind.INVALID_REQUEST


def test_gemini_call_builds_config_with_system_instruction():
    seen = {}

    class FakeModels:
        def generate_content(self, *, model, contents, config):
            seen.update(model=model, contents=contents, config=config)
            return SimpleNamespace(text=" answer ")

    g = bare(GeminiProvider)
    g.model = "gemini-2.5-flash"
    g.client = SimpleNamespace(models=FakeModels())  # type: ignore
    g._config_kwargs = {"max_output_tokens": 77}
    g._config = types.GenerateContentConfig(**g._config_kwargs)  # type: ignore

    assert g._call("q") == " answer "
    assert seen["config"] is g._config

    r = g.generate("q", "be brief")
    assert r.success and r.answer == "answer"
    assert seen["config"].system_instruction == "be brief"
    assert seen["config"].max_output_tokens == 77


# ==========================================================
# Runner
# ==========================================================

if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print(f"  ok  {name}")
    print("\n========================================")
    print(f"UNKNOWN X - LLM CORE TESTS PASSED ({len(tests)})")
    print("========================================")
