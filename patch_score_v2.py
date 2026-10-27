import os
import re
import sys

root = sys.argv[1] if len(sys.argv) > 1 else "."


def read(path):
    raw = open(path, "rb").read().decode("utf-8")
    return raw.replace("\r\n", "\n"), ("\r\n" if "\r\n" in raw else "\n")


def write(path, text, nl):
    open(path, "wb").write(text.replace("\n", nl).encode("utf-8"))


changed = []

# 1. backend schema: derived whole-number percent
p = os.path.join(root, "backend", "app", "api", "schemas.py")
t, nl = read(p)
start = t.find("class ClaimVerificationResponse(BaseModel):")
if start == -1:
    sys.exit("ClaimVerificationResponse not found in schemas.py")
end = t.find("\nclass ", start + 10)
block = t[start:end if end != -1 else len(t)]
if "confidence_score" in block:
    print("schemas.py already patched")
else:
    anchor = "    atomic_claims: list[AtomicClaimVerification] = Field(default_factory=list)\n"
    if block.count(anchor) != 1:
        sys.exit("anchor not found in ClaimVerificationResponse (atomic_claims)")
    if "model_post_init" in block:
        sys.exit("ClaimVerificationResponse already has model_post_init; patch by hand")
    addition = (
        anchor
        + "    # Whole-number percent (0-100) derived from `confidence` so clients display it as is.\n"
        + "    confidence_score: int | None = None\n"
        + "\n"
        + "    def model_post_init(self, __context):\n"
        + "        super().model_post_init(__context)\n"
        + "        if self.confidence_score is None:\n"
        + "            clipped = max(0.0, min(1.0, float(self.confidence)))\n"
        + "            self.confidence_score = int(round(clipped * 100))\n"
    )
    new_block = block.replace(anchor, addition)
    t = t[:start] + new_block + t[start + len(block):]
    write(p, t, nl)
    changed.append("schemas.py")

# 2. frontend type: add the field next to `confidence` in BackendVerifyResponse
src = os.path.join(root, "frontend", "src")
type_file = None
for d, _, files in os.walk(src):
    for f in files:
        if f.endswith((".ts", ".tsx")):
            fp = os.path.join(d, f)
            text, _n = read(fp)
            if re.search(r"export\s+(interface|type)\s+BackendVerifyResponse\b", text):
                type_file = fp
                break
    if type_file:
        break
if not type_file:
    sys.exit("BackendVerifyResponse definition not found in frontend/src")
t, nl = read(type_file)
m = re.search(r"export\s+(interface|type)\s+BackendVerifyResponse\b", t)
if "confidence_score" in t[m.start():m.start() + 1500]:
    print(os.path.basename(type_file) + " already patched")
else:
    region_end = t.find("\n}", m.start())
    region = t[m.start():region_end]
    lm = re.search(r"^(\s*)confidence\??:\s*number;[^\n]*\n", region + "\n", re.M)
    if not lm:
        sys.exit("could not find 'confidence: number;' inside BackendVerifyResponse in " + type_file)
    insert_at = m.start() + lm.end()
    t = t[:insert_at] + lm.group(1) + "confidence_score?: number;\n" + t[insert_at:]
    write(type_file, t, nl)
    changed.append(os.path.basename(type_file))

# 3. frontend builder: show the API score directly
p = os.path.join(src, "lib", "workspaceResultBuilder.ts")
t, nl = read(p)
old = "    confidence: res.confidence,\n    sources: mapBackendSources(res.sources || []),\n    evidence: mapBackendEvidence(res.sources || []),\n    verification: [verificationItem, ...partItems],\n"
new = old.replace("confidence: res.confidence,", "confidence: res.confidence_score,")
if new in t:
    print("workspaceResultBuilder.ts already patched")
else:
    if t.count(old) != 1:
        sys.exit("anchor not found in workspaceResultBuilder.ts: %d" % t.count(old))
    write(p, t.replace(old, new), nl)
    changed.append("workspaceResultBuilder.ts")

# 4. backend test
tp = os.path.join(root, "backend", "tests", "test_verify_confidence_score.py")
if not os.path.exists(tp):
    open(tp, "w", encoding="utf-8", newline="\n").write('''from app.api.schemas import ClaimVerificationResponse


def _response(confidence, **extra):
    return ClaimVerificationResponse(
        claim="c",
        verdict="SUPPORTED",
        confidence=confidence,
        explanation="e",
        evidence=[],
        source_chunk_ids=[],
        sources=[],
        **extra,
    )


def test_score_is_whole_number_percent():
    assert _response(0.95).confidence_score == 95
    assert _response(0.8).confidence_score == 80
    assert _response(0.0).confidence_score == 0
    assert _response(1.0).confidence_score == 100


def test_raw_confidence_is_unchanged():
    assert _response(0.95).confidence == 0.95


def test_explicit_score_is_kept():
    assert _response(0.95, confidence_score=42).confidence_score == 42


def test_score_is_in_serialized_output():
    assert _response(0.5).model_dump()["confidence_score"] == 50
''')
    changed.append("tests/test_verify_confidence_score.py")

print("patched: " + (", ".join(changed) if changed else "nothing"))
