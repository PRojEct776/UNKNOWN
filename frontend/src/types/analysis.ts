export type ClaimAssessment = 'supported' | 'contradicted' | 'uncertain';

export interface ClaimVerification {
  claim: string;
  assessment: ClaimAssessment;
  explanation: string;
  evidenceIds: string[];
  counterEvidenceIds: string[];
  verdict?: string;
  supportingQuotes?: string[];
  contradictingQuotes?: string[];
  partOfClaim?: boolean;
}

export interface ComparisonValueItem {
  entity: string;
  value: string;
  evidence?: string;
  document?: string;
  page?: number | string;
  chunkId?: string;
}

export interface ComparisonRow {
  criterion: string;
  leftValue: string;
  rightValue: string;
  evidenceIds: string[];
  values?: ComparisonValueItem[];
}

export interface ComparisonContradiction {
  topic: string;
  claimA: string;
  documentA: string;
  claimB: string;
  documentB: string;
  explanation: string;
  evidenceChunks: string[];
}

export interface ComparisonUniqueContribution {
  document: string;
  contribution: string;
  evidence: string;
  chunkId: string;
}

export interface ComparisonStrengthLimitation {
  document: string;
  strengths: string[];
  limitations: string[];
}

export interface ComprehensiveComparison {
  summary: string;
  similarities: string[];
  differences: string[];
  entities: string[];
  rows: ComparisonRow[];
  contradictions: ComparisonContradiction[];
  uniqueContributions: ComparisonUniqueContribution[];
  strengthsAndLimitations: ComparisonStrengthLimitation[];
  synthesis: string;
  partial?: boolean;
  notice?: string;
}

// =============================================================================
// RESEARCH GAPS TYPES
// =============================================================================

export type ResearchGapCategory =
  | 'TECHNICAL'
  | 'METHODOLOGICAL'
  | 'PERFORMANCE'
  | 'DATASET'
  | 'EVALUATION'
  | 'IMPLEMENTATION'
  | 'THEORETICAL'
  | 'APPLICATION';

export type ResearchGapNature = 'EXPLICIT' | 'DERIVED' | 'INFERRED' | 'POTENTIAL';

export type ResearchGapPriority = 'HIGH' | 'MEDIUM' | 'LOW';

export interface FutureResearchRecommendation {
  id: string;
  gapId?: string;
  title: string;
  researchQuestion: string;
  problemToInvestigate: string;
  suggestedApproach: string;
  expectedContribution: string;
  supportingEvidence: string[];
  isProposal: boolean;
}

export interface ResearchGapConflict {
  topic: string;
  paperA: string;
  findingA: string;
  paperB: string;
  findingB: string;
  explanation: string;
  evidenceChunks: string[];
}

export interface ResearchOpportunityMapNode {
  id: string;
  label: string;
  type: 'LIMITATION' | 'UNRESOLVED_PROBLEM' | 'CONCEPT' | 'OPPORTUNITY';
  category: string;
  document?: string;
}

export interface ResearchOpportunityMapLink {
  source: string;
  target: string;
  relationship: string;
  evidence?: string;
}

export interface ResearchOpportunityMap {
  nodes: ResearchOpportunityMapNode[];
  links: ResearchOpportunityMapLink[];
}

export interface ResearchGapOverview {
  totalGaps: number;
  highPriorityGaps: number;
  mediumPriorityGaps: number;
  lowPriorityGaps: number;
  explicitGaps: number;
  derivedGaps: number;
  potentialGaps: number;
  supportingPapersCount: number;
  categoriesCount: Record<string, number>;
}

export interface ResearchGapItem {
  id: string;
  gap: string;
  title: string;
  category: ResearchGapCategory;
  type: ResearchGapNature;
  priority: ResearchGapPriority;
  priorityReasoning: string;
  confidence: number;
  rationale: string;
  currentKnowledge: string;
  missingUnresolved: string;
  limitationEvidence: string;
  whyItMatters: string;
  potentialDirection: string;
  relevantMethods: string[];
  document: string;
  page?: number | string;
  chunkId?: string;
  evidence: string[];
  supportingPapers: string[];
  isShared: boolean;
}

export interface ResearchGapsReport {
  query: string;
  researchArea: string;
  existingFindings: string[];
  reportedLimitations: string[];
  gaps: ResearchGapItem[];
  overview: ResearchGapOverview;
  recommendations: FutureResearchRecommendation[];
  opportunityMap: ResearchOpportunityMap;
  conflicts: ResearchGapConflict[];
  multiDocInsights: {
    sharedGaps?: string[];
    uniqueLimitations?: Record<string, string[]>;
    recurringProblems?: string[];
    underexploredAreas?: string[];
  };
  sources: Array<{
    document?: string;
    page?: number | string;
    chunkId?: string;
    passage?: string;
  }>;
  partial?: boolean;
  notice?: string;
}

export interface ResearchGap {
  title: string;
  currentKnowledge: string;
  missingConnection: string;
  potentialGap: string;
  evidenceIds: string[];
  id?: string;
  category?: ResearchGapCategory;
  priority?: ResearchGapPriority;
  confidence?: number;
  supportingPapers?: string[];
}

export interface DebatePosition {
  id: string;
  title: string;
  claim: string;
  evidenceIds: string[];
}

export type DebateEvidenceType = 'DIRECT_EVIDENCE' | 'REASONABLE_INFERENCE' | 'UNSUPPORTED';
export type DebateEvidenceStrength = 'STRONG' | 'MODERATE' | 'WEAK' | 'NONE';

export interface DebateArgumentItem {
  id: string;
  side: 'POSITION_A' | 'POSITION_B' | 'PRO' | 'CON' | string;
  title: string;
  argument: string;
  evidenceType?: DebateEvidenceType | string;
  evidence?: string[];
  confidence?: number;
  evidenceStrength?: DebateEvidenceStrength | string;
  document?: string;
  page?: number | string;
  chunkId?: string;
}

export interface DebateRebuttalItem {
  id: string;
  side: 'POSITION_A' | 'POSITION_B' | 'PRO' | 'CON' | string;
  targetArgument: string;
  rebuttal: string;
  evidence?: string[];
  confidence?: number;
  document?: string;
  page?: number | string;
  chunkId?: string;
}

export interface DebateOpeningStatements {
  pro?: string;
  con?: string;
}

export interface DebateResult {
  query?: string;
  proposition?: string;
  topic?: string;
  positionA?: string;
  positionB?: string;
  openingStatements?: DebateOpeningStatements;
  arguments?: DebateArgumentItem[];
  rebuttals?: DebateRebuttalItem[];
  agreements?: string[];
  disagreements?: string[];
  unresolvedQuestions?: string[];
  neutralAssessment?: string;
  conclusion: string;
  positions: DebatePosition[];
  sources?: Array<{
    document?: string;
    page?: number | string;
    chunkId?: string;
    text?: string;
  }>;
  partial?: boolean;
  notice?: string;
  confidence?: number;
}
