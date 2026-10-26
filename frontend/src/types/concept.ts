import type { GraphEdge, GraphNode } from './graph';

export interface ConceptResult {
  id: string;
  name: string;
  category: string;
  description: string;
  usedIn: string[];
  functions: string[];
  relatedConcepts: string[];
  // Not measured by the backend: leave unset instead of inventing a value.
  confidenceScore?: number | null;
  graphNodes: GraphNode[];
  graphEdges: GraphEdge[];
}