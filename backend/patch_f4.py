import os, shutil, sys

FILES = {
    "api": r"..\frontend\src\lib\api.ts",
    "builder": r"..\frontend\src\lib\workspaceResultBuilder.ts",
    "list": r"..\frontend\src\components\evidence\SourceList.tsx",
    "chat": r"..\frontend\src\components\chat\ChatMessageItem.tsx",
}

CLAIMS_BLOCK = """          {/* Claims: click a claim to jump to its supporting quote */}
          {result?.claims && result.claims.length > 0 && (
            <div className="space-y-1.5" data-testid="claim-chips">
              <div className="font-semibold text-[#a7d0d2] uppercase font-mono text-[11px]">Claims</div>
              <div className="flex flex-wrap gap-2">
                {result.claims.map((claim, ci) => {
                  const q = (claim.quote || '').trim();
                  const src = q ? (result.sources || []).find((s) => (s.passage || '').includes(q)) : undefined;
                  const label = (claim.label || 'supported').toLowerCase();
                  const tone = label === 'supported'
                    ? 'border-emerald-400/30 bg-emerald-500/10 text-emerald-300'
                    : label === 'partial'
                    ? 'border-amber-400/30 bg-amber-500/10 text-amber-300'
                    : 'border-rose-400/30 bg-rose-500/10 text-rose-300';
                  const cls = `inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium ${tone}`;
                  return src ? (
                    <button
                      key={ci}
                      type="button"
                      className={`${cls} cursor-pointer hover:brightness-125`}
                      data-testid="claim-chip"
                      title="Show supporting quote"
                      onClick={() => onOpenSourcesDrawer([{ ...src, quote: q }])}
                    >
                      <span>{claim.text}</span>
                      <span className="rounded bg-black/30 px-1.5 text-[9px] font-mono uppercase opacity-75">{label}</span>
                    </button>
                  ) : (
                    <span key={ci} className={cls} data-testid="claim-chip">
                      <span>{claim.text}</span>
                      <span className="rounded bg-black/30 px-1.5 text-[9px] font-mono uppercase opacity-75">{label}</span>
                    </span>
                  );
                })}
              </div>
            </div>
          )}

"""

HIGHLIGHT = (
    '<p className="italic text-[#c1cbd2]">{(() => {'
    " const q = (source.quote || '').trim();"
    " const at = q && source.passage ? source.passage.indexOf(q) : -1;"
    " if (at < 0 || !source.passage) return passage;"
    " return (<>{source.passage.slice(0, at)}"
    '<mark data-testid="quote-highlight" className="rounded bg-amber-400/30 px-0.5 text-white"'
    " ref={(el) => { el?.scrollIntoView({ block: 'center' }); }}>{q}</mark>"
    "{source.passage.slice(at + q.length)}</>); })()}</p>"
)

EDITS = {
    "api": [(
        "  faiss_score: number;\n}\n\n/** A single indexed document as returned by GET /documents. */",
        "  faiss_score: number;\n  passage?: string | null;\n  quote?: string | null;\n}\n\n/** A single indexed document as returned by GET /documents. */",
    )],
    "builder": [(
        "    faissScore: typeof s.faiss_score === 'number' && Number.isFinite(s.faiss_score) ? s.faiss_score : undefined,\n  }));\n}\n\nexport function mapBackendEvidence",
        "    faissScore: typeof s.faiss_score === 'number' && Number.isFinite(s.faiss_score) ? s.faiss_score : undefined,\n    passage: s.passage ?? undefined,\n    quote: s.quote ?? undefined,\n  }));\n}\n\nexport function mapBackendEvidence",
    )],
    "list": [(
        '<p className="italic text-[#c1cbd2]">{passage}</p>',
        HIGHLIGHT,
    )],
    "chat": [(
        "          {/* Retrieval notes: failed, timed-out or empty sources */}\n",
        CLAIMS_BLOCK + "          {/* Retrieval notes: failed, timed-out or empty sources */}\n",
    )],
}

new = {}
for key, path in FILES.items():
    if not os.path.exists(path):
        print("ABORT: missing", path); sys.exit(1)
    raw = open(path, "rb").read().decode("utf-8")
    nl = "\r\n" if "\r\n" in raw else "\n"
    src = raw
    for old, rep in EDITS[key]:
        o = old.replace("\n", nl)
        n = src.count(o)
        if n != 1:
            print("ABORT:", path, "anchor matched", n, "times:", old.strip()[:70]); sys.exit(1)
        src = src.replace(o, rep.replace("\n", nl))
    new[key] = src

for key, path in FILES.items():
    shutil.copyfile(path, path + ".bak")
    open(path, "wb").write(new[key].encode("utf-8"))
    print("patched", path)