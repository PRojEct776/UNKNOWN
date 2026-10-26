import type { ChatMessage } from '../types/chat';
import type {
  BackendConceptGraphEdge,
  BackendConceptGraphNode,
  BackendConceptGraphResponse,
  BackendConceptSource,
} from './api';

/**
 * Builds the node/edge data for the Knowledge Orbit from a chat message.
 *
 * Integrity rules:
 * - Nodes come only from data the message actually carries (answer sources,
 *   comparison verdicts, overview key topics). Nothing is invented.
 * - Unknown pages are null, missing passages stay missing, no fake chunk ids.
 * - relevance/importance are never set (the backend does not measure them).
 * - No filler nodes: if there is nothing grounded, the graph is empty.
 * - The centre node has id "root" and is excluded from the orbiting set.
 */

/** Orbit-only extras on top of the backend node shape (not backend fields). */
export interface OrbitGraphNode extends BackendConceptGraphNode {
  url?: string;
  detail?: string;
}

const MAX_SOURCE_NODES = 12;
const MAX_COMPARISON_NODES = 6;
const MAX_OVERVIEW_TOPICS = 12;

interface RawSource {
  origin?: unknown;
  url?: unknown;
  title?: unknown;
  document?: unknown;
  documentName?: unknown;
  page?: unknown;
  chunkId?: unknown;
  chunk_id?: unknown;
  passage?: unknown;
  quote?: unknown;
  hybridScore?: unknown;
  hybrid_score?: unknown;
  venue?: unknown;
}

interface RawComparisonPair {
  sub_question?: unknown;
  label?: unknown;
  doc_quote?: unknown;
  web_quote?: unknown;
  doc_source?: unknown;
}

function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max - 3)}...` : text;
}

/** Trimmed string, or '' for non-strings and placeholder values. */
function cleanText(value: unknown): string {
  if (typeof value !== 'string') return '';
  const t = value.trim();
  return /^(n\/a|unknown|none|null)$/i.test(t) ? '' : t;
}

/** Real page number/label, or null when unknown. Never guessed. */
function cleanPage(value: unknown): number | string | null {
  if (typeof value === 'number') {
    return Number.isFinite(value) && value > 0 ? value : null;
  }
  const text = cleanText(value);
  if (!text) return null;
  const asNumber = Number(text);
  return Number.isFinite(asNumber) && asNumber > 0 ? asNumber : text;
}

function isExternal(s: RawSource): boolean {
  return s.origin === 'web' || s.origin === 'scholarly' || cleanText(s.url) !== '';
}

function finish(
  documentTitle: string,
  nodes: OrbitGraphNode[],
  edges: BackendConceptGraphEdge[],
): BackendConceptGraphResponse {
  // total_nodes counts orbiting nodes only (the centre node is not counted).
  const orbiting = Math.max(0, nodes.length - 1);
  return {
    document: documentTitle,
    nodes,
    edges,
    total_nodes: orbiting,
    total_edges: edges.length,
    status: orbiting > 0 ? 'ok' : 'empty',
    empty_reason: orbiting > 0 ? null : 'no_grounded_concepts',
    from_cache: false,
  };
}

export function buildOrbitGraphFromMessage(message: ChatMessage): BackendConceptGraphResponse {
  const nodes: OrbitGraphNode[] = [];
  const edges: BackendConceptGraphEdge[] = [];

  // =========================================================================
  // Case A: Document overview message (heuristic topics only)
  // =========================================================================
  if (message.sender === 'overview' && message.overview) {
    const ov = message.overview;
    const centerTitle = cleanText(ov.title) || cleanText(message.documentName) || 'Document';

    nodes.push({
      id: 'root',
      label: centerTitle,
      cluster: 'General',
      origin: 'document',
      sources: [],
    });

    const rawTopics = Array.isArray(ov.key_topics) ? ov.key_topics : [];
    const seen = new Set<string>();
    const topics: string[] = [];
    for (const t of rawTopics) {
      const label = cleanText(t);
      const key = label.toLowerCase();
      if (!label || seen.has(key)) continue;
      seen.add(key);
      topics.push(label);
    }

    topics.slice(0, MAX_OVERVIEW_TOPICS).forEach((label, idx) => {
      const id = `topic_${idx + 1}`;
      nodes.push({
        id,
        label: truncate(label, 40),
        cluster: 'Method',
        origin: 'overview_topic',
        sources: [],
        detail:
          'Listed as a key topic in the document overview. This is a heuristic topic list: no passage, page or chunk is attached to it.',
      });
      edges.push({
        source: 'root',
        target: id,
        relation: 'listed_topic',
        evidence_status: 'unverified',
        origin: 'overview_topic',
        sources: [],
      });
    });

    return finish(centerTitle, nodes, edges);
  }

  // =========================================================================
  // Case B: Answer message (question + only the sources the answer returned)
  // =========================================================================
  const res = message.result;
  const questionText = cleanText(message.text);
  const centerTitle = questionText ? truncate(questionText, 40) : 'Research question';

  nodes.push({
    id: 'root',
    label: centerTitle,
    cluster: 'General',
    origin: 'question',
    sources: [],
  });

  const rawSources = (res?.sources ?? []) as unknown as RawSource[];
  const ordered = [
    ...rawSources.filter((s) => !isExternal(s)),
    ...rawSources.filter((s) => isExternal(s)),
  ];

  ordered.slice(0, MAX_SOURCE_NODES).forEach((s, idx) => {
    const external = isExternal(s);
    const name =
      cleanText(s.documentName) || cleanText(s.document) || cleanText(s.title) || 'Unknown source';
    const page = cleanPage(s.page);
    const chunkId = cleanText(s.chunkId) || cleanText(s.chunk_id);
    const passage = cleanText(s.passage) || cleanText(s.quote);
    const score =
      typeof s.hybridScore === 'number'
        ? s.hybridScore
        : typeof s.hybrid_score === 'number'
        ? s.hybrid_score
        : null;
    const url = cleanText(s.url);
    const venue = cleanText(s.venue);
    const id = `${external ? 'web' : 'doc'}_src_${idx + 1}`;
    const location = page !== null ? ` (p.${page})` : chunkId ? ` [${chunkId}]` : '';

    const source: BackendConceptSource = {
      document: name,
      page,
      chunk_id: chunkId,
      passage: passage || undefined,
    };

    const detailParts: string[] = ['Retrieved for this question.'];
    if (score !== null) {
      detailParts.push(`Retrieval score ${score.toFixed(4)} (a ranking score, not a relevance percentage).`);
    }
    if (venue) detailParts.push(`Venue: ${venue}.`);

    nodes.push({
      id,
      label: truncate(`${external ? '[Web] ' : ''}${name}${location}`, 40),
      cluster: external ? 'Metric' : 'Architecture',
      origin: external ? 'web_source' : 'answer_source',
      sources: [source],
      detail: detailParts.join(' '),
      url: url || undefined,
    });

    edges.push({
      source: 'root',
      target: id,
      relation: 'retrieved_for',
      evidence_status: 'retrieved',
      origin: external ? 'web_source' : 'answer_source',
      sources: [source],
    });
  });

  // Cross-channel comparison verdicts (model output, labelled as such)
  const pairsRaw = (res as unknown as { comparisonPairs?: unknown } | undefined)?.comparisonPairs;
  const pairs = Array.isArray(pairsRaw) ? (pairsRaw as RawComparisonPair[]) : [];

  pairs.slice(0, MAX_COMPARISON_NODES).forEach((p, idx) => {
    const id = `comp_${idx + 1}`;
    const subQuestion = cleanText(p.sub_question) || `Comparison ${idx + 1}`;
    const verdict = p.label === 'agree' ? 'Agrees' : p.label === 'disagree' ? 'Disagrees' : 'Not addressed';
    const docQuote = cleanText(p.doc_quote);
    const webQuote = cleanText(p.web_quote);

    const passageParts: string[] = [];
    if (docQuote) passageParts.push(`Document: "${docQuote}"`);
    if (webQuote) passageParts.push(`Web: "${webQuote}"`);

    const sources: BackendConceptSource[] = passageParts.length
      ? [
          {
            document: cleanText(p.doc_source) || 'Document channel',
            page: null,
            chunk_id: '',
            passage: passageParts.join('\n'),
          },
        ]
      : [];

    nodes.push({
      id,
      label: truncate(`${verdict}: ${subQuestion}`, 40),
      cluster: 'Theory',
      origin: 'comparison',
      sources,
      detail:
        'Cross-channel verdict between the document and web results. It is model-generated and not independently verified.',
    });

    edges.push({
      source: 'root',
      target: id,
      relation: 'cross_channel_comparison',
      evidence_status: 'model_verdict',
      origin: 'comparison',
      sources: [],
    });
  });

  return finish(centerTitle, nodes, edges);
}
