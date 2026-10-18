import React, { useState } from 'react';
import { AlertTriangle, BookOpenCheck, Loader2, Code, Copy, Check } from 'lucide-react';
import type { AnswerState } from '../../types/query';
import { ConfidenceBadge } from './ConfidenceBadge';
import { AbstentionPanel } from './AbstentionPanel';

interface AnswerPanelProps {
  answer: string;
  detailedAnswer: string;
  confidence?: number;
  answerState: AnswerState;
  showDetailed: boolean;
  onToggleDetail: () => void;
  queryType?: string;
  rawResponse?: unknown;
}

export const AnswerPanel: React.FC<AnswerPanelProps> = ({
  answer,
  detailedAnswer,
  confidence,
  answerState,
  showDetailed,
  onToggleDetail,
  queryType,
  rawResponse,
}) => {
  const [showRawJson, setShowRawJson] = useState(false);
  const [copied, setCopied] = useState(false);
  const [answerCopied, setAnswerCopied] = useState(false);

  const handleCopyAnswer = () => {
    const textToCopy = showDetailed ? detailedAnswer : answer;
    if (!textToCopy) return;
    void navigator.clipboard.writeText(textToCopy);
    setAnswerCopied(true);
    setTimeout(() => setAnswerCopied(false), 2000);
  };

  if (answerState === 'insufficient_evidence') return <AbstentionPanel />;

  if (answerState === 'loading') {
    return (
      <section className="refire-card p-6" aria-live="polite">
        <div className="flex items-center gap-2 text-sm text-[#a7d0d2]">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Preparing a grounded answer...
        </div>
      </section>
    );
  }

  if (answerState === 'error') {
    return (
      <section className="rounded-xl border border-rose-400/25 bg-rose-400/5 p-5" role="alert">
        <div className="flex items-center gap-2 text-sm font-semibold text-rose-200">
          <AlertTriangle className="h-4 w-4" aria-hidden="true" /> Search Request Failed
        </div>
        <p className="mt-2 text-xs leading-relaxed text-[#f3faf0]/80">
          {answer || 'The backend service could not be reached or returned an error.'}
        </p>
      </section>
    );
  }

  const handleCopyJson = () => {
    if (!rawResponse) return;
    void navigator.clipboard.writeText(JSON.stringify(rawResponse, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <section className="refire-card p-5 sm:p-6" aria-labelledby="answer-heading">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-white/8 pb-3">
        <div className="flex items-center gap-2.5">
          <BookOpenCheck className="h-4 w-4 text-[#d2434e]" aria-hidden="true" />
          <h2 id="answer-heading" className="text-xs font-mono uppercase text-[#f3faf0]/75">
            Answer
          </h2>
          {queryType && (
            <span className="rounded-full border border-[#a7d0d2]/30 bg-[#a7d0d2]/15 px-2.5 py-0.5 text-[10px] font-mono text-[#a7d0d2] uppercase">
              {queryType}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleCopyAnswer}
            className="flex items-center gap-1.5 rounded-md border border-white/10 bg-[#141d26] px-2.5 py-1 text-[11px] font-mono text-[#f3faf0]/75 hover:border-[#a7d0d2]/50 hover:text-white transition-colors cursor-pointer"
            title="Copy answer text to clipboard"
          >
            {answerCopied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3 text-[#a7d0d2]" />}
            <span>{answerCopied ? 'Copied!' : 'Copy Answer'}</span>
          </button>
          {rawResponse !== undefined && (
            <button
              type="button"
              onClick={() => setShowRawJson(!showRawJson)}
              className="flex items-center gap-1.5 rounded-md border border-white/10 bg-[#141d26] px-2.5 py-1 text-[11px] font-mono text-[#f3faf0]/75 hover:border-[#a7d0d2]/50 hover:text-white transition-colors cursor-pointer"
              title="Toggle raw backend JSON response"
            >
              <Code className="h-3 w-3 text-[#a7d0d2]" />
              <span>{showRawJson ? 'Hide Raw JSON' : 'Raw JSON'}</span>
            </button>
          )}
          <ConfidenceBadge value={confidence} />
        </div>
      </div>

      <div className="text-base leading-7 text-[#e2e8ed] whitespace-pre-line">
        {showDetailed ? detailedAnswer : answer}
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-white/5 pt-3">
        <button
          type="button"
          onClick={onToggleDetail}
          className="text-xs font-medium text-[#a7d0d2] underline-offset-4 hover:text-white hover:underline"
          aria-expanded={showDetailed}
        >
          {showDetailed ? 'Show concise answer' : 'Expand detailed answer'}
        </button>

        {showRawJson && (
          <button
            type="button"
            onClick={handleCopyJson}
            className="flex items-center gap-1 text-[11px] font-mono text-[#f3faf0]/60 hover:text-white transition-colors"
          >
            {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
            <span>{copied ? 'Copied' : 'Copy JSON'}</span>
          </button>
        )}
      </div>

      {showRawJson && rawResponse !== undefined && (
        <div className="mt-4 overflow-hidden rounded-lg border border-white/10 bg-[#070b10] p-3">
          <pre className="max-h-80 overflow-auto font-mono text-[11px] leading-relaxed text-[#a7d0d2]/90">
            {JSON.stringify(rawResponse, null, 2)}
          </pre>
        </div>
      )}
    </section>
  );
};
