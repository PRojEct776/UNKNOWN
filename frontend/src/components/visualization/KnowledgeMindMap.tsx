import React, { useState } from 'react';
import { Network, Download } from 'lucide-react';
import type { MindMapNode } from '../../types/knowledge';
import { generateMindMapSvg, downloadSvgFile, downloadSvgAsPngFile } from '../../lib/exportUtils';

interface KnowledgeMindMapProps {
  root: MindMapNode;
}

const MindMapBranch: React.FC<{ node: MindMapNode; onSelect: (node: MindMapNode) => void }> = ({ node, onSelect }) => (
  <div className="min-w-36">
    <button type="button" onClick={() => onSelect(node)} className="w-full rounded-lg border border-[#4d728e]/40 bg-[#0b1219] px-3 py-2 text-left text-xs font-medium text-white transition-colors hover:border-[#a7d0d2]">
      {node.label}
    </button>
    {node.children && node.children.length > 0 && (
      <div className="ml-4 mt-2 space-y-2 border-l border-[#4d728e]/50 pl-3">
        {node.children.map((child) => <MindMapBranch key={child.id} node={child} onSelect={onSelect} />)}
      </div>
    )}
  </div>
);

export const KnowledgeMindMap: React.FC<KnowledgeMindMapProps> = ({ root }) => {
  const [selected, setSelected] = useState(root);
  const [isExporting, setIsExporting] = useState<'svg' | 'png' | null>(null);

  const handleDownloadSvg = () => {
    try {
      const svg = generateMindMapSvg(root);
      const safeTitle = (root?.label || 'mind_map').replace(/[^a-zA-Z0-9_-]/g, '_');
      downloadSvgFile(`unknown_mindmap_${safeTitle}_${Date.now()}.svg`, svg, 'researcher', root?.label || 'Mind Map');
    } catch (err) {
      console.error('Failed to export Mind Map SVG:', err);
    }
  };

  const handleDownloadPng = async () => {
    try {
      setIsExporting('png');
      const svg = generateMindMapSvg(root);
      const safeTitle = (root?.label || 'mind_map').replace(/[^a-zA-Z0-9_-]/g, '_');
      const numBranches = Math.max(root?.children?.length || 1, 1);
      const width = Math.max(860, numBranches * 234 + 80);
      await downloadSvgAsPngFile(`unknown_mindmap_${safeTitle}_${Date.now()}.png`, svg, width, 520, 'researcher', root?.label || 'Mind Map');
    } catch (err) {
      console.error('Failed to export Mind Map PNG:', err);
    } finally {
      setIsExporting(null);
    }
  };

  return (
    <section className="refire-card p-5" aria-labelledby="mind-map-title">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/8 pb-3">
        <div className="flex items-center gap-2">
          <Network className="h-4 w-4 text-[#a7d0d2]" />
          <h2 id="mind-map-title" className="text-xs font-mono uppercase text-[#f3faf0]/75">Knowledge mind map</h2>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={handleDownloadSvg}
            className="inline-flex items-center gap-1 rounded bg-[#141d26] border border-[#4d728e]/40 px-2.5 py-1 text-[11px] font-mono text-[#a7d0d2] hover:text-white hover:border-[#a7d0d2] transition-colors cursor-pointer"
            title="Download standalone vector SVG"
          >
            <Download className="h-3 w-3" />
            <span>SVG</span>
          </button>
          <button
            type="button"
            onClick={() => void handleDownloadPng()}
            disabled={isExporting === 'png'}
            className="inline-flex items-center gap-1 rounded bg-[#141d26] border border-[#4d728e]/40 px-2.5 py-1 text-[11px] font-mono text-[#a7d0d2] hover:text-white hover:border-[#a7d0d2] transition-colors cursor-pointer disabled:opacity-50"
            title="Download high-resolution raster PNG"
          >
            <Download className="h-3 w-3" />
            <span>{isExporting === 'png' ? 'PNG...' : 'PNG'}</span>
          </button>
        </div>
      </div>
      <div className="mt-5 overflow-x-auto pb-2">
        <div className="flex min-w-max flex-col items-center gap-3">
          <button type="button" onClick={() => setSelected(root)} className="rounded-lg border border-[#d2434e]/60 bg-[#d2434e]/10 px-5 py-3 text-sm font-semibold text-white">{root.label}</button>
          {root.description && <p className="max-w-xs text-center text-[10px] text-[#f3faf0]/50">{root.description}</p>}
          <div className="h-5 border-l border-[#4d728e]/50" />
          <div className="flex items-start gap-4 border-t border-[#4d728e]/50 pt-3">
            {(root.children || []).map((branch) => <MindMapBranch key={branch.id} node={branch} onSelect={setSelected} />)}
          </div>
        </div>
      </div>
      <div className="mt-4 border-t border-white/8 pt-3" aria-live="polite">
        <p className="text-[10px] font-mono uppercase text-[#d2434e]">Selected node</p>
        <p className="mt-1 text-sm font-semibold text-white">{selected.label}</p>
        {selected.description && <p className="mt-1 text-xs text-[#f3faf0]/60">{selected.description}</p>}
      </div>
    </section>
  );
};