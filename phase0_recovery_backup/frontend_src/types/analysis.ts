export type ClaimAssessment = 'supported' | 'contradicted' | 'uncertain';

export interface ClaimVerification {
  claim: string;
  assessment: ClaimAssessment;
  explanation: string;
  evidenceIds: string[];
  counterEvidenceIds: string[];
}

export interface ComparisonRow {
  criterion: string;
  leftValue: string;
  rightValue: string;
  evidenceIds: string[];
}

export interface ResearchGap {
  title: string;
  currentKnowledge: string;
  missingConnection: string;
  potentialGap: string;
  evidenceIds: string[];
}

export interface DebatePosition {
  id: string;
  title: string;
  claim: string;
  evidenceIds: string[];
}

export interface DebateResult {
  positions: DebatePosition[];
  conclusion: string;
}