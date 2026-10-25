import React from 'react';
import { LibraryBig, Files } from 'lucide-react';
import type { Evidence, Source } from '../../types/evidence';
import { SourceList } from './SourceList';

interface EvidencePanelProps {
  evidence?: Evidence[];
  sources: Source[];
  onOpenSources?: () => void;
}

export const EvidencePanel: React.FC<EvidencePanelProps> = ({ sources, onOpenSources }) => {
  return (
    <section className="refire-card p-5 sm:p-6 space-y-4" aria-labelledby="evidence-heading">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/8 pb-3">
        <div className="flex items-center gap-2">
          <LibraryBig className="h-4 w-4 text-[#a7d0d2]" aria-hidden="true" />
          <div>
            <h2 id="evidence-heading" className="text-xs font-mono uppercase text-[#f3faf0]/75">
              Retrieved Sources
            </h2>
            <p className="mt-0.5 text-[11px] text-[#f3faf0]/45">
              Deterministic, evidence-grounded citations and provenance.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="rounded-full border border-white/10 bg-[#141d26] px-2.5 py-0.5 text-xs font-mono text-[#a7d0d2]">
            {sources.length} {sources.length === 1 ? 'source' : 'sources'}
          </span>

          {onOpenSources && (
            <button
              type="button"
              onClick={onOpenSources}
              disabled={sources.length === 0}
              className="inline-flex items-center gap-1.5 rounded-lg border border-[#4d728e]/35 bg-[#141d26] px-2.5 py-1 text-xs text-[#a7d0d2] hover:border-[#a7d0d2]/60 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
              title="Inspect in side drawer"
            >
              <Files className="h-3 w-3" aria-hidden="true" />
              <span className="hidden sm:inline">Drawer</span>
            </button>
          )}
        </div>
      </div>

      <SourceList sources={sources} />
    </section>
  );
};
