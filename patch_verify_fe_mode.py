import sys
from pathlib import Path

CHECK = "--check" in sys.argv
BASE = Path(__file__).resolve().parent
EDITS = []


def edit(path, old, new):
    EDITS.append((path, old, new))


edit("frontend/src/lib/api.ts", r"""  documentNames?: string[],
  signal?: AbortSignal,
): Promise<BackendVerifyResponse> {
  return apiFetch<BackendVerifyResponse>(
    '/verify',
    {
      method: 'POST',
      body: JSON.stringify({ claim, document_names: documentNames ?? null }),
    },
""", r"""  documentNames?: string[],
  signal?: AbortSignal,
  sourceMode?: 'documents' | 'web' | 'both',
): Promise<BackendVerifyResponse> {
  return apiFetch<BackendVerifyResponse>(
    '/verify',
    {
      method: 'POST',
      body: JSON.stringify({
        claim,
        document_names: documentNames ?? null,
        ...(sourceMode ? { source_mode: sourceMode } : {}),
      }),
    },
""")

edit("frontend/src/pages/KnowledgeWorkspacePage.tsx",
     "const resp = await verifyClaimBackend(currentText, targetDocs, controller.signal);",
     "const resp = await verifyClaimBackend(currentText, targetDocs, controller.signal, currentSourceMode);")

files = {}
errors = []
for rel, old, new in EDITS:
    if rel not in files:
        raw = (BASE / rel).read_bytes()
        files[rel] = [raw.decode("utf-8").replace("\r\n", "\n"), b"\r\n" in raw]
    n = files[rel][0].count(old)
    if n != 1:
        errors.append("%s: anchor matched %d times (need 1):\n%s" % (rel, n, old))
        continue
    files[rel][0] = files[rel][0].replace(old, new, 1)

if errors:
    print("ABORTED. Nothing was written.")
    for e in errors:
        print("-", e)
    sys.exit(1)
if CHECK:
    print("CHECK OK: %d edits, anchors unique. Nothing written." % len(EDITS))
    sys.exit(0)
for rel, (text, crlf) in files.items():
    (BASE / rel).write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
    print("patched", rel)
print("DONE")
