import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  Dna,
  Network,
  BookOpen,
  Table as TableIcon,
  GitCompare,
  Download,
  AlertCircle,
  Loader2,
  ArrowRight,
  RefreshCw,
  Search,
  ZoomIn,
  ZoomOut,
  Maximize2,
  X,
  ExternalLink,
} from 'lucide-react';
import type {
  KnowledgeDNA as KnowledgeDNAData,
  KnowledgeDNANode,
  KnowledgeRelationship,
} from '../../types/knowledge';
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

// Category visual configuration
const CATEGORY_COLORS: Record<string, { bg: string; border: string; text: string; fill: string }> = {
  CONCEPT: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/40', text: 'text-emerald-400', fill: '#10b981' },
  METHODOLOGY: { bg: 'bg-cyan-500/10', border: 'border-cyan-500/40', text: 'text-cyan-400', fill: '#06b6d4' },
  METHOD: { bg: 'bg-cyan-500/10', border: 'border-cyan-500/40', text: 'text-cyan-400', fill: '#06b6d4' },
  DATASET: { bg: 'bg-amber-500/10', border: 'border-amber-500/40', text: 'text-amber-400', fill: '#f59e0b' },
  METRIC: { bg: 'bg-purple-500/10', border: 'border-purple-500/40', text: 'text-purple-400', fill: '#a855f7' },
  RESULT: { bg: 'bg-lime-500/10', border: 'border-lime-500/40', text: 'text-lime-400', fill: '#84cc16' },
  FINDING: { bg: 'bg-lime-500/10', border: 'border-lime-500/40', text: 'text-lime-400', fill: '#84cc16' },
  OBJECTIVE: { bg: 'bg-rose-500/10', border: 'border-rose-500/40', text: 'text-rose-400', fill: '#f43f5e' },
  CONTRIBUTION: { bg: 'bg-violet-500/10', border: 'border-violet-500/40', text: 'text-violet-400', fill: '#8b5cf6' },
  ADVANTAGE: { bg: 'bg-teal-500/10', border: 'border-teal-500/40', text: 'text-teal-400', fill: '#14b8a6' },
  LIMITATION: { bg: 'bg-orange-500/10', border: 'border-orange-500/40', text: 'text-orange-400', fill: '#f97316' },
  FUTURE_DIRECTION: { bg: 'bg-sky-500/10', border: 'border-sky-500/40', text: 'text-sky-400', fill: '#0ea5e9' },
};

function getCategoryColor(cat: string) {
  const upper = (cat || 'CONCEPT').toUpperCase();
  for (const [k, v] of Object.entries(CATEGORY_COLORS)) {
    if (upper.includes(k)) return v;
  }
  return CATEGORY_COLORS.CONCEPT;
}

export const KnowledgeDNA: React.FC<KnowledgeDNAProps> = ({
  data,
  documentName,
  initialDna,
}) => {
  // Main view tab: 'graph' | 'profile' | 'table' | 'strand' | 'compare'
  const [activeTab, setActiveTab] = useState<'graph' | 'profile' | 'table' | 'strand' | 'compare'>('graph');

  // DNA data state for single document endpoint
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

  // Table filter & search state
  const [tableFilter, setTableFilter] = useState<'all' | 'concepts' | 'entities' | 'methods' | 'claims'>('all');
  const [tableSearch, setTableSearch] = useState<string>('');

  // Selected base pair on strand view
  const [selectedPairIndex, setSelectedPairIndex] = useState<number | null>(null);

  // Graph state: Zoom, Pan, Search, Filter, Selection
  const [zoom, setZoom] = useState<number>(1);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [graphSearch, setGraphSearch] = useState<string>('');
  const [categoryFilter, setCategoryFilter] = useState<string>('ALL');
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [collapsedCategories] = useState<Set<string>>(new Set());

  const svgRef = useRef<SVGSVGElement | null>(null);

  // Load single document DNA if needed
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

  useEffect(() => {
    if (documentName && !initialDna && !data) {
      void loadDNA(documentName);
    }
  }, [documentName, initialDna, data, loadDNA]);

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

  // Harmonized Knowledge Graph Nodes & Edges
  const graphData = useMemo(() => {
    const rawNodes = data?.nodes || [];
    const rawEdges = data?.edges || data?.relationships || [];

    if (rawNodes.length > 0) {
      return {
        nodes: rawNodes,
        edges: rawEdges,
        researchArea: data?.researchArea || 'Research Knowledge DNA',
        statistics: data?.statistics || {},
      };
    }

    // Synthesize nodes if only signals/concepts exist
    const synthNodes: KnowledgeDNANode[] = [];
    const synthEdges: KnowledgeRelationship[] = [];

    const rootLabel = data?.researchArea || dnaResponse?.document || documentName || 'Research DNA';
    synthNodes.push({
      id: 'root_node',
      label: rootLabel,
      category: 'CONCEPT',
      explanation: `Core research foundation for ${rootLabel}`,
      evidence: [],
      confidence: 1.0,
      document: dnaResponse?.document || '',
      supporting_papers: [dnaResponse?.document || documentName || 'Document'],
      is_inferred: false,
    });

    // Add concepts
    const concepts = data?.keyConcepts || data?.coreTopics || dnaResponse?.concepts || [];
    concepts.forEach((c, idx) => {
      const nid = `c_${idx}`;
      synthNodes.push({
        id: nid,
        label: c,
        category: 'CONCEPT',
        explanation: `Core concept: ${c}`,
        confidence: 0.92,
        document: dnaResponse?.document || '',
        supporting_papers: [dnaResponse?.document || 'Document'],
        is_inferred: false,
      });
      synthEdges.push({
        source: 'root_node',
        target: nid,
        relationship: 'includes concept',
        confidence: 0.9,
        is_inferred: false,
      });
    });

    // Add methods
    const methods = data?.methods || dnaResponse?.methods || [];
    methods.forEach((m, idx) => {
      const nid = `m_${idx}`;
      synthNodes.push({
        id: nid,
        label: m,
        category: 'METHODOLOGY',
        explanation: `Proposed methodology: ${m}`,
        confidence: 0.95,
        document: dnaResponse?.document || '',
        supporting_papers: [dnaResponse?.document || 'Document'],
        is_inferred: false,
      });
      synthEdges.push({
        source: 'root_node',
        target: nid,
        relationship: 'employs',
        confidence: 0.92,
        is_inferred: false,
      });
    });

    // Add findings/claims
    const findings = data?.findings || dnaResponse?.claims || [];
    findings.forEach((f, idx) => {
      const nid = `f_${idx}`;
      synthNodes.push({
        id: nid,
        label: f.length > 40 ? `${f.slice(0, 37)}...` : f,
        category: 'RESULT',
        explanation: f,
        evidence: [f],
        confidence: 0.91,
        document: dnaResponse?.document || '',
        supporting_papers: [dnaResponse?.document || 'Document'],
        is_inferred: false,
      });
      if (synthNodes.length > 2) {
        synthEdges.push({
          source: synthNodes[2].id,
          target: nid,
          relationship: 'produces',
          confidence: 0.89,
          is_inferred: true,
        });
      }
    });

    return {
      nodes: synthNodes,
      edges: synthEdges,
      researchArea: rootLabel,
      statistics: {
        total_concepts: synthNodes.length,
        unique_methodologies: methods.length,
        datasets: 0,
        findings: findings.length,
        relationships: synthEdges.length,
        explicit_relationships: synthEdges.filter((e) => !e.is_inferred).length,
        inferred_relationships: synthEdges.filter((e) => e.is_inferred).length,
        supporting_documents: 1,
      },
    };
  }, [data, dnaResponse, documentName]);

  // Selected node object for Concept Inspector
  const selectedNode = useMemo(() => {
    if (!selectedNodeId) return graphData.nodes[0] || null;
    return graphData.nodes.find((n) => n.id === selectedNodeId) || graphData.nodes[0] || null;
  }, [selectedNodeId, graphData.nodes]);

  // Connected relationships for selected node
  const selectedNodeRelationships = useMemo(() => {
    if (!selectedNode) return [];
    return graphData.edges.filter(
      (e) => e.source === selectedNode.id || e.target === selectedNode.id
    );
  }, [selectedNode, graphData.edges]);

  // Filtered nodes based on search & category
  const visibleNodes = useMemo(() => {
    return graphData.nodes.filter((node) => {
      if (categoryFilter !== 'ALL' && !node.category.toUpperCase().includes(categoryFilter)) {
        return false;
      }
      if (collapsedCategories.has(node.category.toUpperCase())) {
        return false;
      }
      if (graphSearch.trim()) {
        const q = graphSearch.toLowerCase();
        return (
          node.label.toLowerCase().includes(q) ||
          (node.explanation || '').toLowerCase().includes(q) ||
          node.category.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [graphData.nodes, categoryFilter, collapsedCategories, graphSearch]);

  const visibleNodeIds = useMemo(() => new Set(visibleNodes.map((n) => n.id)), [visibleNodes]);

  // Visible edges connecting visible nodes
  const visibleEdges = useMemo(() => {
    return graphData.edges.filter((e) => visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target));
  }, [graphData.edges, visibleNodeIds]);

  // Position layout calculation for graph nodes (circular/hierarchical layout)
  const nodePositions = useMemo(() => {
    const positions = new Map<string, { x: number; y: number }>();
    const count = visibleNodes.length;
    if (count === 0) return positions;

    const centerX = 400;
    const centerY = 280;

    // Root node in center
    const rootNode = visibleNodes.find((n) => n.id.includes('root') || n.id === 'concept_central') || visibleNodes[0];
    positions.set(rootNode.id, { x: centerX, y: centerY });

    const otherNodes = visibleNodes.filter((n) => n.id !== rootNode.id);
    const radiusStep = otherNodes.length > 12 ? 220 : 180;

    otherNodes.forEach((node, idx) => {
      const angle = (idx / otherNodes.length) * 2 * Math.PI;
      const r = radiusStep + (idx % 2 === 0 ? -30 : 30);
      positions.set(node.id, {
        x: centerX + r * Math.cos(angle),
        y: centerY + r * Math.sin(angle),
      });
    });

    return positions;
  }, [visibleNodes]);

  // Zoom / Pan handlers
  const handleZoomIn = () => setZoom((z) => Math.min(2.5, z + 0.2));
  const handleZoomOut = () => setZoom((z) => Math.max(0.4, z - 0.2));
  const handleResetZoom = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };
  const handleFitToScreen = () => {
    setZoom(0.9);
    setPan({ x: 0, y: 0 });
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
  };

  const handleMouseUp = () => setIsDragging(false);

  // Normalize data for legacy facet table & double-helix strand view
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
        page: 0,
      }));

      return {
        document: data.researchArea || 'Research Document',
        concepts: data.keyConcepts || data.coreTopics || [],
        entities,
        methods: data.methods || data.methodologies || [],
        claims: data.findings || data.results || [],
        difficulty: 'Intermediate',
        novelty: 'Substantial Innovation',
        summary: data.researchArea ? `Knowledge profile for ${data.researchArea}` : '',
      };
    }

    return null;
  }, [dnaResponse, data]);

  // Base pair strands calculation for biological helix view
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
          colorLeft: '#3b82f6',
          colorRight: '#f59e0b',
        });
      } else {
        pairs.push({
          id: i,
          leftLabel: e,
          leftType: 'Entity',
          rightLabel: cl,
          rightType: 'Claim',
          colorLeft: '#10b981',
          colorRight: '#a855f7',
        });
      }
    }

    return pairs;
  }, [normalizedDNA]);

  // Export handlers
  const handleExportJson = () => {
    const payload = data || compareResult || normalizedDNA;
    const title = data?.researchArea || normalizedDNA?.document || 'knowledge_dna';
    downloadJsonFile(`dna_${title.replace(/[^a-zA-Z0-9_-]/g, '_')}_${Date.now()}.json`, payload);
  };

  const handleExportSvg = () => {
    if (!svgRef.current) {
      if (normalizedDNA) {
        const legacyObj: KnowledgeDNAData = {
          researchArea: normalizedDNA.document || 'Knowledge DNA',
          dominantTopics: (normalizedDNA.concepts || []).map((c) => ({ label: c, weight: 0.9 })),
          keyConcepts: normalizedDNA.concepts || [],
          methods: normalizedDNA.methods || [],
          findings: normalizedDNA.claims || [],
          limitations: [],
          researchThemes: [normalizedDNA.difficulty, normalizedDNA.novelty],
        };
        const svg = generateKnowledgeDnaSvg(legacyObj, 900, 480);
        downloadSvgFile(`dna_${(normalizedDNA.document || 'dna').replace(/[^a-zA-Z0-9_-]/g, '_')}_${Date.now()}.svg`, svg);
      }
      return;
    }
    const serializer = new XMLSerializer();
    const svgStr = serializer.serializeToString(svgRef.current);
    const title = data?.researchArea || normalizedDNA?.document || 'knowledge_dna_graph';
    downloadSvgFile(`graph_${title.replace(/[^a-zA-Z0-9_-]/g, '_')}_${Date.now()}.svg`, svgStr);
  };

  const handleExportPng = async () => {
    if (!data && !normalizedDNA) return;
    const legacyObj: KnowledgeDNAData = {
      researchArea: data?.researchArea || normalizedDNA?.document || 'Knowledge DNA',
      dominantTopics: (normalizedDNA?.concepts || data?.coreTopics || []).map((c) => ({ label: c, weight: 0.9 })),
      keyConcepts: normalizedDNA?.concepts || data?.keyConcepts || [],
      methods: normalizedDNA?.methods || data?.methods || [],
      findings: normalizedDNA?.claims || data?.findings || [],
      limitations: data?.limitations || [],
      researchThemes: [normalizedDNA?.difficulty || 'Intermediate', normalizedDNA?.novelty || 'Medium'],
    };
    const svg = generateKnowledgeDnaSvg(legacyObj, 900, 480);
    const title = data?.researchArea || normalizedDNA?.document || 'knowledge_dna';
    await downloadSvgAsPngFile(`dna_${title.replace(/[^a-zA-Z0-9_-]/g, '_')}_${Date.now()}.png`, svg, 900, 480);
  };

  // Loading state
  if (isLoading) {
    return (
      <div data-testid="dna-loading" className="flex flex-col items-center justify-center p-12 space-y-3 min-h-[360px]">
        <Loader2 className="w-8 h-8 text-[#d2434e] animate-spin" />
        <span className="text-sm font-medium text-white/70">Extracting Knowledge DNA from evidence...</span>
      </div>
    );
  }

  // Error state
  if (error && !data && !dnaResponse) {
    return (
      <div data-testid="dna-error" className="flex flex-col items-center justify-center p-8 space-y-3 text-center min-h-[320px]">
        <AlertCircle className="w-8 h-8 text-rose-500" />
        <span className="text-sm text-white/80">{error}</span>
        {documentName && (
          <button
            type="button"
            onClick={() => void loadDNA(documentName)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-[#a7d0d2] bg-white/5 hover:bg-white/10 rounded-lg cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Retry
          </button>
        )}
      </div>
    );
  }

  // Empty state
  if (!data && !dnaResponse && !documentName) {
    return (
      <div data-testid="dna-empty" className="flex flex-col items-center justify-center p-12 text-center text-white/50 space-y-2 min-h-[300px]">
        <Dna className="w-8 h-8 text-white/20" />
        <p className="text-sm">No research document or query selected for Knowledge DNA extraction.</p>
      </div>
    );
  }

  const stats = graphData.statistics || {};

  return (
    <div className="flex flex-col h-full w-full bg-[#070b0f] text-[#f3faf0] overflow-hidden rounded-xl border border-white/10">
      {/* Top Header Bar: Title, Stats summary, Tabs, Exports */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 bg-[#0d151e] border-b border-white/10">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-[#d2434e]/10 border border-[#d2434e]/30">
            <Dna className="w-5 h-5 text-[#d2434e]" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-white tracking-wide">
                KNOWLEDGE DNA EXPLORER
              </h2>
              {data?.partial && (
                <span className="px-2 py-0.5 text-[10px] font-medium bg-amber-500/10 text-amber-300 border border-amber-500/30 rounded-full">
                  Evidence Fallback
                </span>
              )}
            </div>
            <p className="text-xs text-[#f3faf0]/60 truncate max-w-md">
              {graphData.researchArea}
            </p>
          </div>
        </div>

        {/* View Switcher Tabs */}
        <div className="flex items-center gap-1 p-1 bg-[#070b0f] rounded-lg border border-white/5 text-xs">
          <button
            type="button"
            onClick={() => setActiveTab('graph')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-colors cursor-pointer ${
              activeTab === 'graph' ? 'bg-[#d2434e] text-white font-medium shadow-sm' : 'text-[#f3faf0]/70 hover:text-white'
            }`}
          >
            <Network className="w-3.5 h-3.5" />
            <span>Graph</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('profile')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-colors cursor-pointer ${
              activeTab === 'profile' ? 'bg-[#d2434e] text-white font-medium shadow-sm' : 'text-[#f3faf0]/70 hover:text-white'
            }`}
          >
            <BookOpen className="w-3.5 h-3.5" />
            <span>Profile</span>
          </button>
          <button
            type="button"
            data-testid="dna-tab-table"
            onClick={() => setActiveTab('table')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-colors cursor-pointer ${
              activeTab === 'table' ? 'bg-[#d2434e] text-white font-medium shadow-sm' : 'text-[#f3faf0]/70 hover:text-white'
            }`}
          >
            <TableIcon className="w-3.5 h-3.5" />
            <span>Table</span>
          </button>
          <button
            type="button"
            data-testid="dna-tab-strand"
            onClick={() => setActiveTab('strand')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-colors cursor-pointer ${
              activeTab === 'strand' ? 'bg-[#d2434e] text-white font-medium shadow-sm' : 'text-[#f3faf0]/70 hover:text-white'
            }`}
          >
            <Dna className="w-3.5 h-3.5" />
            <span>Strand</span>
          </button>
          <button
            type="button"
            data-testid="dna-tab-compare"
            onClick={() => setActiveTab('compare')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-colors cursor-pointer ${
              activeTab === 'compare' ? 'bg-[#d2434e] text-white font-medium shadow-sm' : 'text-[#f3faf0]/70 hover:text-white'
            }`}
          >
            <GitCompare className="w-3.5 h-3.5" />
            <span>Compare</span>
          </button>
        </div>

        {/* Export Buttons */}
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            data-testid="dna-export-json"
            onClick={handleExportJson}
            title="Export as JSON"
            className="flex items-center gap-1 px-2.5 py-1 text-xs bg-white/5 hover:bg-white/10 text-[#a7d0d2] hover:text-white rounded-md border border-white/5 transition-colors cursor-pointer"
          >
            <Download className="w-3.5 h-3.5" />
            <span>JSON</span>
          </button>
          <button
            type="button"
            data-testid="dna-export-svg"
            onClick={handleExportSvg}
            title="Export as SVG"
            className="flex items-center gap-1 px-2.5 py-1 text-xs bg-white/5 hover:bg-white/10 text-[#a7d0d2] hover:text-white rounded-md border border-white/5 transition-colors cursor-pointer"
          >
            <Download className="w-3.5 h-3.5" />
            <span>SVG</span>
          </button>
          <button
            type="button"
            data-testid="dna-export-png"
            onClick={handleExportPng}
            title="Export as PNG"
            className="flex items-center gap-1 px-2.5 py-1 text-xs bg-white/5 hover:bg-white/10 text-[#a7d0d2] hover:text-white rounded-md border border-white/5 transition-colors cursor-pointer"
          >
            <Download className="w-3.5 h-3.5" />
            <span>PNG</span>
          </button>
        </div>
      </div>

      {/* Statistics Quick-Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2 px-4 py-2 bg-[#0a1017] border-b border-white/5 text-xs">
        <div className="flex flex-col">
          <span className="text-[10px] text-[#f3faf0]/50 uppercase tracking-wider">Concepts</span>
          <span className="font-semibold text-emerald-400">{stats.total_concepts || graphData.nodes.length}</span>
        </div>
        <div className="flex flex-col">
          <span className="text-[10px] text-[#f3faf0]/50 uppercase tracking-wider">Methodologies</span>
          <span className="font-semibold text-cyan-400">{stats.unique_methodologies || (data?.methods || []).length}</span>
        </div>
        <div className="flex flex-col">
          <span className="text-[10px] text-[#f3faf0]/50 uppercase tracking-wider">Datasets</span>
          <span className="font-semibold text-amber-400">{stats.datasets || (data?.datasets || []).length}</span>
        </div>
        <div className="flex flex-col">
          <span className="text-[10px] text-[#f3faf0]/50 uppercase tracking-wider">Findings / Results</span>
          <span className="font-semibold text-lime-400">{stats.findings || (data?.results || data?.findings || []).length}</span>
        </div>
        <div className="flex flex-col">
          <span className="text-[10px] text-[#f3faf0]/50 uppercase tracking-wider">Relationships</span>
          <span className="font-semibold text-white">
            {stats.relationships || graphData.edges.length}{' '}
            <span className="text-[10px] text-[#f3faf0]/40 font-normal">
              ({stats.explicit_relationships || 0} exp / {stats.inferred_relationships || 0} inf)
            </span>
          </span>
        </div>
        <div className="flex flex-col">
          <span className="text-[10px] text-[#f3faf0]/50 uppercase tracking-wider">Papers Supported</span>
          <span className="font-semibold text-rose-400">{stats.supporting_documents || 1}</span>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex overflow-hidden relative min-h-[460px]">
        {/* ================================================================= */}
        {/* TAB 1: KNOWLEDGE GRAPH EXPLORER                                  */}
        {/* ================================================================= */}
        {activeTab === 'graph' && (
          <div className="flex-1 flex flex-col md:flex-row w-full h-full overflow-hidden">
            {/* Graph Canvas & Controls */}
            <div className="flex-1 flex flex-col relative h-full bg-[#070b0f] overflow-hidden">
              {/* Graph Toolbar: Search & Category Filter Pills */}
              <div className="flex flex-wrap items-center justify-between gap-2 p-3 bg-[#0d151e]/80 backdrop-blur-xs border-b border-white/5 z-10">
                <div className="flex items-center gap-2 flex-1 max-w-xs">
                  <div className="relative w-full">
                    <Search className="w-3.5 h-3.5 text-white/40 absolute left-2.5 top-1/2 -translate-y-1/2" />
                    <input
                      type="text"
                      placeholder="Search concepts, methods..."
                      value={graphSearch}
                      onChange={(e) => setGraphSearch(e.target.value)}
                      className="w-full pl-8 pr-3 py-1 text-xs bg-[#070b0f] border border-white/10 rounded-md text-white placeholder-white/40 focus:outline-hidden focus:border-[#d2434e]"
                    />
                    {graphSearch && (
                      <button
                        type="button"
                        onClick={() => setGraphSearch('')}
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-white/40 hover:text-white"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                </div>

                {/* Filter Pills */}
                <div className="flex items-center gap-1 overflow-x-auto text-[11px] py-0.5">
                  {['ALL', 'CONCEPT', 'METHODOLOGY', 'DATASET', 'METRIC', 'RESULT', 'LIMITATION'].map((cat) => (
                    <button
                      key={cat}
                      type="button"
                      onClick={() => setCategoryFilter(cat)}
                      className={`px-2.5 py-1 rounded-full transition-colors cursor-pointer whitespace-nowrap ${
                        categoryFilter === cat
                          ? 'bg-[#a7d0d2]/20 text-[#a7d0d2] border border-[#a7d0d2]/40 font-medium'
                          : 'bg-white/5 text-white/60 hover:text-white border border-white/5'
                      }`}
                    >
                      {cat}
                    </button>
                  ))}
                </div>

                {/* Zoom & Screen Controls */}
                <div className="flex items-center gap-1 bg-[#070b0f] p-0.5 rounded-lg border border-white/10">
                  <button
                    type="button"
                    onClick={handleZoomIn}
                    title="Zoom in"
                    className="p-1 text-white/60 hover:text-white rounded cursor-pointer"
                  >
                    <ZoomIn className="w-3.5 h-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={handleZoomOut}
                    title="Zoom out"
                    className="p-1 text-white/60 hover:text-white rounded cursor-pointer"
                  >
                    <ZoomOut className="w-3.5 h-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={handleFitToScreen}
                    title="Fit to screen"
                    className="p-1 text-white/60 hover:text-white rounded cursor-pointer"
                  >
                    <Maximize2 className="w-3.5 h-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={handleResetZoom}
                    title="Reset view"
                    className="p-1 text-white/60 hover:text-white rounded cursor-pointer text-[10px] font-mono px-1.5"
                  >
                    {Math.round(zoom * 100)}%
                  </button>
                </div>
              </div>

              {/* Interactive SVG Graph Canvas */}
              <div
                className="flex-1 w-full h-full cursor-grab active:cursor-grabbing overflow-hidden select-none"
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseUp}
              >
                <svg
                  ref={svgRef}
                  width="100%"
                  height="100%"
                  className="w-full h-full"
                  viewBox="0 0 800 560"
                >
                  <defs>
                    <marker
                      id="arrow-explicit"
                      viewBox="0 0 10 10"
                      refX="18"
                      refY="5"
                      markerWidth="6"
                      markerHeight="6"
                      orient="auto-start-reverse"
                    >
                      <path d="M 0 0 L 10 5 L 0 10 z" fill="#4d728e" />
                    </marker>
                    <marker
                      id="arrow-inferred"
                      viewBox="0 0 10 10"
                      refX="18"
                      refY="5"
                      markerWidth="6"
                      markerHeight="6"
                      orient="auto-start-reverse"
                    >
                      <path d="M 0 0 L 10 5 L 0 10 z" fill="#f59e0b" />
                    </marker>
                  </defs>

                  <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
                    {/* Relationship Edges */}
                    {visibleEdges.map((edge, idx) => {
                      const posA = nodePositions.get(edge.source);
                      const posB = nodePositions.get(edge.target);
                      if (!posA || !posB) return null;

                      const isSelected = selectedNode && (selectedNode.id === edge.source || selectedNode.id === edge.target);

                      return (
                        <g key={`edge_${idx}`} className="transition-opacity">
                          <line
                            x1={posA.x}
                            y1={posA.y}
                            x2={posB.x}
                            y2={posB.y}
                            stroke={edge.is_inferred ? '#f59e0b' : '#4d728e'}
                            strokeWidth={isSelected ? 2.5 : 1.5}
                            strokeDasharray={edge.is_inferred ? '4 3' : 'none'}
                            strokeOpacity={isSelected ? 0.9 : 0.6}
                            markerEnd={edge.is_inferred ? 'url(#arrow-inferred)' : 'url(#arrow-explicit)'}
                          />
                          {/* Edge label at midpoint */}
                          <text
                            x={(posA.x + posB.x) / 2}
                            y={(posA.y + posB.y) / 2 - 4}
                            fill={edge.is_inferred ? '#f59e0b' : '#a7d0d2'}
                            fontSize="9"
                            fontFamily="sans-serif"
                            textAnchor="middle"
                            className="pointer-events-none select-none opacity-80"
                          >
                            {edge.relationship}
                          </text>
                        </g>
                      );
                    })}

                    {/* Nodes */}
                    {visibleNodes.map((node) => {
                      const pos = nodePositions.get(node.id);
                      if (!pos) return null;

                      const isSelected = selectedNode?.id === node.id;
                      const colors = getCategoryColor(node.category);
                      const isRoot = node.id.includes('root') || node.id === 'concept_central';
                      const boxWidth = Math.max(120, Math.min(220, node.label.length * 7.5 + 24));
                      const boxHeight = isRoot ? 40 : 34;

                      return (
                        <g
                          key={node.id}
                          transform={`translate(${pos.x - boxWidth / 2}, ${pos.y - boxHeight / 2})`}
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedNodeId(node.id);
                          }}
                          className="cursor-pointer group"
                        >
                          <rect
                            width={boxWidth}
                            height={boxHeight}
                            rx={isRoot ? 8 : 6}
                            fill={isSelected ? '#141d26' : '#0b1219'}
                            stroke={isSelected ? '#d2434e' : colors.fill}
                            strokeWidth={isSelected ? 2.5 : 1.5}
                            className="transition-all group-hover:stroke-white shadow-md"
                          />
                          {/* Category indicator dot */}
                          <circle cx="12" cy={boxHeight / 2} r="4" fill={colors.fill} />
                          {/* Node label */}
                          <text
                            x="22"
                            y={boxHeight / 2 + 3.5}
                            fill={isSelected ? '#ffffff' : '#f3faf0'}
                            fontSize={isRoot ? '11' : '10'}
                            fontWeight={isRoot ? '700' : '500'}
                            fontFamily="sans-serif"
                            className="pointer-events-none select-none"
                          >
                            {node.label.length > 24 ? `${node.label.slice(0, 22)}...` : node.label}
                          </text>
                        </g>
                      );
                    })}
                  </g>
                </svg>

                {/* Floating Canvas Legend */}
                <div className="absolute bottom-3 left-3 flex flex-wrap items-center gap-2 p-2 bg-[#0d151e]/90 backdrop-blur-xs rounded-lg border border-white/10 text-[10px] text-white/60 pointer-events-none">
                  <div className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-emerald-400" />
                    <span>Concept</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-cyan-400" />
                    <span>Method</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-amber-400" />
                    <span>Dataset</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-purple-400" />
                    <span>Metric</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-lime-400" />
                    <span>Result</span>
                  </div>
                  <div className="flex items-center gap-1 ml-2 border-l border-white/10 pl-2">
                    <span className="w-3 h-0.5 bg-[#4d728e]" />
                    <span>Explicit</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <span className="w-3 h-0.5 border-b border-dashed border-[#f59e0b]" />
                    <span>Inferred</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Concept Inspector Panel */}
            <div
              data-testid="concept-inspector-panel"
              className="w-full md:w-80 lg:w-96 bg-[#0a1017] border-t md:border-t-0 md:border-l border-white/10 flex flex-col h-full overflow-y-auto p-4 space-y-4"
            >
              {selectedNode ? (
                <>
                  <div className="flex items-start justify-between gap-2 pb-2 border-b border-white/10">
                    <div>
                      <div className="flex items-center gap-2">
                        <span
                          className={`px-2 py-0.5 text-[10px] font-semibold rounded-full border ${
                            getCategoryColor(selectedNode.category).bg
                          } ${getCategoryColor(selectedNode.category).border} ${
                            getCategoryColor(selectedNode.category).text
                          }`}
                        >
                          {selectedNode.category}
                        </span>
                        {selectedNode.is_inferred && (
                          <span className="px-2 py-0.5 text-[10px] font-medium bg-amber-500/10 text-amber-300 border border-amber-500/30 rounded-full">
                            Inferred
                          </span>
                        )}
                      </div>
                      <h3 className="text-sm font-bold text-white mt-1.5 leading-snug">
                        {selectedNode.label}
                      </h3>
                    </div>
                  </div>

                  {/* Quantitative Value Highlight */}
                  {selectedNode.quantitative_value && (
                    <div className="p-2.5 rounded-lg bg-lime-500/10 border border-lime-500/30">
                      <span className="text-[10px] text-lime-400 uppercase font-semibold tracking-wider">
                        Quantitative Measurement
                      </span>
                      <p className="text-xs font-mono font-bold text-lime-200 mt-0.5">
                        {selectedNode.quantitative_value}
                      </p>
                    </div>
                  )}

                  {/* Explanation */}
                  <div>
                    <h4 className="text-xs font-semibold text-[#a7d0d2] mb-1">Explanation</h4>
                    <p className="text-xs text-white/80 leading-relaxed bg-[#070b0f] p-2.5 rounded-lg border border-white/5">
                      {selectedNode.explanation || selectedNode.label}
                    </p>
                  </div>

                  {/* Connected Relationships */}
                  <div>
                    <h4 className="text-xs font-semibold text-[#a7d0d2] mb-1 flex items-center justify-between">
                      <span>Connected Relationships</span>
                      <span className="text-[10px] text-white/40">({selectedNodeRelationships.length})</span>
                    </h4>
                    {selectedNodeRelationships.length > 0 ? (
                      <div className="space-y-1.5 max-h-40 overflow-y-auto pr-1">
                        {selectedNodeRelationships.map((rel, idx) => {
                          const isSource = rel.source === selectedNode.id;
                          const otherId = isSource ? rel.target : rel.source;
                          const otherNode = graphData.nodes.find((n) => n.id === otherId);

                          return (
                            <button
                              key={`rel_${idx}`}
                              type="button"
                              onClick={() => setSelectedNodeId(otherId)}
                              className="w-full text-left p-2 rounded-lg bg-[#070b0f] hover:bg-[#141d26] border border-white/5 hover:border-white/10 transition-colors flex items-center justify-between group cursor-pointer"
                            >
                              <div className="text-[11px] truncate flex-1">
                                <span className="text-[#f59e0b] font-medium">{rel.relationship}</span>{' '}
                                <span className="text-white font-semibold">
                                  {otherNode?.label || otherId}
                                </span>
                              </div>
                              <ExternalLink className="w-3 h-3 text-white/30 group-hover:text-white" />
                            </button>
                          );
                        })}
                      </div>
                    ) : (
                      <p className="text-xs text-white/40 italic">No connected relationships.</p>
                    )}
                  </div>

                  {/* Supporting Papers */}
                  <div>
                    <h4 className="text-xs font-semibold text-[#a7d0d2] mb-1">Supporting Papers</h4>
                    <div className="flex flex-wrap gap-1.5">
                      {(selectedNode.supporting_papers || [selectedNode.document || 'Research Paper']).map(
                        (paper, idx) => (
                          <span
                            key={`paper_${idx}`}
                            className="px-2 py-0.5 text-[11px] bg-white/5 text-white/80 border border-white/10 rounded-md font-mono"
                          >
                            {paper}
                          </span>
                        )
                      )}
                    </div>
                  </div>

                  {/* Evidence Passages & Citations */}
                  <div>
                    <h4 className="text-xs font-semibold text-[#a7d0d2] mb-1">Evidence Passages</h4>
                    <div className="space-y-2">
                      {(selectedNode.citations && selectedNode.citations.length > 0
                        ? selectedNode.citations
                        : (selectedNode.evidence || []).map((ev) => ({
                            passage: ev,
                            document: selectedNode.document,
                            page: selectedNode.page,
                            chunk_id: selectedNode.chunk_id,
                          }))
                      ).map((cit, idx) => (
                        <div
                          key={`cit_${idx}`}
                          className="p-2.5 rounded-lg bg-[#070b0f] border border-white/5 space-y-1.5"
                        >
                          <p className="text-xs text-white/80 italic leading-relaxed">
                            "{cit.passage || selectedNode.evidence?.[idx] || selectedNode.explanation}"
                          </p>
                          <div className="flex items-center justify-between text-[10px] text-white/40 pt-1 border-t border-white/5 font-mono">
                            <span>{cit.document || selectedNode.document || 'Source Document'}</span>
                            {cit.page && <span>Page {cit.page}</span>}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </>
              ) : (
                <div className="flex flex-col items-center justify-center h-full text-center text-white/40 p-4">
                  <Network className="w-8 h-8 mb-2 opacity-30" />
                  <p className="text-xs">Click any node on the graph to inspect its details and citations.</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ================================================================= */}
        {/* TAB 2: KNOWLEDGE PROFILE (10 CORE RESEARCH DIMENSIONS)           */}
        {/* ================================================================= */}
        {activeTab === 'profile' && (
          <div className="flex-1 w-full h-full overflow-y-auto p-4 md:p-6 space-y-4">
            <div className="max-w-4xl mx-auto space-y-4">
              {/* Conflicting Findings Banner (Multi-Document Intelligence) */}
              {data?.conflicting_findings && data.conflicting_findings.length > 0 && (
                <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/40 space-y-2">
                  <div className="flex items-center gap-2 text-amber-300 font-semibold text-xs">
                    <AlertCircle className="w-4 h-4 text-amber-400" />
                    <span>Conflicting Findings Across Papers</span>
                  </div>
                  <div className="space-y-2">
                    {data.conflicting_findings.map((c, idx) => (
                      <div key={idx} className="p-3 rounded-lg bg-[#070b0f] border border-amber-500/20 text-xs space-y-1">
                        <div className="font-bold text-white">{c.topic}</div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-[11px] pt-1">
                          <div className="p-2 rounded bg-white/5">
                            <span className="font-mono text-cyan-400">{c.paper_a}:</span> {c.finding_a}
                          </div>
                          <div className="p-2 rounded bg-white/5">
                            <span className="font-mono text-rose-400">{c.paper_b}:</span> {c.finding_b}
                          </div>
                        </div>
                        <p className="text-[11px] text-white/60 italic pt-1">{c.explanation}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 10 Structured Dimensions */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* 1. Research Objectives */}
                <div className="p-4 rounded-xl bg-[#0d151e] border border-white/10 space-y-2">
                  <div className="flex items-center gap-2 text-rose-400 font-semibold text-xs">
                    <span className="w-2 h-2 rounded-full bg-rose-500" />
                    <span>Research Objectives</span>
                  </div>
                  <ul className="space-y-1.5 text-xs text-white/80">
                    {(data?.objectives && data.objectives.length > 0
                      ? data.objectives
                      : data?.coreTopics || ['Not found in available sources.']
                    ).map((obj, i) => (
                      <li key={i} className="flex items-start gap-1.5">
                        <ArrowRight className="w-3.5 h-3.5 text-rose-400 shrink-0 mt-0.5" />
                        <span>{obj}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* 2. Core Concepts */}
                <div className="p-4 rounded-xl bg-[#0d151e] border border-white/10 space-y-2">
                  <div className="flex items-center gap-2 text-emerald-400 font-semibold text-xs">
                    <span className="w-2 h-2 rounded-full bg-emerald-500" />
                    <span>Core Concepts</span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {(data?.core_concepts && data.core_concepts.length > 0
                      ? data.core_concepts
                      : data?.keyConcepts || ['Not found in available sources.']
                    ).map((c, i) => (
                      <span key={i} className="px-2.5 py-1 text-xs bg-emerald-500/10 text-emerald-300 border border-emerald-500/30 rounded-md">
                        {c}
                      </span>
                    ))}
                  </div>
                </div>

                {/* 3. Methodologies */}
                <div className="p-4 rounded-xl bg-[#0d151e] border border-white/10 space-y-2">
                  <div className="flex items-center gap-2 text-cyan-400 font-semibold text-xs">
                    <span className="w-2 h-2 rounded-full bg-cyan-500" />
                    <span>Methodologies & Algorithms</span>
                  </div>
                  <ul className="space-y-1.5 text-xs text-white/80">
                    {(data?.methodologies && data.methodologies.length > 0
                      ? data.methodologies
                      : data?.methods || ['Not found in available sources.']
                    ).map((m, i) => (
                      <li key={i} className="flex items-start gap-1.5">
                        <ArrowRight className="w-3.5 h-3.5 text-cyan-400 shrink-0 mt-0.5" />
                        <span>{m}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* 4. Datasets */}
                <div className="p-4 rounded-xl bg-[#0d151e] border border-white/10 space-y-2">
                  <div className="flex items-center gap-2 text-amber-400 font-semibold text-xs">
                    <span className="w-2 h-2 rounded-full bg-amber-500" />
                    <span>Experimental Datasets & Materials</span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {(data?.datasets && data.datasets.length > 0
                      ? data.datasets
                      : ['Not found in available sources.']
                    ).map((d, i) => (
                      <span key={i} className="px-2.5 py-1 text-xs bg-amber-500/10 text-amber-300 border border-amber-500/30 rounded-md font-mono">
                        {d}
                      </span>
                    ))}
                  </div>
                </div>

                {/* 5. Evaluation Metrics */}
                <div className="p-4 rounded-xl bg-[#0d151e] border border-white/10 space-y-2">
                  <div className="flex items-center gap-2 text-purple-400 font-semibold text-xs">
                    <span className="w-2 h-2 rounded-full bg-purple-500" />
                    <span>Evaluation Metrics</span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {(data?.metrics && data.metrics.length > 0
                      ? data.metrics
                      : ['Not found in available sources.']
                    ).map((m, i) => (
                      <span key={i} className="px-2.5 py-1 text-xs bg-purple-500/10 text-purple-300 border border-purple-500/30 rounded-md">
                        {m}
                      </span>
                    ))}
                  </div>
                </div>

                {/* 6. Experimental Results */}
                <div className="p-4 rounded-xl bg-[#0d151e] border border-white/10 space-y-2">
                  <div className="flex items-center gap-2 text-lime-400 font-semibold text-xs">
                    <span className="w-2 h-2 rounded-full bg-lime-500" />
                    <span>Experimental Results & Findings</span>
                  </div>
                  <ul className="space-y-1.5 text-xs text-white/80">
                    {(data?.results && data.results.length > 0
                      ? data.results
                      : data?.findings || ['Not found in available sources.']
                    ).map((r, i) => (
                      <li key={i} className="flex items-start gap-1.5">
                        <ArrowRight className="w-3.5 h-3.5 text-lime-400 shrink-0 mt-0.5" />
                        <span>{r}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* 7. Key Contributions */}
                <div className="p-4 rounded-xl bg-[#0d151e] border border-white/10 space-y-2">
                  <div className="flex items-center gap-2 text-violet-400 font-semibold text-xs">
                    <span className="w-2 h-2 rounded-full bg-violet-500" />
                    <span>Key Contributions</span>
                  </div>
                  <ul className="space-y-1.5 text-xs text-white/80">
                    {(data?.contributions && data.contributions.length > 0
                      ? data.contributions
                      : ['Not found in available sources.']
                    ).map((c, i) => (
                      <li key={i} className="flex items-start gap-1.5">
                        <ArrowRight className="w-3.5 h-3.5 text-violet-400 shrink-0 mt-0.5" />
                        <span>{c}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* 8. Advantages */}
                <div className="p-4 rounded-xl bg-[#0d151e] border border-white/10 space-y-2">
                  <div className="flex items-center gap-2 text-teal-400 font-semibold text-xs">
                    <span className="w-2 h-2 rounded-full bg-teal-500" />
                    <span>Advantages & Benefits</span>
                  </div>
                  <ul className="space-y-1.5 text-xs text-white/80">
                    {(data?.advantages && data.advantages.length > 0
                      ? data.advantages
                      : ['Not found in available sources.']
                    ).map((a, i) => (
                      <li key={i} className="flex items-start gap-1.5">
                        <ArrowRight className="w-3.5 h-3.5 text-teal-400 shrink-0 mt-0.5" />
                        <span>{a}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* 9. Limitations */}
                <div className="p-4 rounded-xl bg-[#0d151e] border border-white/10 space-y-2">
                  <div className="flex items-center gap-2 text-orange-400 font-semibold text-xs">
                    <span className="w-2 h-2 rounded-full bg-orange-500" />
                    <span>Limitations & Constraints</span>
                  </div>
                  <ul className="space-y-1.5 text-xs text-white/80">
                    {(data?.limitations && data.limitations.length > 0
                      ? data.limitations
                      : ['Not found in available sources.']
                    ).map((l, i) => (
                      <li key={i} className="flex items-start gap-1.5">
                        <ArrowRight className="w-3.5 h-3.5 text-orange-400 shrink-0 mt-0.5" />
                        <span>{l}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* 10. Future Directions */}
                <div className="p-4 rounded-xl bg-[#0d151e] border border-white/10 space-y-2">
                  <div className="flex items-center gap-2 text-sky-400 font-semibold text-xs">
                    <span className="w-2 h-2 rounded-full bg-sky-500" />
                    <span>Future Directions & Opportunities</span>
                  </div>
                  <ul className="space-y-1.5 text-xs text-white/80">
                    {(data?.future_directions && data.future_directions.length > 0
                      ? data.future_directions
                      : ['Not found in available sources.']
                    ).map((f, i) => (
                      <li key={i} className="flex items-start gap-1.5">
                        <ArrowRight className="w-3.5 h-3.5 text-sky-400 shrink-0 mt-0.5" />
                        <span>{f}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ================================================================= */}
        {/* TAB 3: FACET TABLE VIEW (LEGACY COMPAT & DETAILED DATA)           */}
        {/* ================================================================= */}
        {activeTab === 'table' && (
          <div data-testid="dna-table-view" className="flex-1 w-full h-full overflow-y-auto p-4 md:p-6 space-y-4">
            {normalizedDNA ? (
              <div className="max-w-4xl mx-auto space-y-4">
                {/* Badges row for novelty and difficulty */}
                <div className="flex items-center gap-3">
                  <span
                    data-testid="dna-difficulty-badge"
                    className="px-3 py-1 text-xs font-semibold rounded-full bg-cyan-500/10 text-cyan-300 border border-cyan-500/30"
                  >
                    Difficulty: {normalizedDNA.difficulty}
                  </span>
                  <span
                    data-testid="dna-novelty-badge"
                    className="px-3 py-1 text-xs font-semibold rounded-full bg-purple-500/10 text-purple-300 border border-purple-500/30"
                  >
                    Novelty: {normalizedDNA.novelty}
                  </span>
                </div>

                {/* Filter and search bar */}
                <div className="flex flex-wrap items-center justify-between gap-3 p-3 bg-[#0d151e] rounded-xl border border-white/10">
                  <div className="flex items-center gap-1">
                    {(['all', 'concepts', 'entities', 'methods', 'claims'] as const).map((cat) => (
                      <button
                        key={cat}
                        type="button"
                        className={`dna-filter-${cat} px-3 py-1 text-xs rounded-md capitalize cursor-pointer transition-colors ${
                          tableFilter === cat ? 'bg-[#d2434e] text-white font-medium' : 'text-white/60 hover:text-white'
                        }`}
                        onClick={() => setTableFilter(cat)}
                      >
                        {cat}
                      </button>
                    ))}
                  </div>

                  <input
                    type="text"
                    className="dna-table-search px-3 py-1 text-xs bg-[#070b0f] border border-white/10 rounded-md text-white placeholder-white/40 focus:outline-hidden"
                    placeholder="Search table..."
                    value={tableSearch}
                    onChange={(e) => setTableSearch(e.target.value)}
                  />
                </div>

                {/* Table */}
                <div className="overflow-x-auto rounded-xl border border-white/10">
                  <table data-testid="dna-table" className="w-full text-left text-xs text-white/80">
                    <thead className="bg-[#0d151e] text-[#a7d0d2] uppercase border-b border-white/10">
                      <tr>
                        <th className="px-4 py-3">Facet Type</th>
                        <th className="px-4 py-3">Item / Value</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5 bg-[#070b0f]">
                      {(tableFilter === 'all' || tableFilter === 'concepts') &&
                        normalizedDNA.concepts.map((c, i) => (
                          <tr key={`c_${i}`} data-testid="dna-row-concept">
                            <td className="px-4 py-2.5 font-semibold text-emerald-400">Concept</td>
                            <td className="px-4 py-2.5">{c}</td>
                          </tr>
                        ))}
                      {(tableFilter === 'all' || tableFilter === 'entities') &&
                        normalizedDNA.entities.map((e, i) => (
                          <tr key={`e_${i}`} data-testid="dna-row-entity">
                            <td className="px-4 py-2.5 font-semibold text-cyan-400">Entity ({e.type})</td>
                            <td className="px-4 py-2.5">{e.name}</td>
                          </tr>
                        ))}
                      {(tableFilter === 'all' || tableFilter === 'methods') &&
                        normalizedDNA.methods.map((m, i) => (
                          <tr key={`m_${i}`} data-testid="dna-row-method">
                            <td className="px-4 py-2.5 font-semibold text-amber-400">Method</td>
                            <td className="px-4 py-2.5">{m}</td>
                          </tr>
                        ))}
                      {(tableFilter === 'all' || tableFilter === 'claims') &&
                        normalizedDNA.claims.map((cl, i) => (
                          <tr key={`cl_${i}`} data-testid="dna-row-claim">
                            <td className="px-4 py-2.5 font-semibold text-purple-400">Claim</td>
                            <td className="px-4 py-2.5">{cl}</td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <p className="text-xs text-white/50 text-center py-8">No table data available.</p>
            )}
          </div>
        )}

        {/* ================================================================= */}
        {/* TAB 4: STRAND HELIX VIEW                                         */}
        {/* ================================================================= */}
        {activeTab === 'strand' && (
          <div data-testid="dna-strand-view" className="flex-1 w-full h-full overflow-y-auto p-4 md:p-6 space-y-4">
            <div className="max-w-2xl mx-auto space-y-4">
              <p className="text-xs text-white/60 text-center">
                Interactive double-helix rung representation connecting complementary research facets.
              </p>
              <div className="space-y-2">
                {strandPairs.map((pair, idx) => (
                  <div
                    key={pair.id}
                    onClick={() => setSelectedPairIndex(idx)}
                    className={`flex items-center justify-between p-3 rounded-xl border transition-all cursor-pointer ${
                      selectedPairIndex === idx
                        ? 'bg-[#141d26] border-[#d2434e]'
                        : 'bg-[#0d151e] border-white/5 hover:border-white/20'
                    }`}
                  >
                    <div className="flex items-center gap-2 flex-1">
                      <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: pair.colorLeft }} />
                      <span className="text-xs font-medium text-white">{pair.leftLabel}</span>
                    </div>

                    <div className="w-16 h-0.5 bg-white/20 relative mx-3">
                      <div className="w-2 h-2 rounded-full bg-white/60 absolute left-1/2 -top-[3px] -translate-x-1/2" />
                    </div>

                    <div className="flex items-center justify-end gap-2 flex-1 text-right">
                      <span className="text-xs font-medium text-white">{pair.rightLabel}</span>
                      <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: pair.colorRight }} />
                    </div>
                  </div>
                ))}
              </div>

              {selectedPairIndex !== null && strandPairs[selectedPairIndex] && (
                <div data-testid="strand-selected-detail" className="p-4 rounded-xl bg-[#0d151e] border border-white/10 text-xs space-y-2">
                  <h4 className="font-bold text-[#a7d0d2]">Selected Base Pair Facet</h4>
                  <p className="text-white/80">
                    Left: <strong className="text-white">{strandPairs[selectedPairIndex].leftLabel}</strong> ({strandPairs[selectedPairIndex].leftType})
                  </p>
                  <p className="text-white/80">
                    Right: <strong className="text-white">{strandPairs[selectedPairIndex].rightLabel}</strong> ({strandPairs[selectedPairIndex].rightType})
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ================================================================= */}
        {/* TAB 5: COMPARE VIEW                                              */}
        {/* ================================================================= */}
        {activeTab === 'compare' && (
          <div data-testid="dna-compare-view" className="flex-1 w-full h-full overflow-y-auto p-4 md:p-6 space-y-4">
            <div className="max-w-4xl mx-auto space-y-4">
              {/* Selectors and run button */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 p-4 bg-[#0d151e] rounded-xl border border-white/10 items-end">
                <div>
                  <label className="block text-[11px] text-[#a7d0d2] mb-1 font-semibold uppercase">Document A</label>
                  <select
                    data-testid="compare-doc-a-select"
                    className="w-full px-3 py-1.5 text-xs bg-[#070b0f] border border-white/10 rounded-md text-white"
                    value={docA}
                    onChange={(e) => setDocA(e.target.value)}
                  >
                    {availableDocs.map((d) => (
                      <option key={d} value={d}>
                        {d}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-[11px] text-[#a7d0d2] mb-1 font-semibold uppercase">Document B</label>
                  <select
                    data-testid="compare-doc-b-select"
                    className="w-full px-3 py-1.5 text-xs bg-[#070b0f] border border-white/10 rounded-md text-white"
                    value={docB}
                    onChange={(e) => setDocB(e.target.value)}
                  >
                    {availableDocs.map((d) => (
                      <option key={d} value={d}>
                        {d}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <button
                    type="button"
                    data-testid="compare-run-btn"
                    onClick={handleCompare}
                    disabled={isComparing || !docA || !docB}
                    className="w-full py-2 px-4 rounded-md bg-[#d2434e] hover:bg-[#b0303a] text-white font-medium text-xs flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
                  >
                    {isComparing ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <GitCompare className="w-4 h-4" />
                    )}
                    <span>Compare Documents</span>
                  </button>
                </div>
              </div>

              {compareError && (
                <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-lg text-rose-300 text-xs">
                  {compareError}
                </div>
              )}

              {/* Compare Results Container */}
              {compareResult && (
                <div data-testid="compare-results-container" className="space-y-4">
                  {/* Metrics Row */}
                  <div data-testid="compare-metrics-row" className="grid grid-cols-2 gap-4">
                    <div className="p-3 bg-[#0d151e] rounded-xl border border-white/10 space-y-1">
                      <span className="text-[10px] text-white/50 uppercase">Difficulty Comparison</span>
                      <div className="text-xs text-white">
                        <div>A: <strong className="text-cyan-400">{compareResult.difficulty_comparison?.document_a || 'N/A'}</strong></div>
                        <div>B: <strong className="text-cyan-400">{compareResult.difficulty_comparison?.document_b || 'N/A'}</strong></div>
                      </div>
                    </div>
                    <div className="p-3 bg-[#0d151e] rounded-xl border border-white/10 space-y-1">
                      <span className="text-[10px] text-white/50 uppercase">Novelty Comparison</span>
                      <div className="text-xs text-white">
                        <div>A: <strong className="text-purple-400">{compareResult.novelty_comparison?.document_a || 'N/A'}</strong></div>
                        <div>B: <strong className="text-purple-400">{compareResult.novelty_comparison?.document_b || 'N/A'}</strong></div>
                      </div>
                    </div>
                  </div>

                  {/* Shared Concepts */}
                  <div data-testid="compare-shared-concepts" className="p-4 bg-[#0d151e] rounded-xl border border-white/10 space-y-2">
                    <h4 className="text-xs font-bold text-emerald-400">Shared Concepts</h4>
                    <div className="flex flex-wrap gap-1.5">
                      {(compareResult.shared_concepts || []).map((c, i) => (
                        <span key={i} className="px-2.5 py-1 text-xs bg-emerald-500/10 text-emerald-300 border border-emerald-500/30 rounded-md">
                          {c}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Distinct Concepts */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div data-testid="compare-distinct-a" className="p-4 bg-[#0d151e] rounded-xl border border-white/10 space-y-2">
                      <h4 className="text-xs font-bold text-cyan-400">Distinct Concepts ({docA})</h4>
                      <ul className="text-xs text-white/80 space-y-1">
                        {(compareResult.distinct_concepts_a || []).map((c, i) => (
                          <li key={i}>• {c}</li>
                        ))}
                      </ul>
                    </div>
                    <div data-testid="compare-distinct-b" className="p-4 bg-[#0d151e] rounded-xl border border-white/10 space-y-2">
                      <h4 className="text-xs font-bold text-rose-400">Distinct Concepts ({docB})</h4>
                      <ul className="text-xs text-white/80 space-y-1">
                        {(compareResult.distinct_concepts_b || []).map((c, i) => (
                          <li key={i}>• {c}</li>
                        ))}
                      </ul>
                    </div>
                  </div>

                  {/* Shared Methods */}
                  <div data-testid="compare-shared-methods" className="p-4 bg-[#0d151e] rounded-xl border border-white/10 space-y-2">
                    <h4 className="text-xs font-bold text-cyan-400">Shared Methodologies</h4>
                    <div className="flex flex-wrap gap-1.5">
                      {(compareResult.shared_methods || []).map((m, i) => (
                        <span key={i} className="px-2.5 py-1 text-xs bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 rounded-md">
                          {m}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Claims A & B */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div data-testid="compare-claims-a" className="p-4 bg-[#0d151e] rounded-xl border border-white/10 space-y-2">
                      <h4 className="text-xs font-bold text-purple-400">Claims ({docA})</h4>
                      <ul className="text-xs text-white/80 space-y-1.5">
                        {(compareResult.claims_a || []).map((cl, i) => (
                          <li key={i}>• {cl}</li>
                        ))}
                      </ul>
                    </div>
                    <div data-testid="compare-claims-b" className="p-4 bg-[#0d151e] rounded-xl border border-white/10 space-y-2">
                      <h4 className="text-xs font-bold text-purple-400">Claims ({docB})</h4>
                      <ul className="text-xs text-white/80 space-y-1.5">
                        {(compareResult.claims_b || []).map((cl, i) => (
                          <li key={i}>• {cl}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
