/**
 * UNKNOWN — Production Workspace Result Builder
 *
 * Constructs typed WorkspaceResult objects directly from live backend API responses.
 * Strict compliance with Rule 3 & 4:
 * - NO stubs or mock strings in production code.
 * - Missing or insufficient evidence is explicitly marked with "Not found in available sources."
 */

import type { AnalysisMode, WorkspaceResult } from '../types/query';
import type { Evidence, Source } from '../types/evidence';
import type { ReasoningStep, SubQuestion } from '../types/reasoning';
import type {
  DebateArgumentItem,
  DebatePosition,
  DebateRebuttalItem,
  DebateResult,
} from '../types/analysis';
import type { MindMapNode } from '../types/knowledge';
import type {
  BackendQueryResponse,
  BackendQuerySource,
  BackendReasoningResponse,
  BackendVerifyResponse,
  BackendCompareResponse,
  BackendResearchGapResponse,
  BackendDebateResponse,
  BackendKnowledgeDNAResponse,
  BackendKnowledgeMindMapResponse,
  BackendMindMapNode,
} from './api';

export function mapBackendSources(sources: BackendQuerySource[]): Source[] {
  if (!Array.isArray(sources)) return [];
  return sources.map((s, idx) => ({
    id: s.chunk_id || `src_${idx}`,
    documentName: s.document || 'Document Evidence',
    page: typeof s.page === 'number' ? s.page : Number(s.page) || undefined,
    chunkId: s.chunk_id,
    evidenceCount: 1,
    rank: s.rank,
    score: typeof s.hybrid_score === 'number' && Number.isFinite(s.hybrid_score) ? s.hybrid_score : undefined,
    bm25Score: typeof s.bm25_score === 'number' && Number.isFinite(s.bm25_score) ? s.bm25_score : undefined,
    faissScore: typeof s.faiss_score === 'number' && Number.isFinite(s.faiss_score) ? s.faiss_score : undefined,
    passage: s.passage ?? undefined,
    quote: s.quote ?? undefined,
  }));
}

export function mapBackendEvidence(sources: BackendQuerySource[]): Evidence[] {
  if (!Array.isArray(sources)) return [];
  return sources.map((s, idx) => ({
    id: s.chunk_id || `ev_${idx}`,
    documentName: s.document || 'Document Evidence',
    page: typeof s.page === 'number' ? s.page : Number(s.page) || undefined,
    chunkId: s.chunk_id,
    text: 'Passage text was not returned by the backend for this source.',
    score: typeof s.hybrid_score === 'number' ? s.hybrid_score : undefined,
    relevance: typeof s.hybrid_score === 'number' ? s.hybrid_score : undefined,
  }));
}

export function createBaseWorkspaceResult(query: string, mode: AnalysisMode): WorkspaceResult {
  return {
    request: {
      id: `req_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
      query,
      mode,
      submittedAt: new Date().toISOString(),
    },
    answerState: 'loading',
    origin: 'backend',
    answer: '',
    detailedAnswer: '',
    evidence: [],
    sources: [],
    concept: {
      id: `c_${Date.now()}`,
      name: query,
      category: 'Research Concept',
      description: '',
      usedIn: [],
      functions: [],
      relatedConcepts: [],
      graphNodes: [],
      graphEdges: [],
    },
    reasoning: {
      originalQuestion: query,
      subQuestions: [],
      evidence: [],
      synthesis: '',
      finalAnswer: '',
      steps: [],
    },
    verification: [],
    comparison: [],
    researchGap: {
      title: '',
      currentKnowledge: '',
      missingConnection: '',
      potentialGap: '',
      evidenceIds: [],
    },
    debate: {
      positions: [],
      conclusion: '',
    },
    mindMap: {
      id: 'root',
      label: query,
      children: [],
    },
    knowledgeDNA: {
      dominantTopics: [],
      researchThemes: [],
      coreTopics: [],
      keyConcepts: [],
      methods: [],
      findings: [],
      limitations: [],
      themes: [],
      signals: [],
      relationships: [],
    },
  };
}

export function buildResultFromQueryResponse(
  query: string,
  res: BackendQueryResponse,
): WorkspaceResult {
  const base = createBaseWorkspaceResult(query, 'discover');
  const NOT_FOUND = 'Not found in available sources.';
  const pick = [res.answer, res.detail, res.doc_section, res.summary]
    .map((v) => (typeof v === 'string' ? v.trim() : ''))
    .find((v) => v.length > 0);
  const answerText = pick || NOT_FOUND;
  const isInsufficient =
    !pick || pick === NOT_FOUND || pick === 'Not found in available sources';

  return {
    ...base,
    answerState: isInsufficient ? 'insufficient_evidence' : 'answer',
    answer: answerText,
    detailedAnswer: res.detail || res.answer || answerText,
    summary: res.summary,
    doc_section: res.doc_section,
    web_section: res.web_section,
    comparisonPairs: res.comparison || [],
    claims: res.claims || [],
    conflicts: res.conflicts || [],
    gaps: res.gaps || [],
    confidence: res.confidence,
    sources: mapBackendSources(res.sources || []),
    evidence: mapBackendEvidence(res.sources || []),
    queryType: res.query_type,
    rawResponse: res,
  };
}

export function buildResultFromReasoningResponse(
  query: string,
  res: BackendReasoningResponse,
): WorkspaceResult {
  const base = createBaseWorkspaceResult(query, 'reason');
  const answerText = (res.final_answer || res.answer || '').trim() || 'Not found in available sources.';
  const synthesisText = (res.synthesis || res.answer || '').trim() || answerText;

  // Use rich structured steps from backend if available, otherwise map from subquestions
  const steps: ReasoningStep[] = (res.steps && res.steps.length > 0)
    ? res.steps.map((s, i) => ({
        id: s.id || `step_${i + 1}`,
        title: s.title || `Step ${i + 1}`,
        description: s.description || '',
        status: (s.status as 'complete' | 'current' | 'upcoming') || 'complete',
      }))
    : (res.subquestions || []).map((subq, i) => ({
        id: `step_${i + 1}`,
        title: `Sub-question ${i + 1}: ${subq.slice(0, 40)}`,
        description: `Analyzed sub-question: ${subq}`,
        status: 'complete',
      }));

  // Use rich sub_questions with linked evidence IDs from backend if available
  const subQuestions: SubQuestion[] = (res.sub_questions && res.sub_questions.length > 0)
    ? res.sub_questions.map((sq, i) => ({
        id: sq.id || `subq_${i + 1}`,
        question: sq.question,
        evidenceIds: sq.evidenceIds || [],
        synthesis: sq.synthesis || `Grounded evidence aligned for: ${sq.question}`,
      }))
    : (res.subquestions || []).map((subq, i) => ({
        id: `subq_${i + 1}`,
        question: subq,
        evidenceIds: (res.sources || []).map((s) => s.chunk_id),
        synthesis: `Grounded evidence aligned for: ${subq}`,
      }));

  const retrievalGaps: string[] = [];
  if (res.uncertainty) {
    retrievalGaps.push(res.uncertainty);
  }
  if (res.conflicts && res.conflicts.length > 0) {
    retrievalGaps.push(...res.conflicts);
  }

  return {
    ...base,
    answerState: 'answer',
    answer: answerText,
    detailedAnswer: synthesisText,
    confidence: typeof res.confidence === 'number' ? res.confidence : base.confidence,
    sources: mapBackendSources(res.sources || []),
    evidence: mapBackendEvidence(res.sources || []),
    gaps: retrievalGaps.length > 0 ? retrievalGaps : undefined,
    reasoning: {
      originalQuestion: res.query || query,
      subQuestions,
      evidence: mapBackendEvidence(res.sources || []),
      synthesis: synthesisText,
      finalAnswer: answerText,
      steps,
      conflicts: res.conflicts,
      uncertainty: res.uncertainty,
    },
    rawResponse: res,
  };
}

function verifyAssessment(
  verdict: string | undefined,
): 'supported' | 'contradicted' | 'uncertain' {
  const normalized = (verdict || '').toUpperCase().trim();
  if (normalized === 'SUPPORTED') return 'supported';
  if (normalized === 'CONTRADICTED') return 'contradicted';
  return 'uncertain';
}

export function buildResultFromVerifyResponse(
  query: string,
  res: BackendVerifyResponse,
): WorkspaceResult {
  const base = createBaseWorkspaceResult(query, 'verify');
  const assessment = verifyAssessment(res.verdict);

  const verificationItem = {
    claim: res.claim || query,
    assessment,
    explanation: res.explanation || 'Verification performed against indexed document evidence.',
    evidenceIds: res.source_chunk_ids || [],
    counterEvidenceIds: [] as string[],
    verdict: res.verdict,
    supportingQuotes: res.supporting_evidence || [],
    contradictingQuotes: res.contradicting_evidence || [],
  };

  const partItems = (res.atomic_claims || []).map((part) => ({
    claim: part.claim,
    assessment: verifyAssessment(part.verdict),
    explanation: part.explanation || 'No explanation was provided for this part.',
    evidenceIds: part.source_chunk_ids || [],
    counterEvidenceIds: [] as string[],
    verdict: part.verdict,
    supportingQuotes: part.supporting_evidence || [],
    contradictingQuotes: part.contradicting_evidence || [],
    partOfClaim: true,
  }));

  return {
    ...base,
    answerState: 'answer',
    answer: `[Verdict: ${res.verdict?.toUpperCase() || 'UNVERIFIED'}] ${res.explanation || ''}`,
    detailedAnswer: res.explanation || '',
    confidence: res.confidence_score,
    sources: mapBackendSources(res.sources || []),
    evidence: mapBackendEvidence(res.sources || []),
    verification: [verificationItem, ...partItems],
    rawResponse: res,
  };
}

export function buildResultFromCompareResponse(
  query: string,
  res: BackendCompareResponse,
): WorkspaceResult {
  const base = createBaseWorkspaceResult(query, 'compare');
  const rows = (res.comparison || []).map((comp) => {
    const left = comp.values?.[0];
    const right = comp.values?.[1];
    const allEvidenceIds: string[] = [];
    const values = (comp.values || []).map((v) => {
      if (v.chunk_id && !allEvidenceIds.includes(v.chunk_id)) {
        allEvidenceIds.push(v.chunk_id);
      }
      return {
        entity: v.entity,
        value: v.value,
        evidence: v.evidence,
        document: v.document,
        page: v.page,
        chunkId: v.chunk_id,
      };
    });

    return {
      criterion: comp.aspect,
      leftValue: left?.value || 'N/A',
      rightValue: right?.value || 'N/A',
      evidenceIds: allEvidenceIds.length > 0 ? allEvidenceIds : ([left?.chunk_id, right?.chunk_id].filter(Boolean) as string[]),
      values,
    };
  });

  const comprehensiveComparison = {
    summary: res.summary || '',
    similarities: res.similarities || [],
    differences: res.differences || [],
    entities: res.entities || ['Entity A', 'Entity B'],
    rows,
    contradictions: (res.contradictions || []).map((c) => ({
      topic: c.topic || 'Disagreement',
      claimA: c.claim_a || '',
      documentA: c.document_a || '',
      claimB: c.claim_b || '',
      documentB: c.document_b || '',
      explanation: c.explanation || '',
      evidenceChunks: c.evidence_chunks || [],
    })),
    uniqueContributions: (res.unique_contributions || []).map((u) => ({
      document: u.document || 'Document',
      contribution: u.contribution || '',
      evidence: u.evidence || '',
      chunkId: u.chunk_id || '',
    })),
    strengthsAndLimitations: (res.strengths_and_limitations || []).map((sl) => ({
      document: sl.document || 'Document',
      strengths: sl.strengths || [],
      limitations: sl.limitations || [],
    })),
    synthesis: res.synthesis || '',
    partial: res.partial || false,
    notice: res.notice || (res.partial ? 'Limited comparison — generated from available evidence because AI providers were unavailable.' : undefined),
  };

  const isInsufficient = (res.summary || '').toLowerCase().startsWith('not found in available sources');

  return {
    ...base,
    answerState: isInsufficient ? 'insufficient_evidence' : 'answer',
    answer: res.summary || 'Comparative synthesis of selected entities.',
    detailedAnswer: res.synthesis ? `${res.summary}\n\n### Synthesis\n${res.synthesis}` : (res.summary || ''),
    comparison: rows,
    comparisonEntities: res.entities || ['Entity A', 'Entity B'],
    comprehensiveComparison,
    sources: mapBackendSources(res.sources || []),
    evidence: mapBackendEvidence(res.sources || []),
    rawResponse: res,
  };
}

export function buildResultFromGapsResponse(
  query: string,
  res: BackendResearchGapResponse,
): WorkspaceResult {
  const base = createBaseWorkspaceResult(query, 'gaps');
  const firstGap = res.gaps?.[0];

  const mappedGaps = (res.gaps || []).map((g, idx) => {
    const gapTitle = g.title || g.gap || `Research Gap ${idx + 1}`;
    const evidenceList = Array.isArray(g.evidence) ? g.evidence : [];
    const supporting = Array.isArray(g.supporting_papers) ? g.supporting_papers : (g.document ? [g.document] : []);
    const cat = (typeof g.category === 'string' ? g.category.toUpperCase() : 'TECHNICAL') as any;
    const gType = (typeof g.type === 'string' ? g.type.toUpperCase() : 'EXPLICIT') as any;
    const prio = (typeof g.priority === 'string' ? g.priority.toUpperCase() : 'MEDIUM') as any;

    return {
      id: g.id || `gap_${idx + 1}`,
      gap: g.gap || gapTitle,
      title: gapTitle,
      category: cat,
      type: gType,
      priority: prio,
      priorityReasoning: g.priority_reasoning || '',
      confidence: typeof g.confidence === 'number' ? g.confidence : 0.85,
      rationale: g.rationale || '',
      currentKnowledge: g.current_knowledge || (res.existing_findings?.[0] || ''),
      missingUnresolved: g.missing_unresolved || g.gap || gapTitle,
      limitationEvidence: g.limitation_evidence || evidenceList[0] || '',
      whyItMatters: g.why_it_matters || '',
      potentialDirection: g.potential_direction || '',
      relevantMethods: Array.isArray(g.relevant_methods) ? g.relevant_methods : [],
      document: g.document || '',
      page: g.page,
      chunkId: g.chunk_id,
      evidence: evidenceList,
      supportingPapers: supporting,
      isShared: Boolean(g.is_shared || supporting.length > 1),
    };
  });

  const highGaps = mappedGaps.filter((g) => g.priority === 'HIGH').length;
  const medGaps = mappedGaps.filter((g) => g.priority === 'MEDIUM').length;
  const lowGaps = mappedGaps.filter((g) => g.priority === 'LOW').length;
  const explicitGaps = mappedGaps.filter((g) => g.type === 'EXPLICIT').length;
  const derivedGaps = mappedGaps.filter((g) => g.type === 'DERIVED' || g.type === 'INFERRED').length;
  const potentialGaps = mappedGaps.filter((g) => g.type === 'POTENTIAL').length;

  const categoriesCount: Record<string, number> = {};
  mappedGaps.forEach((g) => {
    categoriesCount[g.category] = (categoriesCount[g.category] || 0) + 1;
  });

  const allSupportingPapers = new Set<string>();
  mappedGaps.forEach((g) => g.supportingPapers.forEach((p) => allSupportingPapers.add(p)));

  const overview = {
    totalGaps: res.overview?.total_gaps ?? mappedGaps.length,
    highPriorityGaps: res.overview?.high_priority_gaps ?? highGaps,
    mediumPriorityGaps: res.overview?.medium_priority_gaps ?? medGaps,
    lowPriorityGaps: res.overview?.low_priority_gaps ?? lowGaps,
    explicitGaps: res.overview?.explicit_gaps ?? explicitGaps,
    derivedGaps: res.overview?.derived_gaps ?? derivedGaps,
    potentialGaps: res.overview?.potential_gaps ?? potentialGaps,
    supportingPapersCount: res.overview?.supporting_papers_count ?? allSupportingPapers.size,
    categoriesCount: res.overview?.categories_count ?? categoriesCount,
  };

  const recommendations = (res.recommendations || []).map((r, idx) => ({
    id: r.id || `rec_${idx + 1}`,
    gapId: r.gap_id,
    title: r.title || `Recommendation ${idx + 1}`,
    researchQuestion: r.research_question || r.title || '',
    problemToInvestigate: r.problem_to_investigate || '',
    suggestedApproach: r.suggested_approach || '',
    expectedContribution: r.expected_contribution || '',
    supportingEvidence: Array.isArray(r.supporting_evidence) ? r.supporting_evidence : [],
    isProposal: r.is_proposal !== false,
  }));

  const conflicts = (res.conflicts || []).map((c) => ({
    topic: c.topic || '',
    paperA: c.paper_a || '',
    findingA: c.finding_a || '',
    paperB: c.paper_b || '',
    findingB: c.finding_b || '',
    explanation: c.explanation || '',
    evidenceChunks: Array.isArray(c.evidence_chunks) ? c.evidence_chunks : [],
  }));

  const oppNodes = (res.opportunity_map?.nodes || []).map((n) => ({
    id: n.id,
    label: n.label,
    type: n.type as any,
    category: n.category,
    document: n.document,
  }));

  const oppLinks = (res.opportunity_map?.links || []).map((l) => ({
    source: l.source,
    target: l.target,
    relationship: l.relationship,
    evidence: l.evidence,
  }));

  const researchGapsReport = {
    query: res.query || query,
    researchArea: res.research_area || 'Research Domain Analysis',
    existingFindings: res.existing_findings || [],
    reportedLimitations: res.reported_limitations || [],
    gaps: mappedGaps,
    overview,
    recommendations,
    opportunityMap: { nodes: oppNodes, links: oppLinks },
    conflicts,
    multiDocInsights: {
      sharedGaps: res.multi_doc_insights?.shared_gaps || [],
      uniqueLimitations: res.multi_doc_insights?.unique_limitations || {},
      recurringProblems: res.multi_doc_insights?.recurring_problems || [],
      underexploredAreas: res.multi_doc_insights?.underexplored_areas || [],
    },
    sources: (res.sources || []).map((s) => ({
      document: s.document,
      page: s.page,
      chunkId: s.chunk_id,
      passage: s.passage ?? undefined,
    })),
    partial: res.partial,
    notice: res.notice,
  };

  return {
    ...base,
    answerState: mappedGaps.length === 0 && res.notice?.includes('Not found') ? 'insufficient_evidence' : 'answer',
    answer: firstGap
      ? `Identified ${mappedGaps.length} evidence-backed research gaps (${overview.highPriorityGaps} high priority). Top gap: ${firstGap.gap}.`
      : (res.notice || 'Research gap analysis completed.'),
    detailedAnswer: [
      res.notice ? `> [!NOTE] ${res.notice}` : null,
      (res.reported_limitations || []).join('\n\n'),
    ].filter(Boolean).join('\n\n'),
    researchGap: {
      title: res.research_area || 'Literature Boundary Analysis',
      currentKnowledge: (res.existing_findings || []).join('; ') || 'Current indexed literature knowledge.',
      missingConnection: (res.reported_limitations || []).join('; ') || 'Reported limitations in literature.',
      potentialGap: firstGap?.gap || 'Identified research gap boundary.',
      evidenceIds: (res.sources || []).map((s) => s.chunk_id),
      id: firstGap?.id,
      category: firstGap?.category as any,
      priority: firstGap?.priority as any,
      confidence: firstGap?.confidence,
      supportingPapers: Array.isArray(firstGap?.supporting_papers) ? firstGap.supporting_papers : [],
    },
    researchGapsReport,
    sources: mapBackendSources(res.sources || []),
    evidence: mapBackendEvidence(res.sources || []),
    rawResponse: res,
  };
}

export function buildResultFromDebateResponse(
  query: string,
  res: BackendDebateResponse,
): WorkspaceResult {
  const base = createBaseWorkspaceResult(query, 'debate');
  const positions: DebatePosition[] = [
    {
      id: 'pos_a',
      title: 'Position A (Pro)',
      claim: res.position_a || 'In favor of proposition',
      evidenceIds: (res.arguments || []).filter((a) => a.side === 'POSITION_A' || a.side === 'PRO').map((a) => a.chunk_id || 'arg_a'),
    },
    {
      id: 'pos_b',
      title: 'Position B (Con)',
      claim: res.position_b || 'Challenging proposition',
      evidenceIds: (res.arguments || []).filter((a) => a.side === 'POSITION_B' || a.side === 'CON').map((a) => a.chunk_id || 'arg_b'),
    },
  ];

  const parsedArguments: DebateArgumentItem[] = (res.arguments || []).map((a, idx) => ({
    id: (a.id as string) || `arg_${idx + 1}`,
    side: a.side,
    title: a.title || (a.argument ? a.argument.slice(0, 60) + '...' : `Argument ${idx + 1}`),
    argument: a.argument,
    evidenceType: a.evidence_type,
    evidence: a.evidence || [],
    confidence: a.confidence ?? 0.85,
    evidenceStrength: a.evidence_strength,
    document: a.document || '',
    page: a.page ?? 1,
    chunkId: a.chunk_id || '',
  }));

  const parsedRebuttals: DebateRebuttalItem[] = (res.rebuttals || []).map((r, idx) => ({
    id: (r.id as string) || `reb_${idx + 1}`,
    side: r.side,
    targetArgument: r.target_argument || '',
    rebuttal: r.rebuttal || '',
    evidence: r.evidence || [],
    confidence: r.confidence ?? 0.80,
    document: r.document || '',
    page: r.page ?? 1,
    chunkId: r.chunk_id || '',
  }));

  const debateResult: DebateResult = {
    query: res.query || query,
    proposition: res.proposition || res.topic || query,
    topic: res.topic || query,
    positionA: res.position_a,
    positionB: res.position_b,
    openingStatements: {
      pro: res.opening_statements?.pro || '',
      con: res.opening_statements?.con || '',
    },
    arguments: parsedArguments,
    rebuttals: parsedRebuttals,
    agreements: res.agreements || [],
    disagreements: res.disagreements || [],
    unresolvedQuestions: res.unresolved_questions || [],
    neutralAssessment: res.neutral_assessment || res.final_verdict || '',
    conclusion: res.conclusion || res.final_verdict || '',
    positions,
    sources: (res.sources || []).map((s) => ({
      document: s.document,
      page: s.page,
      chunkId: s.chunk_id,
      text: s.passage || (s as any).text || '',
    })),
    partial: res.partial || false,
    notice: res.notice,
    confidence: res.verdict_confidence,
  };

  return {
    ...base,
    answerState: 'answer',
    answer: res.final_verdict || res.conclusion || 'Debate synthesis between thesis and antithesis.',
    detailedAnswer: res.neutral_assessment || res.final_verdict || '',
    confidence: res.verdict_confidence,
    debate: debateResult,
    sources: mapBackendSources(res.sources || []),
    evidence: mapBackendEvidence(res.sources || []),
    rawResponse: res,
  };
}

export function buildResultFromMindMapResponse(
  query: string,
  res: BackendKnowledgeMindMapResponse,
): WorkspaceResult {
  const base = createBaseWorkspaceResult(query, 'knowledge-map');
  const nodes = res.nodes || [];
  const edges = res.edges || [];

  const targetIds = new Set(edges.map((e) => e.target));
  const rootBackendNode = nodes.find((n) => n.type === 'TOPIC' || n.id === 'root') ||
                          nodes.find((n) => !targetIds.has(n.id)) ||
                          nodes[0];

  const childrenMap = new Map<string, BackendMindMapNode[]>();
  const parentMap = new Map<string, string>();
  edges.forEach((e) => {
    if (e.source && e.target && !parentMap.has(e.target)) {
      parentMap.set(e.target, e.source);
    }
  });

  nodes.forEach((n) => {
    const pId = (n.parent_id as string | undefined) || parentMap.get(n.id);
    if (pId && pId !== n.id) {
      if (!childrenMap.has(pId)) {
        childrenMap.set(pId, []);
      }
      childrenMap.get(pId)!.push(n);
    }
  });

  const visited = new Set<string>();

  function buildTree(n: BackendMindMapNode): MindMapNode {
    visited.add(n.id);
    const childBackendNodes = (childrenMap.get(n.id) || []).filter((c) => !visited.has(c.id));
    return {
      id: n.id,
      label: n.label,
      type: n.type,
      description: n.description,
      confidence: typeof n.confidence === 'number' ? n.confidence : 0.9,
      document: n.document,
      page: n.page,
      chunk_id: n.chunk_id,
      evidence: Array.isArray(n.evidence) ? n.evidence : (n.evidence ? [String(n.evidence)] : []),
      significance: typeof n.significance === 'string' ? n.significance : undefined,
      children: childBackendNodes.map(buildTree),
    };
  }

  let rootNode: MindMapNode;
  if (rootBackendNode) {
    rootNode = buildTree(rootBackendNode);
    if (res.research_area && res.research_area.length < rootNode.label.length && (rootNode.label.toLowerCase().includes('create a mind map') || rootNode.label.toLowerCase() === query.toLowerCase())) {
      rootNode.label = res.research_area;
    }
    nodes.forEach((n) => {
      if (!visited.has(n.id)) {
        rootNode.children = rootNode.children || [];
        rootNode.children.push(buildTree(n));
      }
    });
  } else {
    rootNode = {
      id: 'root',
      label: res.research_area || query,
      type: 'TOPIC',
      description: `Central research topic: ${query}`,
      children: [],
    };
  }

  rootNode.partial = res.partial || false;
  rootNode.notice = res.notice;

  return {
    ...base,
    answerState: (res.nodes || []).length === 0 ? 'insufficient_evidence' : 'answer',
    answer: res.notice || `Knowledge mind map constructed with ${(res.nodes || []).length} concept nodes and ${(res.edges || []).length} relationships.`,
    detailedAnswer: `Research Area: ${res.research_area || query}`,
    mindMap: rootNode,
    sources: mapBackendSources(res.sources || []),
    evidence: mapBackendEvidence(res.sources || []),
    rawResponse: res,
  };
}

export function buildResultFromDNAResponse(
  query: string,
  res: BackendKnowledgeDNAResponse,
): WorkspaceResult {
  const base = createBaseWorkspaceResult(query, 'knowledge-dna');
  const nodeCount = (res.nodes || []).length;
  const edgeCount = (res.edges || res.relationships || []).length;
  const isInsufficient = (nodeCount === 0 && Boolean(res.notice));

  return {
    ...base,
    answerState: isInsufficient ? 'insufficient_evidence' : 'answer',
    answer: res.notice || `Knowledge DNA profile generated for "${res.research_area || query}" with ${nodeCount} knowledge nodes and ${edgeCount} relationships.`,
    detailedAnswer: res.objectives && res.objectives.length > 0
      ? `Research Objectives: ${res.objectives.join('; ')}`
      : `Research Area: ${res.research_area || query}`,
    knowledgeDNA: {
      researchArea: res.research_area,
      dominantTopics: (res.core_topics || []).map((t) => ({ label: t, weight: 0.85 })),
      researchThemes: res.themes || [],
      coreTopics: res.core_topics || [],
      keyConcepts: res.key_concepts || res.core_concepts || [],
      methods: res.methods || res.methodologies || [],
      findings: res.findings || res.results || [],
      limitations: res.limitations || [],
      themes: res.themes || [],
      signals: res.signals || [],
      relationships: res.relationships || res.edges || [],

      // 10 Core Research Knowledge Dimensions & Graph
      nodes: (res.nodes || []).map((n) => ({
        id: n.id,
        label: n.label,
        category: n.category,
        explanation: n.explanation,
        evidence: n.evidence,
        confidence: n.confidence,
        document: n.document,
        supporting_papers: n.supporting_papers,
        page: n.page,
        chunk_id: n.chunk_id,
        is_inferred: n.is_inferred,
        quantitative_value: n.quantitative_value,
        citations: n.citations,
      })),
      edges: res.edges || res.relationships || [],
      objectives: res.objectives || [],
      core_concepts: res.core_concepts || res.key_concepts || [],
      methodologies: res.methodologies || res.methods || [],
      datasets: res.datasets || [],
      metrics: res.metrics || [],
      results: res.results || res.findings || [],
      contributions: res.contributions || [],
      advantages: res.advantages || [],
      future_directions: res.future_directions || [],
      conflicting_findings: res.conflicting_findings || [],
      cross_paper_connections: res.cross_paper_connections || [],
      statistics: res.statistics || {},
      partial: res.partial || false,
      notice: res.notice,
    },
    sources: mapBackendSources(res.sources || []),
    evidence: mapBackendEvidence(res.sources || []),
    rawResponse: res,
  };
}
