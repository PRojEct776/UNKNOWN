export interface MindMapNode {
  id: string;
  label: string;
  type?: string;
  description?: string;
  evidence?: string[];
  confidence?: number;
  document?: string;
  page?: number | string | null;
  chunk_id?: string;
  parentId?: string | null;
  children?: MindMapNode[];
  notice?: string;
  partial?: boolean;
  significance?: string;
}

export interface KnowledgeTopic {
  label: string;
  weight: number;
}

export interface KnowledgeRelationship {
  source: string;
  target: string;
  relationship: string;
  evidence?: string;
  confidence?: number;
  is_inferred?: boolean;
  supporting_papers?: string[];
  [key: string]: unknown;
}

export interface KnowledgeSignal {
  name?: string;
  type?: string;
  strength?: number;
  description?: string;
  evidence?: string[];
  confidence?: number;
  document?: string;
  page?: number | string | null;
  chunk_id?: string;
  [key: string]: unknown;
}

export interface KnowledgeDNACitation {
  document?: string;
  page?: number | string | null;
  chunk_id?: string;
  passage?: string;
}

export interface KnowledgeDNANode {
  id: string;
  label: string;
  category: string;
  explanation?: string;
  evidence?: string[];
  confidence?: number;
  document?: string;
  supporting_papers?: string[];
  page?: number | string | null;
  chunk_id?: string;
  is_inferred?: boolean;
  quantitative_value?: string | null;
  citations?: KnowledgeDNACitation[];
  [key: string]: unknown;
}

export interface KnowledgeDNAConflict {
  topic: string;
  paper_a: string;
  finding_a: string;
  paper_b: string;
  finding_b: string;
  explanation: string;
  evidence_chunks?: string[];
}

export interface KnowledgeDNAStatistics {
  total_concepts?: number;
  unique_methodologies?: number;
  datasets?: number;
  findings?: number;
  relationships?: number;
  explicit_relationships?: number;
  inferred_relationships?: number;
  supporting_documents?: number;
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

  // 10 Dimensions & Graph
  nodes?: KnowledgeDNANode[];
  edges?: KnowledgeRelationship[];
  objectives?: string[];
  core_concepts?: string[];
  methodologies?: string[];
  datasets?: string[];
  metrics?: string[];
  results?: string[];
  contributions?: string[];
  advantages?: string[];
  future_directions?: string[];
  conflicting_findings?: KnowledgeDNAConflict[];
  cross_paper_connections?: KnowledgeRelationship[];
  statistics?: KnowledgeDNAStatistics;
  partial?: boolean;
  notice?: string | null;
}
