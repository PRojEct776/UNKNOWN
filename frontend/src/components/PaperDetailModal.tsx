import React, { useState, useEffect } from 'react';
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
} from 'lucide-react';
import {
  fetchDocumentDetail,
  getDocumentDownloadUrl,
  type BackendDocument,
  type BackendDocumentDetail,
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
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!isOpen || !document) {
      setDetail(null);
      setError(null);
      return;
    }

    const loadDetail = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const data = await fetchDocumentDetail(document.name);
        setDetail(data);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Failed to load paper details');
      } finally {
        setIsLoading(false);
      }
    };

    void loadDetail();
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

  const handleQuery = () => {
    if (onQueryPaper) {
      const q = document.name.toLowerCase().includes('ieee')
        ? 'What is SAC-RAG and its key findings?'
        : `What are the core findings and methodologies in ${document.name}?`;
      onQueryPaper(q);
      onClose();
    }
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 overflow-y-auto">
        {/* Backdrop Blur */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="fixed inset-0 bg-[#070b10]/80 backdrop-blur-sm"
        />

        {/* Modal Container */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 15 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 15 }}
          transition={{ duration: 0.2 }}
          className="relative z-10 flex max-h-[90vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl border border-[#4d728e]/40 bg-[#111a22] shadow-2xl"
        >
          {/* Header */}
          <div className="flex shrink-0 items-center justify-between border-b border-white/8 bg-[#0c1217] px-6 py-4">
            <div className="flex items-center gap-3 min-w-0">
              <div className="p-2 rounded-xl bg-[#141d26] text-[#d2434e] border border-[#d2434e]/30 shrink-0">
                <FileText className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-[#d2434e]/20 text-[#d2434e] border border-[#d2434e]/30">
                    {document.document_type.toUpperCase().replace('.', '')} Paper
                  </span>
                  <span className="text-xs font-mono text-[#a7d0d2] truncate">
                    {document.name}
                  </span>
                </div>
                <h2 className="text-base font-bold text-white truncate mt-0.5">
                  {document.title || document.name}
                </h2>
              </div>
            </div>

            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-[#f3faf0]/60 hover:text-white hover:bg-white/10 transition-colors cursor-pointer shrink-0 ml-4"
              aria-label="Close paper view"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Quick Action Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/8 bg-[#141d26]/80 px-6 py-3">
            <div className="flex flex-wrap items-center gap-3 text-xs font-mono text-[#f3faf0]/70">
              <span>{document.total_pages} {document.total_pages === 1 ? 'Page' : 'Pages'}</span>
              <span>·</span>
              <span>{document.total_words.toLocaleString()} Words</span>
              <span>·</span>
              <span className="text-emerald-300 font-semibold">{document.chunks_count} Chunks Indexed</span>
            </div>

            <div className="flex items-center gap-2">
              <a
                href={downloadUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 rounded-lg border border-[#a7d0d2]/40 bg-[#141d26] px-3.5 py-1.5 text-xs font-medium text-[#a7d0d2] hover:bg-[#a7d0d2] hover:text-[#0b1219] transition-all cursor-pointer shadow-sm"
              >
                {isPdf ? (
                  <>
                    <ExternalLink className="h-3.5 w-3.5" />
                    <span>Open Original PDF</span>
                  </>
                ) : (
                  <>
                    <Download className="h-3.5 w-3.5" />
                    <span>Download Original File</span>
                  </>
                )}
              </a>

              {onQueryPaper && (
                <button
                  type="button"
                  onClick={handleQuery}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-[#d2434e] px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-[#b83842] transition-colors cursor-pointer shadow-sm"
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  <span>Ask AI About This Paper</span>
                </button>
              )}
            </div>
          </div>

          {/* Content Body */}
          <div className="flex-1 overflow-y-auto p-6 space-y-4 text-[#f3faf0]">
            {isLoading && (
              <div className="flex flex-col items-center justify-center py-16 text-xs text-[#a7d0d2] space-y-3">
                <Loader2 className="h-8 w-8 animate-spin text-[#d2434e]" />
                <p>Loading document content and metadata...</p>
              </div>
            )}

            {error && (
              <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-xs text-rose-300 flex items-start gap-3">
                <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold">Unable to load document preview</p>
                  <p className="mt-1 text-rose-200/80">{error}</p>
                  <a
                    href={downloadUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-3 inline-flex items-center gap-1 underline hover:text-white"
                  >
                    <span>Download original file directly</span>
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              </div>
            )}

            {!isLoading && !error && detail && (
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
                  {detail.content || detail.preview || 'No text extracted for this document.'}
                </div>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="flex shrink-0 items-center justify-between border-t border-white/8 bg-[#0c1217] px-6 py-3.5 text-xs text-[#f3faf0]/60">
            <span className="font-mono text-[11px]">Server Path: backend/datasets/papers/{document.name}</span>
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
