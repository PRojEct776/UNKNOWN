import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  FileText,
  Download,
  ExternalLink,
  X,
  Loader2,
  AlertCircle,
  Sparkles,
  BookOpen,
  Copy,
  Check,
  HelpCircle,
  Award,
  Layers,
  Image as ImageIcon,
  Dna,
  Network,
} from 'lucide-react';
import {
  fetchDocumentDetail,
  fetchDocumentOverview,
  getDocumentDownloadUrl,
  type BackendDocument,
  type BackendDocumentDetail,
  type BackendDocumentOverview,
} from '../lib/api';

interface PaperDetailModalProps {
  document: BackendDocument | null;
  isOpen: boolean;
  onClose: () => void;
  onQueryPaper?: (query: string) => void;
}

export const PaperDetailModal: React.FC<PaperDetailModalProps> = ({
  document,
  isOpen,
  onClose,
  onQueryPaper,
}) => {
  const [detail, setDetail] = useState<BackendDocumentDetail | null>(null);
  const [overview, setOverview] = useState<BackendDocumentOverview | null>(null);
  const [isOverviewLoading, setIsOverviewLoading] = useState(false);
  const [overviewProgress, setOverviewProgress] = useState(15);
  const [activeTab, setActiveTab] = useState<'overview' | 'text'>('overview');
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const progressIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!isOpen || !document) {
      setDetail(null);
      setOverview(null);
      setError(null);
      setIsOverviewLoading(false);
      setOverviewProgress(15);
      if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
      return;
    }

    const loadData = async () => {
      setIsOverviewLoading(true);
      setError(null);
      setOverviewProgress(20);

      // Smooth progress animation while waiting for backend overview
      if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
      progressIntervalRef.current = setInterval(() => {
        setOverviewProgress((prev) => {
          if (prev >= 90) return prev;
          return prev + Math.floor(Math.random() * 8 + 4);
        });
      }, 400);

      try {
        const [overviewData, detailData] = await Promise.all([
          fetchDocumentOverview(document.name),
          fetchDocumentDetail(document.name).catch(() => null),
        ]);
        setOverview(overviewData);
        if (detailData) setDetail(detailData);
        setOverviewProgress(100);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Failed to generate document overview');
      } finally {
        if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
        setIsOverviewLoading(false);
      }
    };

    void loadData();

    return () => {
      if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
    };
  }, [isOpen, document]);

  if (!isOpen || !document) return null;

  const downloadUrl = getDocumentDownloadUrl(document.name);
  const isPdf = document.name.toLowerCase().endsWith('.pdf');

  const handleCopyText = () => {
    const textToCopy = detail?.content || detail?.preview || '';
    if (textToCopy) {
      void navigator.clipboard.writeText(textToCopy);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleQuery = (customQuery?: string) => {
    if (isOverviewLoading) return;
    if (onQueryPaper) {
      const q =
        customQuery ||
        (document.name.toLowerCase().includes('ieee')
          ? 'What is SAC-RAG and its key findings?'
          : `What are the core findings and methodologies in ${document.name}?`);
      onQueryPaper(q);
      onClose();
    }
  };

  const iqScore = overview?.document_iq?.iq_score;
  const iqGrade = overview?.document_iq?.grade;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 overflow-y-auto">
        {/* Backdrop Blur */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="fixed inset-0 bg-[#070b10]/85 backdrop-blur-md"
        />

        {/* Modal Container */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 15 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 15 }}
          transition={{ duration: 0.2 }}
          className="relative z-10 flex max-h-[92vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-[#4d728e]/40 bg-[#10171e] shadow-2xl"
        >
          {/* Header */}
          <div className="flex shrink-0 items-center justify-between border-b border-white/8 bg-[#0c1217] px-6 py-4">
            <div className="flex items-center gap-3 min-w-0">
              <div className="p-2.5 rounded-xl bg-[#141d26] text-[#d2434e] border border-[#d2434e]/30 shrink-0">
                <FileText className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-[#d2434e]/20 text-[#d2434e] border border-[#d2434e]/30">
                    {document.document_type.toUpperCase().replace('.', '')} Document
                  </span>
                  <span className="text-xs font-mono text-[#a7d0d2] truncate">
                    {document.name}
                  </span>
                  {overview?.from_cache && (
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                      ⚡ Cached by Hash
                    </span>
                  )}
                </div>
                <h2 className="text-base font-bold text-white truncate mt-0.5">
                  {overview?.title || document.title || document.name}
                </h2>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <a
                href={downloadUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 rounded-lg border border-[#a7d0d2]/40 bg-[#141d26] px-3 py-1.5 text-xs font-medium text-[#a7d0d2] hover:bg-[#a7d0d2] hover:text-[#0b1219] transition-all cursor-pointer shadow-sm"
              >
                {isPdf ? (
                  <>
                    <ExternalLink className="h-3.5 w-3.5" />
                    <span>PDF</span>
                  </>
                ) : (
                  <>
                    <Download className="h-3.5 w-3.5" />
                    <span>File</span>
                  </>
                )}
              </a>

              <button
                onClick={onClose}
                className="p-1.5 rounded-lg text-[#f3faf0]/60 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
                aria-label="Close modal"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* Progress Bar & Pending Indicator */}
          {isOverviewLoading && (
            <div className="bg-[#141d26] border-b border-white/8 px-6 py-2.5">
              <div className="flex items-center justify-between text-xs mb-1.5">
                <span className="flex items-center gap-2 text-[#a7d0d2] font-mono">
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-[#d2434e]" />
                  <span>Generating Grounded Overview with Page Verifications...</span>
                </span>
                <span className="font-mono text-xs text-[#f3faf0]/60">{overviewProgress}%</span>
              </div>
              <div className="w-full bg-[#0b1219] rounded-full h-2 overflow-hidden border border-white/5">
                <div
                  className="bg-gradient-to-r from-[#d2434e] via-[#a7d0d2] to-emerald-400 h-2 transition-all duration-300 rounded-full"
                  style={{ width: `${overviewProgress}%` }}
                />
              </div>
            </div>
          )}

          {/* Feature Actions Bar (Disabled while pending) */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/8 bg-[#141d26]/70 px-6 py-2.5">
            {/* Tabs */}
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setActiveTab('overview')}
                className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                  activeTab === 'overview'
                    ? 'bg-[#a7d0d2] text-[#0b1219] font-bold shadow'
                    : 'text-[#f3faf0]/70 hover:text-white hover:bg-white/5'
                }`}
              >
                Grounded Overview
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('text')}
                className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                  activeTab === 'text'
                    ? 'bg-[#a7d0d2] text-[#0b1219] font-bold shadow'
                    : 'text-[#f3faf0]/70 hover:text-white hover:bg-white/5'
                }`}
              >
                Extracted Text
              </button>
            </div>

            {/* Feature Action Buttons — strictly disabled while overview is pending */}
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => handleQuery(`Extract Knowledge DNA for ${document.name}`)}
                disabled={isOverviewLoading}
                className={`inline-flex items-center gap-1.5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-1.5 text-xs font-semibold text-emerald-400 transition-all ${
                  isOverviewLoading
                    ? 'opacity-40 cursor-not-allowed pointer-events-none'
                    : 'hover:bg-emerald-500 hover:text-white cursor-pointer shadow-sm'
                }`}
                title={isOverviewLoading ? 'Disabled while overview is pending' : 'Extract Knowledge DNA'}
              >
                <Dna className="h-3.5 w-3.5" />
                <span>Knowledge DNA</span>
              </button>

              <button
                type="button"
                onClick={() => handleQuery(`Generate Mind Map for ${document.name}`)}
                disabled={isOverviewLoading}
                className={`inline-flex items-center gap-1.5 rounded-lg border border-[#a7d0d2]/30 bg-[#a7d0d2]/10 px-3 py-1.5 text-xs font-semibold text-[#a7d0d2] transition-all ${
                  isOverviewLoading
                    ? 'opacity-40 cursor-not-allowed pointer-events-none'
                    : 'hover:bg-[#a7d0d2] hover:text-[#0b1219] cursor-pointer shadow-sm'
                }`}
                title={isOverviewLoading ? 'Disabled while overview is pending' : 'Generate Mind Map'}
              >
                <Network className="h-3.5 w-3.5" />
                <span>Mind Map</span>
              </button>

              <button
                type="button"
                onClick={() => handleQuery()}
                disabled={isOverviewLoading}
                className={`inline-flex items-center gap-1.5 rounded-lg bg-[#d2434e] px-3.5 py-1.5 text-xs font-semibold text-white transition-all ${
                  isOverviewLoading
                    ? 'opacity-40 cursor-not-allowed pointer-events-none'
                    : 'hover:bg-[#b83842] cursor-pointer shadow-md'
                }`}
                title={isOverviewLoading ? 'Disabled while overview is pending' : 'Ask AI About This Paper'}
              >
                <Sparkles className="h-3.5 w-3.5" />
                <span>Ask AI</span>
              </button>
            </div>
          </div>

          {/* Modal Body */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6 text-[#f3faf0]">
            {error && (
              <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-xs text-rose-300 flex items-start gap-3">
                <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold">Failed to load overview</p>
                  <p className="mt-1 text-rose-200/80">{error}</p>
                </div>
              </div>
            )}

            {/* TAB 1: Grounded Overview */}
            {activeTab === 'overview' && (
              <div className="space-y-6">
                {/* Metadata KPI Row */}
                <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
                  <div className="p-3 rounded-xl bg-[#141d26] border border-white/5">
                    <span className="text-[11px] font-mono text-[#f3faf0]/60 uppercase">Year</span>
                    <p className="text-sm font-bold text-white mt-0.5">{overview?.year || 'N/A'}</p>
                  </div>
                  <div className="p-3 rounded-xl bg-[#141d26] border border-white/5">
                    <span className="text-[11px] font-mono text-[#f3faf0]/60 uppercase">Pages</span>
                    <p className="text-sm font-bold text-white mt-0.5">{overview?.page_count || document.total_pages}</p>
                  </div>
                  <div className="p-3 rounded-xl bg-[#141d26] border border-white/5">
                    <span className="text-[11px] font-mono text-[#f3faf0]/60 uppercase">Language</span>
                    <p className="text-sm font-bold text-white mt-0.5 uppercase">{overview?.language || 'EN'}</p>
                  </div>
                  <div className="p-3 rounded-xl bg-[#141d26] border border-white/5">
                    <span className="text-[11px] font-mono text-[#f3faf0]/60 uppercase">Figures & Tables</span>
                    <p className="text-sm font-bold text-[#a7d0d2] mt-0.5">
                      {overview?.figure_count || 0} Figs · {overview?.table_count || 0} Tables
                    </p>
                  </div>
                  <div className="p-3 rounded-xl bg-[#141d26] border border-white/5 col-span-2 flex items-center justify-between">
                    <div>
                      <span className="text-[11px] font-mono text-[#f3faf0]/60 uppercase flex items-center gap-1">
                        <Award className="h-3 w-3 text-emerald-400" />
                        <span>Document IQ</span>
                      </span>
                      <p className="text-sm font-bold text-white mt-0.5">
                        {iqScore != null ? <>Score: <span className="text-emerald-400">{iqScore}</span> / 100</> : 'Not scored'}
                      </p>
                    </div>
                    <span className="text-xs font-mono font-bold px-2.5 py-1 rounded-md bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                      {iqGrade ? `Grade ${iqGrade}` : 'No grade'}
                    </span>
                  </div>
                </div>

                {/* Authors Bar */}
                {overview?.authors && overview.authors.length > 0 && (
                  <div className="p-3 rounded-xl bg-[#141d26]/50 border border-white/5 text-xs">
                    <span className="text-[#a7d0d2] font-semibold">Authors: </span>
                    <span className="text-[#f3faf0]/80">{overview.authors.join(', ')}</span>
                  </div>
                )}

                {/* 5-Sentence Grounded Summary with Page References */}
                <div className="rounded-2xl border border-[#4d728e]/30 bg-[#121b24] p-5 shadow-lg space-y-3">
                  <div className="flex items-center justify-between border-b border-white/8 pb-2.5">
                    <div className="flex items-center gap-2 text-sm font-bold text-white">
                      <BookOpen className="h-4 w-4 text-[#d2434e]" />
                      <span>5-Sentence Grounded Summary</span>
                    </div>
                    <span className="text-[11px] font-mono text-[#a7d0d2]">
                      Grounded & Quote-Verified
                    </span>
                  </div>

                  {isOverviewLoading && !overview?.summary_sentences?.length ? (
                    <div className="py-8 flex flex-col items-center justify-center text-xs text-[#a7d0d2] space-y-2">
                      <Loader2 className="h-6 w-6 animate-spin text-[#d2434e]" />
                      <p>Synthesizing verified sentences from retrieved chunks...</p>
                    </div>
                  ) : (
                    <div className="space-y-3 pt-1">
                      {overview?.summary_sentences?.map((sent, idx) => (
                        <div
                          key={idx}
                          className="flex items-start gap-3 p-3 rounded-xl bg-[#0c131a] border border-white/5 hover:border-[#a7d0d2]/30 transition-colors"
                        >
                          <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#1b2733] text-[10px] font-mono font-bold text-[#a7d0d2] mt-0.5">
                            {idx + 1}
                          </span>
                          <div className="flex-1 space-y-1.5">
                            <p className="text-xs leading-relaxed text-[#f3faf0]/90">
                              {sent.text}
                            </p>
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="inline-flex items-center gap-1 rounded bg-[#d2434e]/15 px-2 py-0.5 text-[10px] font-mono font-semibold text-[#d2434e] border border-[#d2434e]/30">
                                📄 {sent.page_ref}
                              </span>
                              {sent.quote && (
                                <span className="text-[10px] text-[#f3faf0]/50 italic truncate max-w-md font-mono" title={sent.quote}>
                                  "{sent.quote}"
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Key Topics */}
                {overview?.key_topics && overview.key_topics.length > 0 && (
                  <div className="space-y-2">
                    <span className="text-xs font-mono uppercase tracking-wider text-[#a7d0d2] flex items-center gap-1.5">
                      <Layers className="h-3.5 w-3.5" />
                      <span>Key Research Topics</span>
                    </span>
                    <div className="flex flex-wrap gap-2">
                      {overview.key_topics.map((topic, i) => (
                        <span
                          key={i}
                          className="px-2.5 py-1 rounded-lg bg-[#141d26] border border-white/8 text-xs text-[#f3faf0]/80 font-medium hover:border-[#a7d0d2]/40 transition-colors"
                        >
                          {topic}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Figures & Tables Count with Thumbnails */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono uppercase tracking-wider text-[#a7d0d2] flex items-center gap-1.5">
                      <ImageIcon className="h-3.5 w-3.5 text-[#d2434e]" />
                      <span>Figures & Quantitative Tables</span>
                    </span>
                    <span className="text-[11px] font-mono text-[#f3faf0]/50">
                      {overview?.figures?.length || 0} Figures · {overview?.tables?.length || 0} Tables
                    </span>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    {overview?.figures?.slice(0, 2).map((fig) => (
                      <div
                        key={fig.id}
                        className="p-2.5 rounded-xl bg-[#141d26] border border-white/5 space-y-2 flex flex-col items-center text-center"
                      >
                        <img
                          src={fig.thumbnail}
                          alt={fig.label}
                          className="w-full h-20 object-contain rounded-lg bg-[#0b1219]"
                        />
                        <div className="text-[11px]">
                          <p className="font-bold text-white">{fig.label}</p>
                          <p className="text-[10px] text-[#f3faf0]/60">Page {fig.page}</p>
                        </div>
                      </div>
                    ))}

                    {overview?.tables?.slice(0, 2).map((tbl) => (
                      <div
                        key={tbl.id}
                        className="p-2.5 rounded-xl bg-[#141d26] border border-white/5 space-y-2 flex flex-col items-center text-center"
                      >
                        <img
                          src={tbl.thumbnail}
                          alt={tbl.label}
                          className="w-full h-20 object-contain rounded-lg bg-[#0b1219]"
                        />
                        <div className="text-[11px]">
                          <p className="font-bold text-[#a7d0d2]">{tbl.label}</p>
                          <p className="text-[10px] text-[#f3faf0]/60">Page {tbl.page}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* 5 Suggested Research Questions (Click to Ask) */}
                {overview?.suggested_questions && overview.suggested_questions.length > 0 && (
                  <div className="space-y-2.5">
                    <span className="text-xs font-mono uppercase tracking-wider text-[#a7d0d2] flex items-center gap-1.5">
                      <HelpCircle className="h-3.5 w-3.5 text-amber-400" />
                      <span>Suggested Research Questions</span>
                    </span>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                      {overview.suggested_questions.map((q, idx) => (
                        <button
                          key={idx}
                          type="button"
                          onClick={() => handleQuery(q)}
                          disabled={isOverviewLoading}
                          className={`p-3 rounded-xl border border-white/5 bg-[#141d26] text-left transition-all flex items-start gap-2.5 ${
                            isOverviewLoading
                              ? 'opacity-40 cursor-not-allowed pointer-events-none'
                              : 'hover:border-[#a7d0d2]/40 hover:bg-[#1a252f] cursor-pointer group'
                          }`}
                        >
                          <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#1e2a36] text-[10px] font-mono text-[#a7d0d2] mt-0.5 group-hover:bg-[#d2434e] group-hover:text-white transition-colors">
                            ?
                          </span>
                          <span className="text-xs text-[#f3faf0]/85 group-hover:text-white transition-colors">
                            {q}
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* TAB 2: Raw Extracted Text */}
            {activeTab === 'text' && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <BookOpen className="h-4 w-4 text-[#a7d0d2]" />
                    <h3 className="text-xs font-mono uppercase tracking-wider text-[#a7d0d2]">
                      Extracted Text Content & Abstract Preview
                    </h3>
                  </div>
                  <button
                    type="button"
                    onClick={handleCopyText}
                    className="inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-[#141d26] px-2.5 py-1 text-[11px] text-[#f3faf0]/70 hover:text-white hover:border-[#a7d0d2]/40 transition-colors cursor-pointer"
                  >
                    {copied ? (
                      <>
                        <Check className="h-3 w-3 text-emerald-400" />
                        <span className="text-emerald-300">Copied!</span>
                      </>
                    ) : (
                      <>
                        <Copy className="h-3 w-3" />
                        <span>Copy Text</span>
                      </>
                    )}
                  </button>
                </div>

                <div className="rounded-xl border border-white/8 bg-[#0b1219] p-4 text-xs leading-relaxed text-[#f3faf0]/85 font-mono whitespace-pre-wrap max-h-[460px] overflow-y-auto">
                  {detail?.content || detail?.preview || 'No text extracted for this document.'}
                </div>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="flex shrink-0 items-center justify-between border-t border-white/8 bg-[#0c1217] px-6 py-3.5 text-xs text-[#f3faf0]/60">
            <span className="font-mono text-[11px]">Backend Storage: datasets/papers/{document.name}</span>
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg bg-[#1a252d] px-4 py-1.5 text-xs font-semibold text-white border border-white/10 hover:bg-[#253540] transition-colors cursor-pointer"
            >
              Close
            </button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};
