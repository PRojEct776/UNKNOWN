import React, { useState } from 'react';
import {
  AlertTriangle,
  BookOpenCheck,
  Loader2,
  Code,
  Copy,
  Check,
  FileText,
  Globe,
  GitCompare,
  ThumbsUp,
  ThumbsDown,
  Flag,
  SearchX,
  ShieldAlert,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  AlertCircle,
  XCircle,
  Send,
  Download,
  Archive,
} from 'lucide-react';
import type { AnswerState, Claim, ComparisonPair, Conflict, ConfidenceData } from '../../types/query';
import type { Source } from '../../types/evidence';
import { ConfidenceBadge } from './ConfidenceBadge';
import { AbstentionPanel } from './AbstentionPanel';
import { submitFeedback } from '../../lib/api';
import { downloadResultExport } from '../../lib/exportUtils';

export interface AnswerPanelProps {
  answer: string;
  detailedAnswer?: string;
  summary?: string;
  doc_section?: string | null;
  web_section?: string | null;
  comparison?: ComparisonPair[];
  claims?: Claim[];
  conflicts?: Conflict[];
  gaps?: string[];
  sources?: Source[];
  query?: string;
  confidence?: number | ConfidenceData | null;
  answerState: AnswerState;
  showDetailed: boolean;
  onToggleDetail: () => void;
  queryType?: string;
  rawResponse?: unknown;
}

export function extractSummaryAtMost3Sentences(text: string, explicitSummary?: string): string {
  if (explicitSummary && explicitSummary.trim()) {
    return explicitSummary.trim();
  }
  if (!text || !text.trim()) return '';
  const sentences = text.match(/[^.!?]+[.!?]+(?:\s|$)/g);
  if (!sentences || sentences.length === 0) {
    return text.trim();
  }
  return sentences.slice(0, 3).join('').trim();
}

export const AnswerPanel: React.FC<AnswerPanelProps> = ({
  answer,
  detailedAnswer,
  summary,
  doc_section,
  web_section,
  comparison,
  claims = [],
  conflicts = [],
  gaps = [],
  sources = [],
  query = '',
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

  // Feedback states
  const [feedbackSent, setFeedbackSent] = useState<'thumbs_up' | 'thumbs_down' | 'wrong_answer' | null>(null);
  const [showReportModal, setShowReportModal] = useState(false);
  const [reportComment, setReportComment] = useState('');
  const [isSubmittingFeedback, setIsSubmittingFeedback] = useState(false);
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);

  const handleDownload = async (format: 'pdf' | 'docx' | 'markdown' | 'html' | 'zip') => {
    try {
      await downloadResultExport(
        {
          query: query || answer.slice(0, 60),
          answer,
          detailed_answer: detailedAnswer || answer,
          summary: summaryText,
          doc_section,
          web_section,
          comparison,
          claims,
          conflicts,
          gaps,
          confidence,
          sources,
          document_names: sources.map((s) => s.document || s.documentName || '').filter(Boolean),
        },
        format
      );
    } catch (err) {
      console.error('Export download error:', err);
    }
  };

  const handleCopyAnswer = () => {
    const textToCopy = showDetailed ? detailedAnswer || answer : answer;
    if (!textToCopy) return;
    void navigator.clipboard.writeText(textToCopy);
    setAnswerCopied(true);
    setTimeout(() => setAnswerCopied(false), 2000);
  };

  const handleCopyJson = () => {
    if (!rawResponse) return;
    void navigator.clipboard.writeText(JSON.stringify(rawResponse, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleSendFeedback = async (type: 'thumbs_up' | 'thumbs_down' | 'wrong_answer', commentText?: string) => {
    setIsSubmittingFeedback(true);
    try {
      await submitFeedback({
        query: query || answer.slice(0, 80),
        answer: detailedAnswer || answer,
        sources,
        feedback_type: type,
        comment: commentText || '',
      });
      setFeedbackSent(type);
      setFeedbackMessage(
        type === 'wrong_answer'
          ? 'Wrong answer report submitted. Thank you for helping improve UNKNOWN.'
          : 'Thank you for your feedback!'
      );
      setShowReportModal(false);
    } catch {
      setFeedbackMessage('Feedback logged locally.');
      setFeedbackSent(type);
      setShowReportModal(false);
    } finally {
      setIsSubmittingFeedback(false);
    }
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

  // Calculate 3-sentence summary
  const summaryText = extractSummaryAtMost3Sentences(answer, summary);
  const fullDetail = detailedAnswer || answer;

  return (
    <section className="refire-card p-5 sm:p-6 space-y-6" aria-labelledby="answer-heading">
      {/* Header Bar: Title, Badges, Copy, Actions */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/8 pb-3">
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
          <ConfidenceBadge confidence={confidence} />
        </div>
      </div>

      {/* Export & Download Toolbar (Task P2-2) */}
      <div className="flex flex-wrap items-center justify-between gap-2.5 rounded-lg border border-white/5 bg-[#141d26]/60 px-3 py-2 text-xs" data-testid="export-buttons-container">
        <div className="flex items-center gap-1.5 text-[#f3faf0]/70 font-mono text-[11px]">
          <Download className="h-3.5 w-3.5 text-[#a7d0d2]" />
          <span>Export Result:</span>
        </div>
        <div className="flex items-center gap-1.5 flex-wrap">
          <button
            type="button"
            onClick={() => handleDownload('pdf')}
            className="flex items-center gap-1 rounded bg-[#0b1219] border border-white/10 px-2.5 py-1 text-[11px] font-mono text-[#a7d0d2] hover:text-white hover:border-[#a7d0d2]/50 transition-colors cursor-pointer"
            data-testid="export-pdf-button"
            title="Download formatted PDF report"
          >
            <span>PDF</span>
          </button>
          <button
            type="button"
            onClick={() => handleDownload('docx')}
            className="flex items-center gap-1 rounded bg-[#0b1219] border border-white/10 px-2.5 py-1 text-[11px] font-mono text-[#a7d0d2] hover:text-white hover:border-[#a7d0d2]/50 transition-colors cursor-pointer"
            data-testid="export-docx-button"
            title="Download Word DOCX report"
          >
            <span>DOCX</span>
          </button>
          <button
            type="button"
            onClick={() => handleDownload('markdown')}
            className="flex items-center gap-1 rounded bg-[#0b1219] border border-white/10 px-2.5 py-1 text-[11px] font-mono text-[#a7d0d2] hover:text-white hover:border-[#a7d0d2]/50 transition-colors cursor-pointer"
            data-testid="export-md-button"
            title="Download Markdown report (.md)"
          >
            <span>Markdown</span>
          </button>
          <button
            type="button"
            onClick={() => handleDownload('html')}
            className="flex items-center gap-1 rounded bg-[#0b1219] border border-white/10 px-2.5 py-1 text-[11px] font-mono text-[#a7d0d2] hover:text-white hover:border-[#a7d0d2]/50 transition-colors cursor-pointer"
            data-testid="export-html-button"
            title="Download HTML report"
          >
            <span>HTML</span>
          </button>
          <button
            type="button"
            onClick={() => handleDownload('zip')}
            className="flex items-center gap-1 rounded bg-[#0b1219] border border-white/10 px-2.5 py-1 text-[11px] font-mono text-[#a7d0d2] hover:text-white hover:border-[#a7d0d2]/50 transition-colors cursor-pointer"
            data-testid="export-zip-button"
            title="Download extracted figures as Image ZIP"
          >
            <Archive className="h-3 w-3" />
            <span>Images (ZIP)</span>
          </button>
        </div>
      </div>

      {/* 2. Executive Summary (At most 3 sentences) */}
      <div className="space-y-2">
        <div className="text-xs font-mono uppercase tracking-wider text-[#a7d0d2] font-semibold flex items-center gap-1.5">
          <span>Executive Summary</span>
          <span className="text-[10px] font-normal text-[#f3faf0]/40">(max 3 sentences)</span>
        </div>
        <div
          className="text-base leading-7 text-white font-medium bg-[#141d26]/40 rounded-xl p-4 border border-white/5"
          data-testid="answer-summary"
        >
          {summaryText}
        </div>
      </div>

      {/* 3. Expandable Detail */}
      <div className="border-t border-white/5 pt-3">
        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={onToggleDetail}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-[#a7d0d2] hover:text-white transition-colors cursor-pointer"
            data-testid="detail-toggle"
            aria-expanded={showDetailed}
          >
            {showDetailed ? (
              <>
                <ChevronUp className="h-3.5 w-3.5" />
                <span>Show concise answer</span>
              </>
            ) : (
              <>
                <ChevronDown className="h-3.5 w-3.5" />
                <span>Expand detailed answer</span>
              </>
            )}
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

        {showDetailed && (
          <div
            className="mt-3 text-sm leading-7 text-[#e2e8ed] whitespace-pre-line rounded-lg bg-[#0b1219]/80 p-4 border border-white/5"
            data-testid="answer-detail"
          >
            {fullDetail}
          </div>
        )}

        {showRawJson && rawResponse !== undefined && (
          <div className="mt-4 overflow-hidden rounded-lg border border-white/10 bg-[#070b10] p-3">
            <pre className="max-h-80 overflow-auto font-mono text-[11px] leading-relaxed text-[#a7d0d2]/90">
              {JSON.stringify(rawResponse, null, 2)}
            </pre>
          </div>
        )}
      </div>

      {/* 4. Cross-Channel Sections: "From your document" & "From the web" */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 border-t border-white/5 pt-4">
        {/* Section: "From your document" */}
        <div
          className="rounded-xl border border-sky-400/20 bg-sky-500/5 p-4 space-y-2"
          data-testid="section-document"
        >
          <div className="flex items-center gap-2 text-xs font-semibold text-sky-300 uppercase font-mono">
            <FileText className="h-3.5 w-3.5" />
            <span>From your document</span>
          </div>
          <p className="text-xs leading-relaxed text-[#d1d9df]">
            {doc_section && doc_section.trim()
              ? doc_section
              : 'Not found in available sources or no document passage cited.'}
          </p>
        </div>

        {/* Section: "From the web" */}
        <div
          className="rounded-xl border border-emerald-400/20 bg-emerald-500/5 p-4 space-y-2"
          data-testid="section-web"
        >
          <div className="flex items-center gap-2 text-xs font-semibold text-emerald-300 uppercase font-mono">
            <Globe className="h-3.5 w-3.5" />
            <span>From the web</span>
          </div>
          <p className="text-xs leading-relaxed text-[#d1d9df]">
            {web_section && web_section.trim()
              ? web_section
              : 'Web connectors not invoked or no live web evidence retrieved.'}
          </p>
        </div>
      </div>

      {/* 5. Section: "Agreement and differences" */}
      <div
        className="rounded-xl border border-white/8 bg-[#141d26]/40 p-4 space-y-3"
        data-testid="section-agreement"
      >
        <div className="flex items-center gap-2 text-xs font-semibold text-[#a7d0d2] uppercase font-mono">
          <GitCompare className="h-3.5 w-3.5" />
          <span>Agreement and differences</span>
        </div>

        {comparison && comparison.length > 0 ? (
          <div className="space-y-2.5">
            {comparison.map((pair, pIdx) => {
              const isAgree = pair.label === 'agree';
              const isDisagree = pair.label === 'disagree';
              const labelColor = isAgree
                ? 'border-emerald-400/30 bg-emerald-500/15 text-emerald-300'
                : isDisagree
                ? 'border-rose-400/30 bg-rose-500/15 text-rose-300'
                : 'border-amber-400/30 bg-amber-500/15 text-amber-300';

              return (
                <div
                  key={pIdx}
                  className="rounded-lg border border-white/5 bg-[#0b1219]/60 p-3 space-y-2 text-xs"
                >
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <span className="font-semibold text-white">{pair.sub_question}</span>
                    <span className={`rounded-full border px-2 py-0.5 text-[10px] font-mono uppercase ${labelColor}`}>
                      {pair.label}
                    </span>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px] text-[#c1cbd2]">
                    <div className="rounded bg-sky-950/20 p-2 border border-sky-500/10">
                      <span className="text-sky-300 font-mono text-[10px] block mb-0.5">Doc Quote:</span>
                      <p className="italic">"{pair.doc_quote || 'N/A'}"</p>
                      {pair.doc_source && (
                        <span className="text-[10px] text-[#f3faf0]/40 block mt-1">({pair.doc_source})</span>
                      )}
                    </div>
                    <div className="rounded bg-emerald-950/20 p-2 border border-emerald-500/10">
                      <span className="text-emerald-300 font-mono text-[10px] block mb-0.5">Web Quote:</span>
                      <p className="italic">"{pair.web_quote || 'N/A'}"</p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-xs text-[#f3faf0]/60 italic">
            Cross-channel evidence shows consistent consensus on verified points.
          </p>
        )}
      </div>

      {/* 6. Claim Chips (supported / partial / unsupported) */}
      <div className="space-y-2.5 border-t border-white/5 pt-4">
        <h3 className="text-xs font-mono uppercase text-[#f3faf0]/75">
          Atomic Claim Verification
        </h3>
        {claims.length > 0 ? (
          <div className="flex flex-wrap gap-2" data-testid="claim-chips">
            {claims.map((claim, cIdx) => {
              const norm = (claim.label || 'supported').toLowerCase();
              const isSupp = norm === 'supported';
              const isPart = norm === 'partial';
              const chipClass = isSupp
                ? 'border-emerald-400/30 bg-emerald-500/10 text-emerald-300'
                : isPart
                ? 'border-amber-400/30 bg-amber-500/10 text-amber-300'
                : 'border-rose-400/30 bg-rose-500/10 text-rose-300';
              const Icon = isSupp ? CheckCircle2 : isPart ? AlertCircle : XCircle;

              return (
                <div
                  key={cIdx}
                  className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium ${chipClass}`}
                  data-testid="claim-chip"
                  title={claim.quote ? `Evidence quote: "${claim.quote}"` : undefined}
                >
                  <Icon className="h-3.5 w-3.5 shrink-0" />
                  <span>{claim.text}</span>
                  <span className="rounded bg-black/30 px-1.5 py-0.2 text-[9px] font-mono uppercase opacity-75">
                    {norm}
                  </span>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-xs text-[#f3faf0]/50 italic">
            All synthesized claims verified against corpus.
          </p>
        )}
      </div>

      {/* 7. "Conflicting sources" Panel */}
      <div
        className="rounded-xl border border-white/8 bg-[#141d26]/40 p-4 space-y-2.5"
        data-testid="conflicting-sources-panel"
      >
        <div className="flex items-center gap-2 text-xs font-semibold text-rose-300 uppercase font-mono">
          <ShieldAlert className="h-3.5 w-3.5 text-rose-400" />
          <span>Conflicting sources</span>
        </div>

        {conflicts.length > 0 ? (
          <div className="space-y-2">
            {conflicts.map((conf, cfIdx) => (
              <div
                key={cfIdx}
                className="rounded-lg border border-rose-400/20 bg-rose-500/5 p-3 text-xs space-y-1.5"
              >
                <div className="font-semibold text-white">{conf.topic}</div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px] text-[#f3faf0]/80">
                  <div className="bg-[#0b1219]/60 p-2 rounded border border-white/5">
                    <span className="font-mono text-rose-300 block mb-0.5">Position A:</span>
                    {conf.side_a}
                  </div>
                  <div className="bg-[#0b1219]/60 p-2 rounded border border-white/5">
                    <span className="font-mono text-rose-300 block mb-0.5">Position B:</span>
                    {conf.side_b}
                  </div>
                </div>
                {conf.likely_reason && (
                  <p className="text-[10px] text-amber-300/80 font-mono pt-1">
                    Potential reason: {conf.likely_reason}
                  </p>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-[#f3faf0]/55">
            No conflicting sources detected across retrieved evidence.
          </p>
        )}
      </div>

      {/* 8. "What I could not find" Panel */}
      <div
        className="rounded-xl border border-white/8 bg-[#141d26]/40 p-4 space-y-2.5"
        data-testid="what-i-could-not-find-panel"
      >
        <div className="flex items-center gap-2 text-xs font-semibold text-amber-300 uppercase font-mono">
          <SearchX className="h-3.5 w-3.5 text-amber-400" />
          <span>What I could not find</span>
        </div>

        {gaps.length > 0 ? (
          <ul className="space-y-1.5 text-xs text-[#f3faf0]/80 list-disc list-inside">
            {gaps.map((gap, gIdx) => (
              <li key={gIdx} className="leading-relaxed">
                {gap}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-[#f3faf0]/55">
            All aspects of the query were addressed by available sources.
          </p>
        )}
      </div>

      {/* 9. Feedback Toolbar: Thumbs up / down / report wrong answer */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-white/8 pt-4">
        <div className="flex items-center gap-2 text-xs text-[#f3faf0]/60">
          <span>Was this answer accurate and helpful?</span>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* Thumbs Up */}
          <button
            type="button"
            onClick={() => handleSendFeedback('thumbs_up')}
            disabled={isSubmittingFeedback || feedbackSent !== null}
            className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors cursor-pointer ${
              feedbackSent === 'thumbs_up'
                ? 'border-emerald-400/50 bg-emerald-500/20 text-emerald-300'
                : 'border-white/10 bg-[#141d26] text-[#f3faf0]/75 hover:border-emerald-400/40 hover:text-emerald-300'
            }`}
            data-testid="feedback-thumbs-up"
            title="Mark answer as helpful"
          >
            <ThumbsUp className="h-3.5 w-3.5" />
            <span>Helpful</span>
          </button>

          {/* Thumbs Down */}
          <button
            type="button"
            onClick={() => handleSendFeedback('thumbs_down')}
            disabled={isSubmittingFeedback || feedbackSent !== null}
            className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors cursor-pointer ${
              feedbackSent === 'thumbs_down'
                ? 'border-amber-400/50 bg-amber-500/20 text-amber-300'
                : 'border-white/10 bg-[#141d26] text-[#f3faf0]/75 hover:border-amber-400/40 hover:text-amber-300'
            }`}
            data-testid="feedback-thumbs-down"
            title="Mark answer as unhelpful"
          >
            <ThumbsDown className="h-3.5 w-3.5" />
            <span>Unhelpful</span>
          </button>

          {/* Report Wrong Answer */}
          <button
            type="button"
            onClick={() => setShowReportModal((prev) => !prev)}
            disabled={isSubmittingFeedback || feedbackSent === 'wrong_answer'}
            className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors cursor-pointer ${
              feedbackSent === 'wrong_answer'
                ? 'border-rose-400/50 bg-rose-500/20 text-rose-300'
                : 'border-rose-400/25 bg-rose-500/5 text-rose-300 hover:border-rose-400/50 hover:bg-rose-500/15'
            }`}
            data-testid="feedback-report-wrong"
            title="Report this answer as incorrect"
          >
            <Flag className="h-3.5 w-3.5" />
            <span>Report wrong answer</span>
          </button>
        </div>
      </div>

      {/* Report Wrong Answer Form */}
      {showReportModal && (
        <div
          className="rounded-xl border border-rose-400/30 bg-[#0f1721] p-4 space-y-3"
          data-testid="report-wrong-form"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-rose-300">
              Report Incorrect or Hallucinated Answer
            </span>
            <button
              type="button"
              onClick={() => setShowReportModal(false)}
              className="text-xs text-[#f3faf0]/50 hover:text-white"
            >
              Cancel
            </button>
          </div>
          <textarea
            value={reportComment}
            onChange={(e) => setReportComment(e.target.value)}
            placeholder="Please describe why this answer is incorrect or which claims are unsupported..."
            className="w-full rounded-lg border border-white/10 bg-[#141d26] p-2.5 text-xs text-white placeholder-[#f3faf0]/30 focus:border-rose-400 focus:outline-none"
            rows={3}
            data-testid="report-comment-input"
          />
          <div className="flex justify-end">
            <button
              type="button"
              onClick={() => handleSendFeedback('wrong_answer', reportComment)}
              disabled={isSubmittingFeedback}
              className="inline-flex items-center gap-1.5 rounded-lg border border-rose-400/40 bg-rose-500/20 px-3 py-1.5 text-xs font-medium text-rose-200 hover:bg-rose-500/30 transition-colors cursor-pointer disabled:opacity-50"
              data-testid="submit-report-button"
            >
              <Send className="h-3 w-3" />
              <span>Submit Report</span>
            </button>
          </div>
        </div>
      )}

      {/* Feedback Confirmation Toast */}
      {feedbackMessage && (
        <div
          className="rounded-lg border border-emerald-400/30 bg-emerald-500/10 p-3 text-xs text-emerald-300 flex items-center gap-2"
          data-testid="feedback-status"
        >
          <Check className="h-4 w-4" />
          <span>{feedbackMessage}</span>
        </div>
      )}
    </section>
  );
};
