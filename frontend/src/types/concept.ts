import type { GraphEdge, GraphNode } from './graph';

export interface ConceptResult {
  id: string;
  name: string;
  category: string;
  description: string;
  usedIn: string[];
  functions: string[];
  relatedConcepts: string[];
  confidenceScore: number;
  graphNodes: GraphNode[];
  graphEdges: GraphEdge[];
}