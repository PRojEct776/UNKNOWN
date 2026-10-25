import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Dna,
  Table as TableIcon,
  GitCompare,
  Download,
  AlertCircle,
  Loader2,
  ArrowRight,
  RefreshCw,
  FileCode,
} from 'lucide-react';
import type { KnowledgeDNA as KnowledgeDNAData } from '../../types/knowledge';
import {
  fetchDocumentDNA,
  compareDocumentDNA,
  fetchDocuments,
  type BackendDocumentDNAResponse,
  type BackendDocumentDNAEntity,
  type BackendDNACompareResponse,
} from '../../lib/api';
import {
  generateKnowledgeDnaSvg,
  downloadSvgFile,
  downloadSvgAsPngFile,
  downloadJsonFile,
} from '../../lib/exportUtils';

export interface KnowledgeDNAProps {
  data?: KnowledgeDNAData;
  documentName?: string;
  initialDna?: BackendDocumentDNAResponse;
}

export const KnowledgeDNA: React.FC<KnowledgeDNAProps> = ({
  data,
  documentName,
  initialDna,
}) => {
  // Main view tab: 'strand' | 'table' | 'compare'
  const [activeTab, setActiveTab] = useState<'strand' | 'table' | 'compare'>('strand');

  // DNA data state
  const [dnaResponse, setDnaResponse] = useState<BackendDocumentDNAResponse | null>(initialDna || null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Available documents for comparison
  const [availableDocs, setAvailableDocs] = useState<string[]>([]);
  const [docA, setDocA] = useState<string>(documentName || '');
  const [docB, setDocB] = useState<string>('');
  const [compareResult, setCompareResult] = useState<BackendDNACompareResponse | null>(null);
  const [isComparing, setIsComparing] = useState<boolean>(false);
  const [compareError, setCompareError] = useState<string | null>(null);

  // Table filter state
  const [tableFilter, setTableFilter] = useState<'all' | 'concepts' | 'entities' | 'methods' | 'claims'>('all');
  const [tableSearch, setTableSearch] = useState<string>('');

  // Selected base pair on strand view
  const [selectedPairIndex, setSelectedPairIndex] = useState<number | null>(null);

  // Load single document DNA
  const loadDNA = useCallback(async (name: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const resp = await fetchDocumentDNA(name);
      setDnaResponse(resp);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load Knowledge DNA';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Fetch available documents list for compare view
  useEffect(() => {
    async function loadDocsList() {
      try {
        const resp = await fetchDocuments();
        if (resp && resp.documents) {
          const names = resp.documents.map((d) => d.name);
          setAvailableDocs(names);
          if (names.length > 0 && !docA) {
            setDocA(documentName || names[0]);
          }
          if (names.length > 1 && !docB) {
            const second = names.find((n) => n !== (documentName || names[0])) || names[1];
            setDocB(second);
          }
        }
      } catch (err) {
        console.warn('Could not fetch document list for DNA comparison:', err);
      }
    }
    void loadDocsList();
  }, [documentName, docA, docB]);

  useEffect(() => {
    if (documentName && !initialDna && !data) {
      void loadDNA(documentName);
    }
  }, [documentName, initialDna, data, loadDNA]);

  // Normalize data between BackendDocumentDNAResponse and legacy KnowledgeDNAData
  const normalizedDNA = useMemo(() => {
    if (dnaResponse) {
      return {
        document: dnaResponse.document,
        concepts: dnaResponse.concepts || [],
        entities: dnaResponse.entities || [],
        methods: dnaResponse.methods || [],
        claims: dnaResponse.claims || [],
        difficulty: dnaResponse.difficulty || 'Intermediate',
        novelty: dnaResponse.novelty || 'Substantial Innovation',
        summary: dnaResponse.summary || '',
      };
    }

    if (data) {
      const entities: BackendDocumentDNAEntity[] = (data.signals || []).map((s) => ({
        name: s.name || 'Signal',
        type: s.type || 'Concept',
        page: 1,
      }));

      return {
        document: data.researchArea || 'Research Document',
        concepts: data.keyConcepts || data.coreTopics || [],
        entities,
        methods: data.methods || [],
        claims: data.findings || [],
        difficulty: 'Intermediate',
        novelty: 'Substantial Innovation',
        summary: data.researchArea ? `Knowledge profile for ${data.researchArea}` : '',
      };
    }

    return null;
  }, [dnaResponse, data]);

  // Handle compare documents
  const handleCompare = async () => {
    if (!docA || !docB) return;
    setIsComparing(true);
    setCompareError(null);
    try {
      const res = await compareDocumentDNA(docA, docB);
      setCompareResult(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to compare document DNA';
      setCompareError(msg);
    } finally {
      setIsComparing(false);
    }
  };

  // Base pair strands calculation for visualization
  const strandPairs = useMemo(() => {
    if (!normalizedDNA) return [];

    const pairs: Array<{
      id: number;
      leftLabel: string;
      leftType: string;
      rightLabel: string;
      rightType: string;
      colorLeft: string;
      colorRight: string;
    }> = [];

    const concepts = normalizedDNA.concepts;
    const methods = normalizedDNA.methods;
    const entities = normalizedDNA.entities;
    const claims = normalizedDNA.claims;

    const maxLen = Math.max(concepts.length, methods.length, entities.length, claims.length, 6);

    for (let i = 0; i < maxLen; i++) {
      const c = concepts[i % (concepts.length || 1)] || `Concept ${i + 1}`;
      const m = methods[i % (methods.length || 1)] || `Method ${i + 1}`;
      const e = entities[i % (entities.length || 1)]?.name || `Entity ${i + 1}`;
      const cl = claims[i % (claims.length || 1)] || `Claim ${i + 1}`;

      if (i % 2 === 0) {
        pairs.push({
          id: i,
          leftLabel: c,
          leftType: 'Concept',
          rightLabel: m,
          rightType: 'Method',
          colorLeft: '#3b82f6', // blue
          colorRight: '#f59e0b', // amber
        });
      } else {
        pairs.push({
          id: i,
          leftLabel: e,
          leftType: 'Entity',
          rightLabel: cl,
          rightType: 'Claim',
          colorLeft: '#10b981', // emerald
          colorRight: '#a855f7', // purple
        });
      }
    }

    return pairs;
  }, [normalizedDNA]);

  // Standalone exports
  const handleExportJson = () => {
    const payload = compareResult || normalizedDNA;
    const title = normalizedDNA?.document || 'knowledge_dna';
    downloadJsonFile(`dna_${title.replace(/[^a-zA-Z0-9_-]/g, '_')}_${Date.now()}.json`, payload);
  };

  const handleExportSvg = () => {
    if (!data && !normalizedDNA) return;
    const legacyObj: KnowledgeDNAData = {
      researchArea: normalizedDNA?.document || 'Knowledge DNA',
      dominantTopics: (normalizedDNA?.concepts || []).map((c) => ({ label: c, weight: 0.9 })),
      keyConcepts: normalizedDNA?.concepts || [],
      methods: normalizedDNA?.methods || [],
      findings: normalizedDNA?.claims || [],
      limitations: [],
      researchThemes: [normalizedDNA?.difficulty || 'Intermediate', normalizedDNA?.novelty || 'Medium'],
    };
    const svg = generateKnowledgeDnaSvg(legacyObj, 900, 480);
    const title = normalizedDNA?.document || 'knowledge_dna';
    downloadSvgFile(`dna_${title.replace(/[^a-zA-Z0-9_-]/g, '_')}_${Date.now()}.svg`, svg);
  };

  const handleExportPng = async () => {
    if (!data && !normalizedDNA) return;
    const legacyObj: KnowledgeDNAData = {
      researchArea: normalizedDNA?.document || 'Knowledge DNA',
      dominantTopics: (normalizedDNA?.concepts || []).map((c) => ({ label: c, weight: 0.9 })),
      keyConcepts: normalizedDNA?.concepts || [],
      methods: normalizedDNA?.methods || [],
      findings: normalizedDNA?.claims || [],
      limitations: [],
      researchThemes: [normalizedDNA?.difficulty || 'Intermediate', normalizedDNA?.novelty || 'Medium'],
    };
    const svg = generateKnowledgeDnaSvg(legacyObj, 900, 480);
    const title = normalizedDNA?.document || 'knowledge_dna';
    await downloadSvgAsPngFile(`dna_${title.replace(/[^a-zA-Z0-9_-]/g, '_')}_${Date.now()}.png`, svg, 900, 480);
  };

  // Loading State
  if (isLoading) {
    return (
      <section
        data-testid="dna-loading"
        className="refire-card p-8 flex flex-col items-center justify-center min-h-[360px] space-y-4"
        aria-live="polite"
      >
        <Loader2 className="h-8 w-8 animate-spin text-[#d2434e]" />
        <p className="text-sm font-mono text-[#f3faf0]/80">Decoding Knowledge DNA Architecture...</p>
        <p className="text-xs text-[#98a6b0]">Extracting concepts, entities, methodologies, claims, and novelty profile</p>
      </section>
    );
  }

  // Error State
  if (error) {
    return (
      <section
        data-testid="dna-error"
        className="refire-card p-6 border-red-500/30 bg-red-950/10 space-y-4"
      >
        <div className="flex items-center gap-3">
          <AlertCircle className="h-5 w-5 text-red-400" />
          <h3 className="text-sm font-semibold text-red-200">Failed to extract Knowledge DNA</h3>
        </div>
        <p className="text-xs text-red-300/80 font-mono">{error}</p>
        {documentName && (
          <button
            type="button"
            onClick={() => void loadDNA(documentName)}
            className="inline-flex items-center gap-1.5 rounded bg-red-900/40 border border-red-500/40 px-3 py-1.5 text-xs text-white hover:bg-red-800/40 transition-colors"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Retry Extraction
          </button>
        )}
      </section>
    );
  }

  // Empty State
  if (!normalizedDNA) {
    return (
      <section
        data-testid="dna-empty"
        className="refire-card p-10 flex flex-col items-center justify-center text-center space-y-3"
      >
        <Dna className="h-10 w-10 text-[#d2434e]/50" />
        <h3 className="text-sm font-semibold text-white">No Knowledge DNA Extracted</h3>
        <p className="text-xs text-[#98a6b0] max-w-sm">
          Select an indexed document or execute a DNA extraction to visualize the structural genetic ontology of the research.
        </p>
      </section>
    );
  }

  return (
    <section
      data-testid="dna-container"
      className="refire-card p-5 sm:p-6 space-y-6"
      aria-labelledby="knowledge-dna-title"
    >
      {/* Header & View Mode Switcher */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/8 pb-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#d2434e]/15 border border-[#d2434e]/30">
            <Dna className="h-5 w-5 text-[#d2434e]" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 id="knowledge-dna-title" className="text-sm font-semibold text-white tracking-wide">
                Knowledge DNA: {normalizedDNA.document}
              </h2>
              <span className="rounded-full bg-[#1b2734] px-2.5 py-0.5 text-[10px] font-mono text-[#a7d0d2] border border-[#4d728e]/30">
                {normalizedDNA.difficulty} · {normalizedDNA.novelty}
              </span>
            </div>
            <p className="text-[11px] text-[#f3faf0]/55 mt-0.5">
              Ontological genetics mapping concepts, entities, methods, claims, difficulty, and novelty.
            </p>
          </div>
        </div>

        {/* Tab Switcher & Export buttons */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Tabs */}
          <div className="flex items-center rounded-lg bg-[#0b1219] border border-white/10 p-1">
            <button
              data-testid="dna-tab-strand"
              type="button"
              onClick={() => setActiveTab('strand')}
              className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                activeTab === 'strand'
                  ? 'bg-[#1b2734] text-white shadow-sm border border-white/10'
                  : 'text-[#98a6b0] hover:text-white'
              }`}
            >
              <Dna className="h-3.5 w-3.5 text-[#d2434e]" />
              Strand View
            </button>
            <button
              data-testid="dna-tab-table"
              type="button"
              onClick={() => setActiveTab('table')}
              className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                activeTab === 'table'
                  ? 'bg-[#1b2734] text-white shadow-sm border border-white/10'
                  : 'text-[#98a6b0] hover:text-white'
              }`}
            >
              <TableIcon className="h-3.5 w-3.5 text-[#a7d0d2]" />
              DNA Table
            </button>
            <button
              data-testid="dna-tab-compare"
              type="button"
              onClick={() => setActiveTab('compare')}
              className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                activeTab === 'compare'
                  ? 'bg-[#1b2734] text-white shadow-sm border border-white/10'
                  : 'text-[#98a6b0] hover:text-white'
              }`}
            >
              <GitCompare className="h-3.5 w-3.5 text-[#f59e0b]" />
              Compare View
            </button>
          </div>

          {/* Export Buttons */}
          <div className="flex items-center gap-1 pl-1">
            <button
              data-testid="dna-export-svg"
              type="button"
              onClick={handleExportSvg}
              className="inline-flex items-center gap-1 rounded bg-[#141d26] border border-[#4d728e]/40 px-2.5 py-1 text-[11px] font-mono text-[#a7d0d2] hover:text-white hover:border-[#a7d0d2] transition-colors"
              title="Download vector SVG"
            >
              <Download className="h-3 w-3" />
              SVG
            </button>
            <button
              data-testid="dna-export-png"
              type="button"
              onClick={() => void handleExportPng()}
              className="inline-flex items-center gap-1 rounded bg-[#141d26] border border-[#4d728e]/40 px-2.5 py-1 text-[11px] font-mono text-[#a7d0d2] hover:text-white hover:border-[#a7d0d2] transition-colors"
              title="Download raster PNG"
            >
              <Download className="h-3 w-3" />
              PNG
            </button>
            <button
              data-testid="dna-export-json"
              type="button"
              onClick={handleExportJson}
              className="inline-flex items-center gap-1 rounded bg-[#141d26] border border-[#4d728e]/40 px-2.5 py-1 text-[11px] font-mono text-[#a7d0d2] hover:text-white hover:border-[#a7d0d2] transition-colors"
              title="Download structured JSON"
            >
              <FileCode className="h-3 w-3" />
              JSON
            </button>
          </div>
        </div>
      </div>

      {/* Summary Banner */}
      {normalizedDNA.summary && (
        <div className="rounded-lg border border-white/8 bg-[#0b1219] p-3 text-xs text-[#f3faf0]/80 italic">
          "{normalizedDNA.summary}"
        </div>
      )}

      {/* =================================================================== */}
      {/* 1. STRAND VIEW: Biological Double-Helix Topology                    */}
      {/* =================================================================== */}
      {activeTab === 'strand' && (
        <div data-testid="dna-strand-view" className="space-y-4">
          <div className="flex items-center justify-between text-xs text-[#98a6b0]">
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-[#3b82f6]" /> Concepts
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-[#10b981]" /> Entities
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-[#f59e0b]" /> Methods
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-[#a855f7]" /> Claims
              </span>
            </div>
            <span className="text-[10px] font-mono">Click a base pair to inspect pairing details</span>
          </div>

          {/* DNA Double-Helix SVG Canvas */}
          <div className="relative h-[380px] w-full rounded-lg border border-white/8 bg-[#070b0f] overflow-x-auto overflow-y-hidden p-4">
            <svg
              className="min-w-[840px] w-full h-full"
              viewBox="0 0 840 320"
              xmlns="http://www.w3.org/2000/svg"
            >
              <defs>
                <linearGradient id="strand-backbone-a" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#d2434e" stopOpacity="0.8" />
                  <stop offset="100%" stopColor="#a7d0d2" stopOpacity="0.8" />
                </linearGradient>
                <linearGradient id="strand-backbone-b" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.8" />
                  <stop offset="100%" stopColor="#10b981" stopOpacity="0.8" />
                </linearGradient>
              </defs>

              {/* Sine Wave Double Helix Backbones */}
              {(() => {
                const pointsCount = 40;
                let pathA = '';
                let pathB = '';
                const width = 800;
                const midY = 160;
                const amplitude = 70;

                for (let i = 0; i <= pointsCount; i++) {
                  const x = 20 + (i / pointsCount) * width;
                  const angle = (i / pointsCount) * 4 * Math.PI;
                  const yA = midY + Math.sin(angle) * amplitude;
                  const yB = midY - Math.sin(angle) * amplitude;

                  if (i === 0) {
                    pathA = `M ${x} ${yA}`;
                    pathB = `M ${x} ${yB}`;
                  } else {
                    pathA += ` L ${x} ${yA}`;
                    pathB += ` L ${x} ${yB}`;
                  }
                }

                return (
                  <>
                    <path d={pathA} fill="none" stroke="url(#strand-backbone-a)" strokeWidth="3" opacity="0.85" />
                    <path d={pathB} fill="none" stroke="url(#strand-backbone-b)" strokeWidth="3" opacity="0.85" />
                  </>
                );
              })()}

              {/* Base Pair Rungs */}
              {strandPairs.slice(0, 14).map((pair, idx) => {
                const totalPairs = Math.min(strandPairs.length, 14);
                const x = 50 + (idx / (totalPairs - 1 || 1)) * 740;
                const angle = (idx / (totalPairs - 1 || 1)) * 4 * Math.PI;
                const yA = 160 + Math.sin(angle) * 70;
                const yB = 160 - Math.sin(angle) * 70;
                const isSelected = selectedPairIndex === idx;

                return (
                  <g
                    key={`rung-${pair.id}-${idx}`}
                    onClick={() => setSelectedPairIndex(idx)}
                    className="cursor-pointer group"
                    data-testid={`strand-pair-${idx}`}
                  >
                    {/* Connecting Rung */}
                    <line
                      x1={x}
                      y1={yA}
                      x2={x}
                      y2={yB}
                      stroke={isSelected ? '#ffffff' : '#4d728e'}
                      strokeWidth={isSelected ? '3' : '1.75'}
                      strokeDasharray={isSelected ? 'none' : '2 2'}
                      className="transition-all"
                    />

                    {/* Top Base Node */}
                    <circle
                      cx={x}
                      cy={yA}
                      r={isSelected ? '8' : '6'}
                      fill={pair.colorLeft}
                      stroke="#ffffff"
                      strokeWidth={isSelected ? '2' : '0'}
                      className="transition-all hover:scale-125"
                    />

                    {/* Bottom Base Node */}
                    <circle
                      cx={x}
                      cy={yB}
                      r={isSelected ? '8' : '6'}
                      fill={pair.colorRight}
                      stroke="#ffffff"
                      strokeWidth={isSelected ? '2' : '0'}
                      className="transition-all hover:scale-125"
                    />

                    {/* Label */}
                    <text
                      x={x}
                      y={yA < 160 ? yA - 12 : yA + 18}
                      textAnchor="middle"
                      fill="#f3faf0"
                      fontSize="9"
                      fontFamily="system-ui"
                      className="opacity-80 group-hover:opacity-100"
                    >
                      {pair.leftLabel.length > 10 ? `${pair.leftLabel.slice(0, 9)}…` : pair.leftLabel}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>

          {/* Selected Base Pair Detail Card */}
          {selectedPairIndex !== null && strandPairs[selectedPairIndex] && (
            <div
              data-testid="strand-selected-detail"
              className="rounded-lg border border-white/10 bg-[#0b1219] p-4 flex flex-wrap items-center justify-between gap-4"
            >
              <div>
                <span className="text-[10px] font-mono uppercase text-[#a7d0d2]">
                  Base Pair #{selectedPairIndex + 1}
                </span>
                <div className="flex items-center gap-3 mt-1">
                  <span className="text-xs font-semibold text-white">
                    [{strandPairs[selectedPairIndex].leftType}] {strandPairs[selectedPairIndex].leftLabel}
                  </span>
                  <ArrowRight className="h-3 w-3 text-[#98a6b0]" />
                  <span className="text-xs font-semibold text-white">
                    [{strandPairs[selectedPairIndex].rightType}] {strandPairs[selectedPairIndex].rightLabel}
                  </span>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setSelectedPairIndex(null)}
                className="text-xs text-[#98a6b0] hover:text-white"
              >
                Dismiss
              </button>
            </div>
          )}
        </div>
      )}

      {/* =================================================================== */}
      {/* 2. TABLE VIEW: Structured DNA Facets                                */}
      {/* =================================================================== */}
      {activeTab === 'table' && (
        <div data-testid="dna-table-view" className="space-y-4">
          {/* Table Controls */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-1.5">
              {(['all', 'concepts', 'entities', 'methods', 'claims'] as const).map((tab) => (
                <button
                  key={tab}
                  type="button"
                  data-testid={`dna-filter-${tab}`}
                  onClick={() => setTableFilter(tab)}
                  className={`rounded-md px-2.5 py-1 text-xs capitalize transition-colors ${
                    tableFilter === tab
                      ? 'bg-[#1b2734] text-white border border-[#4d728e]/50'
                      : 'text-[#98a6b0] hover:text-white'
                  }`}
                >
                  {tab}
                </button>
              ))}
            </div>

            <input
              type="text"
              data-testid="dna-table-search"
              value={tableSearch}
              onChange={(e) => setTableSearch(e.target.value)}
              placeholder="Filter DNA elements..."
              className="h-7 w-48 rounded bg-[#0b1219] border border-[#4d728e]/40 px-2.5 text-xs text-white placeholder-[#98a6b0]/60 focus:border-[#a7d0d2] focus:outline-none"
            />
          </div>

          {/* Structured Responsive DNA Table */}
          <div className="rounded-lg border border-white/8 bg-[#0b1219] overflow-x-auto">
            <table data-testid="dna-table" className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-white/8 bg-[#141d26]/60 text-[11px] font-mono text-[#a7d0d2]">
                  <th className="py-2.5 px-3">Category</th>
                  <th className="py-2.5 px-3">Name / Assertion</th>
                  <th className="py-2.5 px-3">Type / Detail</th>
                  <th className="py-2.5 px-3 text-right">Page Ref</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {/* Concepts */}
                {(tableFilter === 'all' || tableFilter === 'concepts') &&
                  normalizedDNA.concepts
                    .filter((c) => !tableSearch || c.toLowerCase().includes(tableSearch.toLowerCase()))
                    .map((concept, i) => (
                      <tr key={`row-concept-${i}`} className="hover:bg-white/[0.02]" data-testid="dna-row-concept">
                        <td className="py-2 px-3 font-mono text-[#3b82f6]">Concept</td>
                        <td className="py-2 px-3 text-white font-medium">{concept}</td>
                        <td className="py-2 px-3 text-[#98a6b0]">Foundational domain topic</td>
                        <td className="py-2 px-3 text-right text-xs font-mono text-[#98a6b0]">Page 1-3</td>
                      </tr>
                    ))}

                {/* Entities */}
                {(tableFilter === 'all' || tableFilter === 'entities') &&
                  normalizedDNA.entities
                    .filter(
                      (e) =>
                        !tableSearch ||
                        e.name.toLowerCase().includes(tableSearch.toLowerCase()) ||
                        e.type.toLowerCase().includes(tableSearch.toLowerCase()),
                    )
                    .map((entity, i) => (
                      <tr key={`row-entity-${i}`} className="hover:bg-white/[0.02]" data-testid="dna-row-entity">
                        <td className="py-2 px-3 font-mono text-[#10b981]">Entity</td>
                        <td className="py-2 px-3 text-white font-medium">{entity.name}</td>
                        <td className="py-2 px-3 text-[#a7d0d2]">
                          <span className="rounded bg-[#10b981]/10 px-1.5 py-0.5 border border-[#10b981]/30 text-[10px]">
                            {entity.type}
                          </span>
                        </td>
                        <td className="py-2 px-3 text-right text-xs font-mono text-[#98a6b0]">
                          Page {entity.page || 1}
                        </td>
                      </tr>
                    ))}

                {/* Methods */}
                {(tableFilter === 'all' || tableFilter === 'methods') &&
                  normalizedDNA.methods
                    .filter((m) => !tableSearch || m.toLowerCase().includes(tableSearch.toLowerCase()))
                    .map((method, i) => (
                      <tr key={`row-method-${i}`} className="hover:bg-white/[0.02]" data-testid="dna-row-method">
                        <td className="py-2 px-3 font-mono text-[#f59e0b]">Method</td>
                        <td className="py-2 px-3 text-white font-medium">{method}</td>
                        <td className="py-2 px-3 text-[#98a6b0]">Technique & Algorithm</td>
                        <td className="py-2 px-3 text-right text-xs font-mono text-[#98a6b0]">Methods</td>
                      </tr>
                    ))}

                {/* Claims */}
                {(tableFilter === 'all' || tableFilter === 'claims') &&
                  normalizedDNA.claims
                    .filter((cl) => !tableSearch || cl.toLowerCase().includes(tableSearch.toLowerCase()))
                    .map((claim, i) => (
                      <tr key={`row-claim-${i}`} className="hover:bg-white/[0.02]" data-testid="dna-row-claim">
                        <td className="py-2 px-3 font-mono text-[#a855f7]">Claim</td>
                        <td className="py-2 px-3 text-white font-medium">{claim}</td>
                        <td className="py-2 px-3 text-[#98a6b0]">Empirical / Theoretical Assertion</td>
                        <td className="py-2 px-3 text-right text-xs font-mono text-[#98a6b0]">Findings</td>
                      </tr>
                    ))}
              </tbody>
            </table>
          </div>

          {/* Difficulty & Novelty Summary Footer Card */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
            <div className="rounded-lg border border-white/8 bg-[#0b1219] p-3">
              <span className="text-[10px] font-mono uppercase text-[#a7d0d2]">Difficulty Rating</span>
              <div
                data-testid="dna-difficulty-badge"
                className="mt-1 text-sm font-semibold text-white flex items-center gap-2"
              >
                <span>{normalizedDNA.difficulty}</span>
                <span className="text-[11px] text-[#98a6b0] font-normal">
                  (requires prerequisite background)
                </span>
              </div>
            </div>

            <div className="rounded-lg border border-white/8 bg-[#0b1219] p-3">
              <span className="text-[10px] font-mono uppercase text-[#d2434e]">Novelty Contribution</span>
              <div
                data-testid="dna-novelty-badge"
                className="mt-1 text-sm font-semibold text-white flex items-center gap-2"
              >
                <span>{normalizedDNA.novelty}</span>
                <span className="text-[11px] text-[#98a6b0] font-normal">
                  (calibrated against corpus)
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* =================================================================== */}
      {/* 3. COMPARE VIEW: Compare Two Documents                              */}
      {/* =================================================================== */}
      {activeTab === 'compare' && (
        <div data-testid="dna-compare-view" className="space-y-4">
          {/* Document Selectors & Compare Trigger */}
          <div className="rounded-lg border border-white/8 bg-[#0b1219] p-4 space-y-3">
            <div className="flex items-center gap-2 text-xs font-semibold text-white">
              <GitCompare className="h-4 w-4 text-[#f59e0b]" />
              <span>Compare Genetic Ontologies Between Two Research Documents</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {/* Document A Selector */}
              <div>
                <label className="block text-[11px] font-mono text-[#a7d0d2] mb-1">Document A</label>
                <select
                  data-testid="compare-doc-a-select"
                  value={docA}
                  onChange={(e) => setDocA(e.target.value)}
                  className="w-full h-8 rounded bg-[#141d26] border border-[#4d728e]/40 px-2.5 text-xs text-white focus:outline-none focus:border-[#a7d0d2]"
                >
                  {availableDocs.map((doc) => (
                    <option key={`a-${doc}`} value={doc}>
                      {doc}
                    </option>
                  ))}
                  {!availableDocs.includes(docA) && docA && <option value={docA}>{docA}</option>}
                </select>
              </div>

              {/* Document B Selector */}
              <div>
                <label className="block text-[11px] font-mono text-[#a7d0d2] mb-1">Document B</label>
                <select
                  data-testid="compare-doc-b-select"
                  value={docB}
                  onChange={(e) => setDocB(e.target.value)}
                  className="w-full h-8 rounded bg-[#141d26] border border-[#4d728e]/40 px-2.5 text-xs text-white focus:outline-none focus:border-[#a7d0d2]"
                >
                  {availableDocs.map((doc) => (
                    <option key={`b-${doc}`} value={doc}>
                      {doc}
                    </option>
                  ))}
                  {!availableDocs.includes(docB) && docB && <option value={docB}>{docB}</option>}
                </select>
              </div>
            </div>

            <button
              data-testid="compare-run-btn"
              type="button"
              onClick={() => void handleCompare()}
              disabled={!docA || !docB || isComparing}
              className="inline-flex items-center gap-2 rounded bg-[#1b2734] border border-[#4d728e]/50 px-4 py-2 text-xs font-medium text-white hover:border-[#a7d0d2] transition-colors disabled:opacity-50"
            >
              {isComparing ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-[#a7d0d2]" />
                  Comparing Documents...
                </>
              ) : (
                <>
                  <GitCompare className="h-3.5 w-3.5 text-[#a7d0d2]" />
                  Run DNA Comparison
                </>
              )}
            </button>
          </div>

          {/* Compare Error Message */}
          {compareError && (
            <div
              data-testid="compare-error"
              className="rounded-lg border border-red-500/30 bg-red-950/20 p-3 text-xs text-red-300 flex items-center gap-2"
            >
              <AlertCircle className="h-4 w-4 text-red-400" />
              <span>{compareError}</span>
            </div>
          )}

          {/* Comparison Results */}
          {compareResult && (
            <div data-testid="compare-results-container" className="space-y-4">
              {/* Overlap & Distinct Concepts Grid */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {/* Distinct to A */}
                <div
                  data-testid="compare-distinct-a"
                  className="rounded-lg border border-white/8 bg-[#0b1219] p-3 space-y-2"
                >
                  <span className="text-[10px] font-mono uppercase text-[#3b82f6]">
                    Unique to {compareResult.document_a}
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {compareResult.distinct_concepts_a.length > 0 ? (
                      compareResult.distinct_concepts_a.map((c, i) => (
                        <span
                          key={`da-${i}`}
                          className="rounded bg-[#3b82f6]/10 border border-[#3b82f6]/30 px-2 py-0.5 text-[11px] text-white"
                        >
                          {c}
                        </span>
                      ))
                    ) : (
                      <span className="text-xs text-[#98a6b0] italic">None identified</span>
                    )}
                  </div>
                </div>

                {/* Shared Concepts */}
                <div
                  data-testid="compare-shared-concepts"
                  className="rounded-lg border border-white/8 bg-[#0b1219] p-3 space-y-2"
                >
                  <span className="text-[10px] font-mono uppercase text-[#10b981]">
                    Shared Genetic Concepts ({compareResult.shared_concepts.length})
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {compareResult.shared_concepts.length > 0 ? (
                      compareResult.shared_concepts.map((c, i) => (
                        <span
                          key={`sh-${i}`}
                          className="rounded bg-[#10b981]/15 border border-[#10b981]/40 px-2 py-0.5 text-[11px] text-white font-medium"
                        >
                          {c}
                        </span>
                      ))
                    ) : (
                      <span className="text-xs text-[#98a6b0] italic">No shared concepts</span>
                    )}
                  </div>
                </div>

                {/* Distinct to B */}
                <div
                  data-testid="compare-distinct-b"
                  className="rounded-lg border border-white/8 bg-[#0b1219] p-3 space-y-2"
                >
                  <span className="text-[10px] font-mono uppercase text-[#f59e0b]">
                    Unique to {compareResult.document_b}
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {compareResult.distinct_concepts_b.length > 0 ? (
                      compareResult.distinct_concepts_b.map((c, i) => (
                        <span
                          key={`db-${i}`}
                          className="rounded bg-[#f59e0b]/10 border border-[#f59e0b]/30 px-2 py-0.5 text-[11px] text-white"
                        >
                          {c}
                        </span>
                      ))
                    ) : (
                      <span className="text-xs text-[#98a6b0] italic">None identified</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Shared Methods */}
              <div
                data-testid="compare-shared-methods"
                className="rounded-lg border border-white/8 bg-[#0b1219] p-3 space-y-2"
              >
                <span className="text-[10px] font-mono uppercase text-[#a7d0d2]">
                  Shared Methodologies
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {compareResult.shared_methods.length > 0 ? (
                    compareResult.shared_methods.map((m, i) => (
                      <span
                        key={`sm-${i}`}
                        className="rounded bg-[#141d26] border border-[#4d728e]/40 px-2.5 py-1 text-xs text-white"
                      >
                        {m}
                      </span>
                    ))
                  ) : (
                    <span className="text-xs text-[#98a6b0] italic">Different methodological frameworks</span>
                  )}
                </div>
              </div>

              {/* Side-by-Side Claims */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div
                  data-testid="compare-claims-a"
                  className="rounded-lg border border-white/8 bg-[#0b1219] p-3 space-y-2"
                >
                  <span className="text-[10px] font-mono uppercase text-[#98a6b0]">
                    Claims from {compareResult.document_a}
                  </span>
                  <ul className="space-y-1.5 list-disc list-inside text-xs text-[#f3faf0]/85">
                    {compareResult.claims_a.map((cl, i) => (
                      <li key={`ca-${i}`}>{cl}</li>
                    ))}
                  </ul>
                </div>

                <div
                  data-testid="compare-claims-b"
                  className="rounded-lg border border-white/8 bg-[#0b1219] p-3 space-y-2"
                >
                  <span className="text-[10px] font-mono uppercase text-[#98a6b0]">
                    Claims from {compareResult.document_b}
                  </span>
                  <ul className="space-y-1.5 list-disc list-inside text-xs text-[#f3faf0]/85">
                    {compareResult.claims_b.map((cl, i) => (
                      <li key={`cb-${i}`}>{cl}</li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* Difficulty and Novelty Metric Comparison */}
              <div
                data-testid="compare-metrics-row"
                className="grid grid-cols-1 sm:grid-cols-2 gap-3"
              >
                <div className="rounded-lg border border-white/8 bg-[#0b1219] p-3 flex justify-between items-center text-xs">
                  <span className="text-[#98a6b0]">Difficulty Level:</span>
                  <span className="font-mono text-white">
                    {compareResult.difficulty_comparison.document_a || 'N/A'} vs{' '}
                    {compareResult.difficulty_comparison.document_b || 'N/A'}
                  </span>
                </div>
                <div className="rounded-lg border border-white/8 bg-[#0b1219] p-3 flex justify-between items-center text-xs">
                  <span className="text-[#98a6b0]">Novelty Level:</span>
                  <span className="font-mono text-white">
                    {compareResult.novelty_comparison.document_a || 'N/A'} vs{' '}
                    {compareResult.novelty_comparison.document_b || 'N/A'}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
};
