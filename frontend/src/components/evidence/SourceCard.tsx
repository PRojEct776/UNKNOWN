import React, { useState } from 'react';
import { Award, Check, Copy, Layers } from 'lucide-react';
import type { Evidence, Source } from '../../types/evidence';

interface SourceCardProps {
  source: Source;
  evidence: Evidence[];
  index?: number;
}

export const SourceCard: React.FC<SourceCardProps> = ({ source, evidence, index }) => {
  const [copied, setCopied] = useState(false);

  const handleCopyCitation = () => {
    const textToCopy = `${source.documentName}, Page ${source.page ?? 1} (Chunk: ${source.chunkId || 'N/A'})${evidence.length ? ' — "' + evidence[0].text + '"' : ''}`;
    void navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
  <article className="rounded-xl border border-[#4d728e]/30 bg-[#0b1219]/90 p-4 transition-all hover:border-[#a7d0d2]/50 shadow-sm">
    <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
      <div className="flex items-start gap-3 min-w-0">
        <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-[#141d26] border border-[#4d728e]/40 text-xs font-mono font-bold text-[#d2434e]">
          {source.rank ?? (index !== undefined ? index + 1 : '#')}
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="break-all text-sm font-semibold text-white hover:text-[#a7d0d2] transition-colors">
              {source.documentName}
            </h3>
            {source.page !== undefined && source.page !== null && (
              <span className="rounded-md border border-white/10 bg-white/5 px-2 py-0.5 text-[11px] font-mono text-[#a7d0d2]">
                Page {source.page}
              </span>
            )}
            {source.chunkId && (
              <span className="rounded-md border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] font-mono text-[#f3faf0]/60">
                Chunk: {source.chunkId}
              </span>
            )}
            <button
              type="button"
              onClick={handleCopyCitation}
              className="inline-flex items-center gap-1 rounded bg-[#141d26] border border-white/10 px-2 py-0.5 text-[10px] font-mono text-[#a7d0d2] hover:text-white transition-colors cursor-pointer"
              title="Copy citation string"
            >
              {copied ? <Check className="h-2.5 w-2.5 text-emerald-400" /> : <Copy className="h-2.5 w-2.5" />}
              <span>{copied ? 'Copied!' : 'Copy Citation'}</span>
            </button>
          </div>
          <p className="mt-1 text-xs text-[#f3faf0]/55 flex items-center gap-1.5">
            <Layers className="h-3 w-3 text-[#a7d0d2]" />
            <span>{source.evidenceCount ?? evidence.length} evidence {evidence.length === 1 ? 'passage' : 'passages'}</span>
          </p>
        </div>
      </div>

      {/* Retrieval Scores Row */}
      <div className="flex flex-wrap sm:flex-col sm:items-end gap-1.5 shrink-0 pt-1 sm:pt-0">
        {typeof source.score === 'number' && Number.isFinite(source.score) && (
          <span className="inline-flex items-center gap-1 rounded-md border border-emerald-400/30 bg-emerald-500/15 px-2.5 py-1 text-xs font-mono font-semibold text-emerald-300">
            <Award className="h-3 w-3" />
            Hybrid: {source.score.toFixed(3)}
          </span>
        )}
        <div className="flex items-center gap-1.5 text-[10px] font-mono">
          {typeof source.bm25Score === 'number' && Number.isFinite(source.bm25Score) && (
            <span className="rounded border border-sky-400/30 bg-sky-500/10 px-1.5 py-0.5 text-sky-300">
              BM25: {source.bm25Score.toFixed(3)}
            </span>
          )}
          {typeof source.faissScore === 'number' && Number.isFinite(source.faissScore) && (
            <span className="rounded border border-purple-400/30 bg-purple-500/10 px-1.5 py-0.5 text-purple-300">
              FAISS: {source.faissScore.toFixed(3)}
            </span>
          )}
        </div>
      </div>
    </div>

    {/* Excerpt Evidence Passages */}
    {evidence.length > 0 && (
      <div className="mt-3 space-y-2 border-t border-white/5 pt-3">
        {evidence.map((item, idx) => (
          <div key={item.id || idx} className="rounded-lg bg-[#141d26]/60 border border-white/5 p-2.5 text-xs text-[#f3faf0]/85 leading-relaxed">
            <p className="italic text-[#c1cbd2]">"{item.text}"</p>
          </div>
        ))}
      </div>
    )}
  </article>
  );
};