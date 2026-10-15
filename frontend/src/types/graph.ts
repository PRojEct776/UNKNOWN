export type GraphNodeType =
  | 'concept'
  | 'category'
  | 'environment'
  | 'function'
  | 'process'
  | 'evidence'
  | 'document'
  | 'claim';

export interface GraphNode {
  id: string;
  label: string;
  isCentral?: boolean;
  type?: GraphNodeType;
  description?: string;
  documentName?: string;
  page?: number;
  chunkId?: string;
  evidenceId?: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  relationship: string;
}