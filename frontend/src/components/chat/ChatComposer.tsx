import React, { useState, useRef, useEffect } from 'react';
import {
  Send,
  Paperclip,
  Square,
  Sparkles,
  FileText,
  CheckSquare,
  Square as SquareIcon,
  ChevronDown,
  Globe,
  Dna,
  Waypoints,
  BookOpen,
  Scale,
  ShieldCheck,
  Search,
  Trash2,
  AlertCircle,
  Loader2,
} from 'lucide-react';
import type { AnalysisMode } from '../../types/query';
import type { BackendDocument } from '../../lib/api';

interface ChatComposerProps {
  query: string;
  onQueryChange: (val: string) => void;
  onSubmit: () => void;
  isLoading: boolean;
  onCancel?: () => void;
  // Feature selector
  activeFeature: AnalysisMode;
  onFeatureChange: (feature: AnalysisMode) => void;
  // Web search toggle
  includeWeb: boolean;
  onToggleWeb: () => void;
  // Documents
  availableDocuments: BackendDocument[];
  selectedDocIds: string[];
  onToggleDoc: (docName: string) => void;
  onSelectAllDocs: () => void;
  onClearDocSelection: () => void;
  onDeleteDocument: (docName: string) => void;
  onUploadFiles: (files: File[]) => void;
  isUploading: boolean;
  uploadProgressText?: string;
  // Suggestions
  suggestions?: string[];
  onSelectSuggestion?: (s: string) => void;
}

const FEATURE_CONFIG: Record<
  AnalysisMode,
  { label: string; icon: React.FC<{ className?: string }>; description: string }
> = {
  overview: {
    label: 'Overview',
    icon: FileText,
    description: 'Structured document overview, abstract, methods, findings, and Document IQ.',
  },
  discover: {
    label: 'Assistant / Ask',
    icon: Sparkles,
    description: 'Evidence-grounded dual retrieval across documents and web.',
  },
  'knowledge-map': {
    label: 'Mind Map',
    icon: Waypoints,
    description: 'Interactive concept and relationship graph from document evidence.',
  },
  'knowledge-dna': {
    label: 'Knowledge DNA',
    icon: Dna,
    description: 'Topic clusters, claims, uncertainty, and structural signals.',
  },
  reason: {
    label: 'Reason',
    icon: BookOpen,
    description: 'Multi-hop technical decomposition, derivations, and causal arguments.',
  },
  verify: {
    label: 'Verify',
    icon: ShieldCheck,
    description: 'Claim extraction, evidence citation verification, and consistency check.',
  },
  compare: {
    label: 'Compare',
    icon: Scale,
    description: 'Structured comparison matrix between documents or external findings.',
  },
  gaps: {
    label: 'Research Gaps',
    icon: Sparkles,
    description: 'Identify unexamined assumptions, missing baselines, and open questions.',
  },
  debate: {
    label: 'Debate',
    icon: Scale,
    description: 'Interactive teacher-student dialogue and evidence-backed counterarguments.',
  },
};

export const ChatComposer: React.FC<ChatComposerProps> = ({
  query,
  onQueryChange,
  onSubmit,
  isLoading,
  onCancel,
  activeFeature,
  onFeatureChange,
  includeWeb,
  onToggleWeb,
  availableDocuments,
  selectedDocIds,
  onToggleDoc,
  onSelectAllDocs,
  onClearDocSelection,
  onDeleteDocument,
  onUploadFiles,
  isUploading,
  uploadProgressText,
  suggestions = [],
  onSelectSuggestion,
}) => {
  const [showDocSelector, setShowDocSelector] = useState(false);
  const [showFeatureSelector, setShowFeatureSelector] = useState(false);
  const [docSearchQuery, setDocSearchQuery] = useState('');
  const [docToDelete, setDocToDelete] = useState<string | null>(null);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const docDropdownRef = useRef<HTMLDivElement>(null);
  const featureDropdownRef = useRef<HTMLDivElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      const scrollHeight = textareaRef.current.scrollHeight;
      textareaRef.current.style.height = `${Math.min(scrollHeight, 200)}px`;
    }
  }, [query]);

  // Click outside dropdowns
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (docDropdownRef.current && !docDropdownRef.current.contains(e.target as Node)) {
        setShowDocSelector(false);
      }
      if (featureDropdownRef.current && !featureDropdownRef.current.contains(e.target as Node)) {
        setShowFeatureSelector(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!isLoading && (query.trim() || activeFeature === 'knowledge-map' || activeFeature === 'knowledge-dna')) {
        onSubmit();
      }
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const files = Array.from(e.target.files);
    if (files.length > 20) {
      alert('You can upload up to 20 documents in a single batch.');
    }
    const selectedBatch = files.slice(0, 20);
    onUploadFiles(selectedBatch);
    // Reset file input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const filteredDocs = availableDocuments.filter((d) =>
    (d.title || d.name).toLowerCase().includes(docSearchQuery.toLowerCase())
  );

  const CurrentFeatureIcon = FEATURE_CONFIG[activeFeature]?.icon || Sparkles;

  return (
    <div className="relative w-full max-w-4xl mx-auto px-3 sm:px-4 pb-4">
      {/* Contextual Suggestions pills */}
      {suggestions.length > 0 && (
        <div className="mb-2 flex items-center gap-1.5 overflow-x-auto pb-1 text-xs scrollbar-none">
          <span className="text-[10px] text-[#f3faf0]/50 font-mono uppercase tracking-wider shrink-0 mr-1">
            Suggestions:
          </span>
          {suggestions.map((s, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => onSelectSuggestion && onSelectSuggestion(s)}
              className="shrink-0 px-2.5 py-1 rounded-full bg-[#141d26] hover:bg-[#1b2632] border border-white/10 hover:border-[#a7d0d2]/40 text-[#f3faf0]/80 hover:text-white transition-colors cursor-pointer text-xs"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Main Composer Box */}
      <div className="relative bg-[#111922] border border-[#4d728e]/30 rounded-2xl shadow-xl transition-all focus-within:border-[#a7d0d2]/60 focus-within:ring-1 focus-within:ring-[#a7d0d2]/30">
        {/* Hidden native multiple file input */}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.docx,.txt"
          onChange={handleFileChange}
          className="hidden"
        />

        {/* Text Input */}
        <div className="p-3">
          <textarea
            ref={textareaRef}
            rows={1}
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              selectedDocIds.length > 0
                ? `Ask about ${selectedDocIds.length === 1 ? selectedDocIds[0] : `${selectedDocIds.length} selected documents`} or explore concepts...`
                : 'Ask a question across your research documents or web sources...'
            }
            className="w-full bg-transparent text-sm text-white placeholder-[#f3faf0]/45 resize-none focus:outline-none min-h-[36px] max-h-[200px] leading-relaxed"
          />
        </div>

        {/* Bottom Toolbar */}
        <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 border-t border-white/5 bg-[#0e151d]/70 rounded-b-2xl">
          {/* Left tools: Upload, Document Selector, Feature Selector, Web Toggle */}
          <div className="flex flex-wrap items-center gap-1.5">
            {/* Upload Button */}
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
              className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-white/10 hover:border-[#a7d0d2]/40 bg-[#151f28] hover:bg-[#1a2732] text-xs text-[#a7d0d2] hover:text-white transition-colors cursor-pointer disabled:opacity-50"
              title="Upload up to 20 documents (.pdf, .docx, .txt)"
            >
              {isUploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Paperclip className="w-3.5 h-3.5" />}
              <span className="hidden sm:inline font-medium">Attach</span>
              {isUploading && uploadProgressText && (
                <span className="text-[10px] text-[#f3faf0]/60 ml-1">{uploadProgressText}</span>
              )}
            </button>

            {/* Document Selector Popover */}
            <div className="relative" ref={docDropdownRef}>
              <button
                type="button"
                onClick={() => setShowDocSelector(!showDocSelector)}
                className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs transition-colors cursor-pointer ${
                  selectedDocIds.length > 0
                    ? 'border-[#a7d0d2]/40 bg-[#16222d] text-white font-medium'
                    : 'border-white/10 bg-[#151f28] text-[#f3faf0]/70 hover:text-white hover:bg-[#1a2732]'
                }`}
              >
                <FileText className="w-3.5 h-3.5 text-[#a7d0d2]" />
                <span>
                  {selectedDocIds.length === 0
                    ? 'Documents (All)'
                    : `Documents (${selectedDocIds.length} selected)`}
                </span>
                <ChevronDown className="w-3 h-3 opacity-60" />
              </button>

              {/* Document Popover Menu */}
              {showDocSelector && (
                <div className="absolute bottom-10 left-0 w-80 sm:w-96 bg-[#131b23] border border-[#4d728e]/40 rounded-xl shadow-2xl p-3 z-50 space-y-2 text-xs">
                  <div className="flex items-center justify-between border-b border-white/5 pb-2">
                    <span className="font-semibold text-white">Select Scope Documents</span>
                    <div className="flex items-center gap-1">
                      <button
                        type="button"
                        onClick={onSelectAllDocs}
                        className="text-[11px] text-[#a7d0d2] hover:underline cursor-pointer px-1"
                      >
                        Select all
                      </button>
                      <span className="text-white/20">|</span>
                      <button
                        type="button"
                        onClick={onClearDocSelection}
                        className="text-[11px] text-[#f3faf0]/60 hover:text-white cursor-pointer px-1"
                      >
                        Clear
                      </button>
                    </div>
                  </div>

                  {/* Document search */}
                  <div className="relative">
                    <Search className="w-3.5 h-3.5 absolute left-2.5 top-2 text-[#f3faf0]/40" />
                    <input
                      type="text"
                      placeholder="Search attached papers..."
                      value={docSearchQuery}
                      onChange={(e) => setDocSearchQuery(e.target.value)}
                      className="w-full bg-[#0d141b] text-xs text-white pl-8 pr-2 py-1.5 rounded border border-white/5 focus:border-[#a7d0d2]/40 focus:outline-none"
                    />
                  </div>

                  {/* Document list */}
                  <div className="max-h-56 overflow-y-auto space-y-1 pr-1 scrollbar-thin scrollbar-thumb-white/10">
                    {filteredDocs.length === 0 ? (
                      <div className="py-4 text-center text-[#f3faf0]/40 text-xs">
                        {availableDocuments.length === 0 ? 'No documents indexed yet' : 'No matching documents'}
                      </div>
                    ) : (
                      filteredDocs.map((doc) => {
                        const isSelected = selectedDocIds.includes(doc.name);
                        return (
                          <div
                            key={doc.name}
                            className={`flex items-center justify-between p-2 rounded-lg transition-colors cursor-pointer ${
                              isSelected ? 'bg-[#1b2734] border border-[#a7d0d2]/30' : 'hover:bg-white/5'
                            }`}
                            onClick={() => onToggleDoc(doc.name)}
                          >
                            <div className="flex items-center gap-2 min-w-0 flex-1 pr-2">
                              {isSelected ? (
                                <CheckSquare className="w-4 h-4 text-[#a7d0d2] shrink-0" />
                              ) : (
                                <SquareIcon className="w-4 h-4 text-[#f3faf0]/40 shrink-0" />
                              )}
                              <div className="min-w-0">
                                <p className="text-xs font-medium text-white truncate">{doc.title || doc.name}</p>
                                <p className="text-[10px] text-[#f3faf0]/50 font-mono">
                                  {doc.chunks_count} chunks · {doc.total_pages || 1} pgs
                                </p>
                              </div>
                            </div>

                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                setDocToDelete(doc.name);
                              }}
                              className="p-1 text-[#f3faf0]/30 hover:text-red-400 rounded shrink-0"
                              title="Delete document"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Research Feature Selector Popover */}
            <div className="relative" ref={featureDropdownRef}>
              <button
                type="button"
                onClick={() => setShowFeatureSelector(!showFeatureSelector)}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-white/10 hover:border-[#a7d0d2]/40 bg-[#151f28] hover:bg-[#1a2732] text-xs text-white transition-colors cursor-pointer"
              >
                <CurrentFeatureIcon className="w-3.5 h-3.5 text-[#d2434e]" />
                <span className="font-medium">{FEATURE_CONFIG[activeFeature]?.label || 'Feature'}</span>
                <ChevronDown className="w-3 h-3 opacity-60" />
              </button>

              {/* Feature Popover Menu */}
              {showFeatureSelector && (
                <div className="absolute bottom-10 left-0 w-72 bg-[#131b23] border border-[#4d728e]/40 rounded-xl shadow-2xl p-1.5 z-50 space-y-0.5 text-xs">
                  <div className="px-2 py-1 text-[10px] font-mono uppercase text-[#f3faf0]/50 border-b border-white/5 mb-1">
                    Select Research Engine
                  </div>
                  {(Object.keys(FEATURE_CONFIG) as AnalysisMode[]).map((mode) => {
                    const cfg = FEATURE_CONFIG[mode];
                    const Icon = cfg.icon;
                    const isCurrent = activeFeature === mode;
                    return (
                      <button
                        key={mode}
                        type="button"
                        onClick={() => {
                          onFeatureChange(mode);
                          setShowFeatureSelector(false);
                        }}
                        className={`w-full flex items-start gap-2.5 p-2 rounded-lg text-left transition-colors cursor-pointer ${
                          isCurrent ? 'bg-[#1b2734] border border-[#a7d0d2]/30 text-white' : 'hover:bg-white/5 text-[#f3faf0]/80 hover:text-white'
                        }`}
                      >
                        <Icon className={`w-4 h-4 mt-0.5 shrink-0 ${isCurrent ? 'text-[#d2434e]' : 'text-[#a7d0d2]'}`} />
                        <div className="min-w-0">
                          <p className="font-semibold text-xs text-white">{cfg.label}</p>
                          <p className="text-[10px] text-[#f3faf0]/50 leading-tight mt-0.5">{cfg.description}</p>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Web Evidence Toggle */}
            <button
              type="button"
              onClick={onToggleWeb}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs transition-colors cursor-pointer ${
                includeWeb
                  ? 'border-emerald-500/50 bg-emerald-500/10 text-emerald-300 font-medium'
                  : 'border-white/10 bg-[#151f28] text-[#f3faf0]/60 hover:text-white hover:bg-[#1a2732]'
              }`}
              title={includeWeb ? 'External web research enabled' : 'Click to enable external web research'}
            >
              <Globe className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Web Evidence</span>
            </button>
          </div>

          {/* Right Action: Send / Cancel */}
          <div className="flex items-center gap-2">
            {isLoading ? (
              <button
                type="button"
                onClick={onCancel}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-red-500/20 hover:bg-red-500/30 border border-red-500/40 text-red-200 text-xs font-semibold cursor-pointer transition-colors"
                title="Cancel generation"
              >
                <Square className="w-3.5 h-3.5 fill-current" />
                <span>Stop</span>
              </button>
            ) : (
              <button
                type="button"
                onClick={onSubmit}
                disabled={!query.trim() && activeFeature !== 'knowledge-map' && activeFeature !== 'knowledge-dna'}
                className="flex items-center justify-center w-8 h-8 rounded-xl bg-[#d2434e] hover:bg-[#b0303b] text-white disabled:opacity-30 disabled:cursor-not-allowed transition-all shadow-md cursor-pointer"
                title="Send inquiry (Enter)"
              >
                <Send className="w-4 h-4 ml-0.5" />
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Confirmation Modal for Document Deletion */}
      {docToDelete && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-xs flex items-center justify-center z-50 p-4">
          <div className="bg-[#10171e] border border-red-500/30 rounded-2xl p-5 max-w-sm w-full space-y-4 shadow-2xl">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-xl bg-red-500/10 text-red-400">
                <AlertCircle className="w-5 h-5" />
              </div>
              <h3 className="text-sm font-semibold text-white">Delete document from index?</h3>
            </div>
            <p className="text-xs text-[#f3faf0]/70 leading-relaxed">
              Are you sure you want to delete <span className="font-semibold text-white font-mono">{docToDelete}</span>?
              You will have a 10-second undo period to restore it.
            </p>
            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setDocToDelete(null)}
                className="px-3 py-1.5 rounded-lg border border-white/10 text-xs text-[#f3faf0]/75 hover:bg-white/5 cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  const target = docToDelete;
                  setDocToDelete(null);
                  onDeleteDocument(target);
                }}
                className="px-3 py-1.5 rounded-lg bg-red-600 hover:bg-red-700 text-xs font-semibold text-white cursor-pointer"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
