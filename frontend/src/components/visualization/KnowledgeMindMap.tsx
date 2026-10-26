import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import {
  Network,
  Download,
  Search,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  FileText,
  Bookmark,
  AlertCircle,
  Loader2,
  X,
  FileCode,
} from 'lucide-react';
import type { MindMapNode } from '../../types/knowledge';
import {
  fetchConceptGraph,
  type BackendConceptGraphNode,
  type BackendConceptGraphResponse,
  type BackendConceptSource,
} from '../../lib/api';
import {
  downloadSvgFile,
  downloadSvgAsPngFile,
  downloadJsonFile,
  downloadMarkdownFile,
} from '../../lib/exportUtils';

export interface MindMapDisplayNode {
  id: string;
  label: string;
  cluster: string;
  // Measured: chunks containing the label. null when not measured.
  mentionCount: number | null;
  origin?: string;
  sources: BackendConceptSource[];
  children?: MindMapDisplayNode[];
  isExpanded?: boolean;
}

export interface KnowledgeMindMapProps {
  root?: MindMapNode;
  documentName?: string;
  initialGraph?: BackendConceptGraphResponse;
  onSelectNode?: (node: MindMapDisplayNode) => void;
}

// Convert legacy MindMapNode or raw concept graph to hierarchical display tree
function convertToDisplayTree(
  root?: MindMapNode,
  graph?: BackendConceptGraphResponse | null,
): MindMapDisplayNode | null {
  if (graph && graph.nodes && graph.nodes.length > 0) {
    // Group nodes by cluster
    const clusterMap = new Map<string, BackendConceptGraphNode[]>();
    graph.nodes.forEach((node) => {
      const cluster = node.cluster || 'General Concepts';
      if (!clusterMap.has(cluster)) {
        clusterMap.set(cluster, []);
      }
      clusterMap.get(cluster)!.push(node);
    });

    const clusterChildren: MindMapDisplayNode[] = [];
    clusterMap.forEach((nodes, cluster) => {
      clusterChildren.push({
        id: `cluster-${cluster.replace(/\s+/g, '-').toLowerCase()}`,
        label: cluster,
        cluster: cluster,
        mentionCount: null,
        sources: [],
        children: nodes.map((n) => ({
          id: n.id,
          label: n.label,
          cluster: n.cluster,
          mentionCount: typeof n.mention_count === 'number' ? n.mention_count : null,
          origin: n.origin,
          sources: n.sources || [],
          children: [],
        })),
      });
    });

    return {
      id: 'root-concept-graph',
      label: graph.document || 'Document Knowledge Graph',
      cluster: 'Root',
      mentionCount: null,
      sources: [],
      children: clusterChildren,
    };
  }

  if (root) {
    function mapNode(node: MindMapNode): MindMapDisplayNode {
      return {
        id: node.id || `node-${Math.random().toString(36).substring(7)}`,
        label: node.label,
        cluster: 'Concepts',
        mentionCount: null,
        sources: node.description
          ? [
              {
                document: 'Mind map description (no source page)',
                page: null,
                chunk_id: '',
                passage: node.description,
              },
            ]
          : [],
        children: (node.children || []).map(mapNode),
      };
    }
    return mapNode(root);
  }

  return null;
}

export const KnowledgeMindMap: React.FC<KnowledgeMindMapProps> = ({
  root,
  documentName,
  initialGraph,
  onSelectNode,
}) => {
  const [graphData, setGraphData] = useState<BackendConceptGraphResponse | null>(initialGraph || null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Interaction states
  const [searchQuery, setSearchQuery] = useState('');
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStartRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const [collapsedIds, setCollapsedIds] = useState<Set<string>>(new Set());
  const [selectedNode, setSelectedNode] = useState<MindMapDisplayNode | null>(null);
  const [isExporting, setIsExporting] = useState<'svg' | 'png' | 'json' | 'markdown' | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  // Fetch concept graph if documentName provided and no direct graph/root
  const loadGraph = useCallback(async (docName: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchConceptGraph(docName);
      setGraphData(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load concept graph';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (documentName && !initialGraph && !root) {
      void loadGraph(documentName);
    }
  }, [documentName, initialGraph, root, loadGraph]);

  // Derived hierarchical tree
  const displayTree = useMemo(() => {
    return convertToDisplayTree(root, graphData);
  }, [root, graphData]);

  // Set initial selected node
  useEffect(() => {
    if (displayTree && !selectedNode) {
      setSelectedNode(displayTree);
    }
  }, [displayTree, selectedNode]);

  // Zoom handlers
  const handleZoomIn = () => setZoom((z) => Math.min(2.5, +(z + 0.15).toFixed(2)));
  const handleZoomOut = () => setZoom((z) => Math.max(0.4, +(z - 0.15).toFixed(2)));
  const handleResetZoom = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  // Expand / collapse toggle
  const toggleCollapse = (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setCollapsedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const expandAll = () => setCollapsedIds(new Set());
  const collapseAll = () => {
    if (!displayTree) return;
    const allIds = new Set<string>();
    function collect(n: MindMapDisplayNode) {
      if (n.children && n.children.length > 0) {
        allIds.add(n.id);
        n.children.forEach(collect);
      }
    }
    collect(displayTree);
    setCollapsedIds(allIds);
  };

  // Node selection
  const handleSelectNode = (node: MindMapDisplayNode) => {
    setSelectedNode(node);
    if (onSelectNode) {
      onSelectNode(node);
    }
  };

  // Search filter predicate
  const matchesSearch = useCallback(
    (node: MindMapDisplayNode): boolean => {
      if (!searchQuery.trim()) return false;
      const q = searchQuery.toLowerCase();
      return (
        node.label.toLowerCase().includes(q) ||
        node.cluster.toLowerCase().includes(q) ||
        node.sources.some((s) => s.passage?.toLowerCase().includes(q))
      );
    },
    [searchQuery],
  );

  // Pan dragging
  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return; // primary click only
    setIsDragging(true);
    dragStartRef.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    setPan({
      x: e.clientX - dragStartRef.current.x,
      y: e.clientY - dragStartRef.current.y,
    });
  };

  const handleMouseUp = () => setIsDragging(false);

  // ---------------------------------------------------------------------------
  // Exports (PNG, SVG, JSON, Markdown)
  // ---------------------------------------------------------------------------

  const handleExportSvg = () => {
    if (!svgRef.current) return;
    setIsExporting('svg');
    try {
      const serializer = new XMLSerializer();
      let source = serializer.serializeToString(svgRef.current);
      if (!source.match(/^<svg[^>]+xmlns="http:\/\/www\.w3\.org\/2000\/svg"/)) {
        source = source.replace(/^<svg/, '<svg xmlns="http://www.w3.org/2000/svg"');
      }
      const title = displayTree?.label || 'concept_mind_map';
      const filename = `mindmap_${title.replace(/[^a-zA-Z0-9_-]/g, '_')}_${Date.now()}.svg`;
      downloadSvgFile(filename, source, 'researcher', title);
    } catch (err) {
      console.error('Failed to export SVG:', err);
    } finally {
      setIsExporting(null);
    }
  };

  const handleExportPng = async () => {
    if (!svgRef.current) return;
    setIsExporting('png');
    try {
      const serializer = new XMLSerializer();
      let source = serializer.serializeToString(svgRef.current);
      if (!source.match(/^<svg[^>]+xmlns="http:\/\/www\.w3\.org\/2000\/svg"/)) {
        source = source.replace(/^<svg/, '<svg xmlns="http://www.w3.org/2000/svg"');
      }
      const title = displayTree?.label || 'concept_mind_map';
      const filename = `mindmap_${title.replace(/[^a-zA-Z0-9_-]/g, '_')}_${Date.now()}.png`;
      await downloadSvgAsPngFile(filename, source, 1200, 800, 'researcher', title);
    } catch (err) {
      console.error('Failed to export PNG:', err);
    } finally {
      setIsExporting(null);
    }
  };

  const handleExportJson = () => {
    setIsExporting('json');
    try {
      const dataToExport = graphData || {
        tree: displayTree,
        exported_at: new Date().toISOString(),
      };
      const title = displayTree?.label || 'concept_mind_map';
      const filename = `mindmap_${title.replace(/[^a-zA-Z0-9_-]/g, '_')}_${Date.now()}.json`;
      downloadJsonFile(filename, dataToExport, 'researcher', title);
    } catch (err) {
      console.error('Failed to export JSON:', err);
    } finally {
      setIsExporting(null);
    }
  };

  const handleExportMarkdown = () => {
    if (!displayTree) return;
    setIsExporting('markdown');
    try {
      let md = `# Knowledge Mind Map: ${displayTree.label}\n\n`;
      md += `*Exported on ${new Date().toLocaleString()}*\n\n`;

      function renderMdNode(node: MindMapDisplayNode, depth: number) {
        const indent = '  '.repeat(depth);
        const prefix = depth === 0 ? '# ' : depth === 1 ? '## ' : '- ';
        md += `${indent}${prefix}**${node.label}** *(Cluster: ${node.cluster}${node.mentionCount !== null ? `, mentioned in ${node.mentionCount} chunk(s)` : ''})*\n`;

        if (node.sources && node.sources.length > 0) {
          node.sources.forEach((s) => {
            md += `${indent}  > *Source: ${s.document} (${s.page !== null && s.page !== undefined && s.page !== '' ? `Page ${s.page}` : 'Page unknown'})*\n`;
            if (s.passage) {
              md += `${indent}  > "${s.passage.trim()}"\n`;
            }
          });
        }

        if (node.children && node.children.length > 0) {
          node.children.forEach((child) => renderMdNode(child, depth + 1));
        }
      }

      renderMdNode(displayTree, 0);

      const title = displayTree.label;
      const filename = `mindmap_${title.replace(/[^a-zA-Z0-9_-]/g, '_')}_${Date.now()}.md`;
      downloadMarkdownFile(filename, md, 'researcher', title);
    } catch (err) {
      console.error('Failed to export Markdown:', err);
    } finally {
      setIsExporting(null);
    }
  };

  // ---------------------------------------------------------------------------
  // Tree Node Layout Calculations
  // ---------------------------------------------------------------------------
  interface PositionedNode {
    node: MindMapDisplayNode;
    x: number;
    y: number;
    parent?: PositionedNode;
  }

  const { positionedNodes, links, totalWidth, totalHeight } = useMemo(() => {
    if (!displayTree) {
      return { positionedNodes: [], links: [], totalWidth: 800, totalHeight: 500 };
    }

    const posNodes: PositionedNode[] = [];
    const linkPairs: Array<{ source: PositionedNode; target: PositionedNode }> = [];

    // Horizontal tree layout (root at x=100, branches to the right)
    const levelWidth = 260;
    const nodeHeight = 72;
    let currentY = 60;

    function layout(
      node: MindMapDisplayNode,
      depth: number,
      parent?: PositionedNode,
    ): PositionedNode {
      const isCollapsed = collapsedIds.has(node.id);
      const visibleChildren = isCollapsed ? [] : node.children || [];

      let yCoord = currentY;
      if (visibleChildren.length > 0) {
        const childYs: number[] = [];
        const childNodes = visibleChildren.map((child) => {
          const c = layout(child, depth + 1);
          childYs.push(c.y);
          return c;
        });

        // Center parent between first and last child
        yCoord = (childYs[0] + childYs[childYs.length - 1]) / 2;
        const selfPos: PositionedNode = {
          node,
          x: depth * levelWidth + 80,
          y: yCoord,
          parent,
        };
        posNodes.push(selfPos);

        childNodes.forEach((c) => {
          c.parent = selfPos;
          linkPairs.push({ source: selfPos, target: c });
        });
        return selfPos;
      } else {
        const selfPos: PositionedNode = {
          node,
          x: depth * levelWidth + 80,
          y: currentY,
          parent,
        };
        posNodes.push(selfPos);
        currentY += nodeHeight;
        return selfPos;
      }
    }

    layout(displayTree, 0);

    const maxX = Math.max(...posNodes.map((p) => p.x), 700) + 260;
    const maxY = Math.max(currentY + 60, 480);

    return {
      positionedNodes: posNodes,
      links: linkPairs,
      totalWidth: maxX,
      totalHeight: maxY,
    };
  }, [displayTree, collapsedIds]);

  // Loading State
  if (isLoading) {
    return (
      <section
        data-testid="mindmap-loading"
        className="refire-card p-8 flex flex-col items-center justify-center min-h-[380px] space-y-4"
        aria-live="polite"
      >
        <Loader2 className="h-8 w-8 animate-spin text-[#a7d0d2]" />
        <p className="text-sm font-mono text-[#f3faf0]/80">Constructing concept graph & mind map...</p>
        <p className="text-xs text-[#98a6b0]">Extracting concepts, relations, and page citations from document chunks</p>
      </section>
    );
  }

  // Error State
  if (error) {
    return (
      <section
        data-testid="mindmap-error"
        className="refire-card p-6 border-red-500/30 bg-red-950/10 space-y-4"
      >
        <div className="flex items-center gap-3">
          <AlertCircle className="h-5 w-5 text-red-400" />
          <h3 className="text-sm font-semibold text-red-200">Failed to load Knowledge Mind Map</h3>
        </div>
        <p className="text-xs text-red-300/80 font-mono">{error}</p>
        {documentName && (
          <button
            type="button"
            onClick={() => void loadGraph(documentName)}
            className="inline-flex items-center gap-1.5 rounded bg-red-900/40 border border-red-500/40 px-3 py-1.5 text-xs text-white hover:bg-red-800/40 transition-colors"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            Retry Extraction
          </button>
        )}
      </section>
    );
  }

  // Empty State
  if (!displayTree || positionedNodes.length === 0) {
    return (
      <section
        data-testid="mindmap-empty"
        className="refire-card p-10 flex flex-col items-center justify-center text-center space-y-3"
      >
        <Network className="h-10 w-10 text-[#4d728e]/60" />
        <h3 className="text-sm font-semibold text-white">No Mind Map Data Available</h3>
        <p className="text-xs text-[#98a6b0] max-w-sm">
          Run a knowledge graph query or select an indexed document to generate an interactive topological concept tree.
        </p>
      </section>
    );
  }

  return (
    <section
      data-testid="mindmap-container"
      className="refire-card p-4 sm:p-5 space-y-4"
      aria-labelledby="mind-map-title"
    >
      {/* Header Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/8 pb-3">
        <div className="flex items-center gap-2">
          <Network className="h-4 w-4 text-[#a7d0d2]" />
          <h2 id="mind-map-title" className="text-xs font-mono uppercase text-[#f3faf0]/85 font-semibold">
            Interactive Knowledge Mind Map
          </h2>
          {graphData && (
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-[#1b2734] text-[#a7d0d2] border border-[#4d728e]/30">
              {graphData.total_nodes || graphData.nodes?.length || 0} nodes · {graphData.total_edges || graphData.edges?.length || 0} edges
            </span>
          )}
        </div>

        {/* Action Controls: Search, Zoom, Expand, Exports */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Search Bar */}
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#98a6b0]" />
            <input
              data-testid="mindmap-search-input"
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search concepts..."
              className="h-7 w-36 sm:w-48 rounded bg-[#0b1219] border border-[#4d728e]/40 pl-8 pr-7 text-xs text-white placeholder-[#98a6b0]/60 focus:border-[#a7d0d2] focus:outline-none"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-[#98a6b0] hover:text-white"
                title="Clear search"
              >
                <X className="h-3 w-3" />
              </button>
            )}
          </div>

          {/* Zoom Controls */}
          <div className="flex items-center rounded border border-[#4d728e]/40 bg-[#0b1219]">
            <button
              data-testid="mindmap-zoom-in"
              type="button"
              onClick={handleZoomIn}
              className="p-1.5 text-[#98a6b0] hover:text-white hover:bg-white/5 transition-colors"
              title="Zoom in"
            >
              <ZoomIn className="h-3.5 w-3.5" />
            </button>
            <span
              data-testid="mindmap-zoom-level"
              className="px-1.5 text-[10px] font-mono text-[#a7d0d2] min-w-[32px] text-center"
            >
              {Math.round(zoom * 100)}%
            </span>
            <button
              data-testid="mindmap-zoom-out"
              type="button"
              onClick={handleZoomOut}
              className="p-1.5 text-[#98a6b0] hover:text-white hover:bg-white/5 transition-colors"
              title="Zoom out"
            >
              <ZoomOut className="h-3.5 w-3.5" />
            </button>
            <button
              data-testid="mindmap-zoom-reset"
              type="button"
              onClick={handleResetZoom}
              className="p-1.5 text-[#98a6b0] hover:text-white hover:bg-white/5 border-l border-[#4d728e]/40 transition-colors"
              title="Reset view"
            >
              <RotateCcw className="h-3.5 w-3.5" />
            </button>
          </div>

          {/* Expand / Collapse All */}
          <div className="flex items-center gap-1">
            <button
              data-testid="mindmap-expand-all"
              type="button"
              onClick={expandAll}
              className="rounded bg-[#141d26] border border-[#4d728e]/40 px-2 py-1 text-[11px] font-mono text-[#98a6b0] hover:text-white hover:border-[#a7d0d2] transition-colors"
            >
              Expand
            </button>
            <button
              data-testid="mindmap-collapse-all"
              type="button"
              onClick={collapseAll}
              className="rounded bg-[#141d26] border border-[#4d728e]/40 px-2 py-1 text-[11px] font-mono text-[#98a6b0] hover:text-white hover:border-[#a7d0d2] transition-colors"
            >
              Collapse
            </button>
          </div>

          {/* Export Dropdown / Buttons */}
          <div className="flex items-center gap-1 border-l border-white/10 pl-2">
            <button
              data-testid="mindmap-export-png"
              type="button"
              onClick={() => void handleExportPng()}
              disabled={isExporting !== null}
              className="inline-flex items-center gap-1 rounded bg-[#141d26] border border-[#4d728e]/40 px-2 py-1 text-[11px] font-mono text-[#a7d0d2] hover:text-white hover:border-[#a7d0d2] transition-colors cursor-pointer disabled:opacity-50"
              title="Export as PNG image"
            >
              <Download className="h-3 w-3" />
              <span>PNG</span>
            </button>
            <button
              data-testid="mindmap-export-svg"
              type="button"
              onClick={handleExportSvg}
              disabled={isExporting !== null}
              className="inline-flex items-center gap-1 rounded bg-[#141d26] border border-[#4d728e]/40 px-2 py-1 text-[11px] font-mono text-[#a7d0d2] hover:text-white hover:border-[#a7d0d2] transition-colors cursor-pointer disabled:opacity-50"
              title="Export as vector SVG"
            >
              <Download className="h-3 w-3" />
              <span>SVG</span>
            </button>
            <button
              data-testid="mindmap-export-json"
              type="button"
              onClick={handleExportJson}
              disabled={isExporting !== null}
              className="inline-flex items-center gap-1 rounded bg-[#141d26] border border-[#4d728e]/40 px-2 py-1 text-[11px] font-mono text-[#a7d0d2] hover:text-white hover:border-[#a7d0d2] transition-colors cursor-pointer disabled:opacity-50"
              title="Export as JSON"
            >
              <FileCode className="h-3 w-3" />
              <span>JSON</span>
            </button>
            <button
              data-testid="mindmap-export-markdown"
              type="button"
              onClick={handleExportMarkdown}
              disabled={isExporting !== null}
              className="inline-flex items-center gap-1 rounded bg-[#141d26] border border-[#4d728e]/40 px-2 py-1 text-[11px] font-mono text-[#a7d0d2] hover:text-white hover:border-[#a7d0d2] transition-colors cursor-pointer disabled:opacity-50"
              title="Export as Markdown outline"
            >
              <FileText className="h-3 w-3" />
              <span>MD</span>
            </button>
          </div>
        </div>
      </div>

      {/* Main Canvas + Detail Inspector Drawer */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* SVG Interactive Canvas */}
        <div
          ref={containerRef}
          data-testid="mindmap-canvas"
          className="lg:col-span-3 relative h-[520px] rounded-lg border border-white/8 bg-[#070b0f] overflow-hidden select-none cursor-grab active:cursor-grabbing"
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        >
          {/* Subtle background grid */}
          <div
            className="absolute inset-0 pointer-events-none opacity-20"
            style={{
              backgroundImage: 'radial-gradient(circle, #4d728e 1px, transparent 1px)',
              backgroundSize: '24px 24px',
            }}
          />

          <svg
            ref={svgRef}
            width={totalWidth}
            height={totalHeight}
            className="w-full h-full"
            style={{
              transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
              transformOrigin: 'top left',
              transition: isDragging ? 'none' : 'transform 0.15s ease-out',
            }}
          >
            <defs>
              <linearGradient id="link-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#4d728e" stopOpacity="0.8" />
                <stop offset="100%" stopColor="#a7d0d2" stopOpacity="0.9" />
              </linearGradient>
              <filter id="node-glow" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="3" result="blur" />
                <feComposite in="SourceGraphic" in2="blur" operator="over" />
              </filter>
            </defs>

            {/* Connecting Bezier Curves */}
            <g className="mindmap-links">
              {links.map(({ source, target }, idx) => {
                const sx = source.x + 160;
                const sy = source.y + 18;
                const tx = target.x;
                const ty = target.y + 18;
                const dx = (tx - sx) / 2;
                const pathData = `M ${sx} ${sy} C ${sx + dx} ${sy}, ${tx - dx} ${ty}, ${tx} ${ty}`;

                return (
                  <path
                    key={`link-${source.node.id}-${target.node.id}-${idx}`}
                    d={pathData}
                    fill="none"
                    stroke="url(#link-gradient)"
                    strokeWidth="1.75"
                    strokeDasharray={target.node.origin === 'heuristic' ? '3 3' : 'none'}
                    className="opacity-70 hover:opacity-100 transition-opacity"
                  />
                );
              })}
            </g>

            {/* Interactive Nodes */}
            <g className="mindmap-nodes">
              {positionedNodes.map(({ node, x, y }) => {
                const isSelected = selectedNode?.id === node.id;
                const isMatch = matchesSearch(node);
                const hasChildren = node.children && node.children.length > 0;
                const isCollapsed = collapsedIds.has(node.id);

                return (
                  <g
                    key={`node-${node.id}`}
                    transform={`translate(${x}, ${y})`}
                    onClick={() => handleSelectNode(node)}
                    className="cursor-pointer group"
                    data-testid={`node-${node.id}`}
                  >
                    {/* Node Card Background */}
                    <rect
                      x="0"
                      y="0"
                      width="160"
                      height="38"
                      rx="6"
                      fill={
                        isSelected
                          ? '#182836'
                          : isMatch
                          ? '#2a2216'
                          : node.cluster === 'Root'
                          ? '#1d222b'
                          : '#0d151e'
                      }
                      stroke={
                        isSelected
                          ? '#a7d0d2'
                          : isMatch
                          ? '#f59e0b'
                          : node.cluster === 'Root'
                          ? '#d2434e'
                          : '#2f4356'
                      }
                      strokeWidth={isSelected ? '2' : isMatch ? '2' : '1'}
                      filter={isSelected || isMatch ? 'url(#node-glow)' : undefined}
                      className="transition-all duration-150"
                    />

                    {/* Cluster Category Tag Dot */}
                    <circle
                      cx="10"
                      cy="19"
                      r="4"
                      fill={
                        node.cluster === 'Root'
                          ? '#d2434e'
                          : node.cluster === 'Method'
                          ? '#10b981'
                          : node.cluster === 'Architecture'
                          ? '#3b82f6'
                          : node.cluster === 'Theory'
                          ? '#8b5cf6'
                          : '#a7d0d2'
                      }
                    />

                    {/* Node Text Label */}
                    <text
                      x="20"
                      y="23"
                      fill={isSelected ? '#ffffff' : '#f3faf0'}
                      fontSize="11"
                      fontWeight={isSelected ? '600' : '500'}
                      fontFamily="system-ui, -apple-system, sans-serif"
                      className="truncate"
                    >
                      {node.label.length > 18 ? `${node.label.slice(0, 16)}…` : node.label}
                    </text>

                    {/* Expand/Collapse Toggle Badge */}
                    {hasChildren && (
                      <g
                        transform="translate(142, 10)"
                        onClick={(e) => toggleCollapse(node.id, e)}
                        className="cursor-pointer hover:opacity-80"
                        data-testid={`toggle-${node.id}`}
                      >
                        <circle cx="9" cy="9" r="8" fill="#1b2734" stroke="#4d728e" strokeWidth="1" />
                        <text
                          x="9"
                          y="12.5"
                          textAnchor="middle"
                          fill="#a7d0d2"
                          fontSize="10"
                          fontWeight="bold"
                        >
                          {isCollapsed ? '+' : '−'}
                        </text>
                      </g>
                    )}
                  </g>
                );
              })}
            </g>
          </svg>
        </div>

        {/* Selected Node Details & Passage Inspector */}
        <aside
          data-testid="mindmap-inspector"
          className="rounded-lg border border-white/8 bg-[#0b1219] p-4 flex flex-col justify-between space-y-4 h-[520px] overflow-y-auto"
        >
          {selectedNode ? (
            <div className="space-y-4">
              {/* Header */}
              <div className="border-b border-white/8 pb-3">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-[#d2434e]">
                    Concept Detail
                  </span>
                  <span className="rounded px-2 py-0.5 text-[10px] font-mono bg-[#141d26] text-[#a7d0d2] border border-[#4d728e]/40">
                    {selectedNode.cluster}
                  </span>
                </div>
                <h3
                  data-testid="inspector-node-label"
                  className="mt-1 text-sm font-semibold text-white leading-snug"
                >
                  {selectedNode.label}
                </h3>
              </div>

              {/* Measured facts only */}
              <div className="space-y-1.5 text-xs">
                <div className="flex justify-between text-[11px] text-[#98a6b0]">
                  <span>Mentioned in</span>
                  <span className="font-mono text-[#a7d0d2]">
                    {selectedNode.mentionCount !== null ? `${selectedNode.mentionCount} chunk(s)` : 'not measured'}
                  </span>
                </div>
                {selectedNode.origin && (
                  <div className="flex justify-between text-[11px] text-[#98a6b0]">
                    <span>Origin</span>
                    <span className="font-mono text-[#a7d0d2]">{selectedNode.origin}</span>
                  </div>
                )}
              </div>

              {/* Grounded Sources & Passages */}
              <div className="space-y-2 pt-2 border-t border-white/8">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-white">
                  <Bookmark className="h-3.5 w-3.5 text-[#a7d0d2]" />
                  <span>Passages & Citations</span>
                  <span className="text-[10px] text-[#98a6b0]">
                    ({selectedNode.sources?.length || 0})
                  </span>
                </div>

                {selectedNode.sources && selectedNode.sources.length > 0 ? (
                  <div className="space-y-2.5 max-h-[220px] overflow-y-auto pr-1">
                    {selectedNode.sources.map((src, i) => (
                      <div
                        key={`src-${i}`}
                        data-testid="inspector-source-item"
                        className="rounded border border-white/6 bg-[#141d26]/80 p-2.5 space-y-1.5"
                      >
                        <div className="flex items-center justify-between text-[10px] font-mono text-[#a7d0d2]">
                          <span className="truncate max-w-[130px]">{src.document || 'Document'}</span>
                          <span className="text-[#98a6b0]">
                            {src.page !== null && src.page !== undefined && src.page !== '' ? `Page ${src.page}` : 'Page unknown'}
                          </span>
                        </div>
                        {src.passage ? (
                          <blockquote
                            data-testid="inspector-passage-text"
                            className="text-[11px] text-[#f3faf0]/80 italic border-l-2 border-[#a7d0d2]/40 pl-2 leading-relaxed"
                          >
                            "{src.passage}"
                          </blockquote>
                        ) : (
                          <p className="text-[10px] text-[#98a6b0] italic">
                            Evidence verified in chunk {src.chunk_id || 'reference'}.
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-[#98a6b0] italic py-2">
                    Root grouping node. Select a child concept to inspect citations and text passages.
                  </p>
                )}
              </div>
            </div>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-center text-xs text-[#98a6b0] space-y-2">
              <Network className="h-6 w-6 text-[#4d728e]/50" />
              <p>Click any node to inspect its technical definitions, chunk passages, and citations.</p>
            </div>
          )}

          {/* Quick instructions footer */}
          <div className="border-t border-white/8 pt-2 text-[10px] text-[#98a6b0] flex items-center justify-between">
            <span>Drag canvas to pan</span>
            <span>Scroll or +/- to zoom</span>
          </div>
        </aside>
      </div>
    </section>
  );
};
