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

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const BACKEND_URL: string = (
  import.meta.env.VITE_BACKEND_URL as string | undefined ?? 'http://localhost:8000'
).replace(/\/$/, '');

const TIMEOUT_MS: number = (() => {
  const raw = import.meta.env.VITE_BACKEND_TIMEOUT_MS as string | undefined;
  const parsed = raw ? parseInt(raw, 10) : NaN;
  return Number.isFinite(parsed) && parsed >= 500 ? parsed : 5000;
})();

// ---------------------------------------------------------------------------
// Shared fetch helper
// ---------------------------------------------------------------------------

async function fetchWithTimeout(
  url: string,
  options: RequestInit,
  timeoutMs: number,
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    return response;
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error(
        `Backend request timed out after ${timeoutMs} ms. Is the server running at ${BACKEND_URL}?`,
      );
    }
    throw new Error(
      `Network error reaching ${BACKEND_URL}: ${err instanceof Error ? err.message : String(err)}`,
    );
  } finally {
    clearTimeout(timer);
  }
}

async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetchWithTimeout(
    `${BACKEND_URL}${path}`,
    {
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      ...options,
    },
    TIMEOUT_MS,
  );

  if (!response.ok) {
    let detail: string;
    try {
      const body = await response.json() as { detail?: unknown };
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
    } catch {
      detail = response.statusText || `HTTP ${response.status}`;
    }
    throw new Error(`${response.status}: ${detail}`);
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
 * POST /documents/upload
 * Upload a single research document (PDF, DOCX, or TXT).
 */
export async function uploadDocument(file: File): Promise<BackendUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetchWithTimeout(
    `${BACKEND_URL}/documents/upload`,
    { method: 'POST', body: formData },
    // Use a longer timeout for uploads (up to 5× base timeout)
    Math.max(TIMEOUT_MS * 5, 30_000),
  );

  if (!response.ok) {
    let detail: string;
    try {
      const body = await response.json() as { detail?: unknown };
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
    } catch {
      detail = response.statusText || `HTTP ${response.status}`;
    }
    throw new Error(`Upload failed (${response.status}): ${detail}`);
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
  const formData = new FormData();
  for (const file of files) {
    formData.append('files', file);
  }

  const response = await fetchWithTimeout(
    `${BACKEND_URL}/documents/upload-batch`,
    { method: 'POST', body: formData },
    Math.max(TIMEOUT_MS * 5, 60_000),
  );

  if (!response.ok) {
    let detail: string;
    try {
      const body = await response.json() as { detail?: unknown };
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
    } catch {
      detail = response.statusText || `HTTP ${response.status}`;
    }
    throw new Error(`Batch upload failed (${response.status}): ${detail}`);
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
): Promise<BackendQueryResponse> {
  return apiFetch<BackendQueryResponse>('/query', {
    method: 'POST',
    body: JSON.stringify({ query, document_names: documentNames ?? null }),
  });
}

/**
 * POST /reason
 * Multi-step query decomposition and evidence-grounded reasoning.
 */
export async function reasonBackend(
  query: string,
  documentNames?: string[],
): Promise<BackendReasoningResponse> {
  return apiFetch<BackendReasoningResponse>('/reason', {
    method: 'POST',
    body: JSON.stringify({ query, document_names: documentNames ?? null }),
  });
}

/**
 * POST /verify
 * Verify a claim against indexed document evidence.
 */
export async function verifyClaimBackend(
  claim: string,
  documentNames?: string[],
): Promise<BackendVerifyResponse> {
  return apiFetch<BackendVerifyResponse>('/verify', {
    method: 'POST',
    body: JSON.stringify({ claim, document_names: documentNames ?? null }),
  });
}

/**
 * POST /compare
 * Run a structured research comparison across indexed papers.
 */
export async function compareBackend(
  query: string,
  documentNames?: string[],
): Promise<BackendCompareResponse> {
  return apiFetch<BackendCompareResponse>('/compare', {
    method: 'POST',
    body: JSON.stringify({ query, document_names: documentNames ?? null }),
  });
}

/**
 * POST /gaps
 * Identify research gaps from the indexed literature.
 */
export async function findResearchGapsBackend(
  query: string,
  documentNames?: string[],
): Promise<BackendResearchGapResponse> {
  return apiFetch<BackendResearchGapResponse>('/gaps', {
    method: 'POST',
    body: JSON.stringify({ query, document_names: documentNames ?? null }),
  });
}

/**
 * POST /debate
 * Run an evidence-grounded AI debate.
 *
 * If `positionA` or `positionB` are not provided the function generates
 * sensible default position strings from the query to satisfy the backend's
 * required fields.
 */
export async function runDebateBackend(
  query: string,
  positionA?: string,
  positionB?: string,
  documentNames?: string[],
): Promise<BackendDebateResponse> {
  const pA = positionA?.trim() || `${query} — in favour`;
  const pB = positionB?.trim() || `${query} — against`;

  return apiFetch<BackendDebateResponse>('/debate', {
    method: 'POST',
    body: JSON.stringify({
      query,
      position_a: pA,
      position_b: pB,
      document_names: documentNames ?? null,
    }),
  });
}

/**
 * POST /knowledge-dna
 * Extract the Knowledge DNA profile for a research topic.
 */
export async function queryKnowledgeDNA(
  query: string,
  documentNames?: string[],
): Promise<BackendKnowledgeDNAResponse> {
  return apiFetch<BackendKnowledgeDNAResponse>('/knowledge-dna', {
    method: 'POST',
    body: JSON.stringify({ query, document_names: documentNames ?? null }),
  });
}

/**
 * POST /knowledge-mind-map
 * Generate a knowledge mind map for a research topic.
 */
export async function queryKnowledgeMindMap(
  query: string,
  documentNames?: string[],
): Promise<BackendKnowledgeMindMapResponse> {
  return apiFetch<BackendKnowledgeMindMapResponse>('/knowledge-mind-map', {
    method: 'POST',
    body: JSON.stringify({ query, document_names: documentNames ?? null }),
  });
}
