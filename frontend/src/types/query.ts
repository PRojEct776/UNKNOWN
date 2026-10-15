import type { ClaimVerification, ComparisonRow, DebateResult, ResearchGap } from './analysis';
import type { ConceptResult } from './concept';
import type { Evidence, Source } from './evidence';
import type { ReasoningResult } from './reasoning';
import type { KnowledgeDNA, MindMapNode } from './knowledge';

export type AnalysisMode =
  | 'discover'
  | 'reason'
  | 'verify'
  | 'compare'
  | 'gaps'
  | 'debate'
  | 'knowledge-map'
  | 'knowledge-dna';

export type AnswerState = 'answer' | 'insufficient_evidence' | 'error' | 'loading';
export type ResultOrigin = 'backend' | 'local-fallback' | 'static-demo';

export interface QueryRequest {
  id: string;
  query: string;
  mode: AnalysisMode;
  submittedAt: string;
}

export interface WorkspaceResult {
  request: QueryRequest;
  answerState: AnswerState;
  origin: ResultOrigin;
  answer: string;
  detailedAnswer: string;
  confidence?: number;
  evidence: Evidence[];
  sources: Source[];
  concept: ConceptResult;
  reasoning: ReasoningResult;
  verification: ClaimVerification[];
  comparison: ComparisonRow[];
  comparisonEntities?: string[];
  researchGap: ResearchGap;
  debate: DebateResult;
  mindMap: MindMapNode;
  knowledgeDNA: KnowledgeDNA;
  queryType?: string;
  rawResponse?: unknown;
}

export interface WorkspaceHistoryItem {
  id: string;
  query: string;
  mode: AnalysisMode;
  result: WorkspaceResult;
  timestamp: string;
}