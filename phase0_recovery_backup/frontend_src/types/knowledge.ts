export interface MindMapNode {
  id: string;
  label: string;
  description?: string;
  children?: MindMapNode[];
}

export interface KnowledgeTopic {
  label: string;
  weight: number;
}

export interface KnowledgeRelationship {
  source: string;
  target: string;
  relationship: string;
}

export interface KnowledgeSignal {
  name?: string;
  type?: string;
  strength?: number;
  description?: string;
  [key: string]: unknown;
}

export interface KnowledgeDNA {
  researchArea?: string;
  dominantTopics: KnowledgeTopic[];
  coreTopics?: string[];
  keyConcepts: string[];
  methods?: string[];
  findings?: string[];
  limitations?: string[];
  researchThemes: string[];
  themes?: string[];
  signals?: KnowledgeSignal[];
  relationships?: KnowledgeRelationship[];
}