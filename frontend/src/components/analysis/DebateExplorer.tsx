import React, { useState, useMemo } from 'react';
import {
  AlertCircle,
  AlertTriangle,
  Award,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Download,
  ExternalLink,
  FileText,
  HelpCircle,
  Maximize2,
  Minimize2,
  Scale,
  ShieldAlert,
  Swords,
} from 'lucide-react';
import type { DebateResult } from '../../types/analysis';
import { downloadJsonFile } from '../../lib/exportUtils';

interface DebateExplorerProps {
  debate: DebateResult;
  onOpenSources?: () => void;
  onOpenDocument?: (docName: string, page?: number | string) => void;
}

export const DebateExplorer: React.FC<DebateExplorerProps> = ({
  debate,
  onOpenSources,
  onOpenDocument,
}) => {
  const [activeTab, setActiveTab] = useState<'arguments' | 'openings' | 'rebuttals' | 'synthesis'>('arguments');
  const [selectedSideFilter, setSelectedSideFilter] = useState<'ALL' | 'PRO' | 'CON'>('ALL');
  const [selectedStrengthFilter, setSelectedStrengthFilter] = useState<string>('ALL');
  const [expandedArgId, setExpandedArgId] = useState<string | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Group arguments
  const proArguments = useMemo(() => {
    return (debate.arguments || []).filter(
      (a) => a.side === 'POSITION_A' || a.side === 'PRO'
    );
  }, [debate.arguments]);

  const conArguments = useMemo(() => {
    return (debate.arguments || []).filter(
      (a) => a.side === 'POSITION_B' || a.side === 'CON'
    );
  }, [debate.arguments]);

  // Stats
  const proStrongCount = proArguments.filter((a) => a.evidenceStrength === 'STRONG').length;
  const conStrongCount = conArguments.filter((a) => a.evidenceStrength === 'STRONG').length;
  const totalEvidenceCount = (debate.sources || []).length || (debate.arguments || []).reduce((acc, a) => acc + (a.evidence?.length || 0), 0);

  // Export handlers
  const handleExportJson = () => {
    const filename = `debate_report_${(debate.topic || 'debate').replace(/[^a-zA-Z0-9_-]/g, '_')}_${Date.now()}.json`;
    downloadJsonFile(filename, debate);
  };

  const handleExportMarkdown = () => {
    const lines: string[] = [
      `# Evidence-Grounded Research Debate Report`,
      `**Proposition:** ${debate.proposition || debate.query}`,
      `**Topic:** ${debate.topic || debate.query}`,
      `**Generated:** ${new Date().toLocaleString()}`,
      debate.partial ? `**Notice:** Deterministic Fallback Mode (LLM providers unavailable)` : '',
      ``,
      `## 1. Opening Statements`,
      `### Pro (Position A):`,
      debate.openingStatements?.pro || debate.positionA || 'No opening statement recorded.',
      ``,
      `### Con (Position B):`,
      debate.openingStatements?.con || debate.positionB || 'No opening statement recorded.',
      ``,
      `## 2. Arguments & Empirical Evidence`,
      `### Pro Arguments:`,
    ];

    proArguments.forEach((arg, i) => {
      lines.push(
        `#### Pro ${i + 1}: ${arg.title}`,
        `- **Argument:** ${arg.argument}`,
        `- **Evidence Type:** ${arg.evidenceType || 'DIRECT_EVIDENCE'}`,
        `- **Evidence Strength:** ${arg.evidenceStrength || 'MODERATE'} (Confidence: ${Math.round((arg.confidence || 0.85) * 100)}%)`,
        `- **Source:** ${arg.document || 'Document'} (Page: ${arg.page || 1}, Chunk: ${arg.chunkId || 'N/A'})`,
        arg.evidence?.length ? `- **Evidence Passage:** "${arg.evidence[0]}"` : '',
        ``
      );
    });

    lines.push(`### Con Arguments:`);
    conArguments.forEach((arg, i) => {
      lines.push(
        `#### Con ${i + 1}: ${arg.title}`,
        `- **Counterargument:** ${arg.argument}`,
        `- **Evidence Type:** ${arg.evidenceType || 'DIRECT_EVIDENCE'}`,
        `- **Evidence Strength:** ${arg.evidenceStrength || 'MODERATE'} (Confidence: ${Math.round((arg.confidence || 0.85) * 100)}%)`,
        `- **Source:** ${arg.document || 'Document'} (Page: ${arg.page || 1}, Chunk: ${arg.chunkId || 'N/A'})`,
        arg.evidence?.length ? `- **Evidence Passage:** "${arg.evidence[0]}"` : '',
        ``
      );
    });

    if (debate.rebuttals && debate.rebuttals.length > 0) {
      lines.push(`## 3. Rebuttal Rounds`);
      debate.rebuttals.forEach((reb, i) => {
        const sideLabel = reb.side === 'POSITION_A' || reb.side === 'PRO' ? 'Pro Rebuts Con' : 'Con Rebuts Pro';
        lines.push(
          `### Rebuttal ${i + 1} (${sideLabel})`,
          `- **Challenging Argument:** "${reb.targetArgument}"`,
          `- **Rebuttal:** ${reb.rebuttal}`,
          reb.evidence?.length ? `- **Counter-Evidence:** "${reb.evidence[0]}"` : '',
          ``
        );
      });
    }

    if (debate.agreements?.length || debate.disagreements?.length || debate.unresolvedQuestions?.length) {
      lines.push(`## 4. Points of Agreement & Open Questions`);
      if (debate.agreements?.length) {
        lines.push(`### Agreements across Literature:`);
        debate.agreements.forEach((a) => lines.push(`- ${a}`));
        lines.push(``);
      }
      if (debate.disagreements?.length) {
        lines.push(`### Core Points of Disagreement:`);
        debate.disagreements.forEach((d) => lines.push(`- ${d}`));
        lines.push(``);
      }
      if (debate.unresolvedQuestions?.length) {
        lines.push(`### Unresolved Research Questions:`);
        debate.unresolvedQuestions.forEach((u) => lines.push(`- ${u}`));
        lines.push(``);
      }
    }

    lines.push(
      `## 5. Neutral Assessment & Verdict`,
      `### Neutral Evidence Strength Assessment:`,
      debate.neutralAssessment || debate.conclusion,
      ``,
      `### Conclusion (Distinguishing Evidence Strength from Certainty):`,
      debate.conclusion,
      ``,
      `---`,
      `*Generated by UNKNOWN Evidence-Based Dialectical Debate Engine.*`
    );

    const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `debate_report_${(debate.topic || 'debate').replace(/[^a-zA-Z0-9_-]/g, '_')}_${Date.now()}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const getStrengthBadge = (strength?: string) => {
    switch (strength) {
      case 'STRONG':
        return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300';
      case 'MODERATE':
        return 'border-cyan-500/30 bg-cyan-500/10 text-cyan-300';
      case 'WEAK':
        return 'border-amber-500/30 bg-amber-500/10 text-amber-300';
      case 'NONE':
      default:
        return 'border-rose-500/30 bg-rose-500/10 text-rose-300';
    }
  };

  const getTypeBadge = (type?: string) => {
    switch (type) {
      case 'DIRECT_EVIDENCE':
        return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300';
      case 'REASONABLE_INFERENCE':
        return 'border-purple-500/30 bg-purple-500/10 text-purple-300';
      case 'UNSUPPORTED':
      default:
        return 'border-rose-500/30 bg-rose-500/10 text-rose-300';
    }
  };

  return (
    <section
      className={`rounded-2xl border border-white/10 bg-[#070b0f] text-[#f3faf0] overflow-hidden shadow-2xl transition-all ${
        isFullscreen ? 'fixed inset-4 z-50 flex flex-col' : 'my-4'
      }`}
      aria-label="Evidence-Based Debate Explorer"
    >
      {/* =====================================================================
          HEADER BAR
      ===================================================================== */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 bg-[#0d151e] px-5 py-4">
        <div className="flex items-center gap-3">
          <div className="rounded-xl border border-[#d2434e]/30 bg-[#d2434e]/10 p-2.5 shadow-sm">
            <Scale className="h-5 w-5 text-[#d2434e]" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono font-bold tracking-wider uppercase text-[#d2434e]">
                AI Debate Engine
              </span>
              {debate.partial && (
                <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-mono text-amber-300">
                  Deterministic Fallback
                </span>
              )}
            </div>
            <h2 className="text-base font-semibold text-white tracking-tight">
              {debate.proposition || debate.query}
            </h2>
          </div>
        </div>

        {/* View Navigation & Exports */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex rounded-lg border border-white/10 bg-[#141d26]/80 p-0.5">
            <button
              type="button"
              onClick={() => setActiveTab('arguments')}
              className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                activeTab === 'arguments' ? 'bg-[#d2434e] text-white shadow-sm' : 'text-[#a7d0d2] hover:text-white'
              }`}
            >
              Pro vs Con ({(debate.arguments || []).length})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('openings')}
              className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                activeTab === 'openings' ? 'bg-[#d2434e] text-white shadow-sm' : 'text-[#a7d0d2] hover:text-white'
              }`}
            >
              Opening Statements
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('rebuttals')}
              className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                activeTab === 'rebuttals' ? 'bg-[#d2434e] text-white shadow-sm' : 'text-[#a7d0d2] hover:text-white'
              }`}
            >
              Rebuttals ({(debate.rebuttals || []).length})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('synthesis')}
              className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                activeTab === 'synthesis' ? 'bg-[#d2434e] text-white shadow-sm' : 'text-[#a7d0d2] hover:text-white'
              }`}
            >
              Verdict & Synthesis
            </button>
          </div>

          <div className="h-4 w-px bg-white/10" />

          {/* Export Actions */}
          <button
            type="button"
            onClick={handleExportJson}
            title="Export debate as JSON"
            className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-[#141d26] px-2.5 py-1.5 text-xs text-[#a7d0d2] hover:border-[#4d728e] hover:text-white transition-colors"
          >
            <Download className="h-3.5 w-3.5 text-[#d2434e]" />
            <span>JSON</span>
          </button>
          <button
            type="button"
            onClick={handleExportMarkdown}
            title="Export debate as Markdown"
            className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-[#141d26] px-2.5 py-1.5 text-xs text-[#a7d0d2] hover:border-[#4d728e] hover:text-white transition-colors"
          >
            <FileText className="h-3.5 w-3.5 text-[#a7d0d2]" />
            <span>Report</span>
          </button>

          <button
            type="button"
            onClick={() => setIsFullscreen(!isFullscreen)}
            title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
            className="rounded-lg border border-white/10 bg-[#141d26] p-1.5 text-[#a7d0d2] hover:text-white transition-colors"
          >
            {isFullscreen ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
          </button>
        </div>
      </div>

      {/* =====================================================================
          SUMMARY METRICS BAR
      ===================================================================== */}
      <div className="grid grid-cols-2 md:grid-cols-4 border-b border-white/5 bg-[#090f16] px-5 py-3 text-xs">
        <div className="flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 text-emerald-400" />
          <span className="text-[#f3faf0]/70">Pro Arguments:</span>
          <span className="font-semibold text-emerald-300">
            {proArguments.length} ({proStrongCount} Strong)
          </span>
        </div>
        <div className="flex items-center gap-2">
          <ShieldAlert className="h-4 w-4 text-rose-400" />
          <span className="text-[#f3faf0]/70">Con Arguments:</span>
          <span className="font-semibold text-rose-300">
            {conArguments.length} ({conStrongCount} Strong)
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Swords className="h-4 w-4 text-purple-400" />
          <span className="text-[#f3faf0]/70">Rebuttal Rounds:</span>
          <span className="font-semibold text-white">{(debate.rebuttals || []).length}</span>
        </div>
        <div className="flex items-center gap-2">
          <BookOpen className="h-4 w-4 text-[#a7d0d2]" />
          <span className="text-[#f3faf0]/70">Evidence Chunks:</span>
          <button
            type="button"
            onClick={onOpenSources}
            className="font-semibold text-[#a7d0d2] hover:underline"
          >
            {totalEvidenceCount} linked citations
          </button>
        </div>
      </div>

      {/* Notice Bar if Fallback */}
      {debate.notice && (
        <div className="flex items-start gap-2.5 border-b border-amber-500/20 bg-amber-500/5 px-5 py-2.5 text-xs text-amber-200">
          <AlertTriangle className="h-4 w-4 text-amber-400 flex-shrink-0 mt-0.5" />
          <p className="leading-relaxed">{debate.notice}</p>
        </div>
      )}

      {/* =====================================================================
          MAIN BODY
      ===================================================================== */}
      <div className="p-5 flex-1 overflow-y-auto space-y-6">
        {/* TAB 1: ARGUMENTS (PRO VS CON) */}
        {activeTab === 'arguments' && (
          <div className="space-y-5">
            {/* Filter controls */}
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/5 bg-[#0b1219] p-3 text-xs">
              <div className="flex items-center gap-2">
                <span className="text-[#f3faf0]/60 font-medium">Position:</span>
                <button
                  type="button"
                  onClick={() => setSelectedSideFilter('ALL')}
                  className={`rounded-md px-2.5 py-1 font-medium transition-colors ${
                    selectedSideFilter === 'ALL' ? 'bg-[#d2434e] text-white' : 'bg-white/5 text-[#a7d0d2]'
                  }`}
                >
                  All ({debate.arguments?.length || 0})
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedSideFilter('PRO')}
                  className={`rounded-md px-2.5 py-1 font-medium transition-colors ${
                    selectedSideFilter === 'PRO' ? 'bg-emerald-600 text-white' : 'bg-white/5 text-emerald-300'
                  }`}
                >
                  Pro ({proArguments.length})
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedSideFilter('CON')}
                  className={`rounded-md px-2.5 py-1 font-medium transition-colors ${
                    selectedSideFilter === 'CON' ? 'bg-rose-600 text-white' : 'bg-white/5 text-rose-300'
                  }`}
                >
                  Con ({conArguments.length})
                </button>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-[#f3faf0]/60 font-medium">Evidence Strength:</span>
                {['ALL', 'STRONG', 'MODERATE', 'WEAK', 'NONE'].map((str) => (
                  <button
                    key={str}
                    type="button"
                    onClick={() => setSelectedStrengthFilter(str)}
                    className={`rounded-md px-2 py-0.5 text-[11px] font-medium transition-colors ${
                      selectedStrengthFilter === str ? 'bg-white/20 text-white' : 'bg-white/5 text-[#a7d0d2]'
                    }`}
                  >
                    {str}
                  </button>
                ))}
              </div>
            </div>

            {/* Split Columns Grid */}
            <div className="grid gap-4 md:grid-cols-2">
              {/* PRO COLUMN */}
              {(selectedSideFilter === 'ALL' || selectedSideFilter === 'PRO') && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2 border-b border-emerald-500/20 pb-2">
                    <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                    <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-emerald-300">
                      Pro: Supporting Proposition
                    </h3>
                  </div>

                  {proArguments.length === 0 ? (
                    <div className="rounded-xl border border-white/5 bg-[#0b1219] p-4 text-xs text-[#f3faf0]/60 italic">
                      No direct pro arguments found in the selected evidence.
                    </div>
                  ) : (
                    proArguments
                      .filter((a) => selectedStrengthFilter === 'ALL' || a.evidenceStrength === selectedStrengthFilter)
                      .map((arg) => {
                        const isExpanded = expandedArgId === arg.id;
                        return (
                          <article
                            key={arg.id}
                            className="rounded-xl border border-emerald-500/20 bg-[#0a151b] p-4 shadow-sm transition-all hover:border-emerald-500/40"
                          >
                            <div className="flex items-start justify-between gap-2">
                              <h4 className="text-sm font-semibold text-emerald-200 leading-snug">
                                {arg.title}
                              </h4>
                              <span
                                className={`rounded-full border px-2 py-0.5 text-[10px] font-mono uppercase ${getStrengthBadge(
                                  arg.evidenceStrength
                                )}`}
                              >
                                {arg.evidenceStrength || 'MODERATE'}
                              </span>
                            </div>

                            <p className="mt-2 text-xs leading-relaxed text-[#f3faf0]/90">
                              {arg.argument}
                            </p>

                            <div className="mt-3 flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-white/5 text-[11px]">
                              <span
                                className={`rounded border px-1.5 py-0.5 text-[10px] font-mono ${getTypeBadge(
                                  arg.evidenceType
                                )}`}
                              >
                                {arg.evidenceType || 'DIRECT_EVIDENCE'}
                              </span>

                              {arg.document && (
                                <button
                                  type="button"
                                  onClick={() => onOpenDocument?.(arg.document!, arg.page)}
                                  className="flex items-center gap-1 text-[11px] font-mono text-[#a7d0d2] hover:text-white hover:underline"
                                >
                                  <span>{arg.document}</span>
                                  {arg.page ? <span>(p. {arg.page})</span> : null}
                                  <ExternalLink className="h-3 w-3" />
                                </button>
                              )}
                            </div>

                            {/* Expandable verbatim evidence */}
                            {Boolean(arg.evidence?.length) && (
                              <div className="mt-2.5">
                                <button
                                  type="button"
                                  onClick={() => setExpandedArgId(isExpanded ? null : arg.id)}
                                  className="flex items-center gap-1 text-[11px] text-[#a7d0d2]/80 hover:text-white font-medium"
                                >
                                  <span>{isExpanded ? 'Hide Evidence Quote' : 'View Evidence Passage'}</span>
                                  {isExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                                </button>
                                {isExpanded && (
                                  <blockquote className="mt-2 rounded-lg border-l-2 border-emerald-500/50 bg-[#070e14] p-3 text-xs italic text-[#f3faf0]/80">
                                    "{arg.evidence![0]}"
                                    {arg.chunkId && (
                                      <span className="block mt-1 font-mono text-[10px] text-[#a7d0d2]/60">
                                        Chunk ID: {arg.chunkId}
                                      </span>
                                    )}
                                  </blockquote>
                                )}
                              </div>
                            )}
                          </article>
                        );
                      })
                  )}
                </div>
              )}

              {/* CON COLUMN */}
              {(selectedSideFilter === 'ALL' || selectedSideFilter === 'CON') && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2 border-b border-rose-500/20 pb-2">
                    <ShieldAlert className="h-4 w-4 text-rose-400" />
                    <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-rose-300">
                      Con: Challenging Proposition
                    </h3>
                  </div>

                  {conArguments.length === 0 ? (
                    <div className="rounded-xl border border-white/5 bg-[#0b1219] p-4 text-xs text-[#f3faf0]/60 italic">
                      No direct counterarguments found in the selected evidence.
                    </div>
                  ) : (
                    conArguments
                      .filter((a) => selectedStrengthFilter === 'ALL' || a.evidenceStrength === selectedStrengthFilter)
                      .map((arg) => {
                        const isExpanded = expandedArgId === arg.id;
                        return (
                          <article
                            key={arg.id}
                            className="rounded-xl border border-rose-500/20 bg-[#160c11] p-4 shadow-sm transition-all hover:border-rose-500/40"
                          >
                            <div className="flex items-start justify-between gap-2">
                              <h4 className="text-sm font-semibold text-rose-200 leading-snug">
                                {arg.title}
                              </h4>
                              <span
                                className={`rounded-full border px-2 py-0.5 text-[10px] font-mono uppercase ${getStrengthBadge(
                                  arg.evidenceStrength
                                )}`}
                              >
                                {arg.evidenceStrength || 'MODERATE'}
                              </span>
                            </div>

                            <p className="mt-2 text-xs leading-relaxed text-[#f3faf0]/90">
                              {arg.argument}
                            </p>

                            <div className="mt-3 flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-white/5 text-[11px]">
                              <span
                                className={`rounded border px-1.5 py-0.5 text-[10px] font-mono ${getTypeBadge(
                                  arg.evidenceType
                                )}`}
                              >
                                {arg.evidenceType || 'DIRECT_EVIDENCE'}
                              </span>

                              {arg.document && (
                                <button
                                  type="button"
                                  onClick={() => onOpenDocument?.(arg.document!, arg.page)}
                                  className="flex items-center gap-1 text-[11px] font-mono text-[#a7d0d2] hover:text-white hover:underline"
                                >
                                  <span>{arg.document}</span>
                                  {arg.page ? <span>(p. {arg.page})</span> : null}
                                  <ExternalLink className="h-3 w-3" />
                                </button>
                              )}
                            </div>

                            {/* Expandable verbatim evidence */}
                            {Boolean(arg.evidence?.length) && (
                              <div className="mt-2.5">
                                <button
                                  type="button"
                                  onClick={() => setExpandedArgId(isExpanded ? null : arg.id)}
                                  className="flex items-center gap-1 text-[11px] text-[#a7d0d2]/80 hover:text-white font-medium"
                                >
                                  <span>{isExpanded ? 'Hide Evidence Quote' : 'View Evidence Passage'}</span>
                                  {isExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                                </button>
                                {isExpanded && (
                                  <blockquote className="mt-2 rounded-lg border-l-2 border-rose-500/50 bg-[#12070c] p-3 text-xs italic text-[#f3faf0]/80">
                                    "{arg.evidence![0]}"
                                    {arg.chunkId && (
                                      <span className="block mt-1 font-mono text-[10px] text-[#a7d0d2]/60">
                                        Chunk ID: {arg.chunkId}
                                      </span>
                                    )}
                                  </blockquote>
                                )}
                              </div>
                            )}
                          </article>
                        );
                      })
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 2: OPENING STATEMENTS */}
        {activeTab === 'openings' && (
          <div className="space-y-5">
            <div className="rounded-xl border border-white/10 bg-[#0d151e] p-5">
              <div className="flex items-center gap-2">
                <Award className="h-4 w-4 text-[#d2434e]" />
                <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-white">
                  Formal Debate Proposition
                </h3>
              </div>
              <p className="mt-2 text-sm font-medium text-[#f3faf0]">
                "{debate.proposition || debate.query}"
              </p>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              {/* Pro Opening */}
              <article className="rounded-xl border border-emerald-500/30 bg-[#0a151b] p-5 shadow-sm">
                <div className="flex items-center gap-2 border-b border-emerald-500/20 pb-3">
                  <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                  <h4 className="text-xs font-mono font-bold uppercase tracking-wider text-emerald-300">
                    Pro Opening Argument
                  </h4>
                </div>
                <p className="mt-3 text-sm leading-relaxed text-white">
                  {debate.openingStatements?.pro || debate.positionA || 'No opening statement recorded.'}
                </p>
                <div className="mt-4 pt-3 border-t border-white/5 flex items-center justify-between text-xs text-[#a7d0d2]">
                  <span>Supports proposition</span>
                  <span>{proArguments.length} arguments grounded in literature</span>
                </div>
              </article>

              {/* Con Opening */}
              <article className="rounded-xl border border-rose-500/30 bg-[#160c11] p-5 shadow-sm">
                <div className="flex items-center gap-2 border-b border-rose-500/20 pb-3">
                  <ShieldAlert className="h-4 w-4 text-rose-400" />
                  <h4 className="text-xs font-mono font-bold uppercase tracking-wider text-rose-300">
                    Con Opening Argument
                  </h4>
                </div>
                <p className="mt-3 text-sm leading-relaxed text-white">
                  {debate.openingStatements?.con || debate.positionB || 'No opening statement recorded.'}
                </p>
                <div className="mt-4 pt-3 border-t border-white/5 flex items-center justify-between text-xs text-[#a7d0d2]">
                  <span>Challenges proposition</span>
                  <span>{conArguments.length} constraints documented in literature</span>
                </div>
              </article>
            </div>
          </div>
        )}

        {/* TAB 3: REBUTTAL ROUNDS */}
        {activeTab === 'rebuttals' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between border-b border-white/10 pb-2">
              <div className="flex items-center gap-2">
                <Swords className="h-4 w-4 text-purple-400" />
                <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-white">
                  Direct Rebuttal Rounds ({(debate.rebuttals || []).length})
                </h3>
              </div>
              <span className="text-xs text-[#a7d0d2]">
                Cross-examination of opposing positions
              </span>
            </div>

            {(!debate.rebuttals || debate.rebuttals.length === 0) ? (
              <div className="rounded-xl border border-white/5 bg-[#0b1219] p-5 text-center text-xs text-[#f3faf0]/60">
                No active rebuttal rounds generated for this topic.
              </div>
            ) : (
              debate.rebuttals.map((reb, idx) => {
                const isProRebutting = reb.side === 'POSITION_A' || reb.side === 'PRO';
                return (
                  <article
                    key={reb.id || idx}
                    className={`rounded-xl border p-4 shadow-sm ${
                      isProRebutting
                        ? 'border-emerald-500/25 bg-[#0a151b]'
                        : 'border-rose-500/25 bg-[#160c11]'
                    }`}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/5 pb-2">
                      <span
                        className={`rounded-full px-2.5 py-0.5 text-[10px] font-mono font-bold uppercase ${
                          isProRebutting
                            ? 'bg-emerald-500/20 text-emerald-300'
                            : 'bg-rose-500/20 text-rose-300'
                        }`}
                      >
                        {isProRebutting ? 'Pro Rebuttal' : 'Con Rebuttal'}
                      </span>
                      <span className="text-[11px] text-[#f3faf0]/60">
                        Challenging: <strong className="text-white">"{reb.targetArgument}"</strong>
                      </span>
                    </div>

                    <p className="mt-3 text-xs leading-relaxed text-white">
                      {reb.rebuttal}
                    </p>

                    {Boolean(reb.evidence?.length) && (
                      <blockquote className="mt-2.5 rounded-lg border-l-2 border-white/20 bg-black/30 p-2.5 text-xs italic text-[#f3faf0]/80">
                        "{reb.evidence![0]}"
                      </blockquote>
                    )}

                    {reb.document && (
                      <div className="mt-2 flex items-center justify-end">
                        <button
                          type="button"
                          onClick={() => onOpenDocument?.(reb.document!, reb.page)}
                          className="flex items-center gap-1 text-[11px] font-mono text-[#a7d0d2] hover:underline"
                        >
                          <span>{reb.document}</span>
                          {reb.page ? <span>(p. {reb.page})</span> : null}
                          <ExternalLink className="h-3 w-3" />
                        </button>
                      </div>
                    )}
                  </article>
                );
              })
            )}
          </div>
        )}

        {/* TAB 4: SYNTHESIS & VERDICT */}
        {activeTab === 'synthesis' && (
          <div className="space-y-6">
            {/* Agreements & Disagreements Grid */}
            <div className="grid gap-4 md:grid-cols-2">
              {/* Agreements */}
              <div className="rounded-xl border border-white/10 bg-[#0d151e] p-4">
                <div className="flex items-center gap-2 border-b border-white/10 pb-2">
                  <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                  <h4 className="text-xs font-mono font-bold uppercase tracking-wider text-emerald-300">
                    Points of Consensus across Literature
                  </h4>
                </div>
                <ul className="mt-3 space-y-2 text-xs text-[#f3faf0]/90">
                  {(!debate.agreements || debate.agreements.length === 0) ? (
                    <li className="italic text-[#f3faf0]/50">No explicit consensus points recorded.</li>
                  ) : (
                    debate.agreements.map((item, i) => (
                      <li key={i} className="flex items-start gap-2">
                        <span className="text-emerald-400 font-bold">•</span>
                        <span>{item}</span>
                      </li>
                    ))
                  )}
                </ul>
              </div>

              {/* Disagreements */}
              <div className="rounded-xl border border-white/10 bg-[#0d151e] p-4">
                <div className="flex items-center gap-2 border-b border-white/10 pb-2">
                  <AlertCircle className="h-4 w-4 text-rose-400" />
                  <h4 className="text-xs font-mono font-bold uppercase tracking-wider text-rose-300">
                    Core Points of Disagreement
                  </h4>
                </div>
                <ul className="mt-3 space-y-2 text-xs text-[#f3faf0]/90">
                  {(!debate.disagreements || debate.disagreements.length === 0) ? (
                    <li className="italic text-[#f3faf0]/50">No severe conflicting findings detected.</li>
                  ) : (
                    debate.disagreements.map((item, i) => (
                      <li key={i} className="flex items-start gap-2">
                        <span className="text-rose-400 font-bold">•</span>
                        <span>{item}</span>
                      </li>
                    ))
                  )}
                </ul>
              </div>
            </div>

            {/* Unresolved Questions */}
            {Boolean(debate.unresolvedQuestions?.length) && (
              <div className="rounded-xl border border-purple-500/20 bg-purple-500/5 p-4">
                <div className="flex items-center gap-2 border-b border-purple-500/20 pb-2">
                  <HelpCircle className="h-4 w-4 text-purple-400" />
                  <h4 className="text-xs font-mono font-bold uppercase tracking-wider text-purple-300">
                    Unresolved Empirical Questions
                  </h4>
                </div>
                <ul className="mt-3 space-y-2 text-xs text-[#f3faf0]/90">
                  {debate.unresolvedQuestions!.map((q, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="text-purple-400 font-bold">?</span>
                      <span>{q}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Neutral Assessment & Verdict */}
            <div className="rounded-xl border border-[#d2434e]/30 bg-[#0d151e] p-5 shadow-lg">
              <div className="flex items-center gap-2 border-b border-white/10 pb-3">
                <Scale className="h-5 w-5 text-[#d2434e]" />
                <h4 className="text-xs font-mono font-bold uppercase tracking-wider text-white">
                  Neutral Evidence Assessment & Verdict
                </h4>
              </div>

              <div className="mt-4 space-y-3">
                <div>
                  <span className="text-[10px] font-mono uppercase text-[#a7d0d2] block">
                    Relative Evidence Strength Evaluation:
                  </span>
                  <p className="mt-1 text-sm leading-relaxed text-white">
                    {debate.neutralAssessment || debate.conclusion}
                  </p>
                </div>

                <div className="pt-3 border-t border-white/5">
                  <span className="text-[10px] font-mono uppercase text-[#d2434e] block">
                    Balanced Conclusion (Certainty vs Evidence Strength):
                  </span>
                  <p className="mt-1 text-xs leading-relaxed text-[#f3faf0]/80">
                    {debate.conclusion}
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* =====================================================================
          FOOTER / EVIDENCE DRAWER TRIGGER
      ===================================================================== */}
      <div className="flex items-center justify-between border-t border-white/10 bg-[#0a0f15] px-5 py-3 text-xs">
        <span className="text-[#f3faf0]/60">
          Dialectical synthesis grounded in retrieved document passages.
        </span>
        {onOpenSources && (
          <button
            type="button"
            onClick={onOpenSources}
            className="flex items-center gap-1.5 text-xs text-[#a7d0d2] hover:text-white transition-colors"
          >
            <span>Review Full Citations Drawer</span>
            <ExternalLink className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
    </section>
  );
};
