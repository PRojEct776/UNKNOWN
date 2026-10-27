import re
import sys

root = sys.argv[1] if len(sys.argv) > 1 else "."


def load(rel):
    path = root.rstrip("\\/") + "/" + rel
    raw = open(path, "rb").read().decode("utf-8")
    nl = "\r\n" if "\r\n" in raw else "\n"
    return path, raw.replace("\r\n", "\n"), nl


def once(text, old, new, what):
    if text.count(old) != 1:
        sys.exit("anchor not found or not unique (%s): %d" % (what, text.count(old)))
    return text.replace(old, new)


changes = []

# 1. ConfidenceBadge: optional label that also fixes the explanatory note
path, t, nl = load("frontend/src/components/answers/ConfidenceBadge.tsx")
if "label?: string" in t:
    print("ConfidenceBadge.tsx already patched")
else:
    t = once(t, "  value?: number; // legacy backwards compatibility\n",
             "  value?: number; // legacy backwards compatibility\n"
             "  label?: string; // replaces the default 'Evidence score' wording\n", "props")
    t = once(t, "({ confidence, value }) => {", "({ confidence, value, label }) => {", "signature")
    t = once(t, "<span>Evidence score {score}%</span>",
             "<span>{label ?? 'Evidence score'} {score}%</span>", "badge text")
    note = re.compile(
        r"This score reflects how much evidence was found and how reliable its sources\s+"
        r"are\. It does not measure whether the answer is correct\.")
    if len(note.findall(t)) != 1:
        sys.exit("anchor not found or not unique (note)")
    t = note.sub(
        "{label\n"
        "                ? \"This is the verifier's confidence in its verdict for this claim, as reported by the model after reading the quoted passages. It is not independently calibrated and is not a probability that the claim is true.\"\n"
        "                : 'This score reflects how much evidence was found and how reliable its sources are. It does not measure whether the answer is correct.'}",
        t)
    t = once(t, "<span>Formula: UNKNOWN v1.0</span>",
             "<span>{label ? 'Source: verifier model' : 'Formula: UNKNOWN v1.0'}</span>", "footer")
    open(path, "wb").write(t.replace("\n", nl).encode("utf-8"))
    changes.append("ConfidenceBadge.tsx")

# 2. Verify result: backend confidence is 0..1, the badge expects a percent
path, t, nl = load("frontend/src/lib/workspaceResultBuilder.ts")
old = "    confidence: res.confidence,\n    sources: mapBackendSources(res.sources || []),\n    evidence: mapBackendEvidence(res.sources || []),\n    verification: [verificationItem, ...partItems],\n"
new = "    confidence: Math.round(res.confidence * 100),\n    sources: mapBackendSources(res.sources || []),\n    evidence: mapBackendEvidence(res.sources || []),\n    verification: [verificationItem, ...partItems],\n"
if new in t:
    print("workspaceResultBuilder.ts already patched")
else:
    t = once(t, old, new, "verify confidence")
    open(path, "wb").write(t.replace("\n", nl).encode("utf-8"))
    changes.append("workspaceResultBuilder.ts")

# 3. ChatMessageItem: label verify confidence, count passages not "sources"
path, t, nl = load("frontend/src/components/chat/ChatMessageItem.tsx")
if "Verdict confidence" in t:
    print("ChatMessageItem.tsx already patched")
else:
    t = once(t, "<ConfidenceBadge confidence={result.confidence} />",
             "<ConfidenceBadge confidence={result.confidence} label={result?.verification?.length ? 'Verdict confidence' : undefined} />",
             "badge usage")
    t = once(t, "<span>{result.sources.length} sources</span>",
             "<span>{result.sources.length} {result?.verification?.length ? (result.sources.length === 1 ? 'retrieved passage' : 'retrieved passages') : 'sources'}</span>",
             "sources count")
    open(path, "wb").write(t.replace("\n", nl).encode("utf-8"))
    changes.append("ChatMessageItem.tsx")

print("patched: " + (", ".join(changes) if changes else "nothing"))
