export interface Evidence {
  id: string;
  documentName: string;
  page?: number;
  chunkId?: string;
  text: string;
  score?: number;
  relevance?: number;
}

export interface Source {
  id: string;
  documentName: string;
  page?: number | string;
  chunkId?: string;
  evidenceCount?: number;
  rank?: number;
  score?: number;
  bm25Score?: number;
  faissScore?: number;
}