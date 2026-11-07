import React from 'react';
import { AlertTriangle, ArrowDown, Award, CheckCircle2, FileText, GitCompare, Layers, Scale, ShieldCheck, Sparkles } from 'lucide-react';
import type { ClaimAssessment, ClaimVerification, ComparisonRow, ComprehensiveComparison, DebateResult, ResearchGap } from '../../types/analysis';
import { DebateExplorer } from './DebateExplorer';

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

export const ComparisonView: React.FC<
  AnalysisViewProps & {
    rows: ComparisonRow[];
    entities?: string[];
    comparisonData?: ComprehensiveComparison;
  }
> = ({ rows, entities, comparisonData, onOpenSources }) => {
  const activeEntities = comparisonData?.entities?.length ? comparisonData.entities : (entities || ['Entity A', 'Entity B']);
  const totalEvidenceCount = rows.reduce((count, row) => count + row.evidenceIds.length, 0);

  const similarities = comparisonData?.similarities || [];
  const differences = comparisonData?.differences || [];
  const contradictions = comparisonData?.contradictions || [];
  const uniqueContributions = comparisonData?.uniqueContributions || [];
  const strengthsAndLimitations = comparisonData?.strengthsAndLimitations || [];
  const synthesis = comparisonData?.synthesis || '';
  const summary = comparisonData?.summary || '';

  const isInsufficient = summary.toLowerCase().includes('not found in available sources') && rows.length === 0;

  if (isInsufficient) {
    return (
      <section className="refire-card p-5 border-amber-400/30 bg-amber-500/5 text-amber-200" aria-labelledby="comparison-title">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-amber-400" />
          <h2 id="comparison-title" className="text-xs font-mono uppercase text-amber-300">Insufficient Evidence for Comparison</h2>
        </div>
        <p className="mt-3 text-xs leading-relaxed text-[#f3faf0]/80">
          Not found in available sources. The selected documents do not contain sufficient overlapping evidence to generate a grounded comparison for this query.
        </p>
      </section>
    );
  }

  return (
    <div className="space-y-4" aria-labelledby="comparison-title">
      {/* 1. Overall Header & Entity Chips */}
      <section className="refire-card p-5">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/8 pb-3">
          <div className="flex items-center gap-2">
            <Scale className="h-4 w-4 text-[#a7d0d2]" />
            <h2 id="comparison-title" className="text-xs font-mono uppercase text-[#f3faf0]/85">
              Research Comparison Analysis
            </h2>
          </div>
          <span className="text-[11px] font-mono text-[#a7d0d2]/70">
            {activeEntities.length} {activeEntities.length === 1 ? 'document' : 'documents'} analyzed
          </span>
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          {activeEntities.map((entity, idx) => (
            <span
              key={idx}
              className="inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-[#0b1219]/80 px-2.5 py-1 text-xs text-[#a7d0d2]"
            >
              <FileText className="h-3 w-3 text-[#d2434e]" />
              <span className="font-medium text-white">{entity}</span>
            </span>
          ))}
        </div>

        {(comparisonData?.notice || comparisonData?.partial) && (
          <div className="mt-3 flex items-center gap-2 rounded-lg border border-amber-400/30 bg-amber-500/10 p-3 text-xs text-amber-200">
            <AlertTriangle className="h-4 w-4 shrink-0 text-amber-400" />
            <span>
              {comparisonData.notice || "Limited comparison — generated from available evidence because AI providers were unavailable."}
            </span>
          </div>
        )}

        {summary && (
          <div className="mt-4 rounded-lg border border-white/5 bg-[#0b1219]/50 p-3.5">
            <p className="text-[10px] font-mono uppercase text-[#a7d0d2]/70">Executive Summary</p>
            <p className="mt-1.5 text-xs leading-relaxed text-[#f3faf0]/85">{summary}</p>
          </div>
        )}
      </section>

      {/* 2. Similarities & Common Findings */}
      {similarities.length > 0 && (
        <section className="refire-card p-5">
          <div className="flex items-center gap-2 pb-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
            <h3 className="text-xs font-mono uppercase text-emerald-300">
              Similarities & Shared Ground
            </h3>
          </div>
          <ul className="mt-2 space-y-2">
            {similarities.map((item, idx) => (
              <li key={idx} className="flex items-start gap-2 text-xs leading-relaxed text-[#f3faf0]/80">
                <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400/80" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* 3. Key Differences */}
      {differences.length > 0 && (
        <section className="refire-card p-5">
          <div className="flex items-center gap-2 pb-2">
            <Layers className="h-4 w-4 text-[#a7d0d2]" />
            <h3 className="text-xs font-mono uppercase text-[#a7d0d2]">
              Key Differences & Divergent Approaches
            </h3>
          </div>
          <ul className="mt-2 space-y-2">
            {differences.map((item, idx) => (
              <li key={idx} className="flex items-start gap-2 text-xs leading-relaxed text-[#f3faf0]/80">
                <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-[#a7d0d2]" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* 4. Side-by-Side Comparison Matrix Table */}
      {rows.length > 0 && (
        <section className="refire-card overflow-hidden">
          <div className="flex items-center justify-between border-b border-white/8 px-5 py-4">
            <div className="flex items-center gap-2">
              <GitCompare className="h-4 w-4 text-[#a7d0d2]" />
              <h3 className="text-xs font-mono uppercase text-[#f3faf0]/75">Comparison Matrix</h3>
            </div>
            <span className="text-[10px] font-mono text-[#f3faf0]/50">
              {rows.length} {rows.length === 1 ? 'dimension' : 'dimensions'}
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[620px] border-collapse text-left text-xs">
              <thead>
                <tr className="bg-[#0b1219]/70 text-[#a7d0d2]">
                  <th className="px-4 py-3 font-medium">Dimension / Criterion</th>
                  {activeEntities.map((entity, idx) => (
                    <th key={idx} className="px-4 py-3 font-medium">
                      {entity}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, rIdx) => {
                  return (
                    <tr key={`${row.criterion}-${rIdx}`} className="border-t border-white/8 hover:bg-white/[0.02]">
                      <th className="px-4 py-3 font-medium text-white align-top min-w-[160px]">
                        {row.criterion}
                      </th>
                      {activeEntities.map((entity, eIdx) => {
                        const valItem = row.values?.find((v) => v.entity === entity);
                        let displayValue = valItem ? valItem.value : (eIdx === 0 ? row.leftValue : row.rightValue);
                        const isNotReported = !displayValue || displayValue === 'NOT_REPORTED' || displayValue === 'N/A' || displayValue.toLowerCase().includes('not found in available sources');

                        return (
                          <td key={eIdx} className="px-4 py-3 text-[#f3faf0]/75 align-top">
                            {isNotReported ? (
                              <span className="italic text-[#f3faf0]/35 text-[11px]">Not reported in sources</span>
                            ) : (
                              <div className="space-y-1.5">
                                <span>{displayValue}</span>
                                {valItem?.chunkId && (
                                  <div className="pt-0.5">
                                    <button
                                      type="button"
                                      onClick={onOpenSources}
                                      className="inline-flex items-center text-[10px] font-mono text-[#a7d0d2]/70 hover:text-white"
                                      title={valItem.evidence || 'View source passage'}
                                    >
                                      [{valItem.chunkId}]
                                    </button>
                                  </div>
                                )}
                              </div>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* 5. Contradictions & Disagreements */}
      {contradictions.length > 0 && (
        <section className="refire-card p-5 border-amber-400/20 bg-amber-500/[0.03]">
          <div className="flex items-center gap-2 pb-2">
            <AlertTriangle className="h-4 w-4 text-amber-400" />
            <h3 className="text-xs font-mono uppercase text-amber-300">
              Contradictions & Disagreements ({contradictions.length})
            </h3>
          </div>
          <div className="mt-3 space-y-3">
            {contradictions.map((c, idx) => (
              <article key={idx} className="rounded-lg border border-amber-400/20 bg-[#0b1219]/60 p-4">
                <p className="text-xs font-semibold text-amber-200">{c.topic}</p>
                <div className="mt-2.5 grid gap-2 sm:grid-cols-2 text-xs">
                  {c.claimA && (
                    <div className="rounded border border-white/5 bg-black/20 p-2.5">
                      <span className="text-[10px] font-mono uppercase text-[#a7d0d2] block mb-1">
                        {c.documentA || 'Document A'}
                      </span>
                      <p className="text-[#f3faf0]/85 italic">“{c.claimA}”</p>
                    </div>
                  )}
                  {c.claimB && (
                    <div className="rounded border border-white/5 bg-black/20 p-2.5">
                      <span className="text-[10px] font-mono uppercase text-[#d2434e] block mb-1">
                        {c.documentB || 'Document B'}
                      </span>
                      <p className="text-[#f3faf0]/85 italic">“{c.claimB}”</p>
                    </div>
                  )}
                </div>
                {c.explanation && (
                  <p className="mt-2.5 text-xs text-[#f3faf0]/75 leading-relaxed">
                    <span className="font-medium text-[#a7d0d2]">Analysis: </span>
                    {c.explanation}
                  </p>
                )}
                {c.evidenceChunks.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {c.evidenceChunks.map((chunk, cIdx) => (
                      <span key={cIdx} className="rounded bg-black/40 px-1.5 py-0.5 text-[9px] font-mono text-[#a7d0d2]/70">
                        {chunk}
                      </span>
                    ))}
                  </div>
                )}
              </article>
            ))}
          </div>
        </section>
      )}

      {/* 6. Unique Contributions per Document */}
      {uniqueContributions.length > 0 && (
        <section className="refire-card p-5">
          <div className="flex items-center gap-2 pb-2">
            <Award className="h-4 w-4 text-[#d2434e]" />
            <h3 className="text-xs font-mono uppercase text-[#f3faf0]/85">Unique Contributions</h3>
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {uniqueContributions.map((u, idx) => (
              <article key={idx} className="rounded-lg border border-white/8 bg-[#0b1219]/60 p-4">
                <span className="inline-block rounded bg-white/5 px-2 py-0.5 text-[10px] font-mono uppercase text-[#a7d0d2]">
                  {u.document}
                </span>
                <p className="mt-2 text-xs font-medium text-white leading-relaxed">{u.contribution}</p>
                {u.evidence && (
                  <p className="mt-2 text-[11px] italic text-[#f3faf0]/60 border-l border-white/10 pl-2">
                    “{u.evidence}”
                  </p>
                )}
              </article>
            ))}
          </div>
        </section>
      )}

      {/* 7. Strengths & Limitations */}
      {strengthsAndLimitations.length > 0 && (
        <section className="refire-card p-5">
          <div className="flex items-center gap-2 pb-2">
            <FileText className="h-4 w-4 text-[#a7d0d2]" />
            <h3 className="text-xs font-mono uppercase text-[#f3faf0]/85">Strengths & Limitations</h3>
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {strengthsAndLimitations.map((sl, idx) => (
              <article key={idx} className="rounded-lg border border-white/8 bg-[#0b1219]/60 p-4">
                <p className="text-xs font-semibold text-white mb-2">{sl.document}</p>
                {sl.strengths.length > 0 && (
                  <div className="mb-2">
                    <p className="text-[10px] font-mono uppercase text-emerald-300">Key Strengths</p>
                    <ul className="mt-1 space-y-1">
                      {sl.strengths.map((s, sIdx) => (
                        <li key={sIdx} className="text-xs text-[#f3faf0]/80 flex items-start gap-1.5">
                          <span className="text-emerald-400 font-bold">+</span>
                          <span>{s}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {sl.limitations.length > 0 && (
                  <div>
                    <p className="text-[10px] font-mono uppercase text-amber-300">Limitations & Assumptions</p>
                    <ul className="mt-1 space-y-1">
                      {sl.limitations.map((l, lIdx) => (
                        <li key={lIdx} className="text-xs text-[#f3faf0]/80 flex items-start gap-1.5">
                          <span className="text-amber-400 font-bold">-</span>
                          <span>{l}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </article>
            ))}
          </div>
        </section>
      )}

      {/* 8. Evidence-Backed Final Synthesis */}
      {synthesis && (
        <section className="rounded-xl border border-[#d2434e]/30 bg-[#d2434e]/5 p-5">
          <p className="text-[10px] font-mono uppercase text-[#d2434e]">Evidence-Backed Synthesis</p>
          <p className="mt-2 text-xs sm:text-sm leading-relaxed text-[#f3faf0]/85">{synthesis}</p>
        </section>
      )}

      {/* Review linked evidence button */}
      <div className="px-1">
        <EvidenceButton count={totalEvidenceCount} onOpenSources={onOpenSources} />
      </div>
    </div>
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

export { DebateExplorer };

export const DebateView: React.FC<
  AnalysisViewProps & {
    debate: DebateResult;
    onOpenDocument?: (docName: string, page?: number | string) => void;
  }
> = ({ debate, onOpenSources, onOpenDocument }) => (
  <DebateExplorer
    debate={debate}
    onOpenSources={onOpenSources}
    onOpenDocument={onOpenDocument}
  />
);