import React, { useState } from 'react';
import { Dna, Wrench, Lightbulb, AlertCircle, GitFork, BookOpen, Layers, CheckCircle2, ChevronRight } from 'lucide-react';
import type { KnowledgeDNA as KnowledgeDNAData } from '../../types/knowledge';

interface KnowledgeDNAProps {
  data: KnowledgeDNAData;
}

export const KnowledgeDNA: React.FC<KnowledgeDNAProps> = ({ data }) => {
  const [activeTab, setActiveTab] = useState<'concepts' | 'methods' | 'limitations' | 'relationships'>('concepts');

  const coreTopics = data.coreTopics || [];
  const keyConcepts = data.keyConcepts || [];
  const methods = data.methods || [];
  const findings = data.findings || [];
  const limitations = data.limitations || [];
  const themes = data.themes || data.researchThemes || [];
  const relationships = data.relationships || [];

  // Generate visual nodes for SVG topology
  const allSignals: Array<{ id: string; name: string; type: string; color: string; x: number; y: number }> = [];
  const nodeTypes = [
    { items: coreTopics.slice(0, 3), type: 'TOPIC', color: '#3b82f6' },
    { items: keyConcepts.slice(0, 4), type: 'CONCEPT', color: '#10b981' },
    { items: methods.slice(0, 3), type: 'METHOD', color: '#f59e0b' },
    { items: findings.slice(0, 3), type: 'FINDING', color: '#8b5cf6' },
    { items: limitations.slice(0, 2), type: 'LIMITATION', color: '#ef4444' },
  ];

  let nodeIndex = 0;
  const totalNodes = nodeTypes.reduce((acc, t) => acc + t.items.length, 0);
  const centerX = 350;
  const centerY = 160;
  const radius = 120;

  nodeTypes.forEach((group) => {
    group.items.forEach((name) => {
      const angle = (nodeIndex / (totalNodes || 1)) * 2 * Math.PI;
      const x = centerX + Math.cos(angle) * radius;
      const y = centerY + Math.sin(angle) * (radius * 0.75);
      allSignals.push({
        id: `node_${nodeIndex}`,
        name: typeof name === 'string' ? name : String(name),
        type: group.type,
        color: group.color,
        x,
        y,
      });
      nodeIndex++;
    });
  });

  return (
    <section className="refire-card p-5 sm:p-6 space-y-6" aria-labelledby="knowledge-dna-title">
      {/* Header with Research Area */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/8 pb-4">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#d2434e]/15 border border-[#d2434e]/30">
            <Dna className="h-4 w-4 text-[#d2434e]" />
          </div>
          <div>
            <h2 id="knowledge-dna-title" className="text-sm font-semibold text-white tracking-wide">
              Knowledge DNA Architecture
            </h2>
            <p className="text-[11px] text-[#f3faf0]/55">
              Multi-dimensional ontology extracting topics, methodologies, findings, and constraints.
            </p>
          </div>
        </div>

        {data.researchArea && (
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono uppercase text-[#a7d0d2]">Research Area:</span>
            <span className="rounded-full border border-[#a7d0d2]/40 bg-[#a7d0d2]/15 px-3 py-1 text-xs font-mono font-semibold text-[#a7d0d2]">
              {data.researchArea}
            </span>
          </div>
        )}
      </div>

      {/* 6 Metric Highlight Cards */}
      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-6">
        <div className="rounded-xl border border-blue-500/30 bg-blue-500/10 p-3 text-center">
          <p className="text-[10px] font-mono uppercase text-blue-400">Core Topics</p>
          <p className="mt-1 text-2xl font-black text-white">{coreTopics.length}</p>
        </div>
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-center">
          <p className="text-[10px] font-mono uppercase text-emerald-400">Key Concepts</p>
          <p className="mt-1 text-2xl font-black text-white">{keyConcepts.length}</p>
        </div>
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-center">
          <p className="text-[10px] font-mono uppercase text-amber-400">Methods</p>
          <p className="mt-1 text-2xl font-black text-white">{methods.length}</p>
        </div>
        <div className="rounded-xl border border-purple-500/30 bg-purple-500/10 p-3 text-center">
          <p className="text-[10px] font-mono uppercase text-purple-400">Findings</p>
          <p className="mt-1 text-2xl font-black text-white">{findings.length}</p>
        </div>
        <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-center">
          <p className="text-[10px] font-mono uppercase text-rose-400">Limitations</p>
          <p className="mt-1 text-2xl font-black text-white">{limitations.length}</p>
        </div>
        <div className="rounded-xl border border-[#a7d0d2]/30 bg-[#a7d0d2]/10 p-3 text-center">
          <p className="text-[10px] font-mono uppercase text-[#a7d0d2]">Themes</p>
          <p className="mt-1 text-2xl font-black text-white">{themes.length}</p>
        </div>
      </div>

      {/* Interactive Visual Topology Canvas */}
      {allSignals.length > 0 && (
        <div className="rounded-xl border border-[#4d728e]/30 bg-[#070b0f] p-4">
          <div className="mb-2 flex items-center justify-between text-xs text-[#a7d0d2]">
            <span className="font-mono text-[11px] uppercase">Knowledge DNA Topology Graph</span>
            <div className="flex items-center gap-3 text-[10px] font-mono">
              <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-[#3b82f6]" /> Topic</span>
              <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-[#10b981]" /> Concept</span>
              <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-[#f59e0b]" /> Method</span>
              <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-[#8b5cf6]" /> Finding</span>
              <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-[#ef4444]" /> Limitation</span>
            </div>
          </div>
          <div className="w-full overflow-x-auto">
            <svg viewBox="0 0 700 320" className="w-full min-w-[500px] h-64 select-none">
              <defs>
                <radialGradient id="dnaCoreGlow" cx="50%" cy="50%" r="50%">
                  <stop offset="0%" stopColor="#d2434e" stopOpacity="0.4" />
                  <stop offset="100%" stopColor="#d2434e" stopOpacity="0" />
                </radialGradient>
              </defs>
              {/* Central Hub Core */}
              <circle cx={centerX} cy={centerY} r="50" fill="url(#dnaCoreGlow)" />
              <circle cx={centerX} cy={centerY} r="28" fill="#141d26" stroke="#d2434e" strokeWidth="2" />
              <text x={centerX} y={centerY + 4} textAnchor="middle" fill="#ffffff" fontSize="10" fontWeight="bold" fontFamily="monospace">
                DNA CORE
              </text>

              {/* Connecting lines to satellites */}
              {allSignals.map((node) => (
                <line
                  key={`line_${node.id}`}
                  x1={centerX}
                  y1={centerY}
                  x2={node.x}
                  y2={node.y}
                  stroke={node.color}
                  strokeOpacity="0.35"
                  strokeWidth="1.5"
                  strokeDasharray="3 3"
                />
              ))}

              {/* Satellite Nodes */}
              {allSignals.map((node) => (
                <g key={`group_${node.id}`} className="cursor-pointer transition-transform hover:scale-110">
                  <circle cx={node.x} cy={node.y} r="16" fill="#0b1219" stroke={node.color} strokeWidth="2" />
                  <text
                    x={node.x}
                    y={node.y + 3}
                    textAnchor="middle"
                    fill={node.color}
                    fontSize="8"
                    fontWeight="bold"
                    fontFamily="monospace"
                  >
                    {node.type[0]}
                  </text>
                  <text
                    x={node.x}
                    y={node.y + 24}
                    textAnchor="middle"
                    fill="#f3faf0"
                    fontSize="9"
                    fontWeight="500"
                    className="truncate"
                  >
                    {node.name.length > 18 ? `${node.name.slice(0, 16)}...` : node.name}
                  </text>
                </g>
              ))}
            </svg>
          </div>
        </div>
      )}

      {/* Tabs Navigation */}
      <div className="flex border-b border-white/8 text-xs">
        <button
          type="button"
          onClick={() => setActiveTab('concepts')}
          className={`flex items-center gap-1.5 border-b-2 px-4 py-2.5 font-medium transition-colors ${
            activeTab === 'concepts'
              ? 'border-[#a7d0d2] text-white'
              : 'border-transparent text-[#f3faf0]/55 hover:text-white'
          }`}
        >
          <BookOpen className="h-3.5 w-3.5" />
          <span>Topics & Concepts ({coreTopics.length + keyConcepts.length})</span>
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('methods')}
          className={`flex items-center gap-1.5 border-b-2 px-4 py-2.5 font-medium transition-colors ${
            activeTab === 'methods'
              ? 'border-[#a7d0d2] text-white'
              : 'border-transparent text-[#f3faf0]/55 hover:text-white'
          }`}
        >
          <Wrench className="h-3.5 w-3.5" />
          <span>Methods & Findings ({methods.length + findings.length})</span>
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('limitations')}
          className={`flex items-center gap-1.5 border-b-2 px-4 py-2.5 font-medium transition-colors ${
            activeTab === 'limitations'
              ? 'border-[#a7d0d2] text-white'
              : 'border-transparent text-[#f3faf0]/55 hover:text-white'
          }`}
        >
          <AlertCircle className="h-3.5 w-3.5" />
          <span>Limitations & Themes ({limitations.length + themes.length})</span>
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('relationships')}
          className={`flex items-center gap-1.5 border-b-2 px-4 py-2.5 font-medium transition-colors ${
            activeTab === 'relationships'
              ? 'border-[#a7d0d2] text-white'
              : 'border-transparent text-[#f3faf0]/55 hover:text-white'
          }`}
        >
          <GitFork className="h-3.5 w-3.5" />
          <span>Relationships ({relationships.length})</span>
        </button>
      </div>

      {/* Tab Panels */}
      {activeTab === 'concepts' && (
        <div className="grid gap-6 md:grid-cols-2">
          <div className="space-y-3">
            <h3 className="text-xs font-mono uppercase text-[#a7d0d2] flex items-center gap-1.5">
              <Layers className="h-3.5 w-3.5" /> Core Topics
            </h3>
            <div className="flex flex-wrap gap-2">
              {coreTopics.length > 0 ? (
                coreTopics.map((topic, i) => (
                  <span
                    key={i}
                    className="rounded-lg border border-blue-500/30 bg-blue-500/10 px-3 py-1.5 text-xs font-medium text-blue-200"
                  >
                    {topic}
                  </span>
                ))
              ) : (
                <p className="text-xs text-[#f3faf0]/50">No core topics recorded.</p>
              )}
            </div>
          </div>

          <div className="space-y-3">
            <h3 className="text-xs font-mono uppercase text-emerald-400 flex items-center gap-1.5">
              <CheckCircle2 className="h-3.5 w-3.5" /> Key Concepts
            </h3>
            <div className="flex flex-wrap gap-2">
              {keyConcepts.length > 0 ? (
                keyConcepts.map((concept, i) => (
                  <span
                    key={i}
                    className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-1.5 text-xs font-medium text-emerald-200"
                  >
                    {concept}
                  </span>
                ))
              ) : (
                <p className="text-xs text-[#f3faf0]/50">No key concepts recorded.</p>
              )}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'methods' && (
        <div className="grid gap-6 md:grid-cols-2">
          <div className="space-y-3">
            <h3 className="text-xs font-mono uppercase text-amber-400 flex items-center gap-1.5">
              <Wrench className="h-3.5 w-3.5" /> Research Methodologies
            </h3>
            {methods.length > 0 ? (
              <ul className="space-y-2">
                {methods.map((method, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-xs text-[#f3faf0]/85 leading-relaxed rounded-lg bg-[#141d26]/40 p-2.5 border border-white/5">
                    <ChevronRight className="h-3.5 w-3.5 text-amber-400 shrink-0 mt-0.5" />
                    <span>{method}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-[#f3faf0]/50">No methods reported.</p>
            )}
          </div>

          <div className="space-y-3">
            <h3 className="text-xs font-mono uppercase text-purple-400 flex items-center gap-1.5">
              <Lightbulb className="h-3.5 w-3.5" /> Empirical Findings
            </h3>
            {findings.length > 0 ? (
              <ul className="space-y-2">
                {findings.map((finding, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-xs text-[#f3faf0]/85 leading-relaxed rounded-lg bg-[#141d26]/40 p-2.5 border border-white/5">
                    <span className="text-purple-400 font-bold shrink-0">✅</span>
                    <span>{finding}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-[#f3faf0]/50">No empirical findings reported.</p>
            )}
          </div>
        </div>
      )}

      {activeTab === 'limitations' && (
        <div className="grid gap-6 md:grid-cols-2">
          <div className="space-y-3">
            <h3 className="text-xs font-mono uppercase text-rose-400 flex items-center gap-1.5">
              <AlertCircle className="h-3.5 w-3.5" /> Reported Limitations
            </h3>
            {limitations.length > 0 ? (
              <ul className="space-y-2">
                {limitations.map((limit, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-xs text-[#f3faf0]/85 leading-relaxed rounded-lg bg-[#141d26]/40 p-2.5 border border-white/5">
                    <span className="text-rose-400 font-bold shrink-0">⚠️</span>
                    <span>{limit}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-[#f3faf0]/50">No limitations reported.</p>
            )}
          </div>

          <div className="space-y-3">
            <h3 className="text-xs font-mono uppercase text-[#a7d0d2] flex items-center gap-1.5">
              <Layers className="h-3.5 w-3.5" /> Synthesized Themes
            </h3>
            {themes.length > 0 ? (
              <ul className="space-y-2">
                {themes.map((theme, idx) => (
                  <li key={idx} className="border-l-2 border-[#a7d0d2] pl-3 py-1 text-xs text-[#f3faf0]/80">
                    {theme}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-[#f3faf0]/50">No synthesized themes recorded.</p>
            )}
          </div>
        </div>
      )}

      {activeTab === 'relationships' && (
        <div className="space-y-3">
          <h3 className="text-xs font-mono uppercase text-[#d2434e] flex items-center gap-1.5">
            <GitFork className="h-3.5 w-3.5" /> Signal & Concept Relationships
          </h3>
          {relationships.length > 0 ? (
            <div className="grid gap-2 sm:grid-cols-2">
              {relationships.map((rel, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between gap-2 rounded-lg border border-white/5 bg-[#141d26]/60 px-3 py-2 text-xs"
                >
                  <span className="font-semibold text-white truncate">{rel.source}</span>
                  <span className="text-[10px] font-mono text-[#a7d0d2] px-2 py-0.5 rounded bg-[#a7d0d2]/10 border border-[#a7d0d2]/20 shrink-0">
                    {rel.relationship}
                  </span>
                  <span className="font-semibold text-[#f3faf0]/90 truncate">{rel.target}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-[#f3faf0]/50">No inter-signal relationships recorded.</p>
          )}
        </div>
      )}
    </section>
  );
};