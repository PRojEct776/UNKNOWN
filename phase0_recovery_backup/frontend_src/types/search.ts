import type { ConceptResult } from './concept';

export type { ConceptResult } from './concept';
export type { GraphEdge, GraphNode, GraphNodeType } from './graph';

export interface SearchHistoryItem {
  id: string;
  query: string;
  result: ConceptResult;
  timestamp: string;
}
