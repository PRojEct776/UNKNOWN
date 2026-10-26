import React, { useRef, useState, useMemo, useEffect, useCallback } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Html, Sparkles } from '@react-three/drei';
import * as THREE from 'three';
import {
  Compass,
  Play,
  Pause,
  RotateCcw,
  Search,
  HelpCircle,
  X,
  Bookmark,
  ExternalLink,
  ShieldCheck,
  FileText,
  BarChart3,
} from 'lucide-react';
import type { ConceptResult } from '../types/concept';
import type { Evidence } from '../types/evidence';
import type {
  BackendConceptGraphNode,
  BackendConceptGraphEdge,
  BackendConceptGraphResponse,
  BackendConceptSource,
} from '../lib/api';

export interface ConceptGraph3DProps {
  concept?: ConceptResult;
  evidence?: Evidence[];
  graphData?: BackendConceptGraphResponse;
  documentName?: string;
  onOpenSources?: () => void;
  force2DFallback?: boolean;
}

// ---------------------------------------------------------------------------
// Cluster Color Palette Mapping
// ---------------------------------------------------------------------------
export const CLUSTER_COLORS: Record<string, { main: string; emissive: string; glow: string; text: string }> = {
  Architecture: { main: '#3b82f6', emissive: '#1d4ed8', glow: 'rgba(59, 130, 246, 0.4)', text: 'text-blue-400' },
  Method: { main: '#10b981', emissive: '#047857', glow: 'rgba(16, 185, 129, 0.4)', text: 'text-emerald-400' },
  Theory: { main: '#8b5cf6', emissive: '#6d28d9', glow: 'rgba(139, 92, 246, 0.4)', text: 'text-purple-400' },
  Metric: { main: '#f59e0b', emissive: '#b45309', glow: 'rgba(245, 158, 11, 0.4)', text: 'text-amber-400' },
  General: { main: '#a7d0d2', emissive: '#1f3e40', glow: 'rgba(167, 208, 210, 0.4)', text: 'text-[#a7d0d2]' },
};

export function getClusterTheme(clusterName: string = 'General') {
  for (const [key, val] of Object.entries(CLUSTER_COLORS)) {
    if (clusterName.toLowerCase().includes(key.toLowerCase())) {
      return val;
    }
  }
  return CLUSTER_COLORS.General;
}

// ---------------------------------------------------------------------------
// WebGL Support Detection
// ---------------------------------------------------------------------------
export function checkWebGLSupport(): boolean {
  try {
    if (typeof window === 'undefined') return true;
    const canvas = document.createElement('canvas');
    const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
    return Boolean(gl && gl instanceof WebGLRenderingContext);
  } catch {
    return false;
  }
}

// ---------------------------------------------------------------------------
// Internal Normalized Node Model
// ---------------------------------------------------------------------------
export interface OrbitNode {
  id: string;
  label: string;
  cluster: string;
  // Human-readable node kind (document source, web source, LLM concept, ...)
  kind: string;
  origin?: string;
  // Measured: chunks containing the label. null when not measured.
  mentionCount: number | null;
  sources: BackendConceptSource[];
  // Layout only. Position carries no meaning.
  position: [number, number, number];
  size: number;
  detail?: string;
  url?: string;
}

// Deterministic free-form layout (Fibonacci sphere with depth variance).
function layoutPosition(index: number, total: number): [number, number, number] {
  const n = Math.max(total, 1);
  const golden = Math.PI * (3 - Math.sqrt(5));
  const y = n === 1 ? 0 : 1 - (index / (n - 1)) * 2;
  const ring = Math.sqrt(Math.max(0, 1 - y * y));
  const theta = golden * index;
  const radius = 3.6 + Math.min(n, 60) * 0.05 + (index % 3) * 0.5;
  return [Math.cos(theta) * ring * radius, y * radius * 0.8, Math.sin(theta) * ring * radius];
}

function describeNodeKind(origin: string | undefined, cluster: string | undefined): string {
  switch (origin) {
    case 'answer_source':
      return 'Document source';
    case 'web_source':
      return 'Web source';
    case 'comparison':
      return 'Comparison verdict';
    case 'overview_topic':
      return 'Overview topic (heuristic)';
    case 'llm':
      return 'LLM-extracted concept';
    case 'heuristic':
      return 'Heuristic concept';
    default:
      return cluster || 'Node';
  }
}

function describeEvidenceStatus(status: string): string {
  switch (status) {
    case 'co_occurrence':
      return 'Both concepts appear in the same chunk';
    case 'relation_term_present':
      return 'Same chunk, and a relation term is present (lexical check only)';
    case 'retrieved':
      return 'Retrieved for this question';
    case 'model_verdict':
      return 'Model verdict, not independently verified';
    case 'unverified':
      return 'Not verified';
    default:
      return status;
  }
}

function describeNodeOrigin(origin: string | undefined): string {
  switch (origin) {
    case 'llm':
      return 'Proposed by a language model reading the document, and kept only because the label appears word-for-word in the text.';
    case 'heuristic':
      return 'Picked by a rule-based keyword heuristic, and kept only because the label appears word-for-word in the text.';
    case 'answer_source':
      return 'A document source the answer was built from.';
    case 'web_source':
      return 'An external web source returned for this question.';
    case 'comparison':
      return 'A document-versus-web comparison produced for this question.';
    case 'overview_topic':
      return 'A keyword from the document overview. It has no passage attached.';
    default:
      return 'Origin not specified.';
  }
}

function describeConnection(status: string, relation: string, other: string): string {
  switch (status) {
    case 'co_occurrence':
      return `Appears in the same text chunk as "${other}".`;
    case 'relation_term_present':
      return `Appears in the same text chunk as "${other}", and the word "${relation}" is also there.`;
    case 'retrieved':
      return `Retrieved as a source for "${other}".`;
    case 'model_verdict':
      return `Model-generated comparison verdict for "${other}".`;
    default:
      return `Listed as connected to "${other}" without text evidence.`;
  }
}

function summarizePages(sources: BackendConceptSource[]): string {
  if (sources.length === 0) return 'no sources attached';
  const known = new Set<string>();
  let unknown = 0;
  for (const s of sources) {
    if (s.page === null || s.page === undefined || s.page === '') unknown += 1;
    else known.add(String(s.page));
  }
  const parts: string[] = [];
  if (known.size > 0) {
    const sorted = Array.from(known).sort((a, b) => Number(a) - Number(b));
    parts.push(`page ${sorted.join(', ')}`);
  }
  if (unknown > 0) parts.push(`${unknown} source(s) with unknown page`);
  return parts.join('; ');
}

function highlightPassage(passage: string, label: string): React.ReactNode {
  const idx = label ? passage.toLowerCase().indexOf(label.toLowerCase()) : -1;
  if (idx < 0) return passage;
  return (
    <>
      {passage.slice(0, idx)}
      <mark className="bg-[#a7d0d2]/25 text-white rounded px-0.5">{passage.slice(idx, idx + label.length)}</mark>
      {passage.slice(idx + label.length)}
    </>
  );
}

function tabClass(active: boolean): string {
  return `flex items-center justify-center gap-1 py-1 px-1.5 rounded transition-colors ${
    active
      ? 'bg-[#1b2632] text-[#a7d0d2] font-semibold border border-[#a7d0d2]/40 shadow-xs'
      : 'text-[#f3faf0]/60 hover:text-white hover:bg-white/5'
  }`;
}

// ---------------------------------------------------------------------------
// Central Document Sphere
// ---------------------------------------------------------------------------
const CentralDocumentNode: React.FC<{
  title: string;
  isHovered: boolean;
  onHover: (hover: boolean) => void;
  onClick: () => void;
}> = ({ title, isHovered, onHover, onClick }) => {
  const meshRef = useRef<THREE.Mesh>(null!);
  const ringRef = useRef<THREE.Mesh>(null!);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    if (meshRef.current) {
      const pulse = 1 + Math.sin(t * 2) * 0.04;
      meshRef.current.scale.set(pulse, pulse, pulse);
    }
    if (ringRef.current) {
      ringRef.current.rotation.z = t * 0.3;
      ringRef.current.rotation.x = 1.1 + Math.sin(t * 0.5) * 0.1;
    }
  });

  return (
    <group onClick={onClick}>
      {/* Central glowing core sphere */}
      <mesh
        ref={meshRef}
        onPointerOver={() => onHover(true)}
        onPointerOut={() => onHover(false)}
      >
        <sphereGeometry args={[0.75, 32, 32]} />
        <meshStandardMaterial
          color="#d2434e"
          emissive="#7d1e26"
          emissiveIntensity={isHovered ? 1.4 : 0.8}
          roughness={0.2}
          metalness={0.8}
        />
      </mesh>

      {/* Orbiting Equatorial Ring */}
      <mesh ref={ringRef}>
        <torusGeometry args={[1.1, 0.02, 16, 64]} />
        <meshBasicMaterial color="#a7d0d2" opacity={0.6} transparent />
      </mesh>

      {/* Camera-facing center label */}
      <Html center distanceFactor={14} position={[0, 1.1, 0]}>
        <div className="pointer-events-none select-none rounded bg-[#0b1219]/90 border border-[#d2434e] px-2.5 py-1 text-center shadow-lg backdrop-blur-md">
          <span className="block text-[9px] font-mono uppercase text-[#d2434e] font-bold">CENTER</span>
          <span className="text-xs font-semibold text-white truncate max-w-[140px] block">{title}</span>
        </div>
      </Html>
    </group>
  );
};

// ---------------------------------------------------------------------------
// Orbiting Concept Node Sphere (With LOD Label Culling)
// ---------------------------------------------------------------------------
const OrbitingConceptNode: React.FC<{
  node: OrbitNode;
  isPlaying: boolean;
  isSelected: boolean;
  isHovered: boolean;
  isMatch: boolean;
  showLabel: boolean; // Level-of-Detail toggle
  onHover: (hover: boolean) => void;
  onClick: () => void;
}> = ({ node, isSelected, isHovered, isMatch, showLabel, onHover, onClick }) => {
  const groupRef = useRef<THREE.Group>(null!);
  const meshRef = useRef<THREE.Mesh>(null!);
  const theme = getClusterTheme(node.cluster);

  return (
    <group ref={groupRef} position={node.position} onClick={onClick}>
      <mesh
        ref={meshRef}
        onPointerOver={() => onHover(true)}
        onPointerOut={() => onHover(false)}
      >
        <sphereGeometry args={[node.size, 24, 24]} />
        <meshStandardMaterial
          color={isMatch ? '#f59e0b' : isSelected ? '#ffffff' : theme.main}
          emissive={isMatch ? '#d97706' : isSelected ? '#a7d0d2' : theme.emissive}
          emissiveIntensity={isSelected ? 1.5 : isHovered ? 1.2 : 0.6}
          roughness={0.3}
          metalness={0.6}
        />
      </mesh>

      {/* Camera-Facing Label with LOD culling */}
      {(showLabel || isHovered || isSelected || isMatch) && (
        <Html center distanceFactor={14} position={[0, node.size + 0.3, 0]}>
          <div
            className={`pointer-events-none select-none rounded px-2 py-0.5 text-center shadow-md backdrop-blur-md transition-all ${
              isSelected
                ? 'bg-[#1b2734] border border-[#a7d0d2] text-white scale-110'
                : isMatch
                ? 'bg-[#2a2216] border border-[#f59e0b] text-[#fde68a] scale-105'
                : 'bg-[#0b1219]/80 border border-white/10 text-[#f3faf0]/90'
            }`}
          >
            <span className="text-[10px] font-medium block whitespace-nowrap">{node.label}</span>
          </div>
        </Html>
      )}
    </group>
  );
};

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// 3D Relation Connection Lines
// ---------------------------------------------------------------------------
const RelationLines: React.FC<{ nodes: OrbitNode[]; edges: BackendConceptGraphEdge[] }> = ({ nodes, edges }) => {
  const lineObjects = useMemo(() => {
    const posOf = (id: string): THREE.Vector3 | null => {
      if (id === 'root') return new THREE.Vector3(0, 0, 0);
      const n = nodes.find((x) => x.id === id);
      return n ? new THREE.Vector3(n.position[0], n.position[1], n.position[2]) : null;
    };
    const out: THREE.Line[] = [];
    for (const e of edges) {
      const p1 = posOf(e.source);
      const p2 = posOf(e.target);
      if (!p1 || !p2) continue;
      const geom = new THREE.BufferGeometry().setFromPoints([p1, p2]);
      const dashed = !e.evidence_status || e.evidence_status === 'unverified' || e.evidence_status === 'model_verdict';
      const line = dashed
        ? new THREE.Line(
            geom,
            new THREE.LineDashedMaterial({ color: '#4d728e', opacity: 0.4, transparent: true, dashSize: 0.18, gapSize: 0.12 }),
          )
        : new THREE.Line(geom, new THREE.LineBasicMaterial({ color: '#a7d0d2', opacity: 0.55, transparent: true }));
      if (dashed) line.computeLineDistances();
      out.push(line);
    }
    return out;
  }, [nodes, edges]);

  return (
    <group>
      {lineObjects.map((lineObj, idx) => (
        <primitive key={`rel-line-${idx}`} object={lineObj} />
      ))}
    </group>
  );
};

// Slowly rotates everything inside it while playing (layout only).
const SlowRotation: React.FC<{ enabled: boolean; children: React.ReactNode }> = ({ enabled, children }) => {
  const ref = useRef<THREE.Group>(null!);
  useFrame((_, delta) => {
    if (enabled && ref.current) ref.current.rotation.y += delta * 0.06;
  });
  return <group ref={ref}>{children}</group>;
};

// 3D Scene Container
// ---------------------------------------------------------------------------
const OrbitScene: React.FC<{
  nodes: OrbitNode[];
  edges: BackendConceptGraphEdge[];
  centerTitle: string;
  isPlaying: boolean;
  selectedNodeId: string | null;
  hoveredNodeId: string | null;
  searchQuery: string;
  lodLimit: number;
  onSelectNode: (node: OrbitNode) => void;
  onHoverNode: (node: OrbitNode | null) => void;
  controlsRef: React.RefObject<any>;
}> = ({
  nodes,
  edges,
  centerTitle,
  isPlaying,
  selectedNodeId,
  hoveredNodeId,
  searchQuery,
  lodLimit,
  onSelectNode,
  onHoverNode,
  controlsRef,
}) => {
  return (
    <>
      <ambientLight intensity={0.4} />
      <pointLight position={[10, 10, 10]} intensity={1.2} />
      <pointLight position={[-10, -10, -10]} intensity={0.6} color="#4d728e" />

      {/* Subtle cosmic particles */}
      <Sparkles count={50} scale={18} size={2} speed={0.4} opacity={0.3} color="#a7d0d2" />

      {/* OrbitControls with smooth damping */}
      <OrbitControls
        ref={controlsRef}
        enableDamping={true}
        dampingFactor={0.05}
        minDistance={3}
        maxDistance={22}
      />

      <SlowRotation enabled={isPlaying}>
      {/* Central Document Node */}
      <CentralDocumentNode
        title={centerTitle}
        isHovered={hoveredNodeId === 'center'}
        onHover={(h) => onHoverNode(h ? ({ id: 'center', label: centerTitle, cluster: 'Center', kind: 'Center', mentionCount: null, sources: [], position: [0, 0, 0], size: 0.75 }) : null)}
        onClick={() => {}}
      />

      {/* Relation Connection Lines */}
      <RelationLines nodes={nodes} edges={edges} />

      {/* Concept Spheres with LOD */}
      {nodes.map((node, index) => {
        const isSelected = selectedNodeId === node.id;
        const isHovered = hoveredNodeId === node.id;
        const isMatch = Boolean(
          searchQuery &&
            (node.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
              node.cluster.toLowerCase().includes(searchQuery.toLowerCase())),
        );
        // LOD: render label only if under limit, hovered, selected, or matched
        const showLabel = index < lodLimit;

        return (
          <OrbitingConceptNode
            key={`orbit-node-${node.id}`}
            node={node}
            isPlaying={isPlaying}
            isSelected={isSelected}
            isHovered={isHovered}
            isMatch={isMatch}
            showLabel={showLabel}
            onHover={(h) => onHoverNode(h ? node : null)}
            onClick={() => onSelectNode(node)}
          />
        );
      })}
      </SlowRotation>
    </>
  );
};

// ---------------------------------------------------------------------------
// 2D Accessible Fallback (when WebGL is unavailable or user chooses 2D)
// ---------------------------------------------------------------------------
const Accessible2DOrbitFallback: React.FC<{
  nodes: OrbitNode[];
  edges: BackendConceptGraphEdge[];
  centerTitle: string;
  selectedNode: OrbitNode | null;
  searchQuery: string;
  onSelectNode: (node: OrbitNode) => void;
}> = ({ nodes, edges, centerTitle, selectedNode, searchQuery, onSelectNode }) => {
  const [focusedIndex, setFocusedIndex] = useState(0);

  const filteredNodes = useMemo(() => {
    if (!searchQuery.trim()) return nodes;
    const q = searchQuery.toLowerCase();
    return nodes.filter((n) => n.label.toLowerCase().includes(q) || n.cluster.toLowerCase().includes(q));
  }, [nodes, searchQuery]);

  const coords = useMemo(() => {
    const extent = Math.max(
      1,
      ...nodes.map((n) => Math.max(Math.abs(n.position[0]), Math.abs(n.position[2]))),
    );
    const map = new Map<string, [number, number]>();
    map.set('root', [300, 200]);
    nodes.forEach((n) => {
      map.set(n.id, [300 + (n.position[0] / extent) * 230, 200 + (n.position[2] / extent) * 150]);
    });
    return map;
  }, [nodes]);

  // Keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (filteredNodes.length === 0) return;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      e.preventDefault();
      const next = (focusedIndex + 1) % filteredNodes.length;
      setFocusedIndex(next);
      onSelectNode(filteredNodes[next]);
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault();
      const prev = (focusedIndex - 1 + filteredNodes.length) % filteredNodes.length;
      setFocusedIndex(prev);
      onSelectNode(filteredNodes[prev]);
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      if (filteredNodes[focusedIndex]) {
        onSelectNode(filteredNodes[focusedIndex]);
      }
    }
  };

  return (
    <div
      data-testid="orbit-2d-fallback"
      role="region"
      aria-label="Accessible 2D Knowledge Orbit"
      tabIndex={0}
      onKeyDown={handleKeyDown}
      className="relative w-full h-[500px] rounded-lg border border-white/8 bg-[#070b0f] p-4 flex flex-col justify-between focus:outline-none focus:ring-1 focus:ring-[#a7d0d2]"
    >
      <div className="flex items-center justify-between text-xs text-[#98a6b0] pb-2 border-b border-white/8">
        <span>2D Accessible Orbit: {centerTitle} (Arrow Keys & Enter)</span>
        <span className="font-mono text-[#a7d0d2]">{filteredNodes.length} nodes displayed</span>
      </div>

      {/* SVG 2D Radar Canvas */}
      <div className="relative flex-1 flex items-center justify-center overflow-hidden">
        <svg viewBox="0 0 600 400" className="w-full h-full max-h-[380px]">
          {/* Central Core Document */}
          <circle cx="300" cy="200" r="22" fill="#d2434e" />
          <text x="300" y="204" textAnchor="middle" fill="#ffffff" fontSize="9" fontWeight="bold">
            DOC
          </text>

          {/* Real edges only: dashed when unverified or a model verdict */}
          {edges.map((e, i) => {
            const a = coords.get(e.source);
            const b = coords.get(e.target);
            if (!a || !b) return null;
            const dashed = !e.evidence_status || e.evidence_status === 'unverified' || e.evidence_status === 'model_verdict';
            return (
              <line
                key={`svg-edge-${i}`}
                x1={a[0]}
                y1={a[1]}
                x2={b[0]}
                y2={b[1]}
                stroke="#4d728e"
                strokeWidth="0.75"
                opacity="0.5"
                strokeDasharray={dashed ? '3 3' : undefined}
              />
            );
          })}

          {/* Concept nodes (position is layout only) */}
          {filteredNodes.map((n, idx) => {
            const [cx, cy] = coords.get(n.id) ?? [300, 200];
            const isSelected = selectedNode?.id === n.id;
            const isFocused = idx === focusedIndex;
            const theme = getClusterTheme(n.cluster);

            return (
              <g
                key={`svg-node-${n.id}`}
                onClick={() => {
                  setFocusedIndex(idx);
                  onSelectNode(n);
                }}
                className="cursor-pointer group"
                data-testid={`2d-node-${n.id}`}
              >
                <circle
                  cx={cx}
                  cy={cy}
                  r={isSelected ? 10 : 7}
                  fill={theme.main}
                  stroke={isSelected || isFocused ? '#ffffff' : theme.emissive}
                  strokeWidth={isSelected || isFocused ? 2 : 1}
                  className="transition-all hover:scale-125"
                />

                <text
                  x={cx}
                  y={cy + 16}
                  textAnchor="middle"
                  fill={isSelected ? '#ffffff' : '#f3faf0'}
                  fontSize="9"
                  fontFamily="system-ui"
                  className="opacity-80 group-hover:opacity-100"
                >
                  {n.label.length > 12 ? `${n.label.slice(0, 11)}...` : n.label}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      <div className="text-[10px] text-[#98a6b0] pt-2 border-t border-white/8 flex justify-between">
        <span>Position is layout only and does not encode relevance</span>
        <span>Press Enter to inspect node details</span>
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Main Exported ConceptGraph3D Component
// ---------------------------------------------------------------------------
export const ConceptGraph3D: React.FC<ConceptGraph3DProps> = ({
  concept,
  evidence,
  graphData,
  documentName,
  onOpenSources,
  force2DFallback,
}) => {
  // WebGL availability state
  const [hasWebGL, setHasWebGL] = useState<boolean>(true);
  const [use2DMode, setUse2DMode] = useState<boolean>(Boolean(force2DFallback));

  useEffect(() => {
    const supported = checkWebGLSupport();
    setHasWebGL(supported);
    if (!supported) {
      setUse2DMode(true);
    }
  }, []);

  // Play / Pause & Camera Reset
  const [isPlaying, setIsPlaying] = useState<boolean>(true);
  const controlsRef = useRef<any>(null);

  // Search & Filter
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Node Selection & Hover Tooltip
  const [selectedNode, setSelectedNode] = useState<OrbitNode | null>(null);
  const [hoveredNode, setHoveredNode] = useState<OrbitNode | null>(null);
  const [activeInspectorTab, setActiveInspectorTab] = useState<'details' | 'sources' | 'evidence'>('details');

  // In-app "How to read this" Panel
  const [showHowToRead, setShowHowToRead] = useState<boolean>(false);

  // Normalize incoming data (Supports P1-5 JSON, ConceptResult, or raw nodes)
  const { normalizedNodes, edges, centerTitle } = useMemo(() => {
    let rawNodes: BackendConceptGraphNode[] = [];
    let rawEdges: BackendConceptGraphEdge[] = [];
    let docTitle = documentName || 'Document';

    if (graphData && graphData.nodes) {
      rawNodes = graphData.nodes;
      rawEdges = graphData.edges || [];
      docTitle = graphData.document || docTitle;
    } else if (concept) {
      docTitle = concept.name || docTitle;
      // Concept results carry no per-node evidence, so no sources are attached.
      rawNodes = (concept.graphNodes || []).map((n) => ({
        id: n.id,
        label: n.label,
        cluster: n.type ? n.type.toUpperCase() : 'General',
        sources: [],
      }));
    }

    // Filter out central node from the orbiting set
    const peripheral = rawNodes.filter((n) => n.id !== 'root' && n.label !== docTitle);
    const totalCount = peripheral.length;
    const maxMentions = peripheral.reduce(
      (m, n) => Math.max(m, typeof n.mention_count === 'number' ? n.mention_count : 0),
      0,
    );

    const mapped: OrbitNode[] = peripheral.map((node, index) => {
      const extras = node as BackendConceptGraphNode & { url?: string; detail?: string };
      const mentionCount = typeof node.mention_count === 'number' ? node.mention_count : null;
      // Size encodes the measured mention count; uniform when not measured.
      const size = mentionCount !== null && maxMentions > 0 ? 0.2 + (mentionCount / maxMentions) * 0.3 : 0.28;

      return {
        id: node.id,
        label: node.label,
        cluster: node.cluster || 'General',
        kind: describeNodeKind(node.origin, node.cluster),
        origin: node.origin,
        mentionCount,
        sources: node.sources || [],
        position: layoutPosition(index, totalCount),
        size,
        detail: extras.detail,
        url: extras.url,
      };
    });

    return {
      normalizedNodes: mapped,
      edges: rawEdges,
      centerTitle: docTitle,
    };
  }, [graphData, concept, evidence, documentName]);

  // Set default selected node
  useEffect(() => {
    if (normalizedNodes.length > 0 && !selectedNode) {
      setSelectedNode(normalizedNodes[0]);
    }
  }, [normalizedNodes, selectedNode]);

  // Guided Walkthrough Traversal (Requirement 3)
  const currentTourIndex = useMemo(() => {
    if (!selectedNode) return 0;
    const idx = normalizedNodes.findIndex((n) => n.id === selectedNode.id);
    return idx >= 0 ? idx : 0;
  }, [normalizedNodes, selectedNode]);

  const handleNextConcept = useCallback(() => {
    if (normalizedNodes.length === 0) return;
    const nextIdx = (currentTourIndex + 1) % normalizedNodes.length;
    setSelectedNode(normalizedNodes[nextIdx]);
  }, [normalizedNodes, currentTourIndex]);

  const handlePrevConcept = useCallback(() => {
    if (normalizedNodes.length === 0) return;
    const prevIdx = (currentTourIndex - 1 + normalizedNodes.length) % normalizedNodes.length;
    setSelectedNode(normalizedNodes[prevIdx]);
  }, [normalizedNodes, currentTourIndex]);

  // Reset Camera
  const handleResetCamera = useCallback(() => {
    if (controlsRef.current) {
      controlsRef.current.reset();
    }
  }, []);

  const incidentEdges = useMemo(() => {
    if (!selectedNode) return [];
    return edges
      .filter((e) => e.source === selectedNode.id || e.target === selectedNode.id)
      .map((e) => {
        const otherId = e.source === selectedNode.id ? e.target : e.source;
        const other = normalizedNodes.find((n) => n.id === otherId);
        return {
          otherLabel: other ? other.label : otherId === 'root' ? centerTitle : otherId,
          relation: e.relation,
          status: e.evidence_status || 'unverified',
        };
      });
  }, [edges, selectedNode, normalizedNodes, centerTitle]);

  const firstPassage = selectedNode?.sources.find((s) => s.passage)?.passage ?? null;
  const connectedLabels = incidentEdges
    .filter((ie) => ie.otherLabel !== centerTitle)
    .map((ie) => ie.otherLabel);

  const emptyMessage =
    graphData?.empty_reason === 'no_indexed_content'
      ? 'This document has no indexed content yet.'
      : 'No evidence-backed nodes are available for this view. Nothing is shown rather than inventing filler.';

  return (
    <section
      data-testid="concept-graph-3d-container"
      className="refire-card p-4 sm:p-5 space-y-4"
      aria-labelledby="orbit-view-heading"
    >
      {/* Header Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/8 pb-3">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#141d26] border border-[#d2434e]/40 text-[#d2434e]">
            <Compass className="h-4 w-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 id="orbit-view-heading" className="text-xs font-mono uppercase tracking-wider text-white font-semibold">
                3D Semantic Knowledge Orbit
              </h2>
              <span
                data-testid="orbit-node-count"
                className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-[#1b2734] text-[#a7d0d2] border border-[#4d728e]/30"
              >
                {normalizedNodes.length} nodes
              </span>
            </div>
          </div>
        </div>

        {/* Controls: Search, Play/Pause, Reset, 2D/3D Toggle, Help */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Search / Filter Input */}
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#98a6b0]" />
            <input
              data-testid="orbit-search-input"
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search orbit concepts..."
              className="h-7 w-36 sm:w-44 rounded bg-[#0b1219] border border-[#4d728e]/40 pl-8 pr-3 text-xs text-white placeholder-[#98a6b0]/60 focus:border-[#a7d0d2] focus:outline-none"
            />
          </div>

          {/* Play / Pause Rotation */}
          <button
            data-testid="orbit-play-pause"
            type="button"
            onClick={() => setIsPlaying(!isPlaying)}
            className="inline-flex items-center gap-1 rounded bg-[#141d26] border border-[#4d728e]/40 px-2.5 py-1 text-xs text-[#a7d0d2] hover:text-white hover:border-[#a7d0d2] transition-colors"
            title={isPlaying ? 'Pause orbital rotation' : 'Resume orbital rotation'}
          >
            {isPlaying ? <Pause className="h-3 w-3" /> : <Play className="h-3 w-3" />}
            <span>{isPlaying ? 'Pause' : 'Play'}</span>
          </button>

          {/* Reset Camera */}
          <button
            data-testid="orbit-reset"
            type="button"
            onClick={handleResetCamera}
            className="inline-flex items-center gap-1 rounded bg-[#141d26] border border-[#4d728e]/40 px-2.5 py-1 text-xs text-[#a7d0d2] hover:text-white hover:border-[#a7d0d2] transition-colors"
            title="Reset camera and rotation"
          >
            <RotateCcw className="h-3 w-3" />
            <span>Reset</span>
          </button>

          {/* 2D / 3D Mode Toggle */}
          {hasWebGL && (
            <button
              data-testid="orbit-toggle-2d"
              type="button"
              onClick={() => setUse2DMode(!use2DMode)}
              className="rounded bg-[#141d26] border border-[#4d728e]/40 px-2.5 py-1 text-xs text-[#98a6b0] hover:text-white hover:border-[#a7d0d2] transition-colors"
            >
              {use2DMode ? '3D View' : '2D View'}
            </button>
          )}

          {/* How to Read This Guide Button */}
          <button
            data-testid="orbit-help-btn"
            type="button"
            onClick={() => setShowHowToRead(!showHowToRead)}
            className="inline-flex items-center gap-1 rounded bg-[#141d26] border border-[#4d728e]/40 px-2.5 py-1 text-xs text-[#f59e0b] hover:text-white transition-colors"
            title="How to read this 3D orbit"
          >
            <HelpCircle className="h-3 w-3" />
            <span>Guide</span>
          </button>
        </div>
      </div>

      {/* In-app "How to Read This" Panel */}
      {showHowToRead && (
        <aside
          data-testid="orbit-how-to-read"
          className="rounded-lg border border-[#f59e0b]/40 bg-[#1f190e] p-4 text-xs space-y-2 relative"
        >
          <div className="flex items-center justify-between">
            <span className="font-semibold text-[#f59e0b] flex items-center gap-1.5 font-mono uppercase text-[11px]">
              <HelpCircle className="h-3.5 w-3.5" /> How to Read the 3D Knowledge Orbit
            </span>
            <button
              type="button"
              onClick={() => setShowHowToRead(false)}
              className="text-[#98a6b0] hover:text-white"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 pt-1 text-[#f3faf0]/85">
            <div className="rounded bg-black/30 p-2.5 border border-white/6">
              <span className="text-[#d2434e] font-semibold block mb-0.5">Centre</span>
              <span>The question (answer view) or the document (document view). Lines from the centre appear only where the data contains them.</span>
            </div>
            <div className="rounded bg-black/30 p-2.5 border border-white/6">
              <span className="text-[#a7d0d2] font-semibold block mb-0.5">Position</span>
              <span>Layout only. Distance and angle carry no meaning, so nothing is ranked by where it sits.</span>
            </div>
            <div className="rounded bg-black/30 p-2.5 border border-white/6">
              <span className="text-[#f59e0b] font-semibold block mb-0.5">Sphere size</span>
              <span>For document concepts, the number of chunks that contain the label. Other nodes have a uniform size.</span>
            </div>
            <div className="rounded bg-black/30 p-2.5 border border-white/6">
              <span className="text-[#10b981] font-semibold block mb-0.5">Lines and colours</span>
              <span>Solid lines are backed by retrieved or co-occurring evidence. Dashed lines are unverified or a model verdict. Colours group nodes by kind.</span>
            </div>
          </div>
        </aside>
      )}

      {/* Main Visual Canvas + Inspector Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* 3D WebGL Canvas or 2D Accessible Fallback */}
        <div className="lg:col-span-3 relative h-[520px] rounded-lg border border-white/8 bg-[#070b0f] overflow-hidden select-none">
          {normalizedNodes.length === 0 && (
            <div className="absolute inset-0 z-10 flex items-center justify-center p-6 text-center text-xs text-[#98a6b0]">
              <div className="space-y-1 max-w-sm">
                <Compass className="h-6 w-6 text-[#4d728e]/60 mx-auto" />
                <p className="text-white font-semibold">Nothing grounded to show</p>
                <p>{emptyMessage}</p>
              </div>
            </div>
          )}
          {use2DMode ? (
            <Accessible2DOrbitFallback
              nodes={normalizedNodes}
              edges={edges}
              centerTitle={centerTitle}
              selectedNode={selectedNode}
              searchQuery={searchQuery}
              onSelectNode={(n) => setSelectedNode(n)}
            />
          ) : (
            <>
              <Canvas
                camera={{ position: [0, 4.5, 9.5], fov: 48 }}
                gl={{ antialias: true, alpha: true }}
                className="w-full h-full cursor-grab active:cursor-grabbing"
              >
                <OrbitScene
                  nodes={normalizedNodes}
                  edges={edges}
                  centerTitle={centerTitle}
                  isPlaying={isPlaying}
                  selectedNodeId={selectedNode?.id || null}
                  hoveredNodeId={hoveredNode?.id || null}
                  searchQuery={searchQuery}
                  lodLimit={normalizedNodes.length > 50 ? 40 : 150} // Level-of-Detail limit
                  onSelectNode={(node) => setSelectedNode(node)}
                  onHoverNode={(node) => setHoveredNode(node)}
                  controlsRef={controlsRef}
                />
              </Canvas>

              {/* Floating Hover Tooltip */}
              {hoveredNode && hoveredNode.id !== 'center' && (
                <div
                  data-testid="orbit-hover-tooltip"
                  className="absolute top-4 left-4 pointer-events-none rounded-lg bg-[#0b1219]/90 border border-[#a7d0d2]/50 p-2.5 shadow-xl backdrop-blur-md text-xs space-y-1"
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-semibold text-white">{hoveredNode.label}</span>
                    <span className="font-mono text-[10px] text-[#a7d0d2]">{hoveredNode.kind}</span>
                  </div>
                  <div className="flex items-center gap-3 text-[10px] text-[#98a6b0] font-mono">
                    <span>{hoveredNode.sources.length} source(s)</span>
                    <span>{hoveredNode.mentionCount !== null ? `${hoveredNode.mentionCount} mention(s)` : 'mentions not measured'}</span>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Selected Node Details & Sources Panel */}
        <aside
          data-testid="orbit-inspector"
          className="rounded-lg border border-white/8 bg-[#0b1219] p-4 flex flex-col justify-between space-y-4 h-[520px] overflow-y-auto"
        >
          {selectedNode ? (
            <div className="space-y-3.5">
              {/* Header with Cluster & Evidence Status */}
              <div className="border-b border-white/8 pb-2.5">
                <div className="flex items-center justify-between gap-1 mb-1">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-[#d2434e]">
                    Concept Inspector
                  </span>
                  <div className="flex items-center gap-1">
                    <span className="rounded px-2 py-0.5 text-[10px] font-mono bg-[#141d26] text-[#a7d0d2] border border-[#4d728e]/40">
                      {selectedNode.kind}
                    </span>
                  </div>
                </div>
                <h3
                  data-testid="orbit-node-title"
                  className="text-sm font-semibold text-white leading-snug"
                >
                  {selectedNode.label}
                </h3>

                {/* Concept Tour Navigation (Requirement 3) */}
                <div className="flex items-center justify-between mt-2 pt-2 border-t border-white/5 text-[10px] text-[#f3faf0]/60">
                  <span>Concept {currentTourIndex + 1} of {normalizedNodes.length}</span>
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={handlePrevConcept}
                      className="px-2 py-0.5 rounded bg-[#141d26] hover:bg-[#1b2632] border border-white/10 text-white cursor-pointer"
                    >
                      ← Prev
                    </button>
                    <button
                      type="button"
                      onClick={handleNextConcept}
                      className="px-2 py-0.5 rounded bg-[#141d26] hover:bg-[#1b2632] border border-[#a7d0d2]/40 text-[#a7d0d2] hover:text-white cursor-pointer"
                    >
                      Next →
                    </button>
                  </div>
                </div>
              </div>

              {/* Tabbed Inspector Navigation */}
              <div className="grid grid-cols-3 gap-1 p-1 bg-[#101720] rounded-lg border border-white/8 text-[11px] font-mono">
                <button
                  type="button"
                  onClick={() => setActiveInspectorTab('details')}
                  className={tabClass(activeInspectorTab === 'details')}
                  title="What this node is"
                >
                  <FileText className="w-3 h-3" />
                  <span>Details</span>
                </button>
                <button
                  type="button"
                  onClick={() => setActiveInspectorTab('sources')}
                  className={tabClass(activeInspectorTab === 'sources')}
                  title="Source passages attached to this node"
                >
                  <Bookmark className="w-3 h-3" />
                  <span>Sources</span>
                </button>
                <button
                  type="button"
                  onClick={() => setActiveInspectorTab('evidence')}
                  className={tabClass(activeInspectorTab === 'evidence')}
                  title="Evidence status of this node and its connections"
                >
                  <ShieldCheck className="w-3 h-3" />
                  <span>Evidence</span>
                </button>
              </div>

              {/* TAB 1: DETAILS */}
              {activeInspectorTab === 'details' && (
                <div className="space-y-2.5 text-[11px]">
                  <div className="p-2.5 rounded-lg bg-[#141d26]/80 border border-white/5 space-y-1">
                    <p className="font-medium text-[#a7d0d2] leading-snug">{selectedNode.kind}</p>
                    <p className="text-[#f3faf0]/75 leading-relaxed">{describeNodeOrigin(selectedNode.origin)}</p>
                    {selectedNode.detail && (
                      <p className="text-[#f3faf0]/75 leading-relaxed">{selectedNode.detail}</p>
                    )}
                  </div>

                  <div className="p-2.5 rounded-lg bg-[#0e1620] border border-white/5 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="flex items-center gap-1.5 text-[#98a6b0]">
                        <BarChart3 className="h-3 w-3" />
                        Mention count
                      </span>
                      <span className="font-mono text-[#a7d0d2]">
                        {selectedNode.mentionCount !== null ? selectedNode.mentionCount : 'not measured'}
                      </span>
                    </div>
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-[#98a6b0]">Where it appears</span>
                      <span className="font-mono text-[#a7d0d2] text-right">
                        {summarizePages(selectedNode.sources || [])}
                      </span>
                    </div>
                  </div>

                  {firstPassage && (
                    <div className="p-2.5 rounded-lg bg-[#111922] border border-white/5 space-y-1">
                      <span className="font-semibold text-[#a7d0d2] font-mono text-[10px] uppercase block">
                        Example in the text
                      </span>
                      <p className="text-[#f3faf0]/80 italic leading-relaxed">
                        "{highlightPassage(firstPassage, selectedNode.label)}"
                      </p>
                    </div>
                  )}

                  {connectedLabels.length > 0 && (
                    <div className="p-2.5 rounded-lg bg-[#111922] border border-white/5 space-y-1">
                      <span className="font-semibold text-[#a7d0d2] font-mono text-[10px] uppercase block">
                        Connected concepts
                      </span>
                      <p className="text-[#f3faf0]/80 leading-relaxed">{connectedLabels.join(', ')}</p>
                    </div>
                  )}

                  {selectedNode.url && (
                    <div className="pt-1">
                      <a
                        href={selectedNode.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1.5 text-[11px] text-[#a7d0d2] hover:text-white underline font-mono"
                      >
                        <ExternalLink className="h-3 w-3" />
                        Open external source ({selectedNode.url.slice(0, 32)}...)
                      </a>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 2: SOURCES */}
              {activeInspectorTab === 'sources' && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-xs font-semibold text-white pb-1 border-b border-white/5">
                    <div className="flex items-center gap-1.5">
                      <Bookmark className="h-3.5 w-3.5 text-[#a7d0d2]" />
                      <span>Source passages</span>
                    </div>
                    {onOpenSources && (
                      <button
                        type="button"
                        onClick={onOpenSources}
                        className="text-[10px] text-[#a7d0d2] hover:text-white flex items-center gap-1 font-mono"
                      >
                        <ExternalLink className="h-3 w-3" />
                        View All
                      </button>
                    )}
                  </div>

                  {selectedNode.sources && selectedNode.sources.length > 0 ? (
                    <div className="space-y-2 max-h-[260px] overflow-y-auto pr-1">
                      {selectedNode.sources.map((src, i) => (
                        <div
                          key={`src-${i}`}
                          data-testid="orbit-source-item"
                          className="rounded border border-white/6 bg-[#141d26]/80 p-2.5 space-y-1.5 text-xs"
                        >
                          <div className="flex items-center justify-between text-[10px] font-mono text-[#a7d0d2]">
                            <span className="truncate max-w-[130px] font-semibold">{src.document || centerTitle}</span>
                            <span className="text-[#98a6b0]">
                              {src.page !== null && src.page !== undefined && src.page !== '' ? `Page ${src.page}` : 'Page unknown'}
                            </span>
                          </div>
                          {src.passage ? (
                            <blockquote
                              data-testid="orbit-passage-text"
                              className="text-[11px] text-[#f3faf0]/80 italic border-l-2 border-[#a7d0d2]/40 pl-2 leading-relaxed"
                            >
                              "{src.passage}"
                            </blockquote>
                          ) : (
                            <p className="text-[10px] text-[#98a6b0] italic">
                              Passage text not returned{src.chunk_id ? ` (chunk ${src.chunk_id})` : ''}.
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-[#98a6b0] italic py-3 text-center">
                      No source passages are attached to this node.
                    </p>
                  )}
                </div>
              )}

              {/* TAB 3: EVIDENCE */}
              {activeInspectorTab === 'evidence' && (
                <div className="space-y-2 text-xs">
                  <div className="p-2.5 rounded-lg bg-[#141d26]/90 border border-white/6 space-y-1.5 text-[11px]">
                    <span className="text-[10px] font-mono uppercase text-[#a7d0d2] font-semibold block">
                      Where this node comes from
                    </span>
                    <p className="text-[#f3faf0]/80 leading-relaxed">{describeNodeOrigin(selectedNode.origin)}</p>
                    <p className="text-[#98a6b0]">
                      Source passages attached:{' '}
                      <span className="font-mono text-[#a7d0d2]">{selectedNode.sources?.length || 0}</span>
                    </p>
                  </div>

                  <div className="p-2.5 rounded-lg bg-[#0e1620] border border-white/5 space-y-2">
                    <span className="text-[10px] font-mono uppercase text-[#98a6b0] block">Connections</span>
                    {incidentEdges.length > 0 ? (
                      incidentEdges.map((ie, i) => (
                        <div key={`inc-${i}`} className="text-[11px] leading-snug">
                          <p className="text-[#f3faf0]/85">{describeConnection(ie.status, ie.relation, ie.otherLabel)}</p>
                          <p className="text-[10px] text-[#98a6b0]">{describeEvidenceStatus(ie.status)}</p>
                        </div>
                      ))
                    ) : (
                      <p className="text-[11px] text-[#98a6b0] italic">No connections in the data for this node.</p>
                    )}
                  </div>

                  {incidentEdges.some((ie) => ie.status === 'co_occurrence' || ie.status === 'relation_term_present') && (
                    <p className="text-[10px] text-[#98a6b0] italic">
                      Appearing in the same chunk shows the concepts occur together. It does not prove the stated relationship.
                    </p>
                  )}

                  <p className="text-[10px] text-[#98a6b0] italic">
                    No per-node confidence score is shown because none is measured.
                  </p>
                </div>
              )}
            </div>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-center text-xs text-[#98a6b0] space-y-2">
              <Compass className="h-6 w-6 text-[#4d728e]/50" />
              <p>Click any orbiting concept node to inspect its structural definitions and cited passages.</p>
            </div>
          )}

          {/* Quick instructions footer */}
          <div className="border-t border-white/8 pt-2 text-[10px] text-[#98a6b0] flex items-center justify-between">
            <span>Drag to rotate</span>
            <span>Scroll to zoom</span>
          </div>
        </aside>
      </div>
    </section>
  );
};

export default ConceptGraph3D;
