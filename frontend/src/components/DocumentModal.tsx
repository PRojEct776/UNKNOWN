import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  FileText,
  Upload,
  UploadCloud,
  X,
  Loader2,
  CheckCircle2,
  AlertCircle,
  HardDrive,
  Download,
  ExternalLink,
  Eye,
  Trash2,
} from 'lucide-react';
import {
  fetchDocuments,
  uploadDocumentsBatch,
  deleteDocument,
  getDocumentDownloadUrl,
  type BackendDocument,
} from '../lib/api';

interface DocumentModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectDocumentQuery?: (docName: string) => void;
  onOpenPaperDetail?: (doc: BackendDocument) => void;
}

export const DocumentModal: React.FC<DocumentModalProps> = ({
  isOpen,
  onClose,
  onSelectDocumentQuery,
  onOpenPaperDetail,
}) => {
  const [documents, setDocuments] = useState<BackendDocument[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [deletingDocName, setDeletingDocName] = useState<string | null>(null);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadDocs = async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const res = await fetchDocuments();
      setDocuments(res.documents || []);
    } catch (err: unknown) {
      setErrorMessage(
        err instanceof Error ? err.message : 'Failed to load documents',
      );
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      void loadDocs();
    }
  }, [isOpen]);

  const handleFilesUpload = async (files: FileList | File[]) => {
    const fileArray = Array.from(files).filter((f) =>
      /\.(pdf|docx|txt)$/i.test(f.name),
    );

    if (fileArray.length === 0) {
      setErrorMessage('Please select valid .pdf, .docx, or .txt files.');
      return;
    }

    if (documents.length + fileArray.length > 25) {
      setErrorMessage(
        `Workspace collection limit is 25 papers. You currently have ${documents.length} and tried to add ${fileArray.length}.`,
      );
      return;
    }

    setIsUploading(true);
    setUploadStatus(null);
    setErrorMessage(null);

    try {
      const res = await uploadDocumentsBatch(fileArray);
      const readyFiles = res.results.filter((r) => r.status === 'ready');
      const failedFiles = res.results.filter((r) => r.status === 'failed');

      if (readyFiles.length > 0) {
        setUploadStatus(
          `Ingested ${readyFiles.length} paper(s) successfully.`,
        );
      }
      if (failedFiles.length > 0) {
        setErrorMessage(
          `Errors on ${failedFiles.length} file(s): ` +
            failedFiles.map((e) => `${e.filename}: ${e.error || 'Failed'}`).join('; '),
        );
      }
      await loadDocs();
    } catch (err: unknown) {
      setErrorMessage(
        err instanceof Error ? err.message : 'Batch upload failed.',
      );
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleDelete = async (docName: string) => {
    if (!window.confirm(`Are you sure you want to delete "${docName}" from the corpus?`)) {
      return;
    }

    setDeletingDocName(docName);
    setErrorMessage(null);
    try {
      await deleteDocument(docName);
      setUploadStatus(`Deleted "${docName}" and re-indexed corpus.`);
      await loadDocs();
    } catch (err: unknown) {
      setErrorMessage(
        err instanceof Error ? err.message : `Failed to delete ${docName}`,
      );
    } finally {
      setDeletingDocName(null);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      void handleFilesUpload(e.dataTransfer.files);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
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
            className="relative z-10 flex max-h-[88vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-[#4d728e]/35 bg-[#111a22] shadow-2xl"
          >
            {/* Header */}
            <div className="flex shrink-0 items-center justify-between border-b border-white/8 bg-[#0c1217] px-6 py-4">
              <div className="flex items-center gap-2.5">
                <HardDrive className="h-4 w-4 text-[#d2434e]" />
                <h2 className="text-sm font-bold uppercase tracking-wider text-white">
                  Indexed Knowledge Corpus
                </h2>
              </div>
              <button
                onClick={onClose}
                className="p-1.5 rounded-lg text-[#f3faf0]/60 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
                aria-label="Close document modal"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Body */}
            <div className="p-6 overflow-y-auto space-y-6 text-[#f3faf0]">
              {/* Ingestion Area with Drag & Drop */}
              <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={`rounded-xl border border-dashed p-5 text-center transition-all ${
                  documents.length >= 25
                    ? 'border-white/10 bg-[#0b1219]/40 opacity-60'
                    : isDragging
                    ? 'border-[#d2434e] bg-[#1a2530]'
                    : 'border-[#4d728e]/40 bg-[#0b1219]/60 hover:border-[#a7d0d2]/60'
                }`}
              >
                <UploadCloud className="mx-auto h-8 w-8 text-[#a7d0d2] mb-2" />
                <h3 className="text-sm font-semibold text-white">
                  Ingest Papers into Workspace (Batch Upload Supported)
                </h3>
                <p className="mt-1 text-xs text-[#f3faf0]/60 max-w-md mx-auto">
                  Drag and drop multiple PDF, DOCX, or TXT files here, or click the button below. Up to 25 papers per workspace collection.
                </p>

                <div className="mt-3 flex items-center justify-center gap-2">
                  <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-0.5 text-[11px] font-mono text-[#a7d0d2]">
                    Collection: {documents.length}/25 Papers
                  </span>
                </div>

                <div className="mt-4 flex items-center justify-center">
                  <label
                    className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-semibold text-white shadow transition-colors ${
                      documents.length >= 25
                        ? 'bg-zinc-700 cursor-not-allowed text-zinc-400'
                        : isUploading
                        ? 'bg-[#d2434e]/80 cursor-wait'
                        : 'bg-[#d2434e] hover:bg-[#b83842] cursor-pointer'
                    }`}
                  >
                    {isUploading ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Upload className="h-4 w-4" />
                    )}
                    <span>
                      {isUploading
                        ? 'Ingesting & re-indexing...'
                        : documents.length >= 25
                        ? 'Collection Limit Reached (25/25)'
                        : 'Choose Papers (Batch Allowed)'}
                    </span>
                    <input
                      ref={fileInputRef}
                      type="file"
                      multiple
                      accept=".pdf,.docx,.txt"
                      className="hidden"
                      disabled={isUploading || documents.length >= 25}
                      onChange={(e) => {
                        if (e.target.files) {
                          void handleFilesUpload(e.target.files);
                        }
                      }}
                    />
                  </label>
                </div>

                {uploadStatus && (
                  <div className="mt-3 inline-flex items-center gap-1.5 text-xs text-emerald-400 bg-emerald-500/10 px-3 py-1 rounded-full border border-emerald-500/20">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    <span>{uploadStatus}</span>
                  </div>
                )}

                {errorMessage && (
                  <div className="mt-3 inline-flex items-center gap-1.5 text-xs text-rose-300 bg-rose-500/10 px-3 py-1 rounded-full border border-rose-500/20">
                    <AlertCircle className="h-3.5 w-3.5" />
                    <span>{errorMessage}</span>
                  </div>
                )}
              </div>

              {/* Document List */}
              <div className="space-y-3">
                <div className="flex items-center justify-between text-xs font-mono text-[#a7d0d2] uppercase">
                  <span>Indexed Papers ({documents.length} / 25)</span>
                  {isLoading && (
                    <span className="flex items-center gap-1 text-[#f3faf0]/60">
                      <Loader2 className="h-3 w-3 animate-spin" /> Refreshing...
                    </span>
                  )}
                </div>

                {documents.length === 0 && !isLoading ? (
                  <div className="p-8 text-center text-xs text-[#f3faf0]/50 rounded-xl bg-[#0b1219]">
                    No indexed documents found in backend/datasets/papers.
                  </div>
                ) : (
                  <div className="space-y-2.5">
                    {documents.map((doc) => {
                      const isDeleting = deletingDocName === doc.name;
                      return (
                        <div
                          key={doc.name}
                          className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-xl border border-white/5 bg-[#0b1219] p-4 hover:border-[#a7d0d2]/30 transition-colors"
                        >
                          <div className="flex items-start gap-3 min-w-0">
                            <div className="p-2 rounded-lg bg-[#141d26] text-[#d2434e] shrink-0 mt-0.5">
                              <FileText className="h-5 w-5" />
                            </div>
                            <div className="min-w-0">
                              <h4 className="text-sm font-semibold text-white truncate">
                                {doc.title || doc.name}
                              </h4>
                              <p className="text-[11px] font-mono text-[#a7d0d2] truncate">
                                {doc.name}
                              </p>
                              <div className="mt-1 flex flex-wrap items-center gap-2 text-[10px] text-[#f3faf0]/60 font-mono">
                                <span>{doc.total_pages} {doc.total_pages === 1 ? 'page' : 'pages'}</span>
                                <span>·</span>
                                <span>{doc.total_words.toLocaleString()} words</span>
                                <span>·</span>
                                <span className="text-emerald-300 font-semibold">{doc.chunks_count} chunks indexed</span>
                              </div>
                            </div>
                          </div>

                          <div className="flex flex-wrap items-center gap-2 shrink-0">
                            {onOpenPaperDetail && (
                              <button
                                type="button"
                                onClick={() => {
                                  onOpenPaperDetail(doc);
                                }}
                                className="inline-flex items-center gap-1 rounded-lg border border-[#d2434e]/40 bg-[#d2434e]/10 px-2.5 py-1.5 text-xs text-[#d2434e] hover:bg-[#d2434e] hover:text-white font-medium transition-colors cursor-pointer"
                                title="Read extracted text preview & details"
                              >
                                <Eye className="h-3.5 w-3.5" />
                                <span>Read</span>
                              </button>
                            )}

                            <a
                              href={getDocumentDownloadUrl(doc.name)}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 rounded-lg border border-white/10 bg-[#141d26] px-2.5 py-1.5 text-xs text-[#f3faf0]/80 hover:text-white hover:border-[#a7d0d2]/40 transition-colors cursor-pointer"
                              title="Open or download original file"
                            >
                              {doc.name.toLowerCase().endsWith('.pdf') ? (
                                <>
                                  <ExternalLink className="h-3.5 w-3.5 text-[#a7d0d2]" />
                                  <span>PDF</span>
                                </>
                              ) : (
                                <>
                                  <Download className="h-3.5 w-3.5 text-[#a7d0d2]" />
                                  <span>Download</span>
                                </>
                              )}
                            </a>

                            {onSelectDocumentQuery && (
                              <button
                                type="button"
                                onClick={() => {
                                  onSelectDocumentQuery(`What are the key findings in ${doc.name}?`);
                                  onClose();
                                }}
                                className="inline-flex items-center gap-1 rounded-lg border border-[#a7d0d2]/25 bg-[#141d26] px-2.5 py-1.5 text-xs text-[#a7d0d2] hover:bg-[#a7d0d2] hover:text-[#0b1219] font-medium transition-colors cursor-pointer"
                              >
                                <span>Query</span> →
                              </button>
                            )}

                            <button
                              type="button"
                              onClick={() => void handleDelete(doc.name)}
                              disabled={isDeleting}
                              className="inline-flex items-center gap-1 rounded-lg border border-rose-500/20 bg-rose-500/10 p-1.5 text-xs text-rose-400 hover:bg-rose-500 hover:text-white transition-colors cursor-pointer"
                              title={`Delete ${doc.name}`}
                            >
                              {isDeleting ? (
                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              ) : (
                                <Trash2 className="h-3.5 w-3.5" />
                              )}
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>

            {/* Footer */}
            <div className="px-6 py-3.5 border-t border-white/8 bg-[#0c1217] flex justify-between items-center text-xs text-[#f3faf0]/60">
              <span className="font-mono text-[11px]">Backend Storage: datasets/papers</span>
              <button
                onClick={onClose}
                className="px-4 py-1.5 rounded-lg bg-[#1a252d] hover:bg-[#253540] text-white text-xs font-semibold border border-white/10 transition-colors cursor-pointer"
              >
                Close
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};
