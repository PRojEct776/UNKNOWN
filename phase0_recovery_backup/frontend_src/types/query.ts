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

export interface ConfidenceBreakdown {
  evidence_coverage: number;
  claim_support: number;
  source_agreement: number;
  source_quality: number;
}

export interface ConfidenceData {
  score: number;
  breakdown?: ConfidenceBreakdown;
  formula_version?: string;
}

export interface ComparisonPair {
  sub_question: string;
  label: 'agree' | 'disagree' | 'not_addressed' | string;
  doc_quote: string;
  web_quote: string;
  doc_source: string;
}

export interface Claim {
  text: string;
  label: 'supported' | 'partial' | 'unsupported' | 'contradicted' | string;
  source_ids?: string[];
  quote?: string | null;
}

export interface Conflict {
  topic: string;
  side_a: string;
  side_b: string;
  likely_reason?: string | null;
}

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
  summary?: string;
  doc_section?: string | null;
  web_section?: string | null;
  confidence?: number | ConfidenceData | null;
  evidence: Evidence[];
  sources: Source[];
  claims?: Claim[];
  conflicts?: Conflict[];
  comparisonPairs?: ComparisonPair[];
  gaps?: string[];
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
