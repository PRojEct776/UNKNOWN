import type { Evidence } from './evidence';

export interface ReasoningStep {
  id: string;
  title: string;
  description: string;
  status: 'complete' | 'current' | 'upcoming';
}

export interface SubQuestion {
  id: string;
  question: string;
  evidenceIds: string[];
  synthesis: string;
}

export interface ReasoningResult {
  originalQuestion: string;
  subQuestions: SubQuestion[];
  evidence: Evidence[];
  synthesis: string;
  finalAnswer: string;
  steps: ReasoningStep[];
}