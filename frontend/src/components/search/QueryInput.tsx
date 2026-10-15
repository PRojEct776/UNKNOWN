import React from 'react';
import { ArrowRight, Loader2 } from 'lucide-react';
import type { AnalysisMode } from '../../types/query';

interface QueryInputProps {
  query: string;
  mode: AnalysisMode;
  isLoading: boolean;
  loadingLabel: string;
  onQueryChange: (query: string) => void;
  onSubmit: () => void;
  onShowAbstention: () => void;
}

export const QueryInput: React.FC<QueryInputProps> = ({
  query,
  mode,
  isLoading,
  loadingLabel,
  onQueryChange,
  onSubmit,
  onShowAbstention,
}) => {
  const examplesByMode: Record<AnalysisMode, string[]> = {
    discover: [
      'What is SAC-RAG and its key findings?',
      'What was the difference in mean on-time completion rate?',
      'What are the core components of the intervention?',
    ],
    reason: [
      'Why does adaptive context compression improve retrieval efficiency?',
      'Can the fictional pilot study prove that the intervention caused the improvement?',
    ],
    verify: [
      'SAC-RAG uses semantic adaptive context compression.',
      'The intervention group had an 84% on-time completion rate compared to 72%.',
    ],
    compare: [
      'Compare BM25 and FAISS dense retrieval in SAC-RAG',
      'Compare intervention and comparison groups on baseline and week-four confidence',
    ],
    gaps: [
      'Research gaps in SAC-RAG context compression',
      'What research gaps exist in the study-planning pilot study?',
    ],
    debate: [
      'Should RAG systems use semantic context compression?',
      'Does structured study-planning reliably increase student workload confidence?',
    ],
    'knowledge-map': [
      'SAC-RAG adaptive retrieval architecture',
      'Study planning intervention research packet concepts',
    ],
    'knowledge-dna': [
      'Extract the core Knowledge DNA of SAC-RAG',
      'Synthesize topics, methods, findings, and limitations from corpus',
    ],
  };

  const currentExamples = examplesByMode[mode] || examplesByMode.discover;

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      if (query.trim() && !isLoading) {
        onSubmit();
      }
    }
  };

  return (
    <div className="space-y-3">
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (query.trim() && !isLoading) {
            onSubmit();
          }
        }}
        className="space-y-2"
      >
        <label htmlFor="knowledge-query" className="sr-only">Natural language query</label>
        <textarea
          id="knowledge-query"
          rows={3}
          value={query}
          disabled={isLoading}
          onChange={(event) => onQueryChange(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            mode === 'verify'
              ? 'Enter a specific claim to verify against document evidence (Press Enter to submit)...'
              : mode === 'compare'
              ? 'Enter topics, methods, or entities to compare (Press Enter to submit)...'
              : mode === 'debate'
              ? 'Enter a debate topic or policy question (Press Enter to submit)...'
              : 'Ask a question about your indexed documents (Press Enter to submit, Shift+Enter for new line)...'
          }
          className="w-full resize-y rounded-lg border border-[#46545f] bg-[#0c1217] px-4 py-4 text-base leading-7 text-white placeholder:text-[#82909a] focus:border-[#a7d0d2]/70 focus:outline-none disabled:opacity-60"
        />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-[#98a6b0]">
            Press <kbd className="rounded bg-[#141d26] px-1.5 py-0.5 font-mono text-[11px] text-[#a7d0d2] border border-white/10">Enter</kbd> to submit, <kbd className="rounded bg-[#141d26] px-1.5 py-0.5 font-mono text-[11px] text-[#a7d0d2] border border-white/10">Shift+Enter</kbd> for a new line.
          </p>
          <button
            type="submit"
            disabled={!query.trim() || isLoading}
            className="inline-flex items-center gap-2 rounded-md bg-[#d2434e] px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[#b83842] disabled:cursor-not-allowed disabled:opacity-40 cursor-pointer"
          >
            {isLoading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <ArrowRight className="h-4 w-4" aria-hidden="true" />}
            {isLoading ? loadingLabel : mode === 'discover' ? 'Search' : 'Analyze'}
          </button>
        </div>
      </form>

      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1 text-xs font-mono uppercase text-[#a7d0d2]">
          Example queries:
        </span>
        {currentExamples.map((example) => (
          <button
            key={example}
            type="button"
            disabled={isLoading}
            onClick={() => onQueryChange(example)}
            className="rounded-md border border-white/10 bg-[#111a22] px-2.5 py-1 text-xs text-[#b6c1c9] hover:border-[#a7d0d2]/50 hover:text-white transition-colors cursor-pointer disabled:opacity-50"
          >
            "{example}"
          </button>
        ))}
        <button
          type="button"
          onClick={onShowAbstention}
          className="ml-auto text-xs text-[#98a6b0] hover:text-white transition-colors cursor-pointer"
        >
          Preview insufficient evidence
        </button>
      </div>
    </div>
  );
};