/**
 * STATIC DEMO DATA — NOT REAL BACKEND OUTPUT
 *
 * This module supplies a typed `WorkspaceResult` factory used in two places:
 *
 *   1. As an optimistic placeholder while a real backend call is in-flight
 *      (answerState: 'loading').
 *   2. As a fallback labelled `origin: 'local-fallback'` when the backend is
 *      unreachable or returns an unexpected error.
 *   3. As a labelled `origin: 'static-demo'` fixture for legacy history items
 *      that were stored before the live API was available.
 *
 * Results produced here are NEVER presented as real backend output.
 * Any UI that renders a result from this module must display the appropriate
 * origin badge (static-demo or local-fallback).
 */

import type { ClaimVerification, ComparisonRow, DebateResult, ResearchGap } from '../types/analysis';
import type { ConceptResult } from '../types/concept';
import type { Evidence, Source } from '../types/evidence';
import type { KnowledgeDNA, MindMapNode } from '../types/knowledge';
import type { AnalysisMode, AnswerState, QueryRequest, ResultOrigin, WorkspaceResult } from '../types/query';
import type { ReasoningResult } from '../types/reasoning';

// ---------------------------------------------------------------------------
// Helper utilities
// ---------------------------------------------------------------------------

function uid(): string {
  return Math.random().toString(36).slice(2, 10);
}

function makeRequest(query: string, mode: AnalysisMode): QueryRequest {
  return {
    id: uid(),
    query,
    mode,
    submittedAt: new Date().toISOString(),
  };
}

// ---------------------------------------------------------------------------
// Static fixture data (clearly fictional placeholder content)
// ---------------------------------------------------------------------------

function makeStaticSources(): Source[] {
  return [
    {
      id: 'demo_src_1',
      documentName: '[Demo] sample_ieee.pdf',
      page: 1,
      chunkId: 'demo_chunk_001',
      evidenceCount: 1,
      rank: 1,
      score: 0.87,
    },
    {
      id: 'demo_src_2',
      documentName: '[Demo] sample_ieee.pdf',
      page: 3,
      chunkId: 'demo_chunk_002',
      evidenceCount: 1,
      rank: 2,
      score: 0.74,
    },
  ];
}

function makeStaticEvidence(): Evidence[] {
  return [
    {
      id: 'demo_ev_1',
      documentName: '[Demo] sample_ieee.pdf',
      page: 1,
      chunkId: 'demo_chunk_001',
      text: '[DEMO — not a real backend result] This placeholder passage stands in while the backend is offline or the query has not yet been submitted.',
      score: 0.87,
      relevance: 0.87,
    },
    {
      id: 'demo_ev_2',
      documentName: '[Demo] sample_ieee.pdf',
      page: 3,
      chunkId: 'demo_chunk_002',
      text: '[DEMO] A second placeholder evidence passage with lower relevance score, illustrating how multiple sources would be displayed.',
      score: 0.74,
      relevance: 0.74,
    },
  ];
}

function makeStaticConcept(query: string): ConceptResult {
  return {
    id: 'demo_concept',
    name: query.length > 40 ? query.slice(0, 40) + '…' : query,
    category: '[Demo] Research Topic',
    description:
      '[DEMO placeholder — connect the backend to see a real answer.] This concept card is generated locally and does not reflect retrieved document content.',
    usedIn: ['[Demo] Academic Research'],
    functions: ['[Demo] Placeholder'],
    relatedConcepts: ['[Demo] Backend Integration'],
    confidenceScore: 0,
    graphNodes: [
      { id: 'demo_node_1', label: query.slice(0, 30), isCentral: true, type: 'concept' },
    ],
    graphEdges: [],
  };
}

function makeStaticReasoning(query: string): ReasoningResult {
  return {
    originalQuestion: query,
    subQuestions: [
      {
        id: 'demo_sq_1',
        question: '[DEMO] Sub-question 1 placeholder',
        evidenceIds: ['demo_ev_1'],
        synthesis: '[DEMO] Sub-answer placeholder.',
      },
    ],
    evidence: makeStaticEvidence(),
    synthesis: '[DEMO placeholder — connect the backend to see a real reasoning trace.]',
    finalAnswer: '[DEMO] Reasoning answer placeholder.',
    steps: [
      { id: 'step_1', title: 'Query Decomposition', description: '[Demo]', status: 'complete' },
      { id: 'step_2', title: 'Retrieval', description: '[Demo]', status: 'upcoming' },
      { id: 'step_3', title: 'Synthesis', description: '[Demo]', status: 'upcoming' },
    ],
  };
}

function makeStaticVerification(query: string): ClaimVerification[] {
  return [
    {
      claim: query,
      assessment: 'uncertain',
      explanation:
        '[DEMO placeholder] Claim verification requires a live backend connection. Connect to the FastAPI server to get real verification results.',
      evidenceIds: ['demo_ev_1'],
      counterEvidenceIds: [],
    },
  ];
}

function makeStaticComparison(): ComparisonRow[] {
  return [
    {
      criterion: '[Demo] Methodology',
      leftValue: '[Demo] Approach A',
      rightValue: '[Demo] Approach B',
      evidenceIds: ['demo_ev_1'],
    },
    {
      criterion: '[Demo] Results',
      leftValue: '[Demo] Result A',
      rightValue: '[Demo] Result B',
      evidenceIds: ['demo_ev_2'],
    },
  ];
}

function makeStaticGap(query: string): ResearchGap {
  return {
    title: `[Demo] Research Gaps: ${query.slice(0, 50)}`,
    currentKnowledge:
      '[DEMO] Connect the backend to see real research gap analysis based on your indexed literature.',
    missingConnection:
      '[DEMO] Reported limitations from indexed papers would appear here.',
    potentialGap:
      '[DEMO] Emerging research directions identified by the gap finder would appear here.',
    evidenceIds: ['demo_ev_1'],
  };
}

function makeStaticDebate(): DebateResult {
  return {
    positions: [
      {
        id: 'pos_a',
        title: '[Demo] Position A',
        claim: '[DEMO] The first position in this debate is a placeholder.',
        evidenceIds: ['demo_ev_1'],
      },
      {
        id: 'pos_b',
        title: '[Demo] Position B',
        claim: '[DEMO] The opposing position is also a placeholder.',
        evidenceIds: ['demo_ev_2'],
      },
    ],
    conclusion: '[DEMO] Connect the backend to see real evidence-grounded debate conclusions.',
  };
}

function makeStaticMindMap(query: string): MindMapNode {
  return {
    id: 'root',
    label: query.slice(0, 50),
    description: '[DEMO placeholder — backend mind map would appear here.]',
    children: [
      { id: 'demo_child_1', label: '[Demo] Topic A', description: '[Demo placeholder]' },
      { id: 'demo_child_2', label: '[Demo] Topic B', description: '[Demo placeholder]' },
    ],
  };
}

function makeStaticKnowledgeDNA(): KnowledgeDNA {
  return {
    researchArea: '[DEMO] Research area placeholder',
    dominantTopics: [
      { label: '[Demo] Topic A', weight: 0.9 },
      { label: '[Demo] Topic B', weight: 0.7 },
    ],
    coreTopics: ['[Demo] Core topic 1', '[Demo] Core topic 2'],
    keyConcepts: ['[Demo] Concept A', '[Demo] Concept B'],
    methods: ['[Demo] Method 1'],
    findings: ['[Demo] Finding 1'],
    limitations: ['[Demo] Limitation 1'],
    researchThemes: ['[Demo] Theme A'],
    themes: ['[Demo] Theme A'],
    signals: [],
    relationships: [],
  };
}

// ---------------------------------------------------------------------------
// Public factory
// ---------------------------------------------------------------------------

/**
 * Build a fully-typed `WorkspaceResult` with placeholder data.
 *
 * @param query  - The user's query string.
 * @param mode   - The analysis mode.
 * @param state  - `'loading'` while a live request is in-flight; `'insufficient_evidence'`
 *                 for abstention demos; `'error'` for error states; defaults to `'answer'`
 *                 for history-migration purposes.
 *
 * The returned `origin` is always `'local-fallback'` so consumers can label it correctly.
 */
export function createMockWorkspaceResult(
  query: string,
  mode: AnalysisMode,
  state: AnswerState = 'answer',
): WorkspaceResult {
  const request = makeRequest(query, mode);
  const origin: ResultOrigin = 'local-fallback';
  const sources = state === 'loading' ? [] : makeStaticSources();
  const evidence = state === 'loading' ? [] : makeStaticEvidence();

  let answer: string;
  let detailedAnswer: string;

  if (state === 'loading') {
    answer = '';
    detailedAnswer = '';
  } else if (state === 'insufficient_evidence') {
    answer =
      '[DEMO — Abstention example] The indexed literature does not contain sufficient evidence to confidently answer this query. Please upload relevant papers or try a more specific question.';
    detailedAnswer = answer;
  } else if (state === 'error') {
    answer = '[Error] Query failed. Check that the backend is running on http://localhost:8000.';
    detailedAnswer = answer;
  } else {
    answer =
      '[DEMO — local fallback] This result was generated locally because the backend is offline or returned an unexpected response. Connect the FastAPI server to see real evidence-grounded answers.';
    detailedAnswer = answer;
  }

  return {
    request,
    answerState: state,
    origin,
    answer,
    detailedAnswer,
    confidence: state === 'answer' ? 0.0 : undefined,
    evidence,
    sources,
    concept: makeStaticConcept(query),
    reasoning: makeStaticReasoning(query),
    verification: makeStaticVerification(query),
    comparison: makeStaticComparison(),
    comparisonEntities: ['[Demo] Entity A', '[Demo] Entity B'],
    researchGap: makeStaticGap(query),
    debate: makeStaticDebate(),
    mindMap: makeStaticMindMap(query),
    knowledgeDNA: makeStaticKnowledgeDNA(),
    queryType: undefined,
    rawResponse: undefined,
  };
}
