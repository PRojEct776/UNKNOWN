"""Guarded patch: Verify frontend. All-or-nothing; aborts unless every anchor matches once."""
import os
import shutil
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(BASE, "..", "frontend", "src"))
P_API = os.path.join(SRC, "lib", "api.ts")
P_AN = os.path.join(SRC, "types", "analysis.ts")
P_WB = os.path.join(SRC, "lib", "workspaceResultBuilder.ts")
P_VIEW = os.path.join(SRC, "components", "analysis", "AnalysisViews.tsx")

API, AN, WB, VIEW = [], [], [], []

# ---------------- api.ts ----------------
API.append((r'''export interface BackendVerifyResponse {''', r'''export interface BackendAtomicClaimVerification {
  claim: string;
  verdict: string;
  confidence?: number;
  explanation?: string;
  evidence?: string[];
  supporting_evidence?: string[];
  contradicting_evidence?: string[];
  source_chunk_ids?: string[];
}

export interface BackendVerifyResponse {'''))

API.append((r'''  source_chunk_ids: string[];
  supporting_evidence?: string[];
  contradicting_evidence?: string[];''', r'''  source_chunk_ids: string[];
  supporting_evidence?: string[];
  contradicting_evidence?: string[];
  atomic_claims?: BackendAtomicClaimVerification[];'''))

# ---------------- analysis.ts ----------------
AN.append((r'''  counterEvidenceIds: string[];''', r'''  counterEvidenceIds: string[];
  verdict?: string;
  supportingQuotes?: string[];
  contradictingQuotes?: string[];
  partOfClaim?: boolean;'''))

# ---------------- workspaceResultBuilder.ts ----------------
WB.append((r'''export function buildResultFromVerifyResponse(''', r'''function verifyAssessment(
  verdict: string | undefined,
): 'supported' | 'contradicted' | 'uncertain' {
  const normalized = (verdict || '').toUpperCase().trim();
  if (normalized === 'SUPPORTED') return 'supported';
  if (normalized === 'CONTRADICTED') return 'contradicted';
  return 'uncertain';
}

export function buildResultFromVerifyResponse('''))

WB.append((r'''  const rawVerdict = (res.verdict || 'uncertain').toLowerCase();
  const assessment: 'supported' | 'contradicted' | 'uncertain' =
    rawVerdict.includes('support') && !rawVerdict.includes('unsupported')
      ? 'supported'
      : rawVerdict.includes('contradict')
      ? 'contradicted'
      : 'uncertain';''', r'''  const assessment = verifyAssessment(res.verdict);'''))

WB.append((r'''    evidenceIds: res.source_chunk_ids || [],
    counterEvidenceIds: [],
  };''', r'''    evidenceIds: res.source_chunk_ids || [],
    counterEvidenceIds: [] as string[],
    verdict: res.verdict,
    supportingQuotes: res.supporting_evidence || [],
    contradictingQuotes: res.contradicting_evidence || [],
  };

  const partItems = (res.atomic_claims || []).map((part) => ({
    claim: part.claim,
    assessment: verifyAssessment(part.verdict),
    explanation: part.explanation || 'No explanation was provided for this part.',
    evidenceIds: part.source_chunk_ids || [],
    counterEvidenceIds: [] as string[],
    verdict: part.verdict,
    supportingQuotes: part.supporting_evidence || [],
    contradictingQuotes: part.contradicting_evidence || [],
    partOfClaim: true,
  }));'''))

WB.append((r'''    verification: [verificationItem],''',
           r'''    verification: [verificationItem, ...partItems],'''))

# ---------------- AnalysisViews.tsx ----------------
VIEW.append((r'''export const VerificationView:''', r'''const VERDICT_LABELS: Record<string, string> = {
  SUPPORTED: 'Supported',
  PARTIALLY_SUPPORTED: 'Partially supported',
  CONTRADICTED: 'Contradicted',
  UNSUPPORTED: 'Unsupported',
  UNVERIFIABLE: 'Unverifiable',
  NOT_FOUND: 'No evidence found',
};

const verdictLabel = (verdict: string | undefined, fallback: string): string =>
  (verdict && VERDICT_LABELS[verdict.toUpperCase().trim()]) || fallback;

export const VerificationView:'''))

VIEW.append((r'''{results.map((result) => {''', r'''{results.map((result, index) => {'''))

VIEW.append((r'''<article key={result.claim} className="rounded-lg border border-white/8 bg-[#0b1219]/60 p-4">''',
r'''<article key={`${index}-${result.claim}`} className={`rounded-lg border border-white/8 bg-[#0b1219]/60 p-4 ${result.partOfClaim ? 'ml-4' : ''}`}>'''))

VIEW.append((r'''${assessmentStyle[result.assessment]}`}>{result.assessment}</span>''',
r'''${assessmentStyle[result.assessment]}`}>{verdictLabel(result.verdict, result.assessment)}</span>'''))

VIEW.append((r'''<p className="mt-2 text-xs leading-relaxed text-[#f3faf0]/70">{result.explanation}</p>''',
r'''<p className="mt-2 text-xs leading-relaxed text-[#f3faf0]/70">{result.explanation}</p>
            {(result.supportingQuotes ?? []).length > 0 && (
              <div className="mt-3">
                <p className="text-[10px] font-mono uppercase text-emerald-200/80">Supporting evidence</p>
                <ul className="mt-1 space-y-1">
                  {(result.supportingQuotes ?? []).map((quote, quoteIndex) => (
                    <li key={quoteIndex} className="text-xs italic text-[#f3faf0]/70">{quote}</li>
                  ))}
                </ul>
              </div>
            )}
            {(result.contradictingQuotes ?? []).length > 0 && (
              <div className="mt-3">
                <p className="text-[10px] font-mono uppercase text-rose-200/80">Contradicting evidence</p>
                <ul className="mt-1 space-y-1">
                  {(result.contradictingQuotes ?? []).map((quote, quoteIndex) => (
                    <li key={quoteIndex} className="text-xs italic text-[#f3faf0]/70">{quote}</li>
                  ))}
                </ul>
              </div>
            )}'''))

VIEW.append((r'''<EvidenceButton count={evidenceCount} onOpenSources={onOpenSources} />''',
r'''{evidenceCount > 0 && <EvidenceButton count={evidenceCount} onOpenSources={onOpenSources} />}'''))

PLAN = [(P_API, API), (P_AN, AN), (P_WB, WB), (P_VIEW, VIEW)]


def die(msg):
    print("ABORT:", msg)
    sys.exit(1)


def conv(s, eol):
    return s.replace("\r\n", "\n").replace("\n", eol)


results = []
for path, edits in PLAN:
    if not os.path.exists(path):
        die("missing file " + path)
    if os.path.exists(path + ".bak4"):
        die(path + ".bak4 already exists; move it first")
    try:
        text = open(path, "rb").read().decode("utf-8")
    except UnicodeDecodeError:
        die("not valid UTF-8: " + path)
    if "\r\n" in text:
        if "\n" in text.replace("\r\n", ""):
            die("mixed line endings in " + path)
        eol = "\r\n"
    else:
        eol = "\n"
    for i, (anchor, repl) in enumerate(edits, 1):
        a = conv(anchor, eol)
        n = text.count(a)
        if n != 1:
            die("%s edit %d: anchor matched %d times (need exactly 1)"
                % (os.path.basename(path), i, n))
        text = text.replace(a, conv(repl, eol))
    results.append((path, text))

for path, text in results:
    shutil.copy2(path, path + ".bak4")
    with open(path, "wb") as f:
        f.write(text.encode("utf-8"))
    print("patched", path, "(backup: .bak4)")
print("OK")