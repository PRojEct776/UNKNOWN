import React, { useState } from 'react';
import { ArrowUpRight, Check, Copy, FileText } from 'lucide-react';
import type { Evidence } from '../../types/evidence';

interface EvidenceCardProps {
  evidence: Evidence;
  onOpenSource?: () => void;
}

export const EvidenceCard: React.FC<EvidenceCardProps> = ({ evidence, onOpenSource }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    const textToCopy = `"${evidence.text}" — ${evidence.documentName} (Page ${evidence.page ?? 1})`;
    void navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <article className="rounded-lg border border-white/8 bg-[#0b1219]/70 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex items-center gap-2 text-sm font-semibold text-white">
            <FileText className="h-3.5 w-3.5 shrink-0 text-[#a7d0d2]" aria-hidden="true" />
            <span className="break-all">{evidence.documentName}</span>
          </p>
          <p className="mt-1 text-[11px] text-[#f3faf0]/50">
            {evidence.page !== undefined ? `Page ${evidence.page}` : 'Page not specified'}
            {evidence.chunkId ? ` · Chunk ${evidence.chunkId}` : ''}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleCopy}
            className="flex items-center gap-1 rounded bg-[#141d26] border border-white/10 px-2 py-0.5 text-[10px] font-mono text-[#a7d0d2] hover:text-white transition-colors cursor-pointer"
            title="Copy evidence passage and citation"
          >
            {copied ? <Check className="h-2.5 w-2.5 text-emerald-400" /> : <Copy className="h-2.5 w-2.5" />}
            <span>{copied ? 'Copied!' : 'Copy'}</span>
          </button>
          <div className="flex gap-2 font-mono text-[10px] text-[#a7d0d2]">
            {typeof evidence.score === 'number' && Number.isFinite(evidence.score) && (
              <span>Score {evidence.score.toFixed(2)}</span>
            )}
            {typeof evidence.relevance === 'number' && Number.isFinite(evidence.relevance) && (
              <span>Relevance {Math.round(evidence.relevance * 100)}%</span>
            )}
          </div>
        </div>
      </div>
      <blockquote className="mt-3 border-l-2 border-[#607787] pl-3 text-sm leading-6 text-[#d1d9df]">
        “{evidence.text}”
      </blockquote>
      {onOpenSource && (
        <button type="button" onClick={onOpenSource} className="mt-3 inline-flex items-center gap-1 text-[11px] text-[#a7d0d2] hover:text-white cursor-pointer">
          Open source details <ArrowUpRight className="h-3 w-3" aria-hidden="true" />
        </button>
      )}
    </article>
  );
};