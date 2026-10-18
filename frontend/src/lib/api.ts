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
  return Number.isFinite(parsed) && parsed >= 500 ? parsed : 30000;
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
export async function deleteDocument(documentName: string): Promise<void> {
  await apiFetch<unknown>(
    `/documents/${encodeURIComponent(documentName)}`,
    { method: 'DELETE' },
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
  signal?: AbortSignal,
): Promise<BackendQueryResponse> {
  return apiFetch<BackendQueryResponse>(
    '/query',
    {
      method: 'POST',
      body: JSON.stringify({ query, document_names: documentNames ?? null }),
    },
    DEFAULT_QUERY_TIMEOUT_MS,
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
