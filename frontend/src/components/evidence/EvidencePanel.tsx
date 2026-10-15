import React, { useState } from 'react';
import { Files, LibraryBig, BookOpen } from 'lucide-react';
import type { Evidence, Source } from '../../types/evidence';
import { SourceCard } from './SourceCard';
import { EvidenceCard } from './EvidenceCard';

interface EvidencePanelProps {
  evidence: Evidence[];
  sources: Source[];
  onOpenSources: () => void;
}

export const EvidencePanel: React.FC<EvidencePanelProps> = ({ evidence, sources, onOpenSources }) => {
  const [activeTab, setActiveTab] = useState<'sources' | 'passages'>('sources');

  return (
    <section className="refire-card p-5 sm:p-6 space-y-4" aria-labelledby="evidence-heading">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/8 pb-3">
        <div className="flex items-center gap-2">
          <LibraryBig className="h-4 w-4 text-[#a7d0d2]" aria-hidden="true" />
          <div>
            <h2 id="evidence-heading" className="text-xs font-mono uppercase text-[#f3faf0]/75">
              Retrieved Source Evidence
            </h2>
            <p className="mt-0.5 text-[11px] text-[#f3faf0]/45">
              Grounded citations, chunks, and hybrid retrieval scores from the indexed corpus.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex rounded-lg border border-white/10 bg-[#141d26] p-0.5 text-[11px]">
            <button
              type="button"
              onClick={() => setActiveTab('sources')}
              className={`rounded-md px-2.5 py-1 transition-colors ${
                activeTab === 'sources' ? 'bg-[#1b2734] text-white font-medium' : 'text-[#f3faf0]/60 hover:text-white'
              }`}
            >
              Sources ({sources.length})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('passages')}
              className={`rounded-md px-2.5 py-1 transition-colors ${
                activeTab === 'passages' ? 'bg-[#1b2734] text-white font-medium' : 'text-[#f3faf0]/60 hover:text-white'
              }`}
            >
              Passages ({evidence.length})
            </button>
          </div>

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
        </div>
      </div>

      {sources.length === 0 && evidence.length === 0 ? (
        <div className="py-6 text-center text-xs text-[#f3faf0]/50">
          <BookOpen className="h-5 w-5 mx-auto mb-1.5 text-[#f3faf0]/30" />
          No source evidence records retrieved for this query.
        </div>
      ) : activeTab === 'sources' ? (
        <div className="space-y-3">
          {sources.map((src, idx) => {
            const matchingEvidence = evidence.filter(
              (e) => e.chunkId === src.chunkId || e.documentName === src.documentName
            );
            return (
              <SourceCard
                key={src.id || `${src.documentName}_${idx}`}
                source={src}
                evidence={matchingEvidence}
                index={idx}
              />
            );
          })}
        </div>
      ) : (
        <div className="space-y-3">
          {evidence.map((item) => (
            <EvidenceCard key={item.id} evidence={item} onOpenSource={onOpenSources} />
          ))}
        </div>
      )}
    </section>
  );
};