import React, { useState, useMemo } from 'react';
import {
  AlertCircle,
  AlertTriangle,
  BookOpen,
  ChevronRight,
  Cpu,
  Database,
  Download,
  ExternalLink,
  FileText,
  Filter,
  Layers,
  Lightbulb,
  Maximize2,
  Minimize2,
  Network,
  Scale,
  Sparkles,
  Zap,
} from 'lucide-react';
import type {
  ResearchGapsReport,
  ResearchGapItem,
  ResearchGapCategory,
  ResearchGapPriority,
} from '../../types/analysis';
import { downloadJsonFile } from '../../lib/exportUtils';

interface ResearchGapsExplorerProps {
  report: ResearchGapsReport;
  onOpenSources?: () => void;
  onOpenDocument?: (docName: string, page?: number | string) => void;
}

const CATEGORY_CONFIG: Record<
  ResearchGapCategory,
  { label: string; icon: React.FC<{ className?: string }>; color: string; border: string; bg: string }
> = {
  TECHNICAL: {
    label: 'Technical',
    icon: Cpu,
    color: 'text-rose-400',
    border: 'border-rose-500/30',
    bg: 'bg-rose-500/10',
  },
  METHODOLOGICAL: {
    label: 'Methodological',
    icon: Layers,
    color: 'text-purple-400',
    border: 'border-purple-500/30',
    bg: 'bg-purple-500/10',
  },
  PERFORMANCE: {
    label: 'Performance',
    icon: Zap,
    color: 'text-amber-400',
    border: 'border-amber-500/30',
    bg: 'bg-amber-500/10',
  },
  DATASET: {
    label: 'Dataset',
    icon: Database,
    color: 'text-blue-400',
    border: 'border-blue-500/30',
    bg: 'bg-blue-500/10',
  },
  EVALUATION: {
    label: 'Evaluation',
    icon: Scale,
    color: 'text-emerald-400',
    border: 'border-emerald-500/30',
    bg: 'bg-emerald-500/10',
  },
  IMPLEMENTATION: {
    label: 'Implementation',
    icon: Cpu,
    color: 'text-orange-400',
    border: 'border-orange-500/30',
    bg: 'bg-orange-500/10',
  },
  THEORETICAL: {
    label: 'Theoretical',
    icon: BookOpen,
    color: 'text-cyan-400',
    border: 'border-cyan-500/30',
    bg: 'bg-cyan-500/10',
  },
  APPLICATION: {
    label: 'Application',
    icon: Lightbulb,
    color: 'text-pink-400',
    border: 'border-pink-500/30',
    bg: 'bg-pink-500/10',
  },
};

export const ResearchGapsExplorer: React.FC<ResearchGapsExplorerProps> = ({
  report,
  onOpenSources,
  onOpenDocument,
}) => {
  const [selectedCategory, setSelectedCategory] = useState<ResearchGapCategory | 'ALL'>('ALL');
  const [selectedPriority, setSelectedPriority] = useState<ResearchGapPriority | 'ALL'>('ALL');
  const [selectedGap, setSelectedGap] = useState<ResearchGapItem | null>(report.gaps[0] || null);
  const [activeTab, setActiveTab] = useState<'explorer' | 'map' | 'recommendations' | 'multidoc'>('explorer');
  const [mapSelectedNode, setMapSelectedNode] = useState<string | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Filtered gaps
  const filteredGaps = useMemo(() => {
    return (report.gaps || []).filter((gap) => {
      if (selectedCategory !== 'ALL' && gap.category !== selectedCategory) return false;
      if (selectedPriority !== 'ALL' && gap.priority !== selectedPriority) return false;
      return true;
    });
  }, [report.gaps, selectedCategory, selectedPriority]);

  // Export handlers
  const handleExportJson = () => {
    const filename = `research_gaps_${report.researchArea.replace(/[^a-zA-Z0-9_-]/g, '_')}_${Date.now()}.json`;
    downloadJsonFile(filename, report);
  };

  const handleExportMarkdown = () => {
    const lines: string[] = [
      `# Evidence-Based Research Gaps Discovery Report`,
      `**Research Area:** ${report.researchArea}`,
      `**Query:** ${report.query}`,
      `**Generated:** ${new Date().toLocaleString()}`,
      ``,
      `## 1. Executive Summary`,
      `- Total Gaps Identified: ${report.overview.totalGaps}`,
      `- High Priority Gaps: ${report.overview.highPriorityGaps}`,
      `- Medium Priority Gaps: ${report.overview.mediumPriorityGaps}`,
      `- Low Priority Gaps: ${report.overview.lowPriorityGaps}`,
      `- Explicit Limitations: ${report.overview.explicitGaps}`,
      `- Derived Limitations: ${report.overview.derivedGaps}`,
      `- Supporting Papers: ${report.overview.supportingPapersCount}`,
      ``,
      `## 2. Identified Research Gaps`,
    ];

    report.gaps.forEach((g, idx) => {
      lines.push(
        `### ${idx + 1}. [${g.priority} PRIORITY] ${g.title}`,
        `- **Category:** ${g.category}`,
        `- **Type:** ${g.type}`,
        `- Confidence Score: ${(Number(g.confidence || 0) * 100).toFixed(0)}%`,
        `- **Priority Reasoning:** ${g.priorityReasoning}`,
        `- **Current Knowledge:** ${g.currentKnowledge}`,
        `- **What Remains Unresolved:** ${g.missingUnresolved}`,
        `- **Why It Matters:** ${g.whyItMatters}`,
        `- **Potential Direction:** ${g.potentialDirection}`,
        `- **Relevant Methodologies:** ${g.relevantMethods.join(', ')}`,
        `- **Supporting Documents:** ${g.supportingPapers.join(', ') || g.document} (Page: ${g.page || 'N/A'}, Chunk: ${g.chunkId || 'N/A'})`,
        `- **Evidence Quote:** "${g.limitationEvidence}"`,
        ``,
      );
    });

    if (report.recommendations && report.recommendations.length > 0) {
      lines.push(`## 3. Concrete Future Research Proposals (Proposals for Investigation)`);
      report.recommendations.forEach((r, idx) => {
        lines.push(
          `### Proposal ${idx + 1}: ${r.title}`,
          `- **Research Question:** ${r.researchQuestion}`,
          `- **Problem to Investigate:** ${r.problemToInvestigate}`,
          `- **Suggested Approach:** ${r.suggestedApproach}`,
          `- **Expected Contribution:** ${r.expectedContribution}`,
          r.supportingEvidence.length ? `- **Supporting Evidence:** ${r.supportingEvidence[0]}` : '',
          ``,
        );
      });
    }

    if (report.conflicts && report.conflicts.length > 0) {
      lines.push(`## 4. Conflicting Research Findings Across Papers`);
      report.conflicts.forEach((c, idx) => {
        lines.push(
          `### Conflict ${idx + 1}: ${c.topic}`,
          `- **${c.paperA}:** ${c.findingA}`,
          `- **${c.paperB}:** ${c.findingB}`,
          `- **Synthesis/Explanation:** ${c.explanation}`,
          ``,
        );
      });
    }

    lines.push(`---`, `*Generated by UNKNOWN Evidence-Based Research Gap Discovery Engine.*`);

    const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `research_gaps_${report.researchArea.replace(/[^a-zA-Z0-9_-]/g, '_')}_${Date.now()}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section
      className={`rounded-2xl border border-white/10 bg-[#070b0f] text-[#f3faf0] overflow-hidden shadow-2xl transition-all ${
        isFullscreen ? 'fixed inset-4 z-50 flex flex-col' : 'my-4'
      }`}
      aria-label="Research Gaps Discovery Engine"
    >
      {/* =====================================================================
          HEADER BAR
      ===================================================================== */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 bg-[#0d151e] px-5 py-4">
        <div className="flex items-center gap-3">
          <div className="rounded-xl border border-[#d2434e]/30 bg-[#d2434e]/10 p-2.5 shadow-sm">
            <Lightbulb className="h-5 w-5 text-[#d2434e]" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono font-bold tracking-wider uppercase text-[#d2434e]">
                Research Gaps Engine
              </span>
              {report.partial && (
                <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-mono text-amber-300">
                  Deterministic Fallback
                </span>
              )}
            </div>
            <h2 className="text-base font-semibold text-white tracking-tight">
              {report.researchArea || 'Literature Gap Discovery'}
            </h2>
          </div>
        </div>

        {/* View Navigation & Exports */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex rounded-lg border border-white/10 bg-[#141d26]/80 p-0.5">
            <button
              type="button"
              onClick={() => setActiveTab('explorer')}
              className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                activeTab === 'explorer' ? 'bg-[#d2434e] text-white shadow-sm' : 'text-[#a7d0d2] hover:text-white'
              }`}
            >
              Gap Explorer
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('map')}
              className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                activeTab === 'map' ? 'bg-[#d2434e] text-white shadow-sm' : 'text-[#a7d0d2] hover:text-white'
              }`}
            >
              Opportunity Map
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('recommendations')}
              className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                activeTab === 'recommendations' ? 'bg-[#d2434e] text-white shadow-sm' : 'text-[#a7d0d2] hover:text-white'
              }`}
            >
              Future Proposals ({report.recommendations?.length || 0})
            </button>
            {Boolean(report.conflicts?.length || report.overview.supportingPapersCount > 1) && (
              <button
                type="button"
                onClick={() => setActiveTab('multidoc')}
                className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                  activeTab === 'multidoc' ? 'bg-[#d2434e] text-white shadow-sm' : 'text-[#a7d0d2] hover:text-white'
                }`}
              >
                Multi-Doc Intel
              </button>
            )}
          </div>

          <div className="h-4 w-px bg-white/10" />

          {/* Export Actions */}
          <button
            type="button"
            onClick={handleExportJson}
            title="Export full gaps report as JSON"
            className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-[#141d26] px-2.5 py-1.5 text-xs text-[#a7d0d2] hover:border-[#4d728e] hover:text-white transition-colors"
          >
            <Download className="h-3.5 w-3.5 text-[#d2434e]" />
            <span>JSON</span>
          </button>
          <button
            type="button"
            onClick={handleExportMarkdown}
            title="Export full gaps report as Markdown"
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

      {/* Fallback Notice Banner if applicable */}
      {report.notice && (
        <div className="flex items-center gap-2 border-b border-amber-500/20 bg-amber-500/10 px-5 py-2 text-xs text-amber-200">
          <AlertTriangle className="h-4 w-4 shrink-0 text-amber-400" />
          <span>{report.notice}</span>
        </div>
      )}

      {/* =====================================================================
          SECTION A: RESEARCH GAP OVERVIEW METRICS
      ===================================================================== */}
      <div className="grid grid-cols-2 gap-3 border-b border-white/10 bg-[#0b1219]/60 p-4 sm:grid-cols-3 lg:grid-cols-6">
        <div className="rounded-xl border border-white/5 bg-[#141d26]/60 p-3">
          <span className="block text-[11px] font-mono uppercase text-[#a7d0d2]/70">Total Gaps</span>
          <span className="mt-1 block text-2xl font-bold text-white">{report.overview.totalGaps}</span>
          <span className="text-[10px] text-[#f3faf0]/45">Across analyzed papers</span>
        </div>

        <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-3">
          <span className="block text-[11px] font-mono uppercase text-red-400">High Priority</span>
          <span className="mt-1 block text-2xl font-bold text-red-300">{report.overview.highPriorityGaps}</span>
          <span className="text-[10px] text-red-400/60">Significant bottlenecks</span>
        </div>

        <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-3">
          <span className="block text-[11px] font-mono uppercase text-amber-400">Medium Priority</span>
          <span className="mt-1 block text-2xl font-bold text-amber-300">{report.overview.mediumPriorityGaps}</span>
          <span className="text-[10px] text-amber-400/60">Practical constraints</span>
        </div>

        <div className="rounded-xl border border-blue-500/20 bg-blue-500/5 p-3">
          <span className="block text-[11px] font-mono uppercase text-blue-400">Low Priority</span>
          <span className="mt-1 block text-2xl font-bold text-blue-300">{report.overview.lowPriorityGaps}</span>
          <span className="text-[10px] text-blue-400/60">Exploratory areas</span>
        </div>

        <div className="rounded-xl border border-white/5 bg-[#141d26]/60 p-3">
          <span className="block text-[11px] font-mono uppercase text-[#a7d0d2]/70">Gap Nature</span>
          <div className="mt-1 flex items-baseline gap-1.5">
            <span className="text-lg font-bold text-emerald-400">{report.overview.explicitGaps}</span>
            <span className="text-[10px] text-[#f3faf0]/50">explicit</span>
            <span className="text-white/30">/</span>
            <span className="text-lg font-bold text-purple-400">{report.overview.derivedGaps}</span>
            <span className="text-[10px] text-[#f3faf0]/50">derived</span>
          </div>
          <span className="text-[10px] text-[#f3faf0]/45">Direct author vs synthesis</span>
        </div>

        <div className="rounded-xl border border-white/5 bg-[#141d26]/60 p-3">
          <span className="block text-[11px] font-mono uppercase text-[#a7d0d2]/70">Papers Cited</span>
          <span className="mt-1 block text-2xl font-bold text-[#a7d0d2]">{report.overview.supportingPapersCount}</span>
          <span className="text-[10px] text-[#f3faf0]/45">Indexed document sources</span>
        </div>
      </div>

      {/* =====================================================================
          MAIN CONTENT AREA (TABS)
      ===================================================================== */}
      <div className="flex-1 overflow-y-auto p-5">
        {/* TAB 1: GAP EXPLORER */}
        {activeTab === 'explorer' && (
          <div className="space-y-5">
            {/* SECTION B: GAP CATEGORIES FILTER */}
            <div className="flex flex-wrap items-center gap-2 border-b border-white/8 pb-4">
              <span className="flex items-center gap-1.5 text-xs font-mono uppercase text-[#f3faf0]/60 mr-2">
                <Filter className="h-3.5 w-3.5 text-[#a7d0d2]" />
                <span>Categories:</span>
              </span>

              <button
                type="button"
                onClick={() => setSelectedCategory('ALL')}
                className={`rounded-lg px-2.5 py-1 text-xs font-medium transition-all ${
                  selectedCategory === 'ALL'
                    ? 'border border-[#d2434e]/60 bg-[#d2434e]/20 text-white'
                    : 'border border-white/5 bg-[#141d26]/60 text-[#f3faf0]/70 hover:text-white'
                }`}
              >
                All Categories ({report.gaps.length})
              </button>

              {(Object.keys(CATEGORY_CONFIG) as ResearchGapCategory[]).map((catKey) => {
                const conf = CATEGORY_CONFIG[catKey];
                const Icon = conf.icon;
                const count = report.overview.categoriesCount?.[catKey] || 0;
                const isSelected = selectedCategory === catKey;

                return (
                  <button
                    key={catKey}
                    type="button"
                    onClick={() => setSelectedCategory(isSelected ? 'ALL' : catKey)}
                    className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium transition-all ${
                      isSelected
                        ? `${conf.border} ${conf.bg} ${conf.color} ring-1 ring-white/20`
                        : 'border-white/5 bg-[#141d26]/50 text-[#f3faf0]/60 hover:border-white/10 hover:text-white'
                    }`}
                  >
                    <Icon className="h-3 w-3" />
                    <span>{conf.label}</span>
                    <span className="rounded-full bg-white/10 px-1.5 py-0.2 text-[10px] text-white/80">
                      {count}
                    </span>
                  </button>
                );
              })}

              <div className="ml-auto flex items-center gap-1.5 text-xs font-mono">
                <span className="text-[#f3faf0]/50 text-[11px]">Priority:</span>
                {(['ALL', 'HIGH', 'MEDIUM', 'LOW'] as const).map((prio) => (
                  <button
                    key={prio}
                    type="button"
                    onClick={() => setSelectedPriority(prio)}
                    className={`rounded px-2 py-0.5 text-[11px] transition-colors ${
                      selectedPriority === prio
                        ? prio === 'HIGH'
                          ? 'bg-red-500/20 text-red-300 font-bold border border-red-500/40'
                          : prio === 'MEDIUM'
                          ? 'bg-amber-500/20 text-amber-300 font-bold border border-amber-500/40'
                          : prio === 'LOW'
                          ? 'bg-blue-500/20 text-blue-300 font-bold border border-blue-500/40'
                          : 'bg-white/10 text-white font-bold'
                        : 'text-[#f3faf0]/50 hover:text-white'
                    }`}
                  >
                    {prio}
                  </button>
                ))}
              </div>
            </div>

            {/* SECTION C & E: 2-COLUMN LAYOUT: GAP CARDS + DETAILED INSPECTOR */}
            <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
              {/* SECTION C: GAP CARDS (LEFT 7 COLS) */}
              <div className="space-y-3 lg:col-span-7">
                {filteredGaps.length === 0 ? (
                  <div className="rounded-xl border border-white/5 bg-[#0b1219]/60 p-8 text-center">
                    <AlertCircle className="mx-auto h-8 w-8 text-[#a7d0d2]/50" />
                    <p className="mt-2 text-sm text-[#f3faf0]/75">No research gaps matched the selected filters.</p>
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedCategory('ALL');
                        setSelectedPriority('ALL');
                      }}
                      className="mt-3 text-xs text-[#d2434e] hover:underline"
                    >
                      Clear filters
                    </button>
                  </div>
                ) : (
                  filteredGaps.map((gap) => {
                    const catConf = CATEGORY_CONFIG[gap.category] || CATEGORY_CONFIG.TECHNICAL;
                    const CatIcon = catConf.icon;
                    const isSelected = selectedGap?.id === gap.id;

                    return (
                      <article
                        key={gap.id}
                        onClick={() => setSelectedGap(gap)}
                        className={`group relative cursor-pointer rounded-xl border p-4 transition-all duration-200 ${
                          isSelected
                            ? 'border-[#d2434e]/80 bg-[#141d26] ring-1 ring-[#d2434e]/50 shadow-lg'
                            : 'border-white/8 bg-[#0b1219]/70 hover:border-white/20 hover:bg-[#141d26]/50'
                        }`}
                      >
                        {/* Top row: Category, Priority, Confidence, Nature */}
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <span
                              className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[10px] font-mono uppercase ${catConf.border} ${catConf.bg} ${catConf.color}`}
                            >
                              <CatIcon className="h-3 w-3" />
                              <span>{catConf.label}</span>
                            </span>

                            <span
                              className={`rounded-md px-2 py-0.5 text-[10px] font-mono font-bold uppercase ${
                                gap.priority === 'HIGH'
                                  ? 'bg-red-500/15 text-red-300 border border-red-500/30'
                                  : gap.priority === 'MEDIUM'
                                  ? 'bg-amber-500/15 text-amber-300 border border-amber-500/30'
                                  : 'bg-blue-500/15 text-blue-300 border border-blue-500/30'
                              }`}
                            >
                              {gap.priority} Priority
                            </span>

                            <span className="rounded-md bg-white/5 border border-white/5 px-2 py-0.5 text-[10px] font-mono text-[#a7d0d2]">
                              {gap.type}
                            </span>

                            {gap.isShared && (
                              <span className="rounded-md bg-purple-500/15 border border-purple-500/30 px-2 py-0.5 text-[10px] font-mono text-purple-300">
                                Shared Gap
                              </span>
                            )}
                          </div>

                          {/* Score Indicator */}
                          <div className="flex items-center gap-1.5" title={`Confidence: ${(Number(gap.confidence || 0) * 100).toFixed(0)}%`}>
                            <div className="h-1.5 w-12 overflow-hidden rounded-full bg-white/10">
                              <div
                                className="h-full bg-emerald-400 rounded-full"
                                style={{ width: `${Number(gap.confidence || 0) * 100}%` }}
                              />
                            </div>
                            <span className="text-[11px] font-mono text-emerald-300">
                              {(Number(gap.confidence || 0) * 100).toFixed(0)}%
                            </span>
                          </div>
                        </div>

                        {/* Gap Title */}
                        <h3 className="mt-2.5 text-sm font-semibold text-white group-hover:text-[#a7d0d2] transition-colors">
                          {gap.title}
                        </h3>

                        {/* Short Explanation */}
                        <p className="mt-1.5 text-xs leading-relaxed text-[#f3faf0]/75 line-clamp-2">
                          {gap.missingUnresolved || gap.rationale}
                        </p>

                        {/* Footer Citations */}
                        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-white/5 pt-2.5 text-[11px] text-[#a7d0d2]">
                          <div className="flex items-center gap-1.5">
                            <FileText className="h-3 w-3 text-[#d2434e]" />
                            <span className="truncate max-w-[280px]">
                              {gap.supportingPapers.length > 1
                                ? `${gap.supportingPapers.length} papers: ${gap.supportingPapers.join(', ')}`
                                : gap.document || 'Cited paper'}
                            </span>
                            {gap.page && <span className="text-[#f3faf0]/40">p. {gap.page}</span>}
                          </div>

                          <span className="flex items-center gap-1 text-[11px] text-[#f3faf0]/50 group-hover:text-white transition-colors">
                            <span>Inspect</span>
                            <ChevronRight className="h-3 w-3" />
                          </span>
                        </div>
                      </article>
                    );
                  })
                )}
              </div>

              {/* SECTION E: DETAILED GAP INSPECTOR (RIGHT 5 COLS) */}
              <div className="lg:col-span-5">
                {selectedGap ? (
                  <div className="sticky top-4 rounded-xl border border-white/10 bg-[#0d151e] p-5 shadow-xl space-y-4">
                    <div className="flex items-start justify-between gap-2 border-b border-white/10 pb-3">
                      <div>
                        <span className="text-[10px] font-mono uppercase tracking-wider text-[#d2434e]">
                          Detailed Gap Inspector
                        </span>
                        <h3 className="text-base font-semibold text-white leading-snug mt-0.5">
                          {selectedGap.title}
                        </h3>
                      </div>
                      <span
                        className={`rounded-md px-2 py-0.5 text-[10px] font-mono font-bold uppercase shrink-0 ${
                          selectedGap.priority === 'HIGH'
                            ? 'bg-red-500/20 text-red-300 border border-red-500/30'
                            : selectedGap.priority === 'MEDIUM'
                            ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                            : 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
                        }`}
                      >
                        {selectedGap.priority} Priority
                      </span>
                    </div>

                    {/* Priority Reasoning Box */}
                    <div className="rounded-lg border border-white/5 bg-[#141d26]/80 p-3 text-xs leading-relaxed text-[#f3faf0]/85">
                      <p className="text-[10px] font-mono uppercase text-[#a7d0d2] mb-1">Priority Justification</p>
                      <p>{selectedGap.priorityReasoning || 'Assessed based on evidence strength and scientific relevance.'}</p>
                    </div>

                    {/* Known vs Unresolved */}
                    <div className="space-y-3">
                      <div className="rounded-lg border border-white/5 bg-[#0b1219]/60 p-3">
                        <span className="text-[10px] font-mono uppercase text-emerald-400">What is currently known</span>
                        <p className="mt-1 text-xs text-[#f3faf0]/80 leading-relaxed">
                          {selectedGap.currentKnowledge || 'Established in cited research literature.'}
                        </p>
                      </div>

                      <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-3">
                        <span className="text-[10px] font-mono uppercase text-red-400">What remains unresolved</span>
                        <p className="mt-1 text-xs text-red-200/90 leading-relaxed">
                          {selectedGap.missingUnresolved || selectedGap.gap}
                        </p>
                      </div>
                    </div>

                    {/* Why It Matters */}
                    <div className="rounded-lg border border-white/5 bg-[#141d26]/50 p-3">
                      <span className="text-[10px] font-mono uppercase text-[#a7d0d2]">Why this gap matters</span>
                      <p className="mt-1 text-xs text-[#f3faf0]/80 leading-relaxed">{selectedGap.whyItMatters}</p>
                    </div>

                    {/* Potential Direction & Methodologies */}
                    <div className="rounded-lg border border-white/5 bg-[#141d26]/50 p-3 space-y-2">
                      <div>
                        <span className="text-[10px] font-mono uppercase text-[#a7d0d2]">Potential research direction</span>
                        <p className="mt-1 text-xs text-[#f3faf0]/80 leading-relaxed">{selectedGap.potentialDirection}</p>
                      </div>

                      {selectedGap.relevantMethods?.length > 0 && (
                        <div>
                          <span className="text-[10px] font-mono uppercase text-[#f3faf0]/50">Relevant Methodologies</span>
                          <div className="mt-1 flex flex-wrap gap-1.5">
                            {selectedGap.relevantMethods.map((m, idx) => (
                              <span
                                key={idx}
                                className="rounded bg-white/5 px-2 py-0.5 text-[10px] font-mono text-[#a7d0d2] border border-white/5"
                              >
                                {m}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Evidence Quote & Exact Paper Attribution */}
                    <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3">
                      <div className="flex items-center justify-between text-[10px] font-mono uppercase text-amber-300">
                        <span>Supporting Document Evidence</span>
                        <span>Evidence Score: %</span>
                      </div>
                      <blockquote className="mt-1.5 border-l-2 border-amber-400/50 pl-2.5 text-xs italic text-amber-100/90 leading-relaxed">
                        "{selectedGap.limitationEvidence || (selectedGap.evidence && selectedGap.evidence[0]) || 'Limitation referenced in text.'}"
                      </blockquote>

                      <div className="mt-2.5 flex flex-wrap items-center justify-between gap-2 text-[10px] font-mono text-[#a7d0d2]">
                        <span className="flex items-center gap-1">
                          <FileText className="h-3 w-3 text-[#d2434e]" />
                          <span>{selectedGap.document || 'Indexed paper'}</span>
                          {selectedGap.page && <span>(p. {selectedGap.page})</span>}
                          {selectedGap.chunkId && <span className="text-white/40">[{selectedGap.chunkId}]</span>}
                        </span>

                        {onOpenDocument && selectedGap.document && (
                          <button
                            type="button"
                            onClick={() => onOpenDocument(selectedGap.document, selectedGap.page)}
                            className="flex items-center gap-1 text-[#d2434e] hover:underline"
                          >
                            <span>Open PDF</span>
                            <ExternalLink className="h-2.5 w-2.5" />
                          </button>
                        )}
                      </div>
                    </div>

                    {/* View all citations button */}
                    {onOpenSources && (
                      <button
                        type="button"
                        onClick={onOpenSources}
                        className="w-full rounded-lg border border-[#4d728e]/40 bg-[#141d26] py-2 text-center text-xs font-medium text-[#a7d0d2] hover:bg-[#1b2632] hover:text-white transition-colors"
                      >
                        View Supporting Sources Drawer ({report.sources?.length || 0})
                      </button>
                    )}
                  </div>
                ) : (
                  <div className="rounded-xl border border-white/5 bg-[#0d151e] p-8 text-center text-[#f3faf0]/50 text-xs">
                    Select a research gap on the left to inspect its detailed evidence, methodology, and citations.
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* =====================================================================
            SECTION D: RESEARCH OPPORTUNITY MAP
        ===================================================================== */}
        {activeTab === 'map' && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-white/10 bg-[#0d151e] p-4">
              <div>
                <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                  <Network className="h-4 w-4 text-[#d2434e]" />
                  <span>Research Opportunity Map</span>
                </h3>
                <p className="text-xs text-[#f3faf0]/60 mt-0.5">
                  Visual topology mapping limitations → unresolved challenges → methodologies → research proposals.
                </p>
              </div>

              {/* Map Legend */}
              <div className="flex flex-wrap items-center gap-3 text-[11px] font-mono">
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-red-400" />
                  <span className="text-[#f3faf0]/75">Limitations</span>
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-amber-400" />
                  <span className="text-[#f3faf0]/75">Unresolved Problems</span>
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-cyan-400" />
                  <span className="text-[#f3faf0]/75">Concepts/Methods</span>
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
                  <span className="text-[#f3faf0]/75">Opportunities</span>
                </span>
              </div>
            </div>

            {/* Opportunity Map Visual Flow Canvas */}
            <div className="min-h-[460px] rounded-xl border border-white/10 bg-[#070b0f] p-6 overflow-x-auto">
              <div className="grid grid-cols-1 md:grid-cols-4 gap-6 min-w-[760px]">
                {/* Column 1: Stated Limitations */}
                <div className="space-y-3">
                  <div className="flex items-center gap-2 border-b border-red-500/30 pb-2">
                    <span className="h-2 w-2 rounded-full bg-red-400" />
                    <h4 className="text-xs font-mono font-bold uppercase text-red-300">Stated Limitations</h4>
                  </div>
                  {report.opportunityMap.nodes
                    .filter((n) => n.type === 'LIMITATION')
                    .map((node) => {
                      const isSelected = mapSelectedNode === node.id;
                      return (
                        <div
                          key={node.id}
                          onClick={() => setMapSelectedNode(node.id)}
                          className={`rounded-lg border p-3 cursor-pointer transition-all ${
                            isSelected
                              ? 'border-red-400 bg-red-500/20 ring-1 ring-red-400'
                              : 'border-red-500/25 bg-red-500/5 hover:border-red-500/40 hover:bg-red-500/10'
                          }`}
                        >
                          <span className="text-[10px] font-mono uppercase text-red-300/80">{node.category}</span>
                          <p className="text-xs font-medium text-white mt-1 leading-snug">{node.label}</p>
                          {node.document && (
                            <span className="mt-2 block text-[10px] font-mono text-[#a7d0d2] truncate">
                              {node.document}
                            </span>
                          )}
                        </div>
                      );
                    })}
                </div>

                {/* Column 2: Unresolved Problems */}
                <div className="space-y-3">
                  <div className="flex items-center gap-2 border-b border-amber-500/30 pb-2">
                    <span className="h-2 w-2 rounded-full bg-amber-400" />
                    <h4 className="text-xs font-mono font-bold uppercase text-amber-300">Unresolved Problems</h4>
                  </div>
                  {report.opportunityMap.nodes
                    .filter((n) => n.type === 'UNRESOLVED_PROBLEM')
                    .map((node) => {
                      const isSelected = mapSelectedNode === node.id;
                      return (
                        <div
                          key={node.id}
                          onClick={() => setMapSelectedNode(node.id)}
                          className={`rounded-lg border p-3 cursor-pointer transition-all ${
                            isSelected
                              ? 'border-amber-400 bg-amber-500/20 ring-1 ring-amber-400'
                              : 'border-amber-500/25 bg-amber-500/5 hover:border-amber-500/40 hover:bg-amber-500/10'
                          }`}
                        >
                          <span className="text-[10px] font-mono uppercase text-amber-300/80">{node.category}</span>
                          <p className="text-xs font-medium text-white mt-1 leading-snug">{node.label}</p>
                        </div>
                      );
                    })}
                </div>

                {/* Column 3: Methods / Concepts */}
                <div className="space-y-3">
                  <div className="flex items-center gap-2 border-b border-cyan-500/30 pb-2">
                    <span className="h-2 w-2 rounded-full bg-cyan-400" />
                    <h4 className="text-xs font-mono font-bold uppercase text-cyan-300">Methodologies</h4>
                  </div>
                  {report.opportunityMap.nodes
                    .filter((n) => n.type === 'CONCEPT')
                    .map((node) => {
                      const isSelected = mapSelectedNode === node.id;
                      return (
                        <div
                          key={node.id}
                          onClick={() => setMapSelectedNode(node.id)}
                          className={`rounded-lg border p-3 cursor-pointer transition-all ${
                            isSelected
                              ? 'border-cyan-400 bg-cyan-500/20 ring-1 ring-cyan-400'
                              : 'border-cyan-500/25 bg-cyan-500/5 hover:border-cyan-500/40 hover:bg-cyan-500/10'
                          }`}
                        >
                          <span className="text-[10px] font-mono uppercase text-cyan-300/80">Addressing Method</span>
                          <p className="text-xs font-medium text-white mt-1 leading-snug">{node.label}</p>
                        </div>
                      );
                    })}
                </div>

                {/* Column 4: Potential Research Opportunities */}
                <div className="space-y-3">
                  <div className="flex items-center gap-2 border-b border-emerald-500/30 pb-2">
                    <span className="h-2 w-2 rounded-full bg-emerald-400" />
                    <h4 className="text-xs font-mono font-bold uppercase text-emerald-300">Future Opportunities</h4>
                  </div>
                  {report.opportunityMap.nodes
                    .filter((n) => n.type === 'OPPORTUNITY')
                    .map((node) => {
                      const isSelected = mapSelectedNode === node.id;
                      return (
                        <div
                          key={node.id}
                          onClick={() => setMapSelectedNode(node.id)}
                          className={`rounded-lg border p-3 cursor-pointer transition-all ${
                            isSelected
                              ? 'border-emerald-400 bg-emerald-500/20 ring-1 ring-emerald-400'
                              : 'border-emerald-500/25 bg-emerald-500/5 hover:border-emerald-500/40 hover:bg-emerald-500/10'
                          }`}
                        >
                          <span className="text-[10px] font-mono uppercase text-emerald-300/80">Proposed Study</span>
                          <p className="text-xs font-medium text-white mt-1 leading-snug">{node.label}</p>
                        </div>
                      );
                    })}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* =====================================================================
            SECTION 6: FUTURE RESEARCH RECOMMENDATIONS
        ===================================================================== */}
        {activeTab === 'recommendations' && (
          <div className="space-y-4">
            <div className="rounded-xl border border-white/10 bg-[#0d151e] p-4">
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-[#d2434e]" />
                <span>Evidence-Backed Future Research Recommendations</span>
              </h3>
              <p className="text-xs text-[#f3faf0]/60 mt-1">
                Concrete research directions addressing identified limitations. Clearly formulated as proposals for investigation, not established research findings.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {(report.recommendations || []).map((rec, idx) => (
                <article
                  key={rec.id || idx}
                  className="rounded-xl border border-white/10 bg-[#0b1219]/70 p-5 space-y-3 relative overflow-hidden"
                >
                  <div className="flex items-center justify-between border-b border-white/5 pb-2.5">
                    <div className="flex items-center gap-2">
                      <span className="rounded-md bg-[#d2434e]/15 border border-[#d2434e]/30 px-2 py-0.5 text-[10px] font-mono text-[#d2434e] font-bold">
                        Proposal #{idx + 1}
                      </span>
                      <span className="text-[10px] font-mono uppercase text-amber-300/70">
                        Investigative Hypothesis
                      </span>
                    </div>
                    <span className="text-[10px] font-mono text-[#a7d0d2]/60">Proposal</span>
                  </div>

                  <h4 className="text-sm font-semibold text-white leading-snug">{rec.title}</h4>

                  <div className="space-y-2 text-xs">
                    <div className="rounded-lg border border-white/5 bg-[#141d26]/60 p-2.5">
                      <span className="text-[10px] font-mono uppercase text-[#a7d0d2]">Research Question:</span>
                      <p className="mt-0.5 text-white/90 font-medium italic">"{rec.researchQuestion}"</p>
                    </div>

                    <div className="rounded-lg border border-white/5 bg-[#141d26]/40 p-2.5">
                      <span className="text-[10px] font-mono uppercase text-[#f3faf0]/50">Problem to Investigate:</span>
                      <p className="mt-0.5 text-[#f3faf0]/80">{rec.problemToInvestigate}</p>
                    </div>

                    <div className="rounded-lg border border-white/5 bg-[#141d26]/40 p-2.5">
                      <span className="text-[10px] font-mono uppercase text-[#f3faf0]/50">Suggested Approach:</span>
                      <p className="mt-0.5 text-[#f3faf0]/80">{rec.suggestedApproach}</p>
                    </div>

                    <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-2.5">
                      <span className="text-[10px] font-mono uppercase text-emerald-400">Expected Contribution:</span>
                      <p className="mt-0.5 text-emerald-200/90">{rec.expectedContribution}</p>
                    </div>
                  </div>

                  {rec.supportingEvidence?.length > 0 && (
                    <div className="pt-2 border-t border-white/5 text-[11px] text-[#f3faf0]/50 italic">
                      Supporting limitation citation: "{rec.supportingEvidence[0]}"
                    </div>
                  )}
                </article>
              ))}
            </div>
          </div>
        )}

        {/* =====================================================================
            SECTION 4: MULTI-DOCUMENT INTELLIGENCE & CONTRADICTIONS
        ===================================================================== */}
        {activeTab === 'multidoc' && (
          <div className="space-y-5">
            <div className="rounded-xl border border-white/10 bg-[#0d151e] p-4">
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                <BookOpen className="h-4 w-4 text-[#d2434e]" />
                <span>Multi-Document Comparative Gap Intelligence</span>
              </h3>
              <p className="text-xs text-[#f3faf0]/60 mt-1">
                Synthesized analysis across {report.overview.supportingPapersCount} research papers. Missing information is never treated as a contradiction.
              </p>
            </div>

            {/* Contradictions / Conflicting Findings */}
            {report.conflicts && report.conflicts.length > 0 ? (
              <div className="space-y-3">
                <h4 className="text-xs font-mono uppercase text-amber-300 font-bold flex items-center gap-1.5">
                  <AlertTriangle className="h-4 w-4 text-amber-400" />
                  <span>Conflicting Research Findings Across Papers</span>
                </h4>
                <div className="grid grid-cols-1 gap-3">
                  {report.conflicts.map((c, idx) => (
                    <div key={idx} className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4 space-y-3">
                      <div className="flex items-center justify-between border-b border-amber-500/20 pb-2">
                        <span className="text-xs font-mono font-bold text-amber-200 uppercase">{c.topic}</span>
                        <span className="text-[10px] font-mono text-amber-400/70">Divergent Experimental Results</span>
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                        <div className="rounded-lg bg-[#0b1219]/70 border border-white/5 p-3">
                          <span className="text-[10px] font-mono uppercase text-[#d2434e]">{c.paperA}</span>
                          <p className="mt-1 text-white/90">{c.findingA}</p>
                        </div>
                        <div className="rounded-lg bg-[#0b1219]/70 border border-white/5 p-3">
                          <span className="text-[10px] font-mono uppercase text-[#a7d0d2]">{c.paperB}</span>
                          <p className="mt-1 text-white/90">{c.findingB}</p>
                        </div>
                      </div>
                      <p className="text-xs text-[#f3faf0]/80 italic border-l-2 border-amber-400 pl-2">
                        {c.explanation}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="rounded-xl border border-white/5 bg-[#0b1219]/40 p-4 text-xs text-[#f3faf0]/60">
                No direct empirical contradictions detected across the analyzed papers for this query.
              </div>
            )}

            {/* Shared Gaps vs Unique Paper Limitations */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="rounded-xl border border-purple-500/20 bg-purple-500/5 p-4 space-y-3">
                <h4 className="text-xs font-mono uppercase text-purple-300 font-bold">
                  Shared Limitations Across Papers
                </h4>
                {report.multiDocInsights?.sharedGaps && report.multiDocInsights.sharedGaps.length > 0 ? (
                  <ul className="space-y-2 text-xs">
                    {report.multiDocInsights.sharedGaps.map((sg, idx) => (
                      <li key={idx} className="flex items-start gap-2 text-white/90">
                        <span className="text-purple-400 font-bold">•</span>
                        <span>{sg}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-[#f3faf0]/50">No shared cross-paper limitations identified.</p>
                )}
              </div>

              <div className="rounded-xl border border-blue-500/20 bg-blue-500/5 p-4 space-y-3">
                <h4 className="text-xs font-mono uppercase text-blue-300 font-bold">
                  Paper-Specific Unique Limitations
                </h4>
                {report.multiDocInsights?.uniqueLimitations &&
                Object.keys(report.multiDocInsights.uniqueLimitations).length > 0 ? (
                  <div className="space-y-2 text-xs">
                    {Object.entries(report.multiDocInsights.uniqueLimitations).map(([doc, lims]) => (
                      <div key={doc} className="border-b border-white/5 pb-2">
                        <span className="text-[10px] font-mono text-[#a7d0d2]">{doc}:</span>
                        <ul className="mt-1 space-y-1 pl-2">
                          {lims.map((l, lIdx) => (
                            <li key={lIdx} className="text-[#f3faf0]/80 text-[11px]">
                              - {l}
                            </li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-[#f3faf0]/50">All identified limitations appear paper-specific.</p>
                )}
              </div>
            </div>

            {/* Underexplored Research Categories */}
            {report.multiDocInsights?.underexploredAreas && report.multiDocInsights.underexploredAreas.length > 0 && (
              <div className="rounded-xl border border-white/5 bg-[#141d26]/40 p-4">
                <h4 className="text-xs font-mono uppercase text-[#a7d0d2] mb-2 font-bold">
                  Underexplored Research Dimensions (Zero Gaps or Evidence in Current Selection)
                </h4>
                <div className="flex flex-wrap gap-2">
                  {report.multiDocInsights.underexploredAreas.map((area) => (
                    <span
                      key={area}
                      className="rounded-md border border-white/5 bg-white/5 px-2.5 py-1 text-xs font-mono text-[#f3faf0]/60"
                    >
                      {area}
                    </span>
                  ))}
                </div>
                <p className="mt-2 text-[11px] text-[#f3faf0]/45">
                  These categories receive minimal or no direct empirical treatment in the selected papers.
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  );
};
