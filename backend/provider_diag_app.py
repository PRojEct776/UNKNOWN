"""Manual-only: one minimal request per provider THROUGH the app's own provider classes.

    cd C:\\Users\\HP\\UNKNOWN-clean\\backend
    python provider_diag_app.py

- Prompt is the fixed string "Reply with OK."; no document data.
- Does not use the orchestrator or HealthTracker, so no cooldown state is changed.
- Gemini: ONE direct SDK call with the configured model (provider.generate()
  would run the 3-model x 2-attempt chain, so it is deliberately not used).
- Secret values are redacted from all output.
"""
import re
import sys
import time

from app.rag.config import settings

PROMPT = "Reply with OK."
SECRETS = [
    str(getattr(settings, n, "") or "")
    for n in dir(settings)
    if re.search(r"KEY|TOKEN|ACCOUNT_ID", n) and not n.startswith("_")
]


def clean(text):
    text = str(text)
    for s in SECRETS:
        if len(s) > 6:
            text = text.replace(s, "[REDACTED]")
    text = re.sub(r"(?i)bearer\s+[A-Za-z0-9._\-]+", "Bearer [REDACTED]", text)
    return text[:260].replace("\n", " ")


def label(kind, err):
    k = getattr(kind, "value", str(kind))
    e = (err or "").lower()
    if "403" in e or "401" in e or "unauthor" in e or "forbidden" in e:
        return "AUTH_ERROR"
    if k == "rate_limit" or "429" in e:
        return "RATE_LIMITED"
    if "timeout" in e or "timed out" in e or "504" in e:
        return "TIMEOUT"
    if k in ("invalid_request",) or "404" in e or "model" in e:
        return "MODEL_ERROR"
    return "OTHER_ERROR"


def run(name, factory):
    try:
        p = factory()
    except Exception as exc:
        return name, "CONFIG_MISSING", f"{type(exc).__name__}: {clean(exc)}", "-", 0.0
    t = time.time()
    try:
        if name == "gemini":
            try:
                r = p.client.models.generate_content(
                    model=p.model, contents=PROMPT, config=p._config)
                ok, ans, err, kind = bool(r.text and r.text.strip()), r.text or "", None, None
                if not ok:
                    err, kind = str(p._empty_error(r)), None
            except Exception as exc:
                ok, ans, err, kind = False, "", f"{type(exc).__name__}: {exc}", p._kind_of(exc)
        else:
            resp = p.generate(PROMPT)
            ok, ans, err, kind = resp.success, resp.answer, resp.error, resp.error_kind
    except Exception as exc:
        ok, ans, err, kind = False, "", f"ESCAPED {type(exc).__name__}: {exc}", None
    dt = time.time() - t
    if ok:
        return name, "SUCCESS", f"parsed {len(ans)} chars", p.model, dt
    return name, label(kind, err), f"kind={getattr(kind, 'value', kind)} {clean(err)}", p.model, dt


def main():
    from app.llm.gemini_provider import GeminiProvider
    from app.llm.groq_provider import GroqProvider
    from app.llm.cohere_provider import CohereProvider
    from app.llm.openrouter_provider import OpenRouterProvider
    from app.llm.cloudflare_provider import CloudflareProvider
    jobs = [("gemini", GeminiProvider), ("groq", GroqProvider), ("cohere", CohereProvider),
            ("openrouter", OpenRouterProvider), ("cloudflare", CloudflareProvider)]
    for name, f in jobs:
        n, res, det, model, dt = run(name, f)
        print(f"{n:11} {res:15} model={model}  {det} ({dt:.1f}s)")


if __name__ == "__main__":
    sys.exit(main())
