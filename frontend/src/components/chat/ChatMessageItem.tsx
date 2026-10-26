import React, { useState } from 'react';
import {
  User,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  ThumbsUp,
  ThumbsDown,
  Globe,
  FileText,
  AlertTriangle,
  Dna,
  Waypoints,
  Orbit,
  BookOpen,
  Info,
} from 'lucide-react';
import type { ChatMessage } from '../../types/chat';
import type { Source } from '../../types/evidence';
import { ConfidenceBadge } from '../answers/ConfidenceBadge';
import { ComparisonView, DebateView, GapView, VerificationView } from '../analysis/AnalysisViews';
import { ReasoningTimeline } from '../reasoning/ReasoningTimeline';
import { KnowledgeMindMap } from '../visualization/KnowledgeMindMap';
import { KnowledgeDNA } from '../visualization/KnowledgeDNA';
import { ConceptGraph3D } from '../ConceptGraph3D';
import { buildOrbitGraphFromMessage } from '../../lib/orbitGraphBuilder';
import { OverviewOrbitModal } from './OverviewOrbitModal';
import { submitFeedback } from '../../lib/api';
import { downloadResultExport, exportResultToMarkdown, exportResultToPrintableHtml } from '../../lib/exportUtils';

interface ChatMessageItemProps {
  message: ChatMessage;
  onOpenSourcesDrawer: (sources: Source[]) => void;
}

export const ChatMessageItem: React.FC<ChatMessageItemProps> = ({
  message,
  onOpenSourcesDrawer,
}) => {
  const [copied, setCopied] = useState(false);
  const [showDetailed, setShowDetailed] = useState(false);
  const [showMindMapModal, setShowMindMapModal] = useState(false);
  const [showDnaModal, setShowDnaModal] = useState(false);
  const [showOrbitModal, setShowOrbitModal] = useState(false);
  const [feedbackSent, setFeedbackSent] = useState<'thumbs_up' | 'thumbs_down' | null>(null);
  const [isExporting, setIsExporting] = useState(false);

  // 1. Render Overview Card if sender is 'overview'
  if (message.sender === 'overview') {
    const ov = message.overview;
    const questions = ov?.questions_it_can_answer || ov?.suggested_questions || [];
    const findings = ov?.main_findings || ov?.summary_sentences?.map((s) => s.text) || [];
    // The backend does not generate methods; key_topics are unlabelled keywords,
    // so they are never shown under a Methods heading.
    const methods = ov?.methods_and_investigations || [];

    return (
      <div className="py-4 px-3 sm:px-6">
        <div className="max-w-4xl mx-auto rounded-2xl border border-[#4d728e]/35 bg-[#101720] shadow-xl p-5 space-y-4">
          <div className="flex items-start justify-between gap-3 border-b border-white/8 pb-3">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-[#1b2632] border border-[#a7d0d2]/40 flex items-center justify-center text-[#a7d0d2]">
                <FileText className="w-4 h-4" />
              </div>
              <div>
                <span className="text-[10px] font-mono uppercase text-[#a7d0d2] tracking-wider">
                  Document Overview
                </span>
                <h3 className="text-sm font-bold text-white">
                  {ov?.title || message.documentName || 'Uploaded Document'}
                </h3>
              </div>
            </div>

            {ov?.document_iq && (
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#162330] border border-[#a7d0d2]/30 text-xs font-mono text-[#a7d0d2]">
                <span>
                  IQ:{' '}
                  {typeof ov.document_iq === 'object'
                    ? ov.document_iq.iq_score ?? ov.document_iq.grade ?? 'not available'
                    : ov.document_iq}
                </span>
              </div>
            )}
          </div>

          {/* Executive Summary */}
          {(ov?.executive_summary || (ov?.summary_sentences && ov.summary_sentences.length > 0)) && (
            <div className="text-xs leading-relaxed text-[#f3faf0]/85 bg-[#0b1117]/60 p-3.5 rounded-xl border border-white/5">
              <p className="font-semibold text-[#a7d0d2] text-[11px] mb-1 font-mono uppercase">
                Executive Summary
              </p>
              <p>
                {ov?.executive_summary ||
                  ov?.summary_sentences?.map((s) => s.text).join(' ') ||
                  'Document ingested and indexed.'}
              </p>
            </div>
          )}

          {/* Key Findings and Methods Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
            {findings.length > 0 && (
              <div className="p-3 rounded-xl bg-[#0b1117]/40 border border-white/5 space-y-1.5">
                <p className="text-[11px] font-mono uppercase text-emerald-300 font-semibold">
                  Main Findings & Conclusions
                </p>
                <ul className="list-disc list-inside space-y-1 text-[#f3faf0]/75 text-[11px]">
                  {findings.slice(0, 4).map((f: string, i: number) => (
                    <li key={i}>{f}</li>
                  ))}
                </ul>
              </div>
            )}

            {methods.length > 0 && (
              <div className="p-3 rounded-xl bg-[#0b1117]/40 border border-white/5 space-y-1.5">
                <p className="text-[11px] font-mono uppercase text-[#a7d0d2] font-semibold">
                  Methods & Investigations
                </p>
                <ul className="list-disc list-inside space-y-1 text-[#f3faf0]/75 text-[11px]">
                  {methods.slice(0, 4).map((m: string, i: number) => (
                    <li key={i}>{m}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Suggested Questions - MUST BE PLAIN TEXT, NOT CLICKABLE BUTTONS */}
          {questions.length > 0 && (
            <div className="pt-2 border-t border-white/5 space-y-1.5">
              <p className="text-[11px] font-mono uppercase text-[#f3faf0]/60">
                Key questions this document can answer:
              </p>
              <ul className="list-disc list-inside space-y-1 text-xs text-[#f3faf0]/70 pl-1">
                {questions.slice(0, 3).map((q: string, idx: number) => (
                  <li key={idx} className="leading-relaxed">
                    {q}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Action to launch 3D Knowledge Orbit from Overview (Requirement 4) */}
          <div className="pt-2 border-t border-white/5 flex items-center justify-between">
            <button
              type="button"
              onClick={() => setShowOrbitModal(true)}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#141d26] hover:bg-[#1b2632] border border-[#4d728e]/40 hover:border-[#a7d0d2]/60 text-xs text-[#a7d0d2] hover:text-white transition-all cursor-pointer shadow-sm group"
            >
              <Orbit className="w-3.5 h-3.5 text-[#d2434e] group-hover:rotate-45 transition-transform" />
              <span className="font-medium">Explore Overview in 3D Knowledge Orbit</span>
            </button>
            {showOrbitModal && (
              <OverviewOrbitModal
                documentName={ov?.document_name || message.documentName || ''}
                onClose={() => setShowOrbitModal(false)}
              />
            )}
          </div>
        </div>
      </div>
    );
  }

  // 2. Render User Message
  if (message.sender === 'user') {
    return (
      <div className="py-4 px-3 sm:px-6">
        <div className="max-w-4xl mx-auto flex items-start gap-3 justify-end">
          <div className="flex flex-col items-end max-w-2xl space-y-1.5">
            {/* Scope / Feature badges */}
            <div className="flex flex-wrap items-center gap-1.5 text-[10px] font-mono text-[#f3faf0]/50">
              {message.feature && (
                <span className="px-2 py-0.5 rounded-full bg-[#162330] border border-[#4d728e]/30 text-[#a7d0d2] capitalize">
                  {message.feature}
                </span>
              )}
              {message.selectedDocIds && message.selectedDocIds.length > 0 && (
                <span className="px-2 py-0.5 rounded-full bg-[#151f28] border border-white/10 text-[#f3faf0]/70">
                  {message.selectedDocIds.length === 1
                    ? message.selectedDocIds[0]
                    : `${message.selectedDocIds.length} docs`}
                </span>
              )}
              {message.includeWeb && (
                <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-300">
                  +Web
                </span>
              )}
              <span>{message.timestamp}</span>
            </div>

            {/* Bubble */}
            <div className="bg-[#1b2632] border border-[#4d728e]/35 text-white text-sm rounded-2xl rounded-tr-xs px-4 py-3 shadow-md leading-relaxed">
              {message.text}
            </div>
          </div>

          <div className="w-8 h-8 rounded-full bg-[#d2434e]/20 border border-[#d2434e]/50 flex items-center justify-center text-white shrink-0 mt-1">
            <User className="w-4 h-4 text-[#d2434e]" />
          </div>
        </div>
      </div>
    );
  }

  // 3. Render Assistant Message
  const result = message.result;
  const isInsufficient =
    result?.answerState === 'insufficient_evidence' ||
    (result?.answer && result.answer.includes('Not found in available sources'));

  const handleCopy = () => {
    if (!result?.answer) return;
    navigator.clipboard.writeText(result.answer);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleFeedback = async (type: 'thumbs_up' | 'thumbs_down') => {
    setFeedbackSent(type);
    try {
      await submitFeedback({
        query: message.text || '',
        answer: result?.answer || '',
        sources: (result?.sources || []).map((s) => ({
          document: s.documentName,
          page: s.page,
          chunk_id: s.chunkId || s.id,
        })),
        feedback_type: type,
      });
    } catch {
      // non-blocking
    }
  };

  const handleExport = async (format: 'pdf' | 'docx' | 'markdown' | 'html') => {
    if (!result) return;
    setIsExporting(true);
    try {
      if (format === 'markdown') {
        exportResultToMarkdown(result);
      } else if (format === 'html') {
        exportResultToPrintableHtml(result);
      } else {
        await downloadResultExport(
          {
            query: message.text || 'UNKNOWN Result',
            answer: result.answer,
            detailed_answer: result.detailedAnswer,
            doc_section: result.doc_section || undefined,
            web_section: result.web_section || undefined,
            confidence: result.confidence ?? undefined,
            sources: result.sources.map((s) => ({
              document: s.documentName,
              page: s.page,
              chunk_id: s.chunkId || s.id,
            })),
          },
          format
        );
      }
    } catch (err) {
      console.error('Export failed:', err);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="py-5 px-3 sm:px-6 bg-[#0c1218]/40 border-y border-white/5">
      <div className="max-w-4xl mx-auto flex items-start gap-3 sm:gap-4">
        {/* UNKNOWN Brand Avatar */}
        <div className="w-8 h-8 rounded-xl overflow-hidden border border-[#d2434e]/50 shrink-0 bg-[#080d12] shadow-sm mt-1">
          <img src="/unknown-logo.jpg" alt="UNKNOWN" className="w-full h-full object-cover" />
        </div>

        {/* Message Content */}
        <div className="flex-1 min-w-0 space-y-4">
          {/* Header row: Confidence badge & Sources count */}
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-white tracking-wide">UNKNOWN Research</span>
              {result?.confidence !== undefined && result?.confidence !== null && (
                <ConfidenceBadge confidence={result.confidence} />
              )}
            </div>

            {result?.sources && result.sources.length > 0 && (
              <button
                type="button"
                onClick={() => onOpenSourcesDrawer(result.sources)}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#141d26] hover:bg-[#1b2632] border border-[#4d728e]/35 text-xs text-[#a7d0d2] hover:text-white transition-colors cursor-pointer"
              >
                <BookOpen className="w-3.5 h-3.5" />
                <span>{result.sources.length} sources</span>
              </button>
            )}
          </div>

          {/* Insufficient Evidence Panel (if triggered) */}
          {isInsufficient && (
            <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 space-y-2 text-xs">
              <div className="flex items-center gap-2 text-amber-200 font-semibold">
                <AlertTriangle className="w-4 h-4" />
                <span>Insufficient Evidence in Scoped Sources</span>
              </div>
              <p className="text-[#f3faf0]/80 leading-relaxed">
                The requested query could not be verified or substantiated from the currently selected documents.
                No facts were fabricated. Consider enabling Web Evidence or selecting additional relevant papers.
              </p>
            </div>
          )}

          {/* Direct Answer */}
          {result?.answer && (
            <div className="text-sm leading-relaxed text-[#f3faf0]/90 space-y-2 whitespace-pre-line font-sans">
              {result.answer}
            </div>
          )}

          {/* Collapsible Detailed Answer */}
          {result?.detailedAnswer && result.detailedAnswer !== result.answer && (
            <div className="border border-white/8 rounded-xl overflow-hidden bg-[#0e161f]">
              <button
                type="button"
                onClick={() => setShowDetailed(!showDetailed)}
                className="w-full flex items-center justify-between p-3 text-xs font-semibold text-[#a7d0d2] hover:text-white hover:bg-white/5 transition-colors cursor-pointer"
              >
                <span className="flex items-center gap-1.5">
                  <Info className="w-3.5 h-3.5" />
                  Detailed Evidence Breakdown
                </span>
                {showDetailed ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </button>
              {showDetailed && (
                <div className="p-4 pt-0 border-t border-white/5 text-xs text-[#f3faf0]/80 leading-relaxed whitespace-pre-line">
                  {result.detailedAnswer}
                </div>
              )}
            </div>
          )}

          {/* Dual Evidence: Document vs Web Sections */}
          {(result?.doc_section || result?.web_section) && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs pt-1">
              {result.doc_section && (
                <div className="p-3.5 rounded-xl bg-[#0e161f] border border-[#4d728e]/25 space-y-1.5">
                  <div className="flex items-center gap-1.5 text-[#a7d0d2] font-semibold text-[11px] font-mono uppercase">
                    <FileText className="w-3.5 h-3.5" />
                    <span>From Your Documents</span>
                  </div>
                  <p className="text-[#f3faf0]/80 leading-relaxed text-xs">{result.doc_section}</p>
                </div>
              )}

              {result.web_section && (
                <div className="p-3.5 rounded-xl bg-[#0e161f] border border-emerald-500/25 space-y-1.5">
                  <div className="flex items-center gap-1.5 text-emerald-300 font-semibold text-[11px] font-mono uppercase">
                    <Globe className="w-3.5 h-3.5" />
                    <span>From External Sources</span>
                  </div>
                  <p className="text-[#f3faf0]/80 leading-relaxed text-xs">{result.web_section}</p>
                </div>
              )}
            </div>
          )}

          {/* Feature Specific Rich Panels */}
          {/* Reason timeline */}
          {result?.reasoning && result.reasoning.steps && result.reasoning.steps.length > 0 && (
            <div className="pt-2">
              <ReasoningTimeline
                reasoning={result.reasoning}
                onOpenSources={() => onOpenSourcesDrawer(result.sources)}
              />
            </div>
          )}

          {/* Verification table */}
          {result?.verification && result.verification.length > 0 && (
            <div className="pt-2">
              <VerificationView results={result.verification} onOpenSources={() => onOpenSourcesDrawer(result.sources)} />
            </div>
          )}

          {/* Comparison matrix */}
          {result?.comparison && result.comparison.length > 0 && (
            <div className="pt-2">
              <ComparisonView
                rows={result.comparison}
                entities={result.comparisonEntities}
                onOpenSources={() => onOpenSourcesDrawer(result.sources)}
              />
            </div>
          )}

          {/* Research Gaps view */}
          {result?.researchGap && result.researchGap.title && (
            <div className="pt-2">
              <GapView gap={result.researchGap} onOpenSources={() => onOpenSourcesDrawer(result.sources)} />
            </div>
          )}

          {/* Debate view */}
          {result?.debate && result.debate.positions && result.debate.positions.length > 0 && (
            <div className="pt-2">
              <DebateView debate={result.debate} onOpenSources={() => onOpenSourcesDrawer(result.sources)} />
            </div>
          )}

          {/* One Contextually Relevant 3D Knowledge Orbit Action (Requirement 2) */}
          {(Boolean(result?.sources && result.sources.length > 0) || Boolean(result?.concept) || Boolean(result?.mindMap) || Boolean(result?.knowledgeDNA)) && (
            <div className="pt-2 border-t border-white/5">
              <button
                type="button"
                onClick={() => setShowOrbitModal(true)}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#141d26] hover:bg-[#1b2632] border border-[#4d728e]/40 hover:border-[#a7d0d2]/60 text-xs text-[#a7d0d2] hover:text-white transition-all cursor-pointer shadow-sm group"
              >
                <Orbit className="w-3.5 h-3.5 text-[#d2434e] group-hover:rotate-45 transition-transform" />
                <span className="font-medium">Explore in 3D Knowledge Orbit</span>
                <span className="text-[10px] text-[#f3faf0]/50 font-mono">
                  ({(result?.sources?.length || 0) + (result?.comparison?.length || 0) + 3} nodes)
                </span>
              </button>
            </div>
          )}

          {/* Message Bottom Action Bar: Copy, Feedback, Exports */}
          <div className="flex flex-wrap items-center justify-between gap-2 pt-2 text-xs text-[#f3faf0]/50 border-t border-white/5">
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleCopy}
                className="p-1.5 rounded-lg hover:bg-white/5 hover:text-white transition-colors cursor-pointer flex items-center gap-1"
                title="Copy answer"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span className="text-[11px]">{copied ? 'Copied' : 'Copy'}</span>
              </button>

              <div className="h-3 w-[1px] bg-white/10" />

              <button
                type="button"
                onClick={() => handleFeedback('thumbs_up')}
                className={`p-1.5 rounded-lg hover:bg-white/5 transition-colors cursor-pointer ${
                  feedbackSent === 'thumbs_up' ? 'text-emerald-400 bg-emerald-500/10' : 'hover:text-white'
                }`}
                title="Helpful result"
              >
                <ThumbsUp className="w-3.5 h-3.5" />
              </button>

              <button
                type="button"
                onClick={() => handleFeedback('thumbs_down')}
                className={`p-1.5 rounded-lg hover:bg-white/5 transition-colors cursor-pointer ${
                  feedbackSent === 'thumbs_down' ? 'text-rose-400 bg-rose-500/10' : 'hover:text-white'
                }`}
                title="Unsatisfactory or ungrounded"
              >
                <ThumbsDown className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* Export Menu */}
            <div className="flex items-center gap-1">
              <span className="text-[10px] text-[#f3faf0]/40 font-mono mr-1">Export:</span>
              <button
                type="button"
                disabled={isExporting}
                onClick={() => handleExport('pdf')}
                className="px-2 py-0.5 rounded bg-white/5 hover:bg-white/10 hover:text-white text-[10px] font-mono transition-colors cursor-pointer"
                title="Export as PDF"
              >
                PDF
              </button>
              <button
                type="button"
                disabled={isExporting}
                onClick={() => handleExport('docx')}
                className="px-2 py-0.5 rounded bg-white/5 hover:bg-white/10 hover:text-white text-[10px] font-mono transition-colors cursor-pointer"
                title="Export as DOCX"
              >
                DOCX
              </button>
              <button
                type="button"
                disabled={isExporting}
                onClick={() => handleExport('markdown')}
                className="px-2 py-0.5 rounded bg-white/5 hover:bg-white/10 hover:text-white text-[10px] font-mono transition-colors cursor-pointer"
                title="Export as Markdown"
              >
                MD
              </button>
              <button
                type="button"
                disabled={isExporting}
                onClick={() => handleExport('html')}
                className="px-2 py-0.5 rounded bg-white/5 hover:bg-white/10 hover:text-white text-[10px] font-mono transition-colors cursor-pointer"
                title="Export as HTML"
              >
                HTML
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Mind Map Modal */}
      {showMindMapModal && result?.mindMap && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-xs flex flex-col p-4 sm:p-8">
          <div className="flex items-center justify-between pb-3 border-b border-white/10">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Waypoints className="w-4 h-4 text-[#d2434e]" />
              Knowledge Mind Map Explorer
            </h3>
            <button
              type="button"
              onClick={() => setShowMindMapModal(false)}
              className="p-1.5 text-white/60 hover:text-white rounded-lg cursor-pointer"
            >
              ✕
            </button>
          </div>
          <div className="flex-1 overflow-hidden mt-3 rounded-xl bg-[#0b1219]">
            <KnowledgeMindMap root={result.mindMap} />
          </div>
        </div>
      )}

      {/* Knowledge DNA Modal */}
      {showDnaModal && result?.knowledgeDNA && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-xs flex flex-col p-4 sm:p-8">
          <div className="flex items-center justify-between pb-3 border-b border-white/10">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Dna className="w-4 h-4 text-[#d2434e]" />
              Knowledge DNA Structural View
            </h3>
            <button
              type="button"
              onClick={() => setShowDnaModal(false)}
              className="p-1.5 text-white/60 hover:text-white rounded-lg cursor-pointer"
            >
              ✕
            </button>
          </div>
          <div className="flex-1 overflow-auto mt-3 rounded-xl bg-[#0b1219] p-4">
            <KnowledgeDNA data={result.knowledgeDNA} />
          </div>
        </div>
      )}

      {/* 3D Orbit Modal */}
      {showOrbitModal && (
        <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-xs flex flex-col p-4 sm:p-8">
          <div className="flex items-center justify-between pb-3 border-b border-white/10">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Orbit className="w-4 h-4 text-[#d2434e]" />
              3D Interactive Knowledge Orbit
            </h3>
            <button
              type="button"
              onClick={() => setShowOrbitModal(false)}
              className="p-1.5 text-white/60 hover:text-white rounded-lg cursor-pointer"
            >
              ✕
            </button>
          </div>
          <div className="flex-1 overflow-hidden mt-3 rounded-xl bg-[#070b0e]">
            <ConceptGraph3D graphData={buildOrbitGraphFromMessage(message)} documentName={message.selectedDocIds?.[0] || message.documentName || 'active_doc'} onOpenSources={() => onOpenSourcesDrawer(result?.sources || [])} />
          </div>
        </div>
      )}
    </div>
  );
};
