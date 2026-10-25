import React, { useState } from 'react';
import {
  ExternalLink,
  AlertTriangle,
  FileText,
  Globe,
  GraduationCap,
  Check,
  Copy,
  ShieldAlert,
  Quote,
} from 'lucide-react';
import type { Source } from '../../types/evidence';

export interface SourceListProps {
  sources: Source[];
  className?: string;
  onOpenSource?: (source: Source) => void;
}

export const SourceList: React.FC<SourceListProps> = ({ sources, className = '', onOpenSource }) => {
  const [copiedId, setCopiedId] = useState<string | null>(null);

  if (!sources || sources.length === 0) {
    return (
      <div className="py-6 text-center text-xs text-[#f3faf0]/50" data-testid="source-list-empty">
        <FileText className="h-5 w-5 mx-auto mb-1.5 text-[#f3faf0]/30" />
        No sources retrieved for this result.
      </div>
    );
  }

  const handleCopyCitation = (source: Source) => {
    const title = source.title || source.document || source.documentName || 'Unknown Source';
    const authorsStr = source.authors && source.authors.length > 0 ? `${source.authors.join(', ')}. ` : '';
    const yearStr = source.year ? `(${source.year}). ` : '';
    const citation = `${authorsStr}${yearStr}"${title}". ${source.passage ? `— "${source.passage}"` : ''}`;
    void navigator.clipboard.writeText(citation);
    setCopiedId(source.id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const getOriginBadge = (origin?: string) => {
    const norm = (origin || 'document').toLowerCase();
    if (norm === 'web') {
      return (
        <span
          className="inline-flex items-center gap-1 rounded-md border border-emerald-400/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-mono text-emerald-300"
          data-testid="source-origin"
        >
          <Globe className="h-2.5 w-2.5" />
          Web
        </span>
      );
    }
    if (norm === 'scholarly' || norm === 'arxiv' || norm === 'semantic_scholar') {
      return (
        <span
          className="inline-flex items-center gap-1 rounded-md border border-purple-400/30 bg-purple-500/10 px-2 py-0.5 text-[10px] font-mono text-purple-300"
          data-testid="source-origin"
        >
          <GraduationCap className="h-2.5 w-2.5" />
          Scholarly
        </span>
      );
    }
    return (
      <span
        className="inline-flex items-center gap-1 rounded-md border border-sky-400/30 bg-sky-500/10 px-2 py-0.5 text-[10px] font-mono text-sky-300"
        data-testid="source-origin"
      >
        <FileText className="h-2.5 w-2.5" />
        Document
      </span>
    );
  };

  const getReliabilityBadge = (rel?: number) => {
    if (rel === undefined || rel === null || !Number.isFinite(rel)) return null;
    const isHigh = rel >= 0.8;
    const isMed = rel >= 0.5;
    const colorClass = isHigh
      ? 'border-emerald-400/30 bg-emerald-500/15 text-emerald-300'
      : isMed
      ? 'border-[#a7d0d2]/30 bg-[#a7d0d2]/15 text-[#a7d0d2]'
      : 'border-amber-400/30 bg-amber-500/15 text-amber-300';

    return (
      <span
        className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[10px] font-mono font-medium ${colorClass}`}
        data-testid="source-reliability"
        title={`Source reliability score: ${rel}`}
      >
        <span>Reliability {rel}</span>
      </span>
    );
  };

  return (
    <div className={`space-y-3 ${className}`} data-testid="source-list">
      {sources.map((source, idx) => {
        const title = source.title || source.document || source.documentName || `Source #${idx + 1}`;
        const link = source.url || (source.doi ? `https://doi.org/${source.doi}` : null);
        const passage = source.passage || source.quote;
        const warnings = source.warnings || [];
        const isRetracted = warnings.some((w) => w.toLowerCase().includes('retracted'));
        const isPreprint = warnings.some((w) => w.toLowerCase().includes('preprint'));

        return (
          <article
            key={source.id || `source_${idx}`}
            onClick={() => onOpenSource && onOpenSource(source)}
            className="rounded-xl border border-[#4d728e]/30 bg-[#0b1219]/90 p-4 transition-all hover:border-[#a7d0d2]/50 shadow-sm"
            data-testid="source-item"
          >
            {/* Top Bar: Rank, Badges, Copy button */}
            <div className="flex flex-wrap items-start justify-between gap-2.5">
              <div className="flex items-start gap-2.5 min-w-0 flex-1">
                <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-[#141d26] border border-[#4d728e]/40 text-[11px] font-mono font-bold text-[#d2434e]">
                  {source.rank ?? idx + 1}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    {/* Title */}
                    <h4
                      className="text-sm font-semibold text-white break-words"
                      data-testid="source-title"
                    >
                      {title}
                    </h4>

                    {/* Year */}
                    {source.year && (
                      <span className="text-xs font-mono text-[#f3faf0]/60" data-testid="source-year">
                        ({source.year})
                      </span>
                    )}

                    {/* External Link */}
                    {link && (
                      <a
                        href={link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-0.5 text-xs text-[#a7d0d2] hover:text-white hover:underline transition-colors"
                        data-testid="source-link"
                        title={`Open external link: ${link}`}
                      >
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    )}
                  </div>

                  {/* Authors */}
                  {source.authors && source.authors.length > 0 && (
                    <p className="mt-0.5 text-xs text-[#f3faf0]/70" data-testid="source-authors">
                      {source.authors.join(', ')}
                    </p>
                  )}

                  {/* Document & page info */}
                  <div className="mt-1 flex items-center gap-2 text-[11px] font-mono text-[#f3faf0]/50 flex-wrap">
                    {source.document && source.document !== title && (
                      <span>Doc: {source.document}</span>
                    )}
                    {source.page !== undefined && source.page !== 'N/A' && (
                      <span>Page {source.page}</span>
                    )}
                    {source.chunk_id && source.chunk_id !== 'N/A' && (
                      <span>Chunk: {source.chunk_id}</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Right action & badges */}
              <div className="flex items-center gap-1.5 shrink-0">
                {getOriginBadge(source.origin)}
                {getReliabilityBadge(source.reliability)}
                <button
                  type="button"
                  onClick={() => handleCopyCitation(source)}
                  className="inline-flex items-center gap-1 rounded bg-[#141d26] border border-white/10 px-2 py-0.5 text-[10px] font-mono text-[#a7d0d2] hover:text-white transition-colors cursor-pointer"
                  title="Copy citation"
                >
                  {copiedId === source.id ? (
                    <Check className="h-2.5 w-2.5 text-emerald-400" />
                  ) : (
                    <Copy className="h-2.5 w-2.5" />
                  )}
                  <span>{copiedId === source.id ? 'Copied' : 'Cite'}</span>
                </button>
              </div>
            </div>

            {/* Warnings: Retracted / Preprint */}
            {(isRetracted || isPreprint || warnings.length > 0) && (
              <div className="mt-2.5 space-y-1" data-testid="source-warning-container">
                {isRetracted && (
                  <div
                    className="flex items-center gap-1.5 rounded-md border border-rose-500/40 bg-rose-500/10 px-2.5 py-1 text-xs text-rose-300 font-medium"
                    data-testid="source-warning"
                  >
                    <ShieldAlert className="h-3.5 w-3.5 shrink-0 text-rose-400" />
                    <span>WARNING: This publication has been retracted.</span>
                  </div>
                )}
                {isPreprint && !isRetracted && (
                  <div
                    className="flex items-center gap-1.5 rounded-md border border-amber-500/40 bg-amber-500/10 px-2.5 py-1 text-xs text-amber-300"
                    data-testid="source-warning"
                  >
                    <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-amber-400" />
                    <span>Preprint notice: Work has not completed peer review.</span>
                  </div>
                )}
                {warnings
                  .filter((w) => !w.toLowerCase().includes('retracted') && !w.toLowerCase().includes('preprint'))
                  .map((w, wIdx) => (
                    <div
                      key={wIdx}
                      className="flex items-center gap-1.5 rounded-md border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-xs text-amber-200"
                      data-testid="source-warning"
                    >
                      <AlertTriangle className="h-3 w-3 shrink-0 text-amber-400" />
                      <span>{w}</span>
                    </div>
                  ))}
              </div>
            )}

            {/* Passage Excerpt */}
            {passage && (
              <div
                className="mt-3 rounded-lg border border-white/5 bg-[#141d26]/60 p-2.5 text-xs text-[#f3faf0]/85 leading-relaxed"
                data-testid="source-passage"
              >
                <div className="flex items-start gap-1.5">
                  <Quote className="h-3 w-3 shrink-0 text-[#a7d0d2] mt-0.5 opacity-60" />
                  <p className="italic text-[#c1cbd2]">{passage}</p>
                </div>
              </div>
            )}
          </article>
        );
      })}
    </div>
  );
};
