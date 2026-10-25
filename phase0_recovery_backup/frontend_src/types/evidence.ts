export interface Evidence {
  id: string;
  documentName: string;
  page?: number | string;
  chunkId?: string;
  text: string;
  score?: number;
  relevance?: number;
}

export interface Source {
  id: string;
  rank?: number;
  document?: string;
  documentName?: string; // backwards compatibility
  page?: number | string;
  chunkId?: string;
  chunk_id?: string;
  evidenceCount?: number;
  score?: number;
  hybridScore?: number;
  hybrid_score?: number;
  bm25Score?: number;
  bm25_score?: number;
  faissScore?: number;
  faiss_score?: number;
  title?: string | null;
  authors?: string[];
  year?: number | null;
  venue?: string | null;
  doi?: string | null;
  url?: string | null;
  origin?: 'document' | 'web' | 'scholarly' | string;
  passage?: string | null;
  quote?: string | null;
  retrieved_at?: string | null;
  reliability?: number;
  warnings?: string[];
}
