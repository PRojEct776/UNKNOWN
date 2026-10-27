import React from 'react';
import { ArrowDown, Scale, ShieldCheck, Sparkles } from 'lucide-react';
import type { ClaimAssessment, ClaimVerification, ComparisonRow, DebateResult, ResearchGap } from '../../types/analysis';

interface AnalysisViewProps {
  onOpenSources: () => void;
}

const EvidenceButton: React.FC<AnalysisViewProps & { count: number }> = ({ count, onOpenSources }) => (
  <button type="button" onClick={onOpenSources} className="mt-3 text-xs text-[#a7d0d2] hover:text-white">
    Review {count} linked evidence {count === 1 ? 'item' : 'items'}
  </button>
);

const assessmentStyle: Record<ClaimAssessment, string> = {
  supported: 'border-emerald-300/30 bg-emerald-300/10 text-emerald-200',
  contradicted: 'border-rose-300/30 bg-rose-300/10 text-rose-200',
  uncertain: 'border-amber-200/30 bg-amber-200/10 text-amber-100',
};

const VERDICT_LABELS: Record<string, string> = {
  SUPPORTED: 'Supported',
  PARTIALLY_SUPPORTED: 'Partially supported',
  CONTRADICTED: 'Contradicted',
  UNSUPPORTED: 'Unsupported',
  UNVERIFIABLE: 'Unverifiable',
  NOT_FOUND: 'No evidence found',
};

const verdictLabel = (verdict: string | undefined, fallback: string): string =>
  (verdict && VERDICT_LABELS[verdict.toUpperCase().trim()]) || fallback;

export const VerificationView: React.FC<AnalysisViewProps & { results: ClaimVerification[] }> = ({ results, onOpenSources }) => (
  <section className="refire-card p-5" aria-labelledby="verification-title">
    <div className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-[#a7d0d2]" /><h2 id="verification-title" className="text-xs font-mono uppercase text-[#f3faf0]/75">Claim verification</h2></div>
    <div className="mt-4 space-y-3">
      {results.map((result, index) => {
        const evidenceCount = result.evidenceIds.length + result.counterEvidenceIds.length;
        return (
          <article key={`${index}-${result.claim}`} className={`rounded-lg border border-white/8 bg-[#0b1219]/60 p-4 ${result.partOfClaim ? 'ml-4' : ''}`}>
            <p className="text-sm text-white">“{result.claim}”</p>
            <span className={`mt-3 inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold capitalize ${assessmentStyle[result.assessment]}`}>{verdictLabel(result.verdict, result.assessment)}</span>
            <p className="mt-2 text-xs leading-relaxed text-[#f3faf0]/70">{result.explanation}</p>
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
            )}
            {evidenceCount > 0 && <EvidenceButton count={evidenceCount} onOpenSources={onOpenSources} />}
            {result.counterEvidenceIds.length > 0 && <p className="mt-1 text-[10px] text-rose-200/70">Contradicting evidence is tracked separately.</p>}
          </article>
        );
      })}
    </div>
  </section>
);

export const ComparisonView: React.FC<AnalysisViewProps & { rows: ComparisonRow[]; entities?: string[] }> = ({ rows, entities, onOpenSources }) => {
  const leftHeader = entities?.[0] || 'Entity A';
  const rightHeader = entities?.[1] || 'Entity B';
  return (
    <section className="refire-card overflow-hidden" aria-labelledby="comparison-title">
      <div className="flex items-center gap-2 border-b border-white/8 px-5 py-4"><Scale className="h-4 w-4 text-[#a7d0d2]" /><h2 id="comparison-title" className="text-xs font-mono uppercase text-[#f3faf0]/75">Comparison matrix</h2></div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px] border-collapse text-left text-xs">
          <thead><tr className="bg-[#0b1219]/70 text-[#a7d0d2]"><th className="px-4 py-3 font-medium">Criterion</th><th className="px-4 py-3 font-medium">{leftHeader}</th><th className="px-4 py-3 font-medium">{rightHeader}</th></tr></thead>
          <tbody>{rows.map((row) => <tr key={row.criterion} className="border-t border-white/8"><th className="px-4 py-3 font-medium text-white">{row.criterion}</th><td className="px-4 py-3 text-[#f3faf0]/75">{row.leftValue}</td><td className="px-4 py-3 text-[#f3faf0]/75">{row.rightValue}</td></tr>)}</tbody>
        </table>
      </div>
      <div className="px-5 pb-4"><EvidenceButton count={rows.reduce((count, row) => count + row.evidenceIds.length, 0)} onOpenSources={onOpenSources} /></div>
    </section>
  );
};

export const GapView: React.FC<AnalysisViewProps & { gap: ResearchGap }> = ({ gap, onOpenSources }) => {
  const stages = [
    { title: 'Current knowledge', detail: gap.currentKnowledge },
    { title: 'Missing connection', detail: gap.missingConnection },
    { title: 'Potential research gap', detail: gap.potentialGap },
  ];
  return (
    <section className="refire-card p-5" aria-labelledby="gap-title">
      <div className="flex items-center gap-2"><Sparkles className="h-4 w-4 text-[#a7d0d2]" /><h2 id="gap-title" className="text-xs font-mono uppercase text-[#f3faf0]/75">Research gap exploration</h2></div>
      <h3 className="mt-4 text-base font-semibold text-white">{gap.title}</h3>
      <div className="mt-4 space-y-2">{stages.map((stage, index) => <React.Fragment key={stage.title}><article className="rounded-lg border border-white/8 bg-[#0b1219]/60 p-4"><p className="text-[10px] font-mono uppercase text-[#a7d0d2]">{stage.title}</p><p className="mt-2 text-xs leading-relaxed text-[#f3faf0]/75">{stage.detail}</p></article>{index < stages.length - 1 && <ArrowDown className="ml-4 h-4 w-4 text-[#4d728e]" />}</React.Fragment>)}</div>
      <p className="mt-4 text-[11px] text-amber-100/75">A gap is a question to investigate, not a confirmed finding.</p>
      <EvidenceButton count={gap.evidenceIds.length} onOpenSources={onOpenSources} />
    </section>
  );
};

export const DebateView: React.FC<AnalysisViewProps & { debate: DebateResult }> = ({ debate, onOpenSources }) => (
  <section className="space-y-4" aria-labelledby="debate-title">
    <h2 id="debate-title" className="text-xs font-mono uppercase text-[#f3faf0]/75">Evidence-aware debate</h2>
    <div className="grid gap-3 md:grid-cols-2">
      {debate.positions.map((position) => <article key={position.id} className="refire-card p-5"><p className="text-[10px] font-mono uppercase text-[#a7d0d2]">{position.title}</p><p className="mt-3 text-sm leading-relaxed text-white">{position.claim}</p><EvidenceButton count={position.evidenceIds.length} onOpenSources={onOpenSources} /></article>)}
    </div>
    <article className="rounded-xl border border-[#d2434e]/25 bg-[#d2434e]/5 p-5"><p className="text-[10px] font-mono uppercase text-[#d2434e]">Balanced conclusion</p><p className="mt-2 text-sm leading-relaxed text-[#f3faf0]/80">{debate.conclusion}</p></article>
  </section>
);