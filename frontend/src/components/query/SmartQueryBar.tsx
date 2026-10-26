import React, { useState, useRef, useCallback } from 'react';
import {
  Search,
  Sparkles,
  CheckCircle2,
  Edit2,
  Check,
  X,
  FileText,
  HelpCircle,
  Loader2,
  ArrowRight,
} from 'lucide-react';
import {
  postSmartQuery,
  streamSmartQuery,
  fetchSmartQueryAutocomplete,
  type SmartQueryResponseData,
  type AutocompleteResult,
  type SmartQueryStreamEvent,
} from '../../lib/api';

export interface SmartQueryBarProps {
  initialQuery?: string;
  selectedDocuments?: string[];
  onResultReceived?: (result: SmartQueryResponseData) => void;
  onStreamEvent?: (event: SmartQueryStreamEvent) => void;
}

export interface FeatureProgress {
  feature: string;
  label: string;
  status: 'pending' | 'running' | 'completed' | 'error' | 'not_executed';
  progress: number;
}

const DEFAULT_FEATURES: Array<{ feature: string; label: string }> = [
  { feature: 'overview', label: 'Document Overview' },
  { feature: 'summary', label: 'Executive Summary' },
  { feature: 'qa', label: 'Grounded Answer' },
  { feature: 'dna', label: 'Knowledge DNA' },
  { feature: 'mindmap', label: 'Concept Graph' },
  { feature: 'orbit', label: '3D Orbit' },
  { feature: 'gaps', label: 'Research Gaps' },
];

export const SmartQueryBar: React.FC<SmartQueryBarProps> = ({
  initialQuery = '',
  selectedDocuments = [],
  onResultReceived,
  onStreamEvent,
}) => {
  const [query, setQuery] = useState<string>(initialQuery);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [overallProgress, setOverallProgress] = useState<number>(0);

  // Progressive Feature Steps
  const [featureSteps, setFeatureSteps] = useState<FeatureProgress[]>(
    DEFAULT_FEATURES.map((f) => ({ ...f, status: 'pending', progress: 0 })),
  );

  // Autocomplete state
  const [autocompleteSuggestions, setAutocompleteSuggestions] = useState<AutocompleteResult | null>(null);
  const [showAutocomplete, setShowAutocomplete] = useState<boolean>(false);
  const autocompleteTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Smart Query Response State
  const [_lastResponse, setLastResponse] = useState<SmartQueryResponseData | null>(null);

  // Editable Rewritten Query State
  const [rewrittenQuery, setRewrittenQuery] = useState<string>('');
  const [isEditingRewritten, setIsEditingRewritten] = useState<boolean>(false);

  // Clarification options
  const [clarifications, setClarifications] = useState<string[]>([]);

  // AbortController for cancel
  const abortControllerRef = useRef<AbortController | null>(null);

  // Handle Autocomplete fetching
  const triggerAutocomplete = useCallback((text: string) => {
    if (autocompleteTimerRef.current) clearTimeout(autocompleteTimerRef.current);
    if (!text || text.length < 2) {
      setAutocompleteSuggestions(null);
      setShowAutocomplete(false);
      return;
    }

    autocompleteTimerRef.current = setTimeout(async () => {
      try {
        const result = await fetchSmartQueryAutocomplete(text);
        if (
          result &&
          (result.combined_suggestions.length > 0 ||
            result.document_suggestions.length > 0 ||
            result.feature_suggestions.length > 0)
        ) {
          setAutocompleteSuggestions(result);
          setShowAutocomplete(true);
        } else {
          setShowAutocomplete(false);
        }
      } catch {
        setShowAutocomplete(false);
      }
    }, 180);
  }, []);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setQuery(val);
    triggerAutocomplete(val);
  };

  const handleSelectSuggestion = (suggestion: string) => {
    setQuery(suggestion);
    setShowAutocomplete(false);
    if (inputRef.current) {
      inputRef.current.focus();
    }
  };

  // Run Smart Query (Single Feature or Standard Routing)
  const handleRunQuery = async (runAll: boolean = false) => {
    const textToRun = query.trim();
    if (!textToRun || isLoading) return;

    setShowAutocomplete(false);
    setIsLoading(true);
    setClarifications([]);
    abortControllerRef.current = new AbortController();

    if (runAll) {
      // Execute progressive streaming "Run All"
      setIsStreaming(true);
      setOverallProgress(5);
      setFeatureSteps(
        DEFAULT_FEATURES.map((f) => ({ ...f, status: 'pending', progress: 0 })),
      );

      try {
        await streamSmartQuery(
          {
            text: textToRun,
            document_ids: selectedDocuments.length > 0 ? selectedDocuments : undefined,
            run_all: true,
          },
          (evt: SmartQueryStreamEvent) => {
            if (onStreamEvent) onStreamEvent(evt);

            if (evt.progress !== undefined) {
              setOverallProgress(evt.progress);
            }

            if (evt.feature) {
              setFeatureSteps((prev) =>
                prev.map((step) => {
                  if (step.feature.toLowerCase() === evt.feature?.toLowerCase()) {
                    return {
                      ...step,
                      status: (evt.status as any) || 'running',
                      progress: ['success', 'completed'].includes(String(evt.status)) ? 100 : 0,
                    };
                  }
                  return step;
                }),
              );
            }
          },
          abortControllerRef.current.signal,
        );

      } catch (err: unknown) {
        if ((err as Error)?.name !== 'AbortError') {
          console.error('Smart query stream failed:', err);
        }
      } finally {
        setIsLoading(false);
        setIsStreaming(false);
      }
    } else {
      // Standard /smart-query call
      try {
        const resp = await postSmartQuery({
          text: textToRun,
          document_ids: selectedDocuments.length > 0 ? selectedDocuments : undefined,
          run_all: false,
        });

        setLastResponse(resp);
        setRewrittenQuery(resp.rewritten_query || textToRun);

        if (resp.is_ambiguous && resp.clarification_options) {
          setClarifications(resp.clarification_options);
        }

        if (onResultReceived) {
          onResultReceived(resp);
        }
      } catch (err) {
        console.error('Smart query failed:', err);
      } finally {
        setIsLoading(false);
      }
    }
  };

  // Apply Edited Rewritten Query
  const handleSaveRewrittenQuery = () => {
    setIsEditingRewritten(false);
    setQuery(rewrittenQuery);
  };

  // Run a clarification choice immediately
  const handleSelectClarification = (clarification: string) => {
    setQuery(clarification);
    setClarifications([]);
    void handleRunQuery(false);
  };

  const handleCancel = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    setIsLoading(false);
    setIsStreaming(false);
  };

  return (
    <div data-testid="smart-query-bar" className="w-full space-y-3">
      {/* Search Input Bar with Run All button */}
      <div className="relative">
        <div className="relative flex items-center rounded-xl bg-[#0b1219] border border-[#4d728e]/50 p-1.5 shadow-lg focus-within:border-[#a7d0d2] focus-within:ring-1 focus-within:ring-[#a7d0d2] transition-all">
          <div className="pl-3 pr-2 text-[#a7d0d2]">
            <Search className="h-4 w-4" />
          </div>

          <input
            ref={inputRef}
            data-testid="smart-query-input"
            type="text"
            value={query}
            onChange={handleInputChange}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                void handleRunQuery(false);
              }
            }}
            placeholder="Ask anything, compare papers, or extract DNA (e.g. 'Overview of attention.pdf', 'Run All')..."
            className="w-full bg-transparent text-sm text-white placeholder-[#98a6b0]/60 focus:outline-none py-1"
          />

          {query && (
            <button
              type="button"
              onClick={() => {
                setQuery('');
                setShowAutocomplete(false);
              }}
              className="p-1 text-[#98a6b0] hover:text-white mr-1"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}

          {/* Action Buttons: Run All and Standard Submit */}
          <div className="flex items-center gap-1.5">
            <button
              data-testid="run-all-button"
              type="button"
              onClick={() => void handleRunQuery(true)}
              disabled={isLoading || !query.trim()}
              className="inline-flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-[#d2434e] to-[#b4323c] px-3.5 py-1.5 text-xs font-semibold text-white shadow-md hover:brightness-110 active:scale-98 transition-all disabled:opacity-50 cursor-pointer"
              title="Execute all research features concurrently with live streaming"
            >
              <Sparkles className="h-3.5 w-3.5" />
              <span>Run All</span>
            </button>

            <button
              data-testid="smart-query-submit"
              type="button"
              onClick={() => void handleRunQuery(false)}
              disabled={isLoading || !query.trim()}
              className="inline-flex items-center justify-center rounded-lg bg-[#1b2734] border border-[#4d728e]/60 p-2 text-white hover:border-[#a7d0d2] transition-colors disabled:opacity-50 cursor-pointer"
              title="Run targeted feature or search"
            >
              {isLoading && !isStreaming ? (
                <Loader2 className="h-4 w-4 animate-spin text-[#a7d0d2]" />
              ) : (
                <ArrowRight className="h-4 w-4 text-[#a7d0d2]" />
              )}
            </button>
          </div>
        </div>

        {/* Autocomplete Dropdown */}
        {showAutocomplete && autocompleteSuggestions && (
          <div
            data-testid="autocomplete-dropdown"
            className="absolute left-0 right-0 top-full mt-1.5 z-50 rounded-xl border border-[#4d728e]/50 bg-[#0b1219] shadow-2xl p-2 space-y-2 backdrop-blur-md"
          >
            {autocompleteSuggestions.combined_suggestions.length > 0 && (
              <div className="space-y-1">
                <span className="text-[10px] font-mono uppercase text-[#a7d0d2] px-2 block">
                  Suggested Queries
                </span>
                {autocompleteSuggestions.combined_suggestions.slice(0, 5).map((sug, i) => (
                  <button
                    key={`sug-${i}`}
                    type="button"
                    data-testid="autocomplete-suggestion-item"
                    onClick={() => handleSelectSuggestion(sug)}
                    className="w-full text-left px-2.5 py-1.5 rounded-lg text-xs text-white hover:bg-[#141d26] transition-colors flex items-center justify-between group"
                  >
                    <span>{sug}</span>
                    <ArrowRight className="h-3 w-3 text-[#98a6b0] group-hover:text-white transition-colors" />
                  </button>
                ))}
              </div>
            )}

            {autocompleteSuggestions.document_suggestions.length > 0 && (
              <div className="pt-1 border-t border-white/6 space-y-1">
                <span className="text-[10px] font-mono uppercase text-[#98a6b0] px-2 block">
                  Matched Documents
                </span>
                <div className="flex flex-wrap gap-1.5 px-2">
                  {autocompleteSuggestions.document_suggestions.slice(0, 4).map((doc, i) => (
                    <button
                      key={`doc-${i}`}
                      type="button"
                      data-testid="autocomplete-doc-item"
                      onClick={() => handleSelectSuggestion(`${doc} overview`)}
                      className="inline-flex items-center gap-1 rounded bg-[#141d26] border border-[#4d728e]/40 px-2 py-0.5 text-[11px] text-[#a7d0d2] hover:text-white"
                    >
                      <FileText className="h-3 w-3" />
                      <span>{doc}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Progressive Streaming Results Bar (When Run All is active) */}
      {isStreaming && (
        <div
          data-testid="smart-query-progressive-results"
          className="rounded-xl border border-white/8 bg-[#0b1219] p-3.5 space-y-3"
        >
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-white flex items-center gap-2">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-[#d2434e]" />
              <span>Running All Analyses in Parallel...</span>
            </span>
            <div className="flex items-center gap-3">
              <span className="font-mono text-[11px] text-[#a7d0d2]">{overallProgress}% processed</span>
              <button
                type="button"
                onClick={handleCancel}
                className="text-xs text-red-400 hover:text-red-300"
              >
                Cancel
              </button>
            </div>
          </div>

          {/* Progress Bar */}
          <div className="h-1.5 w-full bg-[#141d26] rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-[#d2434e] via-[#f59e0b] to-[#10b981] transition-all duration-300 rounded-full"
              style={{ width: `${overallProgress}%` }}
            />
          </div>

          {/* Progressive Feature Status Chips */}
          <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-7 gap-2 pt-1">
            {featureSteps.map((step) => (
              <div
                key={step.feature}
                data-testid={`progressive-step-${step.feature}`}
                className={`rounded-lg border p-2 text-center text-[10px] font-mono transition-all ${
                  step.status === 'completed'
                    ? 'border-[#10b981]/50 bg-[#10b981]/10 text-white'
                    : step.status === 'running'
                    ? 'border-[#f59e0b]/50 bg-[#f59e0b]/10 text-[#fde68a] animate-pulse'
                    : 'border-white/6 bg-[#141d26]/40 text-[#98a6b0]'
                }`}
              >
                <div className="flex items-center justify-center gap-1 mb-1">
                  {step.status === 'completed' ? (
                    <CheckCircle2 className="h-3 w-3 text-[#10b981]" />
                  ) : step.status === 'running' ? (
                    <Loader2 className="h-3 w-3 animate-spin text-[#f59e0b]" />
                  ) : (
                    <div className="h-2 w-2 rounded-full bg-white/20" />
                  )}
                  <span className="truncate">{step.label}</span>
                </div>
                <span className="text-[9px] opacity-75 capitalize">{step.status === 'not_executed' ? 'not run' : step.status}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Editable Rewritten Query Pill */}
      {rewrittenQuery && rewrittenQuery !== query && (
        <div
          data-testid="rewritten-query-container"
          className="flex flex-wrap items-center gap-2 rounded-lg border border-[#a7d0d2]/30 bg-[#141d26]/80 px-3 py-1.5 text-xs"
        >
          <span className="text-[10px] font-mono uppercase text-[#a7d0d2]">Rewritten Query:</span>
          {isEditingRewritten ? (
            <div className="flex items-center gap-2 flex-1">
              <input
                data-testid="rewritten-query-input"
                type="text"
                value={rewrittenQuery}
                onChange={(e) => setRewrittenQuery(e.target.value)}
                className="flex-1 bg-[#0b1219] border border-[#a7d0d2] rounded px-2 py-0.5 text-xs text-white focus:outline-none"
              />
              <button
                data-testid="rewritten-query-save"
                type="button"
                onClick={handleSaveRewrittenQuery}
                className="p-1 rounded bg-[#a7d0d2]/20 text-[#a7d0d2] hover:text-white"
                title="Save and use rewritten query"
              >
                <Check className="h-3.5 w-3.5" />
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2 flex-1 justify-between">
              <span data-testid="rewritten-query-text" className="text-white font-medium italic">
                "{rewrittenQuery}"
              </span>
              <button
                data-testid="rewritten-query-edit-btn"
                type="button"
                onClick={() => setIsEditingRewritten(true)}
                className="inline-flex items-center gap-1 text-[11px] text-[#a7d0d2] hover:text-white"
              >
                <Edit2 className="h-3 w-3" />
                <span>Edit</span>
              </button>
            </div>
          )}
        </div>
      )}

      {/* Clarification Options (When query intent is ambiguous) */}
      {clarifications.length > 0 && (
        <div
          data-testid="clarification-options-container"
          className="rounded-lg border border-[#f59e0b]/40 bg-[#1b170f] p-3 space-y-2 text-xs"
        >
          <div className="flex items-center gap-1.5 text-[#f59e0b] font-medium font-mono uppercase text-[10px]">
            <HelpCircle className="h-3.5 w-3.5" />
            <span>Multiple Interpretations Detected — Select Clarification:</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {clarifications.map((opt, i) => (
              <button
                key={`clarify-${i}`}
                data-testid="clarification-chip"
                type="button"
                onClick={() => handleSelectClarification(opt)}
                className="inline-flex items-center gap-1.5 rounded-lg border border-[#f59e0b]/40 bg-[#261e12] px-3 py-1.5 text-xs text-white hover:border-[#f59e0b] hover:bg-[#342714] transition-all cursor-pointer"
              >
                <Sparkles className="h-3 w-3 text-[#f59e0b]" />
                <span>{opt}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default SmartQueryBar;
