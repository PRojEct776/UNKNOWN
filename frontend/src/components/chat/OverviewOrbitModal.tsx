import React, { useEffect, useState } from 'react';
import { Orbit, X } from 'lucide-react';
import { ConceptGraph3D } from '../ConceptGraph3D';
import { fetchConceptGraph } from '../../lib/api';
import type { BackendConceptGraphResponse } from '../../lib/api';

interface OverviewOrbitModalProps {
  documentName: string;
  onClose: () => void;
}

/**
 * Document-level Knowledge Orbit. Loads the real backend concept graph and
 * shows it as returned. Failures and empty graphs are reported honestly;
 * no filler nodes are ever generated.
 */
export const OverviewOrbitModal: React.FC<OverviewOrbitModalProps> = ({ documentName, onClose }) => {
  const [graph, setGraph] = useState<BackendConceptGraphResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchConceptGraph(documentName)
      .then((data) => {
        if (!cancelled) setGraph(data);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Request failed');
      });
    return () => {
      cancelled = true;
    };
  }, [documentName]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const loading = graph === null && error === null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Document Knowledge Orbit"
      className="fixed inset-0 z-50 bg-black/85 backdrop-blur-xs flex flex-col p-4 sm:p-8"
    >
      <div className="flex items-center justify-between pb-3 border-b border-white/10">
        <h3 className="text-sm font-bold text-white flex items-center gap-2">
          <Orbit className="w-4 h-4 text-[#d2434e]" />
          Document Knowledge Orbit
        </h3>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close knowledge orbit"
          className="p-1.5 text-white/60 hover:text-white rounded-lg cursor-pointer"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 overflow-auto mt-3 rounded-xl bg-[#070b0e]">
        {loading && (
          <p className="p-6 text-xs text-[#98a6b0]">Loading concept graph from the document...</p>
        )}

        {error && (
          <div className="p-6 text-xs space-y-1">
            <p className="text-white font-semibold">Could not load the concept graph.</p>
            <p className="text-[#98a6b0]">{error}</p>
            <p className="text-[#98a6b0]">Nothing is shown rather than inventing a graph.</p>
          </div>
        )}

        {graph && (
          <div className="space-y-2">
            <ConceptGraph3D graphData={graph} documentName={documentName} />
            {graph.extraction && (
              <p className="px-4 pb-3 text-[10px] font-mono text-[#98a6b0]">
                Extraction: {graph.extraction.method} | {graph.extraction.chunks_analyzed} of{' '}
                {graph.extraction.chunks_total} chunks analysed
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
