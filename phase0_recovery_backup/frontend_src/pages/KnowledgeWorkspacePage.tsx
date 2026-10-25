import React, { useEffect, useEffectEvent, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Loader2,
  FileText,
  CheckCircle2,
  AlertCircle,
  Sparkles,
  Layers,
  Dna,
  Waypoints,
  BookOpen,
  MessageCircleQuestion,
  ChevronDown,
  ChevronUp,
  Download,
  ExternalLink,
  Eye,
  RefreshCw,
  Scale,
  Trash2,
  RotateCcw,
  CheckSquare,
  Square,
  Filter,
  UploadCloud,
  XCircle,
} from 'lucide-react';
import { SearchSidebar } from '../components/SearchSidebar';
import { QueryInput } from '../components/search/QueryInput';
import { SmartQueryBar } from '../components/query/SmartQueryBar';
import { SearchModeSelector } from '../components/search/SearchModeSelector';
import { AnswerPanel } from '../components/answers/AnswerPanel';
import { EvidencePanel } from '../components/evidence/EvidencePanel';
import { SourcesDrawer } from '../components/evidence/SourcesDrawer';
import { ReasoningTimeline } from '../components/reasoning/ReasoningTimeline';
import { ComparisonView, DebateView, GapView, VerificationView } from '../components/analysis/AnalysisViews';
import { KnowledgeDNA } from '../components/visualization/KnowledgeDNA';
import { KnowledgeMindMap } from '../components/visualization/KnowledgeMindMap';
import { ConceptGraph3D } from '../components/ConceptGraph3D';
import { PaperDetailModal } from '../components/PaperDetailModal';
import { createMockWorkspaceResult } from '../lib/mockWorkspaceData';
import {
  queryBackend,
  reasonBackend,
  verifyClaimBackend,
  compareBackend,
  findResearchGapsBackend,
  runDebateBackend,
  queryKnowledgeDNA,
  queryKnowledgeMindMap,
  fetchDocuments,
  uploadDocument,
  uploadDocumentsBatch,
  deleteDocument,
  undoDeleteDocument,
  getDocumentDownloadUrl,
  type BackendQuerySource,
  type BackendDocument,
} from '../lib/api';
import { DocumentModal } from '../components/DocumentModal';
import {
  exportResultToMarkdown,
  exportResultToPrintableHtml,
  exportSessionToMarkdown,
  exportSessionToHtml,
  exportMindMapToJson,
  getDownloadHistory,
  clearDownloadHistory,
  type DownloadHistoryEntry,
} from '../lib/exportUtils';
import { getStoredUser } from '../lib/mockAuth';
import type { MindMapNode } from '../types/knowledge';
import type { Evidence, Source } from '../types/evidence';
import type { AnalysisMode, WorkspaceHistoryItem, WorkspaceResult } from '../types/query';

function formatScore(score?: number | null, digits = 3): string | null {
  return typeof score === 'number' && Number.isFinite(score) ? score.toFixed(digits) : null;
}

function mapBackendSources(sources: BackendQuerySource[]): Source[] {
  if (!Array.isArray(sources)) return [];
  return sources.map((source, idx) => ({
    id: source.chunk_id || `src_${idx}`,
    documentName: source.document || 'Document Evidence',
    page:
      typeof source.page === 'number'
        ? source.page
        : Number(source.page) || undefined,
    chunkId: source.chunk_id,
    evidenceCount: 1,
    rank: source.rank,
    score: typeof source.hybrid_score === 'number' && Number.isFinite(source.hybrid_score) ? source.hybrid_score : undefined,
    bm25Score: typeof source.bm25_score === 'number' && Number.isFinite(source.bm25_score) ? source.bm25_score : undefined,
    faissScore: typeof source.faiss_score === 'number' && Number.isFinite(source.faiss_score) ? source.faiss_score : undefined,
  }));
}

function mapBackendEvidence(
  sources: BackendQuerySource[],
  quotes?: string[],
): Evidence[] {
  const safeSources = Array.isArray(sources) ? sources : [];

  if (quotes && quotes.length > 0) {
    return quotes.map((quote, idx) => {
      const src = safeSources.length > 0 ? safeSources[idx % safeSources.length] : undefined;
      return {
        id: src?.chunk_id ? `${src.chunk_id}_${idx}` : `ev_${idx}`,
        documentName: src?.document || 'Document Evidence',
        page: typeof src?.page === 'number' ? src.page : Number(src?.page) || undefined,
        chunkId: src?.chunk_id,
        text: quote,
        score: typeof src?.hybrid_score === 'number' && Number.isFinite(src.hybrid_score) ? src.hybrid_score : undefined,
        relevance: typeof src?.hybrid_score === 'number' && Number.isFinite(src.hybrid_score) ? src.hybrid_score : 0.9,
      };
    });
  }

  return safeSources.map((source, idx) => {
    const parts: string[] = [];
    if (source.rank !== undefined && source.rank !== null) {
      parts.push(`Rank #${source.rank}`);
    }
    const hybrid = formatScore(source.hybrid_score);
    if (hybrid !== null) parts.push(`Hybrid: ${hybrid}`);
    const bm25 = formatScore(source.bm25_score);
    if (bm25 !== null) parts.push(`BM25: ${bm25}`);
    const faiss = formatScore(source.faiss_score);
    if (faiss !== null) parts.push(`FAISS: ${faiss}`);

    const metadataTag = parts.length > 0 ? ` (${parts.join(', ')})` : '';
    const chunkTag = source.chunk_id ? ` [${source.chunk_id}]` : '';

    return {
      id: source.chunk_id || `ev_${idx}`,
      documentName: source.document || 'Document Evidence',
      page:
        typeof source.page === 'number'
          ? source.page
          : Number(source.page) || undefined,
      chunkId: source.chunk_id,
      text: `Retrieved passage from ${source.document || 'Document'}${chunkTag}${metadataTag}`,
      score: typeof source.hybrid_score === 'number' && Number.isFinite(source.hybrid_score) ? source.hybrid_score : undefined,
      relevance: typeof source.hybrid_score === 'number' && Number.isFinite(source.hybrid_score) ? source.hybrid_score : 0.85,
    };
  });
}

const getHistoryKey = (userId?: string): string => {
  return userId ? `unknown_workspace_history_${userId}` : 'unknown_workspace_history_guest';
};

const readHistory = (key: string): WorkspaceHistoryItem[] => {
  try {
    const saved = localStorage.getItem(key);
    if (saved) {
      const parsed = JSON.parse(saved) as WorkspaceHistoryItem[];
      if (Array.isArray(parsed)) return parsed;
    }
    return [];
  } catch {
    return [];
  }
};

type VisualizationView = 'knowledge' | 'mind-map' | 'dna';

const isAnalysisMode = (value: string | null): value is AnalysisMode =>
  value !== null && [
    'discover',
    'reason',
    'verify',
    'compare',
    'gaps',
    'debate',
    'knowledge-map',
    'knowledge-dna',
  ].includes(value);

const pipelineByMode: Record<AnalysisMode, string[]> = {
  discover: ['Analyzing research intent...', 'Retrieving documents (BM25 + FAISS)...', 'Extracting cited evidence...', 'Synthesizing grounded answer...'],
  reason: ['Decomposing inquiry...', 'Evaluating sub-hypotheses...', 'Retrieving causal passages...', 'Synthesizing reasoning verdict...'],
  verify: ['Extracting target claim...', 'Aligning supporting evidence...', 'Evaluating counter-claims...', 'Determining verification verdict...'],
  compare: ['Identifying comparative axes...', 'Aligning entities from literature...', 'Extracting structured values...', 'Synthesizing comparative summary...'],
  gaps: ['Analyzing literature boundaries...', 'Scanning reported limitations...', 'Extracting unaddressed questions...', 'Synthesizing research gaps...'],
  debate: ['Formulating thesis & antithesis...', 'Retrieving opposing evidence trails...', 'Evaluating rebuttals...', 'Synthesizing final verdict...'],
  'knowledge-map': ['Extracting ontological entities...', 'Classifying concepts & relations...', 'Constructing topological graph...', 'Synthesizing mind map...'],
  'knowledge-dna': ['Extracting research area...', 'Discovering core topics & concepts...', 'Synthesizing methods & findings...', 'Mapping DNA topology...'],
};

const modeTitles: Record<AnalysisMode, string> = {
  discover: 'Research Assistant',
  reason: 'Multi-Step Reasoning',
  verify: 'Claim Verification',
  compare: 'Research Comparison',
  gaps: 'Research Gaps',
  debate: 'AI Debate',
  'knowledge-map': 'Knowledge Mind Map',
  'knowledge-dna': 'Knowledge DNA',
};

export const KnowledgeWorkspacePage: React.FC = () => {
  const currentUser = getStoredUser();
  const currentUserId = currentUser?.id || 'default_user';
  const historyKey = getHistoryKey(currentUser?.id);

  const [searchParams, setSearchParams] = useSearchParams();
  const autoRunId = searchParams.get('run');
  const autoRunQuery = searchParams.get('q');
  const autoRunMode = isAnalysisMode(searchParams.get('mode')) ? searchParams.get('mode') as AnalysisMode : 'discover';
  const initialMode = isAnalysisMode(searchParams.get('mode')) ? searchParams.get('mode') as AnalysisMode : 'discover';
  const [mode, setMode] = useState<AnalysisMode>(initialMode);
  const [query, setQuery] = useState(searchParams.get('q') || '');
  const [activeResult, setActiveResult] = useState<WorkspaceResult | null>(null);
  const [history, setHistory] = useState<WorkspaceHistoryItem[]>(() => readHistory(historyKey));
  const [isDownloadsOpen, setIsDownloadsOpen] = useState(false);
  const [downloadHistory, setDownloadHistory] = useState<DownloadHistoryEntry[]>(() => getDownloadHistory(currentUserId));
  const [activeHistoryId, setActiveHistoryId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [pipelineStage, setPipelineStage] = useState('');
  const [showDetailedAnswer, setShowDetailedAnswer] = useState(false);
  const [visualization, setVisualization] = useState<VisualizationView>(
    initialMode === 'knowledge-dna'
      ? 'dna'
      : initialMode === 'knowledge-map'
      ? 'mind-map'
      : 'knowledge',
  );
  const [isSourcesOpen, setIsSourcesOpen] = useState(false);
  const [isDocumentModalOpen, setIsDocumentModalOpen] = useState(false);

  // Corpus & Ingestion State
  const [corpusDocuments, setCorpusDocuments] = useState<BackendDocument[]>([]);
  const [selectedDocNames, setSelectedDocNames] = useState<Set<string>>(new Set());
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [isCorpusExpanded, setIsCorpusExpanded] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [deletingDocName, setDeletingDocName] = useState<string | null>(null);
  const [confirmDocName, setConfirmDocName] = useState<string | null>(null);
  const [undoToast, setUndoToast] = useState<{ docName: string; secondsLeft: number } | null>(null);
  const undoTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploadFeedback, setUploadFeedback] = useState<{ message: string; type: 'success' | 'error' } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const startedAutoRunId = useRef<string | null>(null);

  const [selectedPaperForDetail, setSelectedPaperForDetail] = useState<BackendDocument | null>(null);
  const [isCheckingBackend, setIsCheckingBackend] = useState(false);

  // Load documents & check backend on mount with auto-reconnection
  const loadCorpus = async () => {
    setIsCheckingBackend(true);
    try {
      const docRes = await fetchDocuments();
      const docs = docRes.documents || [];
      setCorpusDocuments(docs);
      setBackendOnline(true);
      setSelectedDocNames((prev) => {
        if (prev.size === 0) {
          return new Set(docs.map((d) => d.name));
        }
        const updated = new Set([...prev].filter((name) => docs.some((d) => d.name === name)));
        return updated.size > 0 ? updated : new Set(docs.map((d) => d.name));
      });
    } catch {
      setBackendOnline(false);
    } finally {
      setIsCheckingBackend(false);
    }
  };

  useEffect(() => {
    void loadCorpus();
    // Auto-probe every 4 seconds if backend is offline or connecting
    const interval = setInterval(() => {
      if (backendOnline === false || backendOnline === null) {
        void loadCorpus();
      }
    }, 4000);
    return () => clearInterval(interval);
  }, [backendOnline]);

  const toggleDocSelection = (docName: string) => {
    setSelectedDocNames((prev) => {
      const next = new Set(prev);
      if (next.has(docName)) {
        next.delete(docName);
      } else {
        next.add(docName);
      }
      return next;
    });
  };

  const selectAllDocs = () => {
    setSelectedDocNames(new Set(corpusDocuments.map((d) => d.name)));
  };

  const clearDocSelection = () => {
    setSelectedDocNames(new Set());
  };

  const handleConfirmDeleteDocument = async () => {
    if (!confirmDocName) return;
    const docName = confirmDocName;
    setConfirmDocName(null);
    setDeletingDocName(docName);
    setUploadFeedback(null);
    try {
      await deleteDocument(docName);
      setUploadFeedback({
        message: `Staged "${docName}" for deletion. Undo available for 10 seconds.`,
        type: 'success',
      });
      await loadCorpus();

      if (undoTimerRef.current) clearInterval(undoTimerRef.current);
      setUndoToast({ docName, secondsLeft: 10 });
      undoTimerRef.current = setInterval(() => {
        setUndoToast((prev) => {
          if (!prev || prev.secondsLeft <= 1) {
            if (undoTimerRef.current) clearInterval(undoTimerRef.current);
            return null;
          }
          return { ...prev, secondsLeft: prev.secondsLeft - 1 };
        });
      }, 1000);
    } catch (err: unknown) {
      setUploadFeedback({
        message: err instanceof Error ? err.message : 'Failed to delete document',
        type: 'error',
      });
    } finally {
      setDeletingDocName(null);
    }
  };

  const handleUndoDeleteDocument = async (docName: string) => {
    if (undoTimerRef.current) clearInterval(undoTimerRef.current);
    setUndoToast(null);
    try {
      await undoDeleteDocument(docName);
      setUploadFeedback({
        message: `Restored "${docName}" and rebuilt retrieval indexes.`,
        type: 'success',
      });
      await loadCorpus();
    } catch (err: unknown) {
      setUploadFeedback({
        message: err instanceof Error ? err.message : 'Failed to restore document',
        type: 'error',
      });
    }
  };

  const handleFilesUpload = async (files: FileList | File[]) => {
    const fileArray = Array.from(files);
    if (fileArray.length === 0) return;

    if (corpusDocuments.length + fileArray.length > 25) {
      const available = Math.max(0, 25 - corpusDocuments.length);
      setUploadFeedback({
        message: `Maximum collection limit is 25 papers. You currently have ${corpusDocuments.length} papers, so you can upload at most ${available} more.`,
        type: 'error',
      });
      return;
    }

    setIsUploading(true);
    setUploadFeedback(null);

    try {
      if (fileArray.length === 1) {
        const res = await uploadDocument(fileArray[0]);
        setUploadFeedback({
          message: `Indexed "${res.filename}" (${res.chunks_count ?? 0} chunks, ${res.total_pages} pages).`,
          type: 'success',
        });
      } else {
        const batchRes = await uploadDocumentsBatch(fileArray);
        if (batchRes.failed === 0) {
          setUploadFeedback({
            message: `Successfully ingested and indexed all ${batchRes.successful} papers into research workspace.`,
            type: 'success',
          });
        } else {
          const failedDetails = batchRes.results
            .filter((r) => r.status === 'failed')
            .map((r) => `${r.filename}: ${r.error}`)
            .join('; ');
          setUploadFeedback({
            message: `Ingested ${batchRes.successful} of ${batchRes.total} papers. Failed: ${failedDetails}`,
            type: batchRes.successful > 0 ? 'success' : 'error',
          });
        }
      }
      await loadCorpus();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Upload failed';
      setUploadFeedback({ message: msg, type: 'error' });
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      void handleFilesUpload(e.target.files);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      void handleFilesUpload(e.dataTransfer.files);
    }
  };

  const runDemo = async (submittedQuery: string, submittedMode = mode) => {
    if (!submittedQuery.trim() || isLoading) return;
    const cleanQuery = submittedQuery.trim();
    setIsLoading(true);
    setIsSourcesOpen(false);
    setShowDetailedAnswer(false);
    setPipelineStage(pipelineByMode[submittedMode][0]);
    setActiveResult(createMockWorkspaceResult(cleanQuery, submittedMode, 'loading'));

    const targetDocs =
      selectedDocNames.size > 0
        ? Array.from(selectedDocNames)
        : undefined;

    try {
      let result: WorkspaceResult;

      if (submittedMode === 'discover') {
        setPipelineStage('Searching your documents with hybrid retrieval...');
        const response = await queryBackend(cleanQuery, targetDocs);
        const template = createMockWorkspaceResult(cleanQuery, 'discover');

        let dnaData = template.knowledgeDNA;
        try {
          const dna = await queryKnowledgeDNA(cleanQuery, targetDocs);
          dnaData = {
            researchArea: dna.research_area,
            dominantTopics: dna.core_topics.map((t) => ({ label: t, weight: 0.85 })),
            coreTopics: dna.core_topics,
            keyConcepts: dna.key_concepts,
            methods: dna.methods,
            findings: dna.findings,
            limitations: dna.limitations,
            researchThemes: dna.themes,
            themes: dna.themes,
            signals: dna.signals,
            relationships: dna.relationships,
          };
        } catch {
          // Keep template DNA if background call encounters transient issue
        }

        result = {
          ...template,
          request: { ...template.request, query: cleanQuery },
          origin: 'backend',
          answer: response.answer,
          detailedAnswer: response.detail || response.answer,
          summary: response.summary,
          doc_section: response.doc_section,
          web_section: response.web_section,
          comparisonPairs: response.comparison,
          claims: response.claims,
          conflicts: response.conflicts,
          gaps: response.gaps,
          confidence: response.confidence,
          queryType: response.query_type,
          rawResponse: response,
          answerState: response.answer.trim() ? 'answer' : 'insufficient_evidence',
          sources: mapBackendSources(response.sources),
          evidence: mapBackendEvidence(response.sources),
          knowledgeDNA: dnaData,
        };
      } else if (submittedMode === 'knowledge-dna') {
        setPipelineStage('Extracting Knowledge DNA, methods, findings, and ontology...');
        const dna = await queryKnowledgeDNA(cleanQuery, targetDocs);
        const template = createMockWorkspaceResult(cleanQuery, 'knowledge-map');

        const dnaData = {
          researchArea: dna.research_area,
          dominantTopics: dna.core_topics.map((t) => ({ label: t, weight: 0.85 })),
          coreTopics: dna.core_topics,
          keyConcepts: dna.key_concepts,
          methods: dna.methods,
          findings: dna.findings,
          limitations: dna.limitations,
          researchThemes: dna.themes,
          themes: dna.themes,
          signals: dna.signals,
          relationships: dna.relationships,
        };

        const dnaQuotes = [
          ...dna.findings.map((f) => `Finding: ${f}`),
          ...dna.methods.map((m) => `Method: ${m}`),
          ...dna.limitations.map((l) => `Limitation: ${l}`),
          ...dna.signals.flatMap((s) => (Array.isArray(s.evidence) ? s.evidence : [])),
        ].filter(Boolean);

        result = {
          ...template,
          request: { ...template.request, mode: 'knowledge-dna', query: cleanQuery },
          origin: 'backend',
          answer: `Knowledge DNA for "${cleanQuery}": Identified ${dna.core_topics.length} core topics, ${dna.key_concepts.length} key concepts, ${dna.methods.length} methods, and ${dna.findings.length} empirical findings.`,
          detailedAnswer: `Research Area: ${dna.research_area}\n\nCore Topics: ${dna.core_topics.join(', ')}\n\nKey Concepts: ${dna.key_concepts.join(', ')}\n\nMethods: ${dna.methods.join(', ')}\n\nFindings:\n${dna.findings.map((f) => `• ${f}`).join('\n')}\n\nReported Limitations:\n${dna.limitations.map((l) => `• ${l}`).join('\n')}`,
          queryType: 'knowledge_dna',
          rawResponse: dna,
          answerState: 'answer',
          knowledgeDNA: dnaData,
          sources: mapBackendSources(dna.sources || []),
          evidence: mapBackendEvidence(dna.sources || [], dnaQuotes.length > 0 ? dnaQuotes : undefined),
        };
      } else if (submittedMode === 'verify') {
        setPipelineStage('Verifying claim against document evidence...');
        const response = await verifyClaimBackend(cleanQuery, targetDocs);
        const template = createMockWorkspaceResult(cleanQuery, 'verify');

        const isSupported = response.verdict.toUpperCase() === 'SUPPORTED';
        const isContradicted = response.verdict.toUpperCase() === 'CONTRADICTED';
        const assessment = isSupported ? 'supported' : isContradicted ? 'contradicted' : 'uncertain';

        result = {
          ...template,
          request: { ...template.request, query: cleanQuery },
          origin: 'backend',
          confidence: response.confidence,
          answer: `Claim Verdict: ${response.verdict}\n\n${response.explanation}`,
          detailedAnswer: `${response.explanation}\n\nExtracted Evidence:\n${response.evidence.map((e) => `• ${e}`).join('\n')}`,
          rawResponse: response,
          answerState: 'answer',
          verification: [
            {
              claim: response.claim || cleanQuery,
              assessment,
              explanation: response.explanation,
              evidenceIds: response.source_chunk_ids || [],
              counterEvidenceIds: [],
            },
          ],
          sources: mapBackendSources(response.sources),
          evidence: mapBackendEvidence(response.sources, response.evidence),
        };
      } else if (submittedMode === 'compare') {
        setPipelineStage('Analyzing comparative dimensions across papers...');
        const response = await compareBackend(cleanQuery, targetDocs);
        const template = createMockWorkspaceResult(cleanQuery, 'compare');

        const rows = response.comparison.map((aspect) => {
          const v0 = aspect.values[0];
          const v1 = aspect.values[1];
          return {
            criterion: aspect.aspect,
            leftValue: v0 ? `${v0.entity}: ${v0.value}` : 'N/A',
            rightValue: v1 ? `${v1.entity}: ${v1.value}` : (v0 ? `${v0.entity}: ${v0.value}` : 'N/A'),
            evidenceIds: aspect.values.map((v) => v.chunk_id).filter(Boolean),
          };
        });

        const compareQuotes = response.comparison.flatMap((aspect) =>
          aspect.values
            .map((v) => (v.evidence ? `${v.entity} [${aspect.aspect}]: ${v.value} — "${v.evidence}"` : `${v.entity} [${aspect.aspect}]: ${v.value}`))
        ).filter(Boolean);

        result = {
          ...template,
          request: { ...template.request, query: cleanQuery },
          origin: 'backend',
          answer: response.summary,
          detailedAnswer: `${response.summary}\n\nEntities analyzed: ${response.entities.join(', ')}`,
          rawResponse: response,
          answerState: 'answer',
          comparison: rows.length > 0 ? rows : template.comparison,
          comparisonEntities: response.entities,
          sources: mapBackendSources(response.sources),
          evidence: mapBackendEvidence(
            response.sources,
            compareQuotes.length > 0 ? compareQuotes : undefined,
          ),
        };
      } else if (submittedMode === 'gaps') {
        setPipelineStage('Identifying literature boundaries and research gaps...');
        const response = await findResearchGapsBackend(cleanQuery, targetDocs);
        const template = createMockWorkspaceResult(cleanQuery, 'gaps');

        const gapSummary = response.gaps.map((g) => `• ${g.gap} (${g.rationale})`).join('\n');

        result = {
          ...template,
          request: { ...template.request, query: cleanQuery },
          origin: 'backend',
          answer: `Research Area: ${response.research_area}\n\nIdentified ${response.gaps.length} potential research gaps:\n${gapSummary}`,
          detailedAnswer: `Research Area: ${response.research_area}\n\nExisting Findings:\n${response.existing_findings.map((f) => `• ${f}`).join('\n')}\n\nReported Limitations:\n${response.reported_limitations.map((l) => `• ${l}`).join('\n')}`,
          rawResponse: response,
          answerState: 'answer',
          researchGap: {
            title: response.research_area || `Research Gaps: ${cleanQuery}`,
            currentKnowledge: response.existing_findings.join('; ') || 'Identified findings from indexed literature',
            missingConnection: response.reported_limitations.join('; ') || 'Reported literature limitations and constraints',
            potentialGap: response.gaps.map((g) => `${g.gap} [Rationale: ${g.rationale}]`).join(' | ') || 'Emerging research directions',
            evidenceIds: response.sources.map((s) => s.chunk_id),
          },
          sources: mapBackendSources(response.sources),
          evidence: mapBackendEvidence(
            response.sources,
            response.gaps.flatMap((g) => g.evidence)
          ),
        };
      } else if (submittedMode === 'debate') {
        setPipelineStage('Generating evidence-grounded debate arguments...');
        const response = await runDebateBackend(cleanQuery, undefined, undefined, targetDocs);
        const template = createMockWorkspaceResult(cleanQuery, 'debate');

        result = {
          ...template,
          request: { ...template.request, query: cleanQuery },
          origin: 'backend',
          confidence: response.verdict_confidence,
          answer: `Debate Conclusion: ${response.final_verdict}`,
          detailedAnswer: `Topic: ${response.topic}\n\nVerdict (${response.verdict_confidence}% confidence): ${response.final_verdict}`,
          rawResponse: response,
          answerState: 'answer',
          debate: {
            positions: [
              {
                id: 'pos_a',
                title: response.position_a,
                claim: response.arguments.filter((a) => a.side === 'POSITION_A').map((a) => a.argument).join(' ') || response.position_a,
                evidenceIds: response.arguments.filter((a) => a.side === 'POSITION_A').map((a) => a.chunk_id || '').filter(Boolean),
              },
              {
                id: 'pos_b',
                title: response.position_b,
                claim: response.arguments.filter((a) => a.side === 'POSITION_B').map((a) => a.argument).join(' ') || response.position_b,
                evidenceIds: response.arguments.filter((a) => a.side === 'POSITION_B').map((a) => a.chunk_id || '').filter(Boolean),
              },
            ],
            conclusion: response.final_verdict,
          },
          sources: mapBackendSources(response.sources),
          evidence: mapBackendEvidence(
            response.sources,
            response.arguments.map((a) => a.argument)
          ),
        };
      } else if (submittedMode === 'knowledge-map') {
        setPipelineStage('Constructing knowledge mind map graph...');
        const response = await queryKnowledgeMindMap(cleanQuery, targetDocs);
        const template = createMockWorkspaceResult(cleanQuery, 'knowledge-map');

        const rootNode: MindMapNode = {
          id: 'root',
          label: response.research_area || cleanQuery,
          description: `Synthesized knowledge graph covering ${response.nodes.length} concepts and ${response.edges.length} relationships.`,
          children: response.nodes.map((node) => ({
            id: node.id,
            label: `${node.label} (${node.type})`,
            description: node.description,
          })),
        };

        result = {
          ...template,
          request: { ...template.request, query: cleanQuery },
          origin: 'backend',
          answer: `Knowledge Mind Map for "${cleanQuery}": Extracted ${response.nodes.length} conceptual nodes and ${response.edges.length} relationships.`,
          detailedAnswer: `Research Area: ${response.research_area}\n\nExtracted Nodes:\n${response.nodes.map((n) => `• [${n.type}] ${n.label}: ${n.description}`).join('\n')}`,
          rawResponse: response,
          answerState: 'answer',
          mindMap: rootNode,
          sources: mapBackendSources(response.sources),
          evidence: mapBackendEvidence(
            response.sources,
            response.nodes.map((n) => n.description)
          ),
        };
      } else {
        // 'reason' mode: multi-step query decomposition and evidence-grounded reasoning
        setPipelineStage('Decomposing query into reasoning sub-questions...');
        const response = await reasonBackend(cleanQuery, targetDocs);
        const template = createMockWorkspaceResult(cleanQuery, 'reason');

        const steps = [
          {
            id: 'step_1',
            title: 'Query Decomposition',
            description: `Decomposed complex inquiry into ${response.subquestions.length} logical sub-questions.`,
            status: 'complete' as const,
          },
          {
            id: 'step_2',
            title: 'Multi-Hop Hybrid Retrieval',
            description: `Gathered ${response.sources.length} evidence passages across BM25 and FAISS indexes.`,
            status: 'complete' as const,
          },
          {
            id: 'step_3',
            title: 'Evidence-Grounded Synthesis',
            description: 'Synthesized verified multi-step reasoning response.',
            status: 'complete' as const,
          },
        ];

        const subQuestions = response.subquestions.map((sq, i) => ({
          id: `sq_${i + 1}`,
          question: sq,
          evidenceIds: response.sources.map((s) => s.chunk_id),
          synthesis: 'Evidence-grounded sub-inquiry evaluated across indexed literature.',
        }));

        result = {
          ...template,
          request: { ...template.request, query: cleanQuery },
          origin: 'backend',
          answer: response.answer,
          detailedAnswer: `Multi-Step Reasoning Outcome:\n\n${response.answer}\n\nDecomposed Sub-Questions:\n${response.subquestions.map((sq, i) => `${i + 1}. ${sq}`).join('\n')}`,
          queryType: 'reasoning',
          rawResponse: response,
          answerState: response.answer.trim() ? 'answer' : 'insufficient_evidence',
          reasoning: {
            originalQuestion: cleanQuery,
            subQuestions,
            evidence: mapBackendEvidence(response.sources),
            synthesis: response.answer,
            finalAnswer: response.answer,
            steps,
          },
          sources: mapBackendSources(response.sources),
          evidence: mapBackendEvidence(response.sources),
        };
      }

      const item: WorkspaceHistoryItem = {
        id: result.request.id,
        query: cleanQuery,
        mode: submittedMode,
        result,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setActiveResult(result);
      setActiveHistoryId(item.id);
      setHistory((previous) => [item, ...previous.filter((entry) => entry.query.toLowerCase() !== cleanQuery.toLowerCase())]);
      setVisualization(
        submittedMode === 'knowledge-dna'
          ? 'dna'
          : submittedMode === 'knowledge-map'
          ? 'mind-map'
          : 'knowledge',
      );
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Backend request failed';
      const errorResult = createMockWorkspaceResult(cleanQuery, submittedMode, 'error');
      errorResult.answer = `Query failed: ${errorMessage}. Check backend logs and network connection.`;
      errorResult.detailedAnswer = errorResult.answer;
      errorResult.origin = 'local-fallback';
      setActiveResult(errorResult);
    } finally {
      setIsLoading(false);
      setPipelineStage('');
    }
  };

  const runAutoQuery = useEffectEvent((query: string, queryMode: AnalysisMode) => {
    void runDemo(query, queryMode);
  });

  useEffect(() => {
    if (!autoRunId || !autoRunQuery || startedAutoRunId.current === autoRunId) return;
    startedAutoRunId.current = autoRunId;
    runAutoQuery(autoRunQuery, autoRunMode);
  }, [autoRunId, autoRunMode, autoRunQuery]);

  const handleModeChange = (nextMode: AnalysisMode) => {
    setMode(nextMode);
    setActiveResult(null);
    setActiveHistoryId(null);
    setIsSourcesOpen(false);
    setVisualization(
      nextMode === 'knowledge-dna'
        ? 'dna'
        : nextMode === 'knowledge-map'
        ? 'mind-map'
        : 'knowledge',
    );
    setSearchParams((previous) => {
      const next = new URLSearchParams(previous);
      next.set('mode', nextMode);
      next.delete('q');
      return next;
    }, { replace: true });
  };

  const handleSelectHistory = (item: WorkspaceHistoryItem) => {
    setQuery(item.query);
    setMode(item.mode);
    setActiveResult(item.result);
    setActiveHistoryId(item.id);
    setShowDetailedAnswer(false);
    setIsSourcesOpen(false);
    setVisualization(
      item.mode === 'knowledge-dna'
        ? 'dna'
        : item.mode === 'knowledge-map'
        ? 'mind-map'
        : 'knowledge',
    );
    setSearchParams({ mode: item.mode }, { replace: true });
  };

  const handleNewSearch = () => {
    setQuery('');
    setActiveResult(null);
    setActiveHistoryId(null);
    setPipelineStage('');
    setIsSourcesOpen(false);
  };

  const handleClearHistory = () => {
    if (!window.confirm('Are you sure you want to clear your entire research query history?')) {
      return;
    }
    setHistory([]);
    setActiveHistoryId(null);
    localStorage.removeItem(historyKey);
    setActiveResult(null);
  };

  const showAbstention = () => {
    const exampleQuery = query.trim() || 'Show an example with insufficient evidence';
    setActiveResult(createMockWorkspaceResult(exampleQuery, mode, 'insufficient_evidence'));
    setActiveHistoryId(null);
    setIsSourcesOpen(false);
  };

  React.useEffect(() => {
    try {
      localStorage.setItem(historyKey, JSON.stringify(history));
    } catch (error) {
      console.error('Failed to save workspace history', error);
    }
  }, [history, historyKey]);

  const isAnswered = activeResult?.answerState === 'answer';

  return (
    <div className="flex min-h-[calc(100vh-4rem)] flex-col bg-[#0b1219] text-[#f3faf0] lg:h-[calc(100vh-4rem)] lg:flex-row lg:overflow-hidden">
      <SearchSidebar
        history={history}
        activeId={activeHistoryId}
        onSelectHistory={handleSelectHistory}
        onNewSearch={handleNewSearch}
        onClearHistory={handleClearHistory}
        onOpenDocuments={() => setIsDocumentModalOpen(true)}
        onExportSessionMarkdown={() => {
          exportSessionToMarkdown(history, currentUser?.name || 'Researcher');
          setDownloadHistory(getDownloadHistory(currentUserId));
        }}
        onExportSessionHtml={() => {
          exportSessionToHtml(history, currentUser?.name || 'Researcher');
          setDownloadHistory(getDownloadHistory(currentUserId));
        }}
        onOpenDownloads={() => setIsDownloadsOpen(true)}
        downloadCount={downloadHistory.length}
      />

      <main className="min-w-0 flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-7 sm:px-6 lg:px-10 lg:py-8">
          
          {/* Header & Backend Live Status Banner */}
          <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-1">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-mono uppercase tracking-wider text-[#a7d0d2]">
                  UNKNOWN · Research Intelligence
                </span>
                {backendOnline === true ? (
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-[10px] font-mono text-emerald-400">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    <span>Backend Online (127.0.0.1:8000)</span>
                  </span>
                ) : backendOnline === false ? (
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-rose-500/30 bg-rose-500/10 px-2.5 py-0.5 text-[10px] font-mono text-rose-300">
                    <span className="h-1.5 w-1.5 rounded-full bg-rose-400" />
                    <span>Backend Offline</span>
                    <button
                      type="button"
                      onClick={() => void loadCorpus()}
                      disabled={isCheckingBackend}
                      className="ml-1 inline-flex items-center gap-1 underline text-rose-200 hover:text-white cursor-pointer"
                    >
                      {isCheckingBackend ? <Loader2 className="h-2.5 w-2.5 animate-spin" /> : <RefreshCw className="h-2.5 w-2.5" />}
                      <span>Retry</span>
                    </button>
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-0.5 text-[10px] font-mono text-amber-300">
                    <Loader2 className="h-2.5 w-2.5 animate-spin text-amber-400" />
                    <span>Connecting to Backend...</span>
                  </span>
                )}
              </div>
              <h1 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
                Academic Research Assistant
              </h1>
              <p className="max-w-3xl text-sm leading-relaxed text-[#c1cbd2]">
                Adaptive Hybrid Semantic Research &amp; Evidence Engine
              </p>
            </div>

            {/* Document and download toolbar */}
            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={() => setIsDownloadsOpen(true)}
                className="inline-flex items-center gap-1.5 rounded-xl border border-[#4d728e]/40 bg-[#141d26] px-3.5 py-2 text-xs font-semibold text-white hover:border-[#a7d0d2] hover:bg-[#1b2734] transition-all shadow-sm cursor-pointer"
                title="View download and export history"
              >
                <Download className="h-4 w-4 text-[#a7d0d2]" />
                <span>Downloads ({downloadHistory.length})</span>
              </button>

              <button
                type="button"
                onClick={() => setIsDocumentModalOpen(true)}
                className="inline-flex items-center gap-1.5 rounded-xl border border-[#4d728e]/40 bg-[#141d26] px-3.5 py-2 text-xs font-semibold text-white hover:border-[#a7d0d2] hover:bg-[#1b2734] transition-all shadow-sm cursor-pointer"
              >
                <FileText className="h-4 w-4 text-[#d2434e]" />
                <span>Corpus ({corpusDocuments.length})</span>
              </button>
            </div>
          </header>

          {/* Prominent Indexed Document Corpus & Ingestion Panel */}
          <section
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={`rounded-2xl border transition-all duration-200 p-4 sm:p-5 shadow-lg backdrop-blur-md ${
              isDragging
                ? 'border-[#d2434e] bg-[#141d26] ring-2 ring-[#d2434e]/50'
                : 'border-[#4d728e]/35 bg-[#10171d]/90'
            }`}
          >
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/8 pb-3">
              <div className="flex flex-wrap items-center gap-2">
                <Layers className="h-4 w-4 text-[#a7d0d2]" />
                <h2 className="text-xs font-mono uppercase tracking-wider text-[#f3faf0]/90">
                  Research Document Collection
                </h2>
                <span className={`rounded-full border px-2.5 py-0.5 text-[10px] font-mono ${
                  corpusDocuments.length >= 25
                    ? 'border-rose-500/40 bg-rose-500/10 text-rose-300'
                    : 'border-white/10 bg-[#1b2734] text-[#a7d0d2]'
                }`}>
                  {corpusDocuments.length}/25 Papers
                </span>
                <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-mono text-emerald-400">
                  {selectedDocNames.size} Selected for Analysis
                </span>
              </div>

              <div className="flex items-center gap-2">
                {corpusDocuments.length > 0 && (
                  <>
                    <button
                      type="button"
                      onClick={selectAllDocs}
                      className="text-[11px] font-mono text-[#a7d0d2] hover:text-white transition-colors cursor-pointer"
                    >
                      Select All
                    </button>
                    <span className="text-[#f3faf0]/20">·</span>
                    <button
                      type="button"
                      onClick={clearDocSelection}
                      className="text-[11px] font-mono text-[#f3faf0]/60 hover:text-white transition-colors cursor-pointer"
                    >
                      Clear
                    </button>
                    <span className="text-[#f3faf0]/20">·</span>
                  </>
                )}
                <button
                  type="button"
                  onClick={() => setIsCorpusExpanded(!isCorpusExpanded)}
                  className="text-xs text-[#a7d0d2] hover:text-white flex items-center gap-1 cursor-pointer"
                >
                  <span>{isCorpusExpanded ? 'Collapse' : 'Expand'}</span>
                  {isCorpusExpanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                </button>
              </div>
            </div>

            {isCorpusExpanded && (
              <div className="mt-4 space-y-4">
                {/* Active Document Cards */}
                <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
                  {corpusDocuments.map((doc) => {
                    const isSelected = selectedDocNames.has(doc.name);
                    const isDeleting = deletingDocName === doc.name;

                    return (
                      <div
                        key={doc.name}
                        onClick={() => toggleDocSelection(doc.name)}
                        className={`group relative flex flex-col justify-between rounded-xl border p-3 transition-all shadow-sm cursor-pointer ${
                          isSelected
                            ? 'border-[#a7d0d2]/60 bg-[#17232e]'
                            : 'border-white/8 bg-[#141d26]/60 opacity-70 hover:opacity-100 hover:border-white/20'
                        }`}
                      >
                        <div className="flex items-start gap-2.5">
                          {/* Selection Checkbox */}
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              toggleDocSelection(doc.name);
                            }}
                            className="mt-0.5 text-[#a7d0d2] hover:text-white transition-colors cursor-pointer shrink-0"
                            title={isSelected ? 'Deselect from analysis scope' : 'Select for analysis scope'}
                          >
                            {isSelected ? (
                              <CheckSquare className="h-4 w-4 text-emerald-400" />
                            ) : (
                              <Square className="h-4 w-4 text-[#f3faf0]/40" />
                            )}
                          </button>

                          <div className="min-w-0 flex-1">
                            <p className="text-xs font-semibold text-white truncate group-hover:text-[#a7d0d2] transition-colors">
                              {doc.title || doc.name}
                            </p>
                            <p className="text-[10px] font-mono text-[#f3faf0]/55 mt-0.5">
                              {doc.document_type.toUpperCase()} · {doc.total_pages} {doc.total_pages === 1 ? 'page' : 'pages'} · {doc.chunks_count} chunks
                            </p>
                          </div>
                        </div>

                        {/* Action buttons on card */}
                        <div
                          className="mt-3 flex items-center justify-between border-t border-white/5 pt-2"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <button
                            type="button"
                            onClick={() => setSelectedPaperForDetail(doc)}
                            className="inline-flex items-center gap-1 text-[11px] font-medium text-[#d2434e] hover:text-[#ff6b76] transition-colors cursor-pointer"
                            title="Open extracted text, abstract preview & full details"
                          >
                            <Eye className="h-3 w-3" />
                            <span>Read Paper</span>
                          </button>

                          <div className="flex items-center gap-2">
                            <a
                              href={getDocumentDownloadUrl(doc.name)}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-mono text-[#a7d0d2] hover:bg-[#a7d0d2]/10 transition-colors cursor-pointer"
                              title="Open or download original file"
                            >
                              {doc.name.toLowerCase().endsWith('.pdf') ? (
                                <>
                                  <ExternalLink className="h-2.5 w-2.5" />
                                  <span>PDF</span>
                                </>
                              ) : (
                                <>
                                  <Download className="h-2.5 w-2.5" />
                                  <span>File</span>
                                </>
                              )}
                            </a>

                            <button
                              type="button"
                              onClick={() => setConfirmDocName(doc.name)}
                              disabled={isDeleting}
                              className="inline-flex items-center gap-1 rounded p-1 text-rose-400/80 hover:text-rose-300 hover:bg-rose-500/10 transition-colors cursor-pointer"
                              title={`Delete "${doc.name}" from collection`}
                            >
                              {isDeleting ? (
                                <Loader2 className="h-3 w-3 animate-spin text-rose-400" />
                              ) : (
                                <Trash2 className="h-3 w-3" />
                              )}
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })}

                  {/* Batch Upload & Drop Zone Card */}
                  <label className={`flex flex-col items-center justify-center rounded-xl border border-dashed p-4 transition-all ${
                    corpusDocuments.length >= 25
                      ? 'border-white/10 bg-[#141d26]/20 cursor-not-allowed opacity-50'
                      : isDragging
                      ? 'border-[#d2434e] bg-[#1a2530] cursor-pointer'
                      : 'border-[#4d728e]/50 bg-[#141d26]/40 hover:border-[#d2434e] hover:bg-[#141d26]/70 cursor-pointer'
                  }`}>
                    <input
                      ref={fileInputRef}
                      type="file"
                      multiple
                      accept=".pdf,.docx,.txt"
                      onChange={handleFileUpload}
                      className="hidden"
                      disabled={isUploading || corpusDocuments.length >= 25}
                    />
                    {isUploading ? (
                      <div className="flex flex-col items-center gap-1.5 text-center text-xs text-[#a7d0d2]">
                        <Loader2 className="h-5 w-5 animate-spin text-[#d2434e]" />
                        <span className="font-semibold text-white">Ingesting & Re-indexing Chunks...</span>
                        <span className="text-[10px] text-[#f3faf0]/50 font-mono">Running OCR & building FAISS index</span>
                      </div>
                    ) : corpusDocuments.length >= 25 ? (
                      <div className="flex flex-col items-center gap-1 text-center">
                        <AlertCircle className="h-5 w-5 text-amber-400 mb-1" />
                        <span className="text-xs font-semibold text-white">Capacity Full (25/25 Papers)</span>
                        <span className="text-[10px] font-mono text-[#f3faf0]/50">Remove a paper to upload more</span>
                      </div>
                    ) : (
                      <>
                        <UploadCloud className="h-5 w-5 text-[#a7d0d2] mb-1.5" />
                        <span className="text-xs font-semibold text-white text-center">
                          Upload Papers (Batch Supported)
                        </span>
                        <span className="text-[10px] font-mono text-[#f3faf0]/55 mt-0.5 text-center">
                          Drag & drop or click · Up to 25 papers
                        </span>
                      </>
                    )}
                  </label>
                </div>

                {uploadFeedback && (
                  <div
                    className={`rounded-lg border px-3 py-2 text-xs flex items-center justify-between gap-2 ${
                      uploadFeedback.type === 'success'
                        ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                        : 'border-rose-500/30 bg-rose-500/10 text-rose-300'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      {uploadFeedback.type === 'success' ? (
                        <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
                      ) : (
                        <AlertCircle className="h-4 w-4 text-rose-400 shrink-0" />
                      )}
                      <span>{uploadFeedback.message}</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => setUploadFeedback(null)}
                      className="text-[#f3faf0]/50 hover:text-white cursor-pointer"
                    >
                      <XCircle className="h-3.5 w-3.5" />
                    </button>
                  </div>
                )}
              </div>
            )}
          </section>

          {/* Research Query & Tool Selector Box */}
          <section className="refire-card space-y-4 p-5 sm:p-6" aria-label="Knowledge query">
            {/* Active Document Scope Pill */}
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-[#4d728e]/30 bg-[#141d26]/80 px-3.5 py-2 text-xs">
              <div className="flex items-center gap-2">
                <Filter className="h-3.5 w-3.5 text-[#a7d0d2]" />
                <span className="font-mono text-[11px] text-[#f3faf0]/80 font-medium">
                  Analysis Scope:
                </span>
                {corpusDocuments.length === 0 ? (
                  <span className="font-mono text-[11px] text-[#f3faf0]/50">
                    Corpus is empty — upload a paper above
                  </span>
                ) : selectedDocNames.size === corpusDocuments.length ? (
                  <span className="inline-flex items-center gap-1.5 font-mono text-[11px] text-emerald-400">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    All {corpusDocuments.length} Papers Active
                  </span>
                ) : selectedDocNames.size > 0 ? (
                  <span className="inline-flex items-center gap-1.5 font-mono text-[11px] text-amber-300">
                    <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
                    {selectedDocNames.size} of {corpusDocuments.length} Papers Selected
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1.5 font-mono text-[11px] text-rose-400">
                    <AlertCircle className="h-3 w-3" />
                    No papers selected (retrieval will abstain or fallback)
                  </span>
                )}
              </div>

              {corpusDocuments.length > 0 && selectedDocNames.size < corpusDocuments.length && (
                <button
                  type="button"
                  onClick={selectAllDocs}
                  className="text-[11px] font-mono text-[#a7d0d2] hover:text-white hover:underline cursor-pointer"
                >
                  Reset Scope to All Papers ({corpusDocuments.length})
                </button>
              )}
            </div>

            {/* One-Button Smart Query Bar (Task P2-4) */}
            <div className="mb-3">
              <SmartQueryBar
                initialQuery={query}
                selectedDocuments={Array.from(selectedDocNames)}
                onResultReceived={(res) => {
                  if (res.rewritten_query) setQuery(res.rewritten_query);
                }}
              />
            </div>

            <QueryInput
              query={query}
              mode={mode}
              isLoading={isLoading}
              loadingLabel={pipelineStage || 'Processing...'}
              selectedDocuments={Array.from(selectedDocNames)}
              onQueryChange={setQuery}
              onSubmit={() => void runDemo(query)}
              onShowAbstention={showAbstention}
            />
            <div className="border-t border-white/8 pt-4">
              <SearchModeSelector value={mode} onChange={handleModeChange} disabled={isLoading} />
            </div>
          </section>

          {/* Initial State Dashboard (When no query has been run yet) */}
          {!activeResult && (
            <section className="space-y-4 pt-2">
              <div className="flex items-center justify-between border-b border-white/8 pb-2">
                <div className="flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-[#d2434e]" />
                  <h3 className="text-xs font-mono uppercase tracking-wider text-[#f3faf0]/85">
                    One-Click Quick Start Inquiries
                  </h3>
                </div>
                <span className="text-[11px] text-[#f3faf0]/45">Click any inquiry to test live</span>
              </div>

              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
                <button
                  type="button"
                  onClick={() => {
                    const q = 'What are the core components of SAC-RAG?';
                    setMode('discover');
                    setQuery(q);
                    void runDemo(q, 'discover');
                  }}
                  className="rounded-xl border border-white/8 bg-[#141d26]/60 p-4 text-left hover:border-[#a7d0d2] hover:bg-[#1b2734] transition-all group cursor-pointer shadow-sm"
                >
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-[#a7d0d2] mb-1.5">
                    <BookOpen className="h-3.5 w-3.5 text-[#d2434e]" />
                    <span>Research Assistant</span>
                  </div>
                  <p className="text-xs text-white group-hover:text-[#a7d0d2] transition-colors leading-relaxed font-medium">
                    "What are the core components of SAC-RAG?"
                  </p>
                  <span className="mt-2.5 block text-[10px] font-mono text-[#f3faf0]/50">
                    Runs /query → Answers + Citations + Scores
                  </span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    const q = 'Extract the complete Knowledge DNA of SAC-RAG';
                    setMode('knowledge-dna');
                    setQuery(q);
                    void runDemo(q, 'knowledge-dna');
                  }}
                  className="rounded-xl border border-white/8 bg-[#141d26]/60 p-4 text-left hover:border-[#a7d0d2] hover:bg-[#1b2734] transition-all group cursor-pointer shadow-sm"
                >
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-400 mb-1.5">
                    <Dna className="h-3.5 w-3.5 text-emerald-400" />
                    <span>Knowledge DNA</span>
                  </div>
                  <p className="text-xs text-white group-hover:text-emerald-300 transition-colors leading-relaxed font-medium">
                    "Extract the complete Knowledge DNA of SAC-RAG"
                  </p>
                  <span className="mt-2.5 block text-[10px] font-mono text-[#f3faf0]/50">
                    Runs /knowledge-dna → Topics, Methods, Findings
                  </span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    const q = 'Compare dense retrieval and sparse retrieval in SAC-RAG';
                    setMode('compare');
                    setQuery(q);
                    void runDemo(q, 'compare');
                  }}
                  className="rounded-xl border border-white/8 bg-[#141d26]/60 p-4 text-left hover:border-[#a7d0d2] hover:bg-[#1b2734] transition-all group cursor-pointer shadow-sm"
                >
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-cyan-400 mb-1.5">
                    <Scale className="h-3.5 w-3.5 text-cyan-400" />
                    <span>Compare Matrix</span>
                  </div>
                  <p className="text-xs text-white group-hover:text-cyan-300 transition-colors leading-relaxed font-medium">
                    "Compare dense retrieval and sparse retrieval in SAC-RAG"
                  </p>
                  <span className="mt-2.5 block text-[10px] font-mono text-[#f3faf0]/50">
                    Runs /compare → Comparative aspect matrix
                  </span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    const q = 'Analyze the reasoning framework in SAC-RAG';
                    setMode('reason');
                    setQuery(q);
                    void runDemo(q, 'reason');
                  }}
                  className="rounded-xl border border-white/8 bg-[#141d26]/60 p-4 text-left hover:border-[#a7d0d2] hover:bg-[#1b2734] transition-all group cursor-pointer shadow-sm"
                >
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-amber-400 mb-1.5">
                    <Waypoints className="h-3.5 w-3.5 text-amber-400" />
                    <span>Multi-Step Reasoning</span>
                  </div>
                  <p className="text-xs text-white group-hover:text-amber-300 transition-colors leading-relaxed font-medium">
                    "Analyze the reasoning framework in SAC-RAG"
                  </p>
                  <span className="mt-2.5 block text-[10px] font-mono text-[#f3faf0]/50">
                    Runs /reason → Subquestion decomposition
                  </span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    const q = 'Dense retrieval can completely replace lexical search in academic RAG';
                    setMode('debate');
                    setQuery(q);
                    void runDemo(q, 'debate');
                  }}
                  className="rounded-xl border border-white/8 bg-[#141d26]/60 p-4 text-left hover:border-[#a7d0d2] hover:bg-[#1b2734] transition-all group cursor-pointer shadow-sm"
                >
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-purple-400 mb-1.5">
                    <MessageCircleQuestion className="h-3.5 w-3.5 text-purple-400" />
                    <span>AI Debate</span>
                  </div>
                  <p className="text-xs text-white group-hover:text-purple-300 transition-colors leading-relaxed font-medium">
                    "Dense retrieval can completely replace lexical search"
                  </p>
                  <span className="mt-2.5 block text-[10px] font-mono text-[#f3faf0]/50">
                    Runs /debate → Evidence-backed thesis/antithesis
                  </span>
                </button>
              </div>
            </section>
          )}

          {/* Active Result View */}
          {activeResult && (
            <div className="space-y-6">
              {/* Status Header & Result Export Toolbar */}
              <div className={`rounded-xl border px-4 py-3 text-xs leading-relaxed flex flex-wrap items-center justify-between gap-3 ${
                activeResult.origin === 'backend'
                  ? 'border-emerald-500/25 bg-[#141d26]/80 text-[#f3faf0]/85'
                  : activeResult.origin === 'static-demo'
                  ? 'border-amber-400/25 bg-amber-400/[0.05] text-amber-200/90'
                  : 'border-orange-400/25 bg-orange-400/[0.05] text-orange-200/90'
              }`}>
                <div className="flex flex-wrap items-center gap-2">
                  {activeResult.origin === 'backend' ? (
                    <span className="font-mono font-semibold uppercase text-emerald-400">● Live Backend Response</span>
                  ) : activeResult.origin === 'static-demo' ? (
                    <span className="font-mono font-semibold uppercase text-amber-400">○ Static Demo Data</span>
                  ) : (
                    <span className="font-mono font-semibold uppercase text-orange-400">▲ Local Fallback (Backend Offline/Unavailable)</span>
                  )}
                  <span>·</span>
                  <span className="text-[#a7d0d2] font-mono">{modeTitles[activeResult.request.mode]}</span>
                  <span>·</span>
                  <span className="text-[11px] font-mono text-[#f3faf0]/50">
                    {activeResult.sources.length} Sources {activeResult.origin === 'backend' ? 'Retrieved' : 'Referenced'}
                  </span>
                </div>

                {/* Export Buttons */}
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      exportResultToMarkdown(activeResult, currentUser?.name || 'Researcher');
                      setDownloadHistory(getDownloadHistory(currentUserId));
                    }}
                    className="flex items-center gap-1 rounded bg-[#10171d] hover:bg-[#1b2734] border border-white/10 px-2.5 py-1 text-[11px] font-mono text-[#a7d0d2] hover:text-white transition-colors cursor-pointer"
                    title="Export result as Markdown report"
                  >
                    <Download className="h-3 w-3" />
                    <span>Markdown</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      exportResultToPrintableHtml(activeResult, currentUser?.name || 'Researcher');
                      setDownloadHistory(getDownloadHistory(currentUserId));
                    }}
                    className="flex items-center gap-1 rounded bg-[#10171d] hover:bg-[#1b2734] border border-white/10 px-2.5 py-1 text-[11px] font-mono text-[#a7d0d2] hover:text-white transition-colors cursor-pointer"
                    title="Export result as styled Printable HTML (Print to PDF)"
                  >
                    <ExternalLink className="h-3 w-3" />
                    <span>Printable HTML / PDF</span>
                  </button>

                  {(activeResult.request.mode === 'knowledge-map' || activeResult.request.mode === 'knowledge-dna') && (
                    <button
                      type="button"
                      onClick={() => {
                        exportMindMapToJson(activeResult, currentUser?.name || 'Researcher');
                        setDownloadHistory(getDownloadHistory(currentUserId));
                      }}
                      className="flex items-center gap-1 rounded bg-[#10171d] hover:bg-[#1b2734] border border-white/10 px-2.5 py-1 text-[11px] font-mono text-[#a7d0d2] hover:text-white transition-colors cursor-pointer"
                      title="Export graph topology as JSON"
                    >
                      <Layers className="h-3 w-3" />
                      <span>Graph JSON</span>
                    </button>
                  )}
                </div>
              </div>

              {/* Progress Bar (while loading) */}
              {isLoading && (
                <div className="rounded-xl border border-[#4d728e]/30 bg-[#141d26]/60 p-4" role="status" aria-live="polite">
                  <div className="flex items-center gap-2 text-xs font-medium text-[#a7d0d2]">
                    <Loader2 className="h-4 w-4 animate-spin text-[#d2434e]" />
                    <span>{pipelineStage}</span>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {pipelineByMode[mode].map((stage, index) => (
                      <span
                        key={stage}
                        className={`rounded-full border px-2.5 py-1 text-[10px] font-mono ${
                          stage === pipelineStage
                            ? 'border-[#a7d0d2]/60 text-[#a7d0d2] bg-[#a7d0d2]/10'
                            : 'border-white/8 text-[#f3faf0]/35'
                        }`}
                      >
                        {String(index + 1).padStart(2, '0')} · {stage.replace('...', '')}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Primary Answer Panel */}
              <AnswerPanel
                answer={activeResult.answer}
                detailedAnswer={activeResult.detailedAnswer}
                summary={activeResult.summary}
                doc_section={activeResult.doc_section}
                web_section={activeResult.web_section}
                comparison={activeResult.comparisonPairs}
                claims={activeResult.claims}
                conflicts={activeResult.conflicts}
                gaps={activeResult.gaps}
                sources={activeResult.sources}
                query={activeResult.request?.query}
                confidence={activeResult.confidence}
                answerState={activeResult.answerState}
                showDetailed={showDetailedAnswer}
                onToggleDetail={() => setShowDetailedAnswer((value) => !value)}
                queryType={activeResult.queryType}
                rawResponse={activeResult.rawResponse}
              />

              {/* Mode-Specific Structured Views */}
              {isAnswered && (
                <>
                  {activeResult.request.mode === 'knowledge-dna' && (
                    <KnowledgeDNA data={activeResult.knowledgeDNA} documentName={Array.from(selectedDocNames)[0]} />
                  )}

                  {activeResult.request.mode === 'reason' && (
                    <ReasoningTimeline reasoning={activeResult.reasoning} onOpenSources={() => setIsSourcesOpen(true)} />
                  )}

                  {activeResult.request.mode === 'verify' && (
                    <VerificationView results={activeResult.verification} onOpenSources={() => setIsSourcesOpen(true)} />
                  )}

                  {activeResult.request.mode === 'compare' && (
                    <ComparisonView
                      rows={activeResult.comparison}
                      entities={activeResult.comparisonEntities}
                      onOpenSources={() => setIsSourcesOpen(true)}
                    />
                  )}

                  {activeResult.request.mode === 'gaps' && (
                    <GapView gap={activeResult.researchGap} onOpenSources={() => setIsSourcesOpen(true)} />
                  )}

                  {activeResult.request.mode === 'debate' && (
                    <DebateView debate={activeResult.debate} onOpenSources={() => setIsSourcesOpen(true)} />
                  )}

                  {activeResult.request.mode === 'knowledge-map' && (
                    <KnowledgeMindMap root={activeResult.mindMap} documentName={Array.from(selectedDocNames)[0]} />
                  )}
                </>
              )}

              {/* Retrieved Source Evidence Panel with BM25, FAISS, and Hybrid Scores */}
              <EvidencePanel
                evidence={activeResult.evidence}
                sources={activeResult.sources}
                onOpenSources={() => setIsSourcesOpen(true)}
              />

              {/* Visualization Views (3D Graph / Mind Map / Knowledge DNA Explorer) */}
              {isAnswered && (
                <section className="space-y-3" aria-labelledby="visualization-heading">
                  <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/8 pb-2">
                    <div>
                      <h2 id="visualization-heading" className="text-xs font-mono uppercase tracking-wider text-white">
                        Exploratory Visualizations
                      </h2>
                      <p className="mt-0.5 text-[11px] text-[#98a6b0]">
                        Interactive 3D orbit and conceptual mind map topology.
                      </p>
                    </div>
                    <div className="flex gap-1 rounded-lg border border-white/10 bg-[#141d26]/80 p-1" role="tablist">
                      {([
                        ['knowledge', '3D Knowledge Orbit'],
                        ['mind-map', 'Relational Mind Map'],
                        ['dna', 'Knowledge DNA'],
                      ] as [VisualizationView, string][]).map(([view, label]) => (
                        <button
                          key={view}
                          type="button"
                          role="tab"
                          aria-selected={visualization === view}
                          onClick={() => setVisualization(view)}
                          className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                            visualization === view
                              ? 'bg-[#1b2734] text-white shadow-sm border border-white/10'
                              : 'text-[#f3faf0]/55 hover:text-white'
                          }`}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  </div>

                  {visualization === 'knowledge' && (
                    <ConceptGraph3D
                      concept={activeResult.concept}
                      evidence={activeResult.evidence}
                      onOpenSources={() => setIsSourcesOpen(true)}
                    />
                  )}
                  {visualization === 'mind-map' && (

                    <KnowledgeMindMap root={activeResult.mindMap} documentName={Array.from(selectedDocNames)[0]} />

                  )}

                  {visualization === 'dna' && (

                    <KnowledgeDNA data={activeResult.knowledgeDNA} documentName={Array.from(selectedDocNames)[0]} />

                  )}
                </section>
              )}
            </div>
          )}
        </div>
      </main>

      {/* Sources Side Drawer */}
      <SourcesDrawer
        isOpen={isSourcesOpen}
        sources={activeResult?.sources || []}
        evidence={activeResult?.evidence || []}
        onClose={() => setIsSourcesOpen(false)}
      />

      {/* Corpus Ingestion & Management Modal */}
      <DocumentModal
        isOpen={isDocumentModalOpen}
        onClose={() => setIsDocumentModalOpen(false)}
        onOpenPaperDetail={(doc) => setSelectedPaperForDetail(doc)}
        onSelectDocumentQuery={(suggestedQuery) => {
          setQuery(suggestedQuery);
          void runDemo(suggestedQuery, 'discover');
        }}
      />

      {/* Paper Detail & Content Preview Modal */}
      <PaperDetailModal
        document={selectedPaperForDetail}
        isOpen={!!selectedPaperForDetail}
        onClose={() => setSelectedPaperForDetail(null)}
        onQueryPaper={(suggestedQuery) => {
          setQuery(suggestedQuery);
          void runDemo(suggestedQuery, 'discover');
        }}
      />

      {/* User-Isolated Download History Modal */}
      {isDownloadsOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="relative w-full max-w-2xl rounded-2xl border border-white/10 bg-[#10171d] p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <Download className="h-4 w-4 text-[#d2434e]" />
                  <span>Research Download History</span>
                </h3>
                <p className="text-xs text-[#a7d0d2] font-mono mt-0.5">
                  User Workspace: {currentUser?.name || 'Local Researcher'} ({currentUser?.id || 'guest'})
                </p>
              </div>
              <button
                type="button"
                onClick={() => setIsDownloadsOpen(false)}
                className="rounded-lg p-1 text-[#f3faf0]/50 hover:bg-white/10 hover:text-white transition-colors cursor-pointer"
              >
                <XCircle className="h-5 w-5" />
              </button>
            </div>

            {downloadHistory.length === 0 ? (
              <div className="py-12 text-center text-xs text-[#f3faf0]/50">
                <Download className="h-8 w-8 mx-auto mb-2 text-[#f3faf0]/20" />
                <p>No reports exported in this workspace yet.</p>
                <p className="text-[11px] mt-1 text-[#f3faf0]/40">Export individual results or complete sessions to see them logged here.</p>
              </div>
            ) : (
              <div className="max-h-80 overflow-y-auto space-y-2">
                {downloadHistory.map((item) => (
                  <div key={item.id} className="flex items-center justify-between p-3 rounded-lg border border-white/5 bg-[#141d26]/70 text-xs">
                    <div className="min-w-0 flex-1 pr-3">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-[10px] uppercase px-1.5 py-0.5 rounded bg-[#1b2734] text-[#a7d0d2] border border-white/10">
                          {item.format}
                        </span>
                        <span className="font-mono text-[10px] text-[#f3faf0]/40">
                          {new Date(item.timestamp).toLocaleString()}
                        </span>
                      </div>
                      <p className="font-medium text-white truncate mt-1 text-xs">
                        {item.query}
                      </p>
                      <p className="text-[10px] font-mono text-[#f3faf0]/40 mt-0.5">
                        {item.filename} ({(item.sizeBytes / 1024).toFixed(1)} KB)
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="flex items-center justify-between border-t border-white/10 pt-3">
              {downloadHistory.length > 0 ? (
                <button
                  type="button"
                  onClick={() => {
                    if (window.confirm('Clear all recorded downloads for your account?')) {
                      clearDownloadHistory(currentUserId);
                      setDownloadHistory([]);
                    }
                  }}
                  className="inline-flex items-center gap-1.5 text-xs text-rose-400 hover:text-rose-300 transition-colors cursor-pointer"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  <span>Clear Download History</span>
                </button>
              ) : <div />}

              <button
                type="button"
                onClick={() => setIsDownloadsOpen(false)}
                className="rounded-lg bg-[#141d26] hover:bg-[#1b2734] border border-white/10 px-4 py-1.5 text-xs font-medium text-white transition-colors cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {confirmDocName && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-2xl border border-rose-500/30 bg-[#0f171e] p-6 shadow-2xl">
            <div className="flex items-center gap-3 text-rose-400 mb-3">
              <Trash2 className="h-6 w-6" />
              <h3 className="text-lg font-bold text-white">Confirm Deletion</h3>
            </div>
            <p className="text-sm text-[#f3faf0]/80 mb-6 leading-relaxed">
              Are you sure you want to delete <strong className="text-white font-mono">{confirmDocName}</strong>?
              This removes its chunks, FAISS vectors, and derived artifacts with a 10-second undo window.
            </p>
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setConfirmDocName(null)}
                className="px-4 py-2 rounded-lg bg-[#1a252d] text-sm text-[#f3faf0]/80 hover:bg-[#253540] hover:text-white transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => void handleConfirmDeleteDocument()}
                className="px-4 py-2 rounded-lg bg-rose-600 hover:bg-rose-500 text-sm font-semibold text-white shadow-lg transition-colors cursor-pointer"
              >
                Delete Document
              </button>
            </div>
          </div>
        </div>
      )}

      {undoToast && (
        <div className="fixed bottom-6 right-6 z-[70] flex items-center gap-3 rounded-xl border border-[#a7d0d2]/40 bg-[#0c131a] px-5 py-3.5 shadow-2xl backdrop-blur-md">
          <div className="flex flex-col">
            <span className="text-sm font-semibold text-white">
              Staged <span className="font-mono text-[#a7d0d2]">{undoToast.docName}</span> for deletion
            </span>
            <span className="text-xs text-[#f3faf0]/60">
              Undo available: {undoToast.secondsLeft}s remaining
            </span>
          </div>
          <button
            type="button"
            onClick={() => void handleUndoDeleteDocument(undoToast.docName)}
            className="ml-2 inline-flex items-center gap-1.5 rounded-lg bg-[#a7d0d2] px-3 py-1.5 text-xs font-bold text-[#0b1219] hover:bg-white shadow transition-colors cursor-pointer"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            <span>Undo</span>
          </button>
          <button
            type="button"
            onClick={() => {
              if (undoTimerRef.current) clearInterval(undoTimerRef.current);
              setUndoToast(null);
            }}
            className="text-white/40 hover:text-white text-xs ml-1 cursor-pointer"
          >
            ✕
          </button>
        </div>
      )}

    </div>
  );
};