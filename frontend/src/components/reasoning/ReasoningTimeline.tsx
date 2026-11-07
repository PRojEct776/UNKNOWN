import React from 'react';
import { ArrowDown, Check, Circle, Waypoints, AlertTriangle, HelpCircle } from 'lucide-react';
import type { ReasoningResult } from '../../types/reasoning';

interface ReasoningTimelineProps {
  reasoning: ReasoningResult;
  onOpenSources: () => void;
}

export const ReasoningTimeline: React.FC<ReasoningTimelineProps> = ({ reasoning, onOpenSources }) => (
  <section className="space-y-4" aria-labelledby="reasoning-title">
    <div className="flex items-center gap-2">
      <Waypoints className="h-4 w-4 text-[#a7d0d2]" aria-hidden="true" />
      <h2 id="reasoning-title" className="text-xs font-mono uppercase text-[#f3faf0]/75">Reasoning</h2>
    </div>

    <article className="rounded-lg border border-[#4d728e]/30 bg-[#0b1219]/70 p-4">
      <p className="text-[10px] font-mono uppercase text-[#a7d0d2]">Original question</p>
      <p className="mt-2 text-sm text-white">{reasoning.originalQuestion}</p>
    </article>

    {/* Sub-questions grid */}
    {reasoning.subQuestions && reasoning.subQuestions.length > 0 && (
      <div className="grid gap-3 sm:grid-cols-2">
        {reasoning.subQuestions.map((question, index) => (
          <article key={question.id || `subq_${index}`} className="rounded-lg border border-white/8 bg-[#141d26]/65 p-4">
            <p className="text-[10px] font-mono text-[#d2434e]">SUB-QUESTION {String(index + 1).padStart(2, '0')}</p>
            <h3 className="mt-2 text-sm font-semibold text-white">{question.question}</h3>
            <p className="mt-2 text-xs leading-relaxed text-[#f3faf0]/65">{question.synthesis}</p>
            <p className="mt-3 text-[10px] text-[#a7d0d2]">
              {(question.evidenceIds || []).length} linked evidence {(question.evidenceIds || []).length === 1 ? 'item' : 'items'}
            </p>
          </article>
        ))}
      </div>
    )}

    {/* Ordered reasoning steps timeline */}
    {reasoning.steps && reasoning.steps.length > 0 && (
      <div className="space-y-2 rounded-lg border border-white/8 bg-[#0b1219]/55 p-4">
        {reasoning.steps.map((step, index) => (
          <React.Fragment key={step.id || `step_${index}`}>
            <div className="flex items-start gap-3">
              <span className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border ${step.status === 'complete' ? 'border-[#a7d0d2]/45 bg-[#a7d0d2]/10 text-[#a7d0d2]' : 'border-white/15 text-[#f3faf0]/40'}`}>
                {step.status === 'complete' ? <Check className="h-3.5 w-3.5" /> : <Circle className="h-2.5 w-2.5" />}
              </span>
              <div>
                <h3 className="text-xs font-semibold text-white">{step.title}</h3>
                <p className="mt-1 text-xs text-[#f3faf0]/60">{step.description}</p>
              </div>
            </div>
            {index < reasoning.steps.length - 1 && <ArrowDown className="ml-2 h-3.5 w-3.5 text-[#4d728e]" aria-hidden="true" />}
          </React.Fragment>
        ))}
      </div>
    )}

    {/* Cross-document conflicts if present */}
    {reasoning.conflicts && reasoning.conflicts.length > 0 && (
      <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 space-y-2">
        <div className="flex items-center gap-2 text-amber-300">
          <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
          <p className="text-[10px] font-mono uppercase tracking-wider">Cross-Document Conflict Analysis</p>
        </div>
        <ul className="list-disc pl-5 text-xs text-[#f3faf0]/80 space-y-1">
          {reasoning.conflicts.map((conflict, i) => (
            <li key={i}>{conflict}</li>
          ))}
        </ul>
      </div>
    )}

    {/* Uncertainty & Limitations if present */}
    {reasoning.uncertainty && (
      <div className="rounded-lg border border-blue-500/30 bg-blue-500/10 p-4 space-y-1.5">
        <div className="flex items-center gap-2 text-[#a7d0d2]">
          <HelpCircle className="h-4 w-4 shrink-0" aria-hidden="true" />
          <p className="text-[10px] font-mono uppercase tracking-wider">Evidence Uncertainty & Limitations</p>
        </div>
        <p className="text-xs leading-relaxed text-[#f3faf0]/80">{reasoning.uncertainty}</p>
      </div>
    )}

    {/* Final synthesis and evidence review */}
    <div className="rounded-lg border border-[#d2434e]/20 bg-[#d2434e]/5 p-4">
      <p className="text-[10px] font-mono uppercase text-[#d2434e]">Synthesis</p>
      <p className="mt-2 text-sm leading-relaxed text-[#f3faf0]/85">{reasoning.synthesis || 'Synthesis completed.'}</p>
      <button type="button" onClick={onOpenSources} className="mt-3 text-xs font-medium text-[#a7d0d2] hover:text-white cursor-pointer transition-colors">
        Review evidence sources
      </button>
    </div>
  </section>
);
