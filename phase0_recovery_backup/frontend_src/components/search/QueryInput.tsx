import React from 'react';
import { ArrowRight, Loader2 } from 'lucide-react';
import type { AnalysisMode } from '../../types/query';

interface QueryInputProps {
  query: string;
  mode: AnalysisMode;
  isLoading: boolean;
  loadingLabel: string;
  selectedDocuments?: string[];
  onQueryChange: (query: string) => void;
  onSubmit: () => void;
  onShowAbstention: () => void;
}

function getContextAwareExamples(mode: AnalysisMode, docs: string[] = []): string[] {
  const docNames = docs.map((d) => d.toLowerCase());
  const hasDna = docNames.some((d) => d.includes('dna') || d.includes('microbial') || d.includes('ieee'));
  const hasEmotion = docNames.some((d) => d.includes('emotion') || d.includes('transformer') || d.includes('roberta'));
  const hasAnn = docNames.some((d) => d.includes('nearest') || d.includes('neighbor') || d.includes('dimensional') || d.includes('scalable'));

  if (hasDna && hasAnn) {
    if (mode === 'compare') {
      return [
        'Compare information storage density in microbial DNA vs electronic vector memory',
        'Compare algorithmic indexing complexity in vector retrieval with biochemical addressing in DNA',
      ];
    }
  }

  if (hasDna) {
    switch (mode) {
      case 'discover':
        return [
          'What is the storage density and half-life of microbial DNA in Deinococcus radiodurans?',
          'How does in vivo DNA error-correction differ from in vitro synthetic storage?',
        ];
      case 'reason':
        return [
          'Why does bacterial replication introduce mutational drift in synthetic DNA encodings?',
          'How do radiation-resistant organisms protect high-density digital archives across centuries?',
        ];
      case 'verify':
        return [
          'Deinococcus radiodurans can withstand 5,000 Gy of ionizing radiation without viability loss.',
          'Microbial DNA achieves higher volumetric data density than modern magnetic tape.',
        ];
      case 'compare':
        return [
          'Compare in vivo living plasmid DNA storage versus in vitro synthetic oligo pools',
          'Compare Reed-Solomon versus Fountain codes for biological DNA error correction',
        ];
      case 'gaps':
        return [
          'Research gaps in biological mutation rates and DNA synthesis cost barriers',
          'What are the unaddressed security and bio-containment risks of bacterial data storage?',
        ];
      case 'debate':
        return [
          'Is living microbial DNA storage economically superior to cryogenic tape archiving?',
          'Should synthetic data payload genes be engineered with metabolic kill-switches?',
        ];
      case 'knowledge-map':
        return [
          'Microbial DNA digital data storage architecture and biochemical mechanisms',
          'In vivo data encoding, preservation, and retrieval workflow topology',
        ];
      case 'knowledge-dna':
        return [
          'Extract the Knowledge DNA of microbial DNA information storage',
          'Synthesize core topics, synthesis methods, findings, and stability limitations of biological storage',
        ];
    }
  }

  if (hasEmotion) {
    switch (mode) {
      case 'discover':
        return [
          'What is the accuracy and inference latency of the multimodal ViT and RoBERTa model?',
          'How are visual and linguistic representations aligned in real-time emotion recognition?',
        ];
      case 'reason':
        return [
          'Why does early cross-attention fusion outperform late feature concatenation for affective computing?',
          'How does model quantization reduce transformer latency on edge deployment hardware?',
        ];
      case 'verify':
        return [
          'The RoBERTa-based multimodal model operates under 45ms per frame on edge hardware.',
          'Vision Transformer feature maps capture subtle facial action units better than ResNet.',
        ];
      case 'compare':
        return [
          'Compare unimodal facial emotion recognition against multimodal audio-visual-text fusion',
          'Compare Vision Transformer (ViT) and CNN backbones for real-time video frames',
        ];
      case 'gaps':
        return [
          'Limitations in cross-cultural affective transfer and noisy lighting conditions',
          'What research gaps remain in real-time edge quantization for multimodal transformers?',
        ];
      case 'debate':
        return [
          'Should real-time emotion recognition rely exclusively on open-source edge hardware?',
          'Is facial expression alone sufficient for automated sentiment classification in clinical settings?',
        ];
      case 'knowledge-map':
        return [
          'Multimodal emotion recognition pipeline: ViT, RoBERTa, and fusion layers',
          'Real-time edge affective computing system architecture',
        ];
      case 'knowledge-dna':
        return [
          'Extract the Knowledge DNA of real-time multimodal emotion recognition',
          'Core architectures, attention mechanisms, benchmarks, and latency tradeoffs',
        ];
    }
  }

  if (hasAnn) {
    switch (mode) {
      case 'discover':
        return [
          'What indexing structures achieve sub-linear query time for high-dimensional nearest neighbors?',
          'How does randomized kd-tree search compare with hierarchical k-means?',
        ];
      case 'reason':
        return [
          'Why does the curse of dimensionality degrade Euclidean distance discrimination in vector search?',
          'How does graph-based proximity indexing scale with billion-scale embedding vectors?',
        ];
      case 'verify':
        return [
          'Hierarchical k-means achieves higher recall than single kd-trees on 128-dimensional SIFT vectors.',
          'Approximate nearest neighbor search provides over 95% recall with 10x speedup.',
        ];
      case 'compare':
        return [
          'Compare FAISS IVFFlat vs HNSW indexing on high-dimensional vectors',
          'Compare randomized kd-forest and hierarchical k-means tree clustering',
        ];
      case 'gaps':
        return [
          'Scalability bottlenecks in dynamic real-time vector index updates',
          'Memory overhead and index construction time in extreme dimensional vector spaces',
        ];
      case 'debate':
        return [
          'Is graph-based nearest neighbor search (HNSW) fundamentally superior to inverted file quantization?',
          'Should vector databases prioritize index build speed or sub-millisecond query recall?',
        ];
      case 'knowledge-map':
        return [
          'High-dimensional nearest neighbor search algorithms and indexing taxonomy',
          'Vector quantization, tree structures, and graph proximity routing',
        ];
      case 'knowledge-dna':
        return [
          'Extract the Knowledge DNA of scalable nearest neighbor algorithms',
          'Vector search principles, distance metrics, empirical complexity, and scaling limits',
        ];
    }
  }

  // Fallback: general research queries for active tool
  const defaultExamples: Record<AnalysisMode, string[]> = {
    discover: [
      'What are the primary methodologies and empirical findings in the indexed papers?',
      'How do the experimental results validate the core hypothesis?',
    ],
    reason: [
      'Why does the proposed architecture achieve superior empirical performance over baseline methods?',
      'Analyze the causal relationships and underlying mechanisms described in the literature.',
    ],
    verify: [
      'The proposed framework achieves statistically significant improvements over classical baselines.',
      'The experimental evaluation accounts for cross-validation and variance across trials.',
    ],
    compare: [
      'Compare the algorithmic complexity, runtime efficiency, and resource tradeoffs across methods',
      'What are the key structural and theoretical differences between the evaluated approaches?',
    ],
    gaps: [
      'Identify methodological limitations, unaddressed questions, and future research directions',
      'What contradictory findings or untested boundary conditions exist in the literature?',
    ],
    debate: [
      'Should researchers prioritize computational efficiency over marginal accuracy gains?',
      'Evaluate the competing arguments surrounding algorithmic complexity versus interpretability.',
    ],
    'knowledge-map': [
      'Synthesize a hierarchical concept map of key themes and relationships across the corpus',
      'Map the conceptual dependencies and algorithmic flow of the research literature',
    ],
    'knowledge-dna': [
      'Extract the thematic DNA, core concepts, methods, findings, and limitations from the corpus',
      'Generate an evidence-grounded Knowledge DNA profile from the indexed literature',
    ],
  };

  return defaultExamples[mode] || defaultExamples.discover;
}

export const QueryInput: React.FC<QueryInputProps> = ({
  query,
  mode,
  isLoading,
  loadingLabel,
  selectedDocuments = [],
  onQueryChange,
  onSubmit,
  onShowAbstention,
}) => {
  const currentExamples = getContextAwareExamples(mode, selectedDocuments);

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      if (query.trim() && !isLoading) {
        onSubmit();
      }
    }
  };

  const getPlaceholder = (m: AnalysisMode): string => {
    switch (m) {
      case 'discover':
        return 'Ask a research question across your selected documents (Press Enter to submit)...';
      case 'reason':
        return 'Enter a complex question to decompose into step-by-step reasoning chains...';
      case 'verify':
        return 'Enter a specific empirical claim or quantitative metric to verify against cited evidence...';
      case 'compare':
        return 'Enter concepts, techniques, or papers to compare across structured aspects...';
      case 'gaps':
        return 'Enter a research topic to detect literature boundaries and unaddressed research gaps...';
      case 'debate':
        return 'Enter a thesis, claim, or policy question for evidence-grounded dialectical debate...';
      case 'knowledge-map':
        return 'Enter a domain concept to construct an interactive topological mind map...';
      case 'knowledge-dna':
        return 'Enter a research domain or topic to extract its complete Knowledge DNA profile...';
      default:
        return 'Ask a question about your indexed documents (Press Enter to submit)...';
    }
  };

  const getActionLabel = (m: AnalysisMode): string => {
    switch (m) {
      case 'discover':
        return 'Ask Assistant';
      case 'reason':
        return 'Reason Multi-Hop';
      case 'verify':
        return 'Verify Claim';
      case 'compare':
        return 'Run Comparison';
      case 'gaps':
        return 'Find Gaps';
      case 'debate':
        return 'Generate Debate';
      case 'knowledge-map':
        return 'Build Mind Map';
      case 'knowledge-dna':
        return 'Extract Concept DNA';
      default:
        return 'Analyze';
    }
  };

  return (
    <div className="space-y-3">
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (query.trim() && !isLoading) {
            onSubmit();
          }
        }}
        className="space-y-2"
      >
        <label htmlFor="knowledge-query" className="sr-only">Natural language query</label>
        <textarea
          id="knowledge-query"
          rows={3}
          value={query}
          disabled={isLoading}
          onChange={(event) => onQueryChange(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={getPlaceholder(mode)}
          className="w-full resize-y rounded-lg border border-[#46545f] bg-[#0c1217] px-4 py-4 text-base leading-7 text-white placeholder:text-[#82909a] focus:border-[#a7d0d2]/70 focus:outline-none disabled:opacity-60"
        />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-[#98a6b0]">
            Press <kbd className="rounded bg-[#141d26] px-1.5 py-0.5 font-mono text-[11px] text-[#a7d0d2] border border-white/10">Enter</kbd> to submit, <kbd className="rounded bg-[#141d26] px-1.5 py-0.5 font-mono text-[11px] text-[#a7d0d2] border border-white/10">Shift+Enter</kbd> for a new line.
          </p>
          <button
            type="submit"
            disabled={!query.trim() || isLoading}
            className="inline-flex items-center gap-2 rounded-md bg-[#d2434e] px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[#b83842] disabled:cursor-not-allowed disabled:opacity-40 cursor-pointer"
          >
            {isLoading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <ArrowRight className="h-4 w-4" aria-hidden="true" />}
            {isLoading ? loadingLabel : getActionLabel(mode)}
          </button>
        </div>
      </form>

      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1 text-xs font-mono uppercase text-[#a7d0d2]">
          Context-aware suggestions:
        </span>
        {currentExamples.map((example) => (
          <button
            key={example}
            type="button"
            disabled={isLoading}
            onClick={() => onQueryChange(example)}
            className="rounded-md border border-white/10 bg-[#111a22] px-2.5 py-1 text-xs text-[#b6c1c9] hover:border-[#a7d0d2]/50 hover:text-white transition-colors cursor-pointer disabled:opacity-50 text-left"
          >
            "{example}"
          </button>
        ))}
        <button
          type="button"
          onClick={onShowAbstention}
          className="ml-auto text-xs text-[#98a6b0] hover:text-white transition-colors cursor-pointer"
        >
          Preview insufficient evidence
        </button>
      </div>
    </div>
  );
};