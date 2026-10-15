import React from 'react';
import { CircleHelp, FilePlus2 } from 'lucide-react';

export const AbstentionPanel: React.FC = () => (
  <section className="rounded-xl border border-amber-300/25 bg-amber-300/5 p-5" aria-labelledby="abstention-title">
    <div className="flex items-start gap-3">
      <CircleHelp className="mt-0.5 h-5 w-5 shrink-0 text-amber-200" aria-hidden="true" />
      <div>
        <p className="font-mono text-[11px] uppercase text-amber-200">Insufficient evidence</p>
        <h2 id="abstention-title" className="mt-1 text-base font-semibold text-white">
          UNKNOWN does not have enough evidence to answer this confidently.
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-[#f3faf0]/70">
          Try refining the question or adding relevant documents to the collection.
        </p>
        <p className="mt-3 inline-flex items-center gap-2 text-xs text-[#f3faf0]/55">
          <FilePlus2 className="h-4 w-4" aria-hidden="true" /> No supporting passages or confidence score are shown.
        </p>
      </div>
    </div>
  </section>
);