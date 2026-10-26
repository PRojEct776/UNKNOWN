/**
 * UNKNOWN Frontend — Backend API Client
 *
 * Typed fetch wrappers for every real endpoint exposed by the FastAPI backend
 * (`backend/app/main.py`). The base URL is read from VITE_BACKEND_URL (env
 * variable), defaulting to http://localhost:8000.
 *
 * All requests use a configurable timeout (VITE_BACKEND_TIMEOUT_MS, default
 * 5000 ms). On timeout or network failure the functions throw an Error with a
 * descriptive message so callers can surface the issue clearly in the UI.
 *
 * CORS: The backend allows all HTTP/HTTPS origins. No extra headers needed.
 *
 * Do NOT add endpoints here that do not exist in the backend.
 */

import { getStoredUser } from './mockAuth';
import type { ComparisonPair, Claim, Conflict, ConfidenceData } from '../types/query';

// ---------------------------------------------------------------------------
// Error Classification Classes
// ---------------------------------------------------------------------------

export class BackendTimeoutError extends Error {
  readonly timeoutMs: number;
  readonly url: string;
  constructor(timeoutMs: number, url: string) {
    super(
      `Backend request timed out after ${(timeoutMs / 1000).toFixed(0)}s while querying ${url}. ` +
      `The deep multi-hop reasoning pipeline or embedding model may be loading context.`
    );
    this.name = 'BackendTimeoutError';
    this.timeoutMs = timeoutMs;
    this.url = url;
  }
}

export class BackendConnectionError extends Error {
  readonly url: string;
  constructor(url: string, cause?: unknown) {
    super(`Cannot reach UNKNOWN backend at ${url}. Please confirm the server is running on port 8000.`, { cause });
    this.name = 'BackendConnectionError';
    this.url = url;
  }
}

export class BackendHttpError extends Error {
  readonly status: number;
  readonly detail: string;
  constructor(status: number, detail: string) {
    super(`Backend returned error ${status}: ${detail}`);
    this.name = 'BackendHttpError';
    this.status = status;
    this.detail = detail;
  }
}

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

export const BACKEND_URL: string = (
  import.meta.env.VITE_BACKEND_URL as string | undefined ?? 'http://localhost:8000'
).replace(/\/$/, '');

/** Default timeout for actual research queries (approx 30s for embedding & multi-hop RAG). */
export const DEFAULT_QUERY_TIMEOUT_MS: number = (() => {
  const raw = import.meta.env.VITE_BACKEND_TIMEOUT_MS as string | undefined;
  const parsed = raw ? parseInt(raw, 10) : NaN;
  return Number.isFinite(parsed) && parsed >= 500 ? parsed : 120000;
})();

/** Fast timeout for health checks, pings, and lightweight metadata calls (5s). */
export const FAST_TIMEOUT_MS: number = (() => {
  const raw = import.meta.env.VITE_FAST_TIMEOUT_MS as string | undefined;
  const parsed = raw ? parseInt(raw, 10) : NaN;
  return Number.isFinite(parsed) && parsed >= 500 ? parsed : 5000;
})();

// ---------------------------------------------------------------------------
// Shared fetch helper with AbortController & Timeout
// ---------------------------------------------------------------------------

async function fetchWithTimeout(
  url: string,
  options: RequestInit,
  timeoutMs: number,
  externalSignal?: AbortSignal,
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  if (externalSignal) {
    if (externalSignal.aborted) {
      clearTimeout(timer);
      throw new DOMException('Aborted by user', 'AbortError');
    }
    externalSignal.addEventListener('abort', () => controller.abort());
  }

  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    return response;
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      if (externalSignal?.aborted) {
        throw err;
      }
      throw new BackendTimeoutError(timeoutMs, url);
    }
    throw new BackendConnectionError(url, err);
  } finally {
    clearTimeout(timer);
  }
}

async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  timeoutMs: number = DEFAULT_QUERY_TIMEOUT_MS,
  signal?: AbortSignal,
): Promise<T> {
  const storedUser = getStoredUser();
  const userHeaders: Record<string, string> = {};
  if (storedUser?.id) {
    userHeaders['X-User-Id'] = storedUser.id;
  }
  if (storedUser?.apiToken && storedUser.apiToken.startsWith('bearer_')) {
    userHeaders['Authorization'] = `Bearer ${storedUser.apiToken}`;
  }

  const response = await fetchWithTimeout(
    `${BACKEND_URL}${path}`,
    {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        ...userHeaders,
        ...(options.headers as Record<string, string> | undefined),
      },
    },
    timeoutMs,
    signal,
  );

  if (!response.ok) {
    let detail: string;
    try {
      const body = await response.json() as { detail?: unknown };
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
    } catch {
      detail = response.statusText || `HTTP ${response.status}`;
    }
    throw new BackendHttpError(response.status, detail);
  }

  return response.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Shared backend types (mirroring backend/app/api/schemas.py)
// ---------------------------------------------------------------------------

/** A single retrieved source chunk as returned by the backend. */
export interface BackendQuerySource {
  rank: number;
  document: string;
  page: number | string;
  chunk_id: string;
  hybrid_score: number;
  bm25_score: number;
  faiss_score: number;
}

/** A single indexed document as returned by GET /documents. */
export interface BackendDocument {
  name: string;
  title: string;
  document_type: string;
  total_pages: number;
  total_words: number;
  chunks_count: number;
  status: string;
}

// ---------------------------------------------------------------------------
// Response types (mirrors backend Pydantic models)
// ---------------------------------------------------------------------------

export interface BackendQueryResponse {
  query: string;
  query_type: string;
  answer: string;
  summary?: string;
  detail?: string;
  doc_section?: string | null;
  web_section?: string | null;
  comparison?: ComparisonPair[];
  claims?: Claim[];
  conflicts?: Conflict[];
  gaps?: string[];
  confidence?: number | ConfidenceData | null;
  sources: BackendQuerySource[];
}

export interface BackendReasoningResponse {
  query: string;
  subquestions: string[];
  answer: string;
  sources: BackendQuerySource[];
}

export interface BackendVerifyResponse {
  claim: string;
  verdict: string;
  confidence: number;
  explanation: string;
  evidence: string[];
  source_chunk_ids: string[];
  sources: BackendQuerySource[];
}

export interface BackendComparisonValue {
  entity: string;
  value: string;
  evidence: string;
  document: string;
  page: number | string;
  chunk_id: string;
}

export interface BackendComparisonAspect {
  aspect: string;
  values: BackendComparisonValue[];
}

export interface BackendCompareResponse {
  query: string;
  entities: string[];
  comparison: BackendComparisonAspect[];
  summary: string;
  sources: BackendQuerySource[];
}

export interface BackendResearchGap {
  gap: string;
  rationale: string;
  evidence: string[];
  [key: string]: unknown;
}

export interface BackendResearchGapResponse {
  query: string;
  research_area: string;
  existing_findings: string[];
  reported_limitations: string[];
  gaps: BackendResearchGap[];
  sources: BackendQuerySource[];
}

export interface BackendDebateArgument {
  side: 'POSITION_A' | 'POSITION_B' | string;
  argument: string;
  chunk_id?: string;
  [key: string]: unknown;
}

export interface BackendDebateResponse {
  query: string;
  topic: string;
  position_a: string;
  position_b: string;
  arguments: BackendDebateArgument[];
  rebuttals: unknown[];
  final_verdict: string;
  verdict_confidence: number;
  sources: BackendQuerySource[];
}

export interface BackendKnowledgeDNASignal {
  name?: string;
  type?: string;
  strength?: number;
  description?: string;
  evidence?: string[];
  [key: string]: unknown;
}

export interface BackendKnowledgeDNARelationship {
  source: string;
  target: string;
  relationship: string;
  [key: string]: unknown;
}

export interface BackendKnowledgeDNAResponse {
  query: string;
  research_area: string;
  core_topics: string[];
  key_concepts: string[];
  methods: string[];
  findings: string[];
  limitations: string[];
  themes: string[];
  signals: BackendKnowledgeDNASignal[];
  relationships: BackendKnowledgeDNARelationship[];
  sources: BackendQuerySource[];
}

export interface BackendMindMapNode {
  id: string;
  label: string;
  type: string;
  description: string;
  [key: string]: unknown;
}

export interface BackendMindMapEdge {
  source: string;
  target: string;
  label?: string;
  [key: string]: unknown;
}

export interface BackendKnowledgeMindMapResponse {
  query: string;
  research_area: string;
  nodes: BackendMindMapNode[];
  edges: BackendMindMapEdge[];
  sources: BackendQuerySource[];
}

// Document management response types

export interface BackendDocumentsResponse {
  documents: BackendDocument[];
  total: number;
}

export interface BackendUploadResponse {
  status: string;
  filename: string;
  total_pages: number;
  total_words: number;
  chunks_count: number;
  message: string;
}

export interface BackendBatchUploadResult {
  filename: string;
  status: 'ready' | 'failed';
  error: string | null;
  total_pages: number;
  total_words: number;
  chunks_count: number;
}

export interface BackendBatchUploadResponse {
  status: string;
  total: number;
  successful: number;
  failed: number;
  results: BackendBatchUploadResult[];
}

/** Detailed document response from GET /documents/{document_name}. */
export interface BackendDocumentDetail extends BackendDocument {
  content: string;
  preview: string;
  has_original_file: boolean;
  download_url: string;
}

// ---------------------------------------------------------------------------
// API functions — Document Management
// ---------------------------------------------------------------------------

/**
 * GET /documents
 * List all indexed research documents.
 */
export async function fetchDocuments(): Promise<BackendDocumentsResponse> {
  return apiFetch<BackendDocumentsResponse>('/documents', { method: 'GET' });
}

/**
 * GET /documents/{document_name}
 * Retrieve full metadata, extracted text content, and preview for a document.
 */
export async function fetchDocumentDetail(documentName: string): Promise<BackendDocumentDetail> {
  return apiFetch<BackendDocumentDetail>(
    `/documents/${encodeURIComponent(documentName)}`,
    { method: 'GET' },
  );
}

/**
 * GET /health
 * Fast health check for backend availability.
 */
export async function checkBackendHealth(): Promise<{ status: string; service?: string; version?: string }> {
  return apiFetch<{ status: string; service?: string; version?: string }>('/health', { method: 'GET' }, FAST_TIMEOUT_MS);
}

/**
 * POST /documents/upload
 * Upload a single research document (PDF, DOCX, or TXT).
 */
export async function uploadDocument(file: File): Promise<BackendUploadResponse> {
  const storedUser = getStoredUser();
  const formData = new FormData();
  formData.append('file', file);
  if (storedUser?.id) {
    formData.append('user_id', storedUser.id);
  }

  const userHeaders: Record<string, string> = {};
  if (storedUser?.id) {
    userHeaders['X-User-Id'] = storedUser.id;
  }
  if (storedUser?.apiToken && storedUser.apiToken.startsWith('bearer_')) {
    userHeaders['Authorization'] = `Bearer ${storedUser.apiToken}`;
  }

  const response = await fetchWithTimeout(
    `${BACKEND_URL}/documents/upload`,
    { method: 'POST', body: formData, headers: userHeaders },
    Math.max(DEFAULT_QUERY_TIMEOUT_MS * 2, 60_000),
  );

  if (!response.ok) {
    let detail: string;
    try {
      const body = await response.json() as { detail?: unknown };
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
    } catch {
      detail = response.statusText || `HTTP ${response.status}`;
    }
    throw new BackendHttpError(response.status, `Upload failed: ${detail}`);
  }

  return response.json() as Promise<BackendUploadResponse>;
}

/**
 * POST /documents/upload-batch
 * Upload multiple research documents in a single request.
 */
export async function uploadDocumentsBatch(
  files: File[],
): Promise<BackendBatchUploadResponse> {
  const storedUser = getStoredUser();
  const formData = new FormData();
  for (const file of files) {
    formData.append('files', file);
  }
  if (storedUser?.id) {
    formData.append('user_id', storedUser.id);
  }

  const userHeaders: Record<string, string> = {};
  if (storedUser?.id) {
    userHeaders['X-User-Id'] = storedUser.id;
  }
  if (storedUser?.apiToken && storedUser.apiToken.startsWith('bearer_')) {
    userHeaders['Authorization'] = `Bearer ${storedUser.apiToken}`;
  }

  const response = await fetchWithTimeout(
    `${BACKEND_URL}/documents/upload-batch`,
    { method: 'POST', body: formData, headers: userHeaders },
    Math.max(DEFAULT_QUERY_TIMEOUT_MS * 2, 60_000),
  );

  if (!response.ok) {
    let detail: string;
    try {
      const body = await response.json() as { detail?: unknown };
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
    } catch {
      detail = response.statusText || `HTTP ${response.status}`;
    }
    throw new BackendHttpError(response.status, `Batch upload failed: ${detail}`);
  }

  return response.json() as Promise<BackendBatchUploadResponse>;
}

/**
 * DELETE /documents/{document_name}
 * Delete a research document and rebuild indexes.
 */
export async function deleteDocument(documentName: string, undoWindow: number = 10.0): Promise<{ status: string; document_name: string; undo_window_seconds: number; remaining_chunks: number; message: string }> {
  return apiFetch<{ status: string; document_name: string; undo_window_seconds: number; remaining_chunks: number; message: string }>(
    `/documents/${encodeURIComponent(documentName)}?undo_window=${undoWindow}`,
    { method: 'DELETE' },
  );
}

/**
 * POST /documents/{document_name}/undo
 * Restore a soft-deleted research document.
 */
export async function undoDeleteDocument(documentName: string): Promise<{ status: string; document_name: string; total_chunks: number; message: string }> {
  return apiFetch<{ status: string; document_name: string; total_chunks: number; message: string }>(
    `/documents/${encodeURIComponent(documentName)}/undo`,
    { method: 'POST' },
  );
}

/**
 * Return the URL to download or view the original file for a document.
 * (Convenience helper — no network request; the backend serves this directly.)
 */
export function getDocumentDownloadUrl(documentName: string): string {
  return `${BACKEND_URL}/documents/download/${encodeURIComponent(documentName)}`;
}

// ---------------------------------------------------------------------------
// API functions — RAG Pipeline
// ---------------------------------------------------------------------------

/**
 * POST /query
 * Execute the full UNKNOWN RAG pipeline (discover mode).
 */
export async function queryBackend(
  query: string,
  documentNames?: string[],
  docOnly: boolean = false,
  scope?: string,
  signal?: AbortSignal,
  sourceMode?: 'documents' | 'web' | 'both',
): Promise<BackendQueryResponse> {
  return apiFetch<BackendQueryResponse>(
    '/answer',
    {
      method: 'POST',
      body: JSON.stringify({
        query,
        document_names: documentNames ?? null,
        doc_only: docOnly,
        source_mode: sourceMode ?? (docOnly ? 'documents' : 'both'),
        scope: scope ?? null,
      }),
    },
    Math.max(DEFAULT_QUERY_TIMEOUT_MS, 120_000),
    signal,
  );
}

/**
 * POST /reason
 * Multi-step query decomposition and evidence-grounded reasoning.
 */
export async function reasonBackend(
  query: string,
  documentNames?: string[],
  signal?: AbortSignal,
): Promise<BackendReasoningResponse> {
  return apiFetch<BackendReasoningResponse>(
    '/reason',
    {
      method: 'POST',
      body: JSON.stringify({ query, document_names: documentNames ?? null }),
    },
    DEFAULT_QUERY_TIMEOUT_MS,
    signal,
  );
}

/**
 * POST /verify
 * Verify a claim against indexed document evidence.
 */
export async function verifyClaimBackend(
  claim: string,
  documentNames?: string[],
  signal?: AbortSignal,
): Promise<BackendVerifyResponse> {
  return apiFetch<BackendVerifyResponse>(
    '/verify',
    {
      method: 'POST',
      body: JSON.stringify({ claim, document_names: documentNames ?? null }),
    },
    DEFAULT_QUERY_TIMEOUT_MS,
    signal,
  );
}

/**
 * POST /compare
 * Run a structured research comparison across indexed papers.
 */
export async function compareBackend(
  query: string,
  documentNames?: string[],
  signal?: AbortSignal,
): Promise<BackendCompareResponse> {
  return apiFetch<BackendCompareResponse>(
    '/compare',
    {
      method: 'POST',
      body: JSON.stringify({ query, document_names: documentNames ?? null }),
    },
    DEFAULT_QUERY_TIMEOUT_MS,
    signal,
  );
}

/**
 * POST /gaps
 * Identify research gaps from the indexed literature.
 */
export async function findResearchGapsBackend(
  query: string,
  documentNames?: string[],
  signal?: AbortSignal,
): Promise<BackendResearchGapResponse> {
  return apiFetch<BackendResearchGapResponse>(
    '/gaps',
    {
      method: 'POST',
      body: JSON.stringify({ query, document_names: documentNames ?? null }),
    },
    DEFAULT_QUERY_TIMEOUT_MS,
    signal,
  );
}

/**
 * POST /debate
 * Run an evidence-grounded AI debate.
 */
export async function runDebateBackend(
  query: string,
  positionA?: string,
  positionB?: string,
  documentNames?: string[],
  signal?: AbortSignal,
): Promise<BackendDebateResponse> {
  const pA = positionA?.trim() || `${query} — in favour`;
  const pB = positionB?.trim() || `${query} — against`;

  return apiFetch<BackendDebateResponse>(
    '/debate',
    {
      method: 'POST',
      body: JSON.stringify({
        query,
        position_a: pA,
        position_b: pB,
        document_names: documentNames ?? null,
      }),
    },
    DEFAULT_QUERY_TIMEOUT_MS,
    signal,
  );
}

/**
 * POST /knowledge-dna
 * Extract the Knowledge DNA profile for a research topic.
 */
export async function queryKnowledgeDNA(
  query: string,
  documentNames?: string[],
  signal?: AbortSignal,
): Promise<BackendKnowledgeDNAResponse> {
  return apiFetch<BackendKnowledgeDNAResponse>(
    '/knowledge-dna',
    {
      method: 'POST',
      body: JSON.stringify({ query, document_names: documentNames ?? null }),
    },
    DEFAULT_QUERY_TIMEOUT_MS,
    signal,
  );
}

/**
 * POST /knowledge-mind-map
 * Generate a knowledge mind map for a research topic.
 */
export async function queryKnowledgeMindMap(
  query: string,
  documentNames?: string[],
  signal?: AbortSignal,
): Promise<BackendKnowledgeMindMapResponse> {
  return apiFetch<BackendKnowledgeMindMapResponse>(
    '/knowledge-mind-map',
    {
      method: 'POST',
      body: JSON.stringify({ query, document_names: documentNames ?? null }),
    },
    DEFAULT_QUERY_TIMEOUT_MS,
    signal,
  );
}


// ---------------------------------------------------------------------------
// API functions — History
// ---------------------------------------------------------------------------

export interface HistoryRecord {
  id: string;
  user: string;
  workspace: string;
  document_ids: string[];
  scope: string;
  query: string;
  feature: string;
  result_snapshot: unknown;
  created_at: string;
}

export async function fetchHistory(filters?: {
  user?: string;
  workspace?: string;
  feature?: string;
  document_id?: string;
  limit?: number;
  offset?: number;
}): Promise<HistoryRecord[]> {
  const params = new URLSearchParams();
  if (filters?.user) params.set('user', filters.user);
  if (filters?.workspace) params.set('workspace', filters.workspace);
  if (filters?.feature) params.set('feature', filters.feature);
  if (filters?.document_id) params.set('document_id', filters.document_id);
  if (filters?.limit) params.set('limit', String(filters.limit));
  if (filters?.offset) params.set('offset', String(filters.offset));
  const qs = params.toString() ? `?${params.toString()}` : '';
  return apiFetch<HistoryRecord[]>(`/history${qs}`);
}

export async function fetchHistoryItem(historyId: string): Promise<HistoryRecord> {
  return apiFetch<HistoryRecord>(`/history/${encodeURIComponent(historyId)}`);
}

export async function rerunHistoryItem(historyId: string): Promise<HistoryRecord> {
  return apiFetch<HistoryRecord>(`/history/${encodeURIComponent(historyId)}/rerun`, {
    method: 'POST',
  });
}

export async function deleteHistoryItem(historyId: string): Promise<{ status: string; id: string }> {
  return apiFetch<{ status: string; id: string }>(`/history/${encodeURIComponent(historyId)}`, {
    method: 'DELETE',
  });
}

export async function clearAllHistory(filters?: { user?: string; workspace?: string }): Promise<{ status: string; deleted_count: number }> {
  const params = new URLSearchParams();
  if (filters?.user) params.set('user', filters.user);
  if (filters?.workspace) params.set('workspace', filters.workspace);
  const qs = params.toString() ? `?${params.toString()}` : '';
  return apiFetch<{ status: string; deleted_count: number }>(`/history${qs}`, {
    method: 'DELETE',
  });
}


// ---------------------------------------------------------------------------
// API functions — Document Overview (Task P1-4)
// ---------------------------------------------------------------------------

export interface OverviewSentence {
  text: string;
  source_ids: number[];
  quote: string;
  page_ref: string;
  // "grounded" | "extractive": how the sentence is supported by retrieved text.
  support?: string;
}

export interface OverviewFigureDetail {
  id: string;
  label: string;
  caption: string;
  page: number | string;
  thumbnail: string;
  thumbnail_is_placeholder?: boolean;
}

export interface OverviewTableDetail {
  id: string;
  label: string;
  caption: string;
  page: number | string;
  thumbnail: string;
  thumbnail_is_placeholder?: boolean;
}

export interface BackendDocumentOverview {
  document_name: string;
  document_hash: string;
  title: string;
  authors: string[];
  year: number | null;
  page_count: number;
  language: string;
  figure_count: number;
  table_count: number;
  figures: OverviewFigureDetail[];
  tables: OverviewTableDetail[];
  summary_sentences: OverviewSentence[];
  key_topics: string[];
  document_iq: {
    iq_score?: number;
    grade?: string;
    extraction_score?: number;
    chunk_score?: number;
    embedding_score?: number;
    ocr_score?: number;
    metadata_score?: number;
    max_score?: number;
    score_basis?: string;
    points_without_direct_measurement?: number;
    // Per-component basis is measured | assumed | unavailable (exact shape not yet typed).
    components?: unknown;
  };
  suggested_questions: string[];
  question_details?: Array<{ text: string; type: string }>;
  section_status?: Record<
    string,
    { status: string; error?: string | null; detail?: string | null }
  >;
  generated_at: string;
  generation_ms: number;
  from_cache: boolean;
  executive_summary?: string;
  main_findings?: string[];
  methods_and_investigations?: string[];
  questions_it_can_answer?: string[];
}

export async function fetchDocumentOverview(
  documentName: string,
): Promise<BackendDocumentOverview> {
  return apiFetch<BackendDocumentOverview>(
    `/documents/${encodeURIComponent(documentName)}/overview`,
  );
}


// ---------------------------------------------------------------------------
// Feedback API (Task P2-1)
// ---------------------------------------------------------------------------

export interface FeedbackPayload {
  query: string;
  answer: string;
  sources?: unknown[];
  feedback_type: 'thumbs_up' | 'thumbs_down' | 'wrong_answer';
  comment?: string;
  user_id?: string;
}

export interface FeedbackResponse {
  status: string;
  id: string;
  feedback_type: string;
  recorded_at: string;
}

export async function submitFeedback(payload: FeedbackPayload): Promise<FeedbackResponse> {
  return apiFetch<FeedbackResponse>('/feedback', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function fetchFeedbackRecords(): Promise<FeedbackResponse[]> {
  return apiFetch<FeedbackResponse[]>('/feedback');
}


// ---------------------------------------------------------------------------
// Concept Graph & Knowledge DNA APIs (Task P1-5 & P2-3)
// ---------------------------------------------------------------------------

export interface BackendConceptSource {
  document: string;
  // null when the page is unknown. Never substitute a guessed page.
  page: number | string | null;
  chunk_id: string;
  passage?: string;
}

export interface BackendConceptGraphNode {
  id: string;
  label: string;
  cluster: string;
  // Not measured by the backend: always null. Never display or invent a value.
  relevance?: number | null;
  importance?: number | null;
  // Measured: number of document chunks containing the label.
  mention_count?: number;
  // "llm" or "heuristic"
  origin?: string;
  sources: BackendConceptSource[];
}

export interface BackendConceptGraphEdge {
  source: string;
  target: string;
  relation: string;
  // "co_occurrence" | "relation_term_present" (lexical evidence only) | "unverified"
  evidence_status?: string;
  origin?: string;
  sources: BackendConceptSource[];
}

export interface BackendConceptGraphResponse {
  document: string;
  nodes: BackendConceptGraphNode[];
  edges: BackendConceptGraphEdge[];
  total_nodes: number;
  total_edges: number;
  // "ok" or "empty"; when empty, empty_reason says why.
  status?: string;
  empty_reason?: string | null;
  extraction?: {
    method: string;
    chunks_analyzed: number;
    chunks_total: number;
    dropped_nodes: number;
    dropped_edges: number;
  };
  from_cache: boolean;
}

export interface BackendDocumentDNAEntity {
  name: string;
  type: string;
  page?: number | string;
}

export interface BackendDocumentDNAResponse {
  document: string;
  concepts: string[];
  entities: BackendDocumentDNAEntity[];
  methods: string[];
  claims: string[];
  difficulty: string;
  novelty: string;
  summary: string;
  sources: BackendConceptSource[];
  from_cache: boolean;
}

export interface BackendDNACompareResponse {
  document_a: string;
  document_b: string;
  shared_concepts: string[];
  distinct_concepts_a: string[];
  distinct_concepts_b: string[];
  shared_methods: string[];
  claims_a: string[];
  claims_b: string[];
  difficulty_comparison: {
    document_a?: string;
    document_b?: string;
  };
  novelty_comparison: {
    document_a?: string;
    document_b?: string;
  };
}

export async function fetchConceptGraph(
  documentName: string,
): Promise<BackendConceptGraphResponse> {
  return apiFetch<BackendConceptGraphResponse>(
    '/documents/' + encodeURIComponent(documentName) + '/concept-graph',
  );
}

export async function fetchDocumentDNA(
  documentName: string,
): Promise<BackendDocumentDNAResponse> {
  return apiFetch<BackendDocumentDNAResponse>(
    '/documents/' + encodeURIComponent(documentName) + '/dna',
  );
}

export async function compareDocumentDNA(
  docA: string,
  docB: string,
): Promise<BackendDNACompareResponse> {
  return apiFetch<BackendDNACompareResponse>('/documents/dna/compare', {
    method: 'POST',
    body: JSON.stringify({ document_a: docA, document_b: docB }),
  });
}


// ---------------------------------------------------------------------------
// Smart Query & Autocomplete APIs (Task P1-5 & P2-4)
// ---------------------------------------------------------------------------

export interface SmartQueryPayload {
  text: string;
  document_ids?: string[];
  run_all?: boolean;
  stream?: boolean;
}

export interface SmartQueryResponseData {
  original_query: string;
  rewritten_query: string;
  matched_documents: string[];
  detected_feature?: string | null;
  executed_feature?: string | null;
  run_all: boolean;
  is_ambiguous: boolean;
  clarification_options: string[];
  result?: unknown;
}

export interface AutocompleteResult {
  query: string;
  document_suggestions: string[];
  feature_suggestions: string[];
  combined_suggestions: string[];
}

export interface SmartQueryStreamEvent {
  event?: string;
  feature?: string;
  status?: string;
  progress?: number;
  message?: string;
  result?: unknown;
}

export async function postSmartQuery(payload: SmartQueryPayload): Promise<SmartQueryResponseData> {
  return apiFetch<SmartQueryResponseData>('/smart-query', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function fetchSmartQueryAutocomplete(query: string): Promise<AutocompleteResult> {
  return apiFetch<AutocompleteResult>(
    '/smart-query/autocomplete?q=' + encodeURIComponent(query),
  );
}

export async function streamSmartQuery(
  payload: SmartQueryPayload,
  onEvent: (event: SmartQueryStreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';
  const response = await fetch(backendUrl + '/smart-query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...payload, stream: true }),
    signal,
  });

  if (!response.ok || !response.body) {
    throw new Error('Smart query stream failed: ' + response.statusText);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed.startsWith('data: ')) {
        try {
          const parsed = JSON.parse(trimmed.slice(6));
          onEvent(parsed);
        } catch {
          // ignore malformed chunks
        }
      }
    }
  }
}


// ---------------------------------------------------------------------------
// Secure Sharing API
// ---------------------------------------------------------------------------

export interface ShareResponse {
  share_token: string;
  share_url: string;
  expires_at: number | null;
  is_active: boolean;
}

export async function createShareLink(
  conversation: unknown,
  includeDocContent: boolean = false,
  expiresInHours: number = 72,
): Promise<ShareResponse> {
  return apiFetch<ShareResponse>('/share', {
    method: 'POST',
    body: JSON.stringify({
      conversation,
      include_doc_content: includeDocContent,
      expires_in_hours: expiresInHours,
    }),
  });
}

export async function getSharedConversation(token: string): Promise<unknown> {
  return apiFetch<unknown>(`/share/${encodeURIComponent(token)}`, {
    method: 'GET',
  });
}

export async function revokeShareLink(token: string): Promise<{ status: string; token: string }> {
  return apiFetch<{ status: string; token: string }>(`/share/${encodeURIComponent(token)}`, {
    method: 'DELETE',
  });
}
