import React, { useState } from 'react';
import { Network } from 'lucide-react';
import type { MindMapNode } from '../../types/knowledge';

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
  return (
    <section className="refire-card p-5" aria-labelledby="mind-map-title">
      <div className="flex items-center gap-2"><Network className="h-4 w-4 text-[#a7d0d2]" /><h2 id="mind-map-title" className="text-xs font-mono uppercase text-[#f3faf0]/75">Knowledge mind map</h2></div>
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