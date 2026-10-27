"""Safe one-request-per-provider diagnostic for UNKNOWN VERIFY.

Run manually only (never imported by the app):
    cd C:\\Users\\HP\\UNKNOWN-clean\\backend
    python provider_diag.py
    python provider_diag.py --timeout 10 --model groq=<id> --model gemini=<id>

- Sends the fixed prompt "Reply with OK." (no document data), max 8 tokens.
- Reads keys from the process environment and backend\\.env; prints NAMES only,
  never values. Error text is truncated and has secrets redacted.
- Does not touch app code, provider order, or credentials.
"""
import argparse, json, os, re, sys, time, urllib.request, urllib.error, socket

PROMPT = "Reply with OK."
ORDER = ["gemini", "groq", "cohere", "openrouter", "cloudflare"]
PAT = {"gemini": r"GEMINI|GOOGLE", "groq": r"GROQ", "cohere": r"COHERE",
       "openrouter": r"OPENROUTER", "cloudflare": r"CLOUDFLARE|CF_"}


def load_env(path):
    out = {}
    if os.path.exists(path):
        for line in open(path, encoding="utf-8", errors="ignore"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def discover(env, prov):
    names = [n for n in env if re.search(PAT[prov], n, re.I)]
    key = [n for n in names if re.search(r"KEY|TOKEN", n, re.I) and env[n]]
    model = [n for n in names if re.search(r"MODEL", n, re.I) and env[n]]
    acct = [n for n in names if re.search(r"ACCOUNT", n, re.I) and env[n]]
    return key, model, acct, names


def redact(text, secrets):
    text = str(text)
    for s in secrets:
        if s and len(s) > 6:
            text = text.replace(s, "[REDACTED]")
    text = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._\-]+", r"\1[REDACTED]", text)
    text = re.sub(r"(?i)(key=)[A-Za-z0-9._\-]+", r"\1[REDACTED]", text)
    return text[:240].replace("\n", " ")


def post(url, headers, body, timeout):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={
        "Content-Type": "application/json", **headers}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read().decode("utf-8", "replace"))


def build(prov, key, model, acct):
    if prov == "gemini":
        return (f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                {"x-goog-api-key": key},
                {"contents": [{"parts": [{"text": PROMPT}]}],
                 "generationConfig": {"maxOutputTokens": 8}},
                lambda j: j["candidates"][0]["content"]["parts"][0]["text"])
    if prov in ("groq", "openrouter"):
        base = "https://api.groq.com/openai/v1" if prov == "groq" else "https://openrouter.ai/api/v1"
        return (base + "/chat/completions", {"Authorization": f"Bearer {key}"},
                {"model": model, "messages": [{"role": "user", "content": PROMPT}], "max_tokens": 8},
                lambda j: j["choices"][0]["message"]["content"])
    if prov == "cohere":
        return ("https://api.cohere.com/v2/chat", {"Authorization": f"Bearer {key}"},
                {"model": model, "messages": [{"role": "user", "content": PROMPT}], "max_tokens": 8},
                lambda j: j["message"]["content"][0]["text"])
    return (f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/{model}",
            {"Authorization": f"Bearer {key}"},
            {"messages": [{"role": "user", "content": PROMPT}], "max_tokens": 8},
            lambda j: j["result"]["response"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=float, default=10)
    ap.add_argument("--model", action="append", default=[], help="provider=model_id override")
    a = ap.parse_args()
    env = {**load_env(".env"), **load_env(os.path.join("..", ".env")), **os.environ}
    over = dict(m.split("=", 1) for m in a.model if "=" in m)
    rows = []
    for prov in ORDER:
        key_n, model_n, acct_n, names = discover(env, prov)
        print(f"[{prov}] env names seen: {sorted(names) or 'none'}")
        model = over.get(prov) or (env[model_n[0]] if model_n else "")
        key = env[key_n[0]] if key_n else ""
        acct = env[acct_n[0]] if acct_n else ""
        missing = [x for x, v in (("key", key), ("model", model),
                                  ("account_id", acct if prov == "cloudflare" else "x")) if not v]
        if missing:
            rows.append((prov, "CONFIG_MISSING", f"missing: {', '.join(missing)}", model or "-"))
            continue
        url, hdr, body, parse = build(prov, key, model, acct)
        secrets = [key, acct]
        t = time.time()
        try:
            st, j = post(url, hdr, body, a.timeout)
            try:
                parse(j)
                res, det = "SUCCESS", f"HTTP {st}"
            except Exception as e:
                res, det = "OTHER_ERROR", f"HTTP {st} but parser failed: {type(e).__name__}"
        except urllib.error.HTTPError as e:
            msg = redact(e.read().decode("utf-8", "replace"), secrets)
            res = ("AUTH_ERROR" if e.code in (401, 403) else
                   "RATE_LIMITED" if e.code == 429 else
                   "MODEL_ERROR" if e.code in (400, 404) else
                   "TIMEOUT" if e.code in (408, 504) else "OTHER_ERROR")
            det = f"HTTP {e.code}: {msg}"
        except (socket.timeout, TimeoutError):
            res, det = "TIMEOUT", f"no response in {a.timeout}s"
        except urllib.error.URLError as e:
            r = e.reason
            res = "TIMEOUT" if isinstance(r, (socket.timeout, TimeoutError)) else "OTHER_ERROR"
            det = redact(r, secrets)
        except Exception as e:
            res, det = "OTHER_ERROR", f"{type(e).__name__}: {redact(e, secrets)}"
        rows.append((prov, res, f"{det} ({time.time()-t:.1f}s)", model))
    print()
    for prov, res, det, model in rows:
        print(f"{prov:11} {res:15} model={model}  {det}")


if __name__ == "__main__":
    sys.exit(main())
