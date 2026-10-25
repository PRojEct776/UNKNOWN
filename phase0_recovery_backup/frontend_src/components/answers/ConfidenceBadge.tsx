import React, { useState } from 'react';
import { Gauge, ChevronDown, ChevronUp, X, ShieldCheck, FileCheck, Users, Award } from 'lucide-react';
import type { ConfidenceData, ConfidenceBreakdown } from '../../types/query';

export interface ConfidenceBadgeProps {
  confidence?: number | ConfidenceData | null;
  value?: number; // legacy backwards compatibility
}

export const ConfidenceBadge: React.FC<ConfidenceBadgeProps> = ({ confidence, value }) => {
  const [isOpen, setIsOpen] = useState(false);

  // Normalize API confidence
  const confData: ConfidenceData | null =
    typeof confidence === 'object' && confidence !== null
      ? confidence
      : typeof confidence === 'number'
      ? { score: confidence }
      : typeof value === 'number'
      ? { score: value }
      : null;

  if (!confData || confData.score === undefined || confData.score === null || !Number.isFinite(confData.score)) {
    return null;
  }

  const score = confData.score;
  const breakdown: ConfidenceBreakdown | undefined = confData.breakdown;

  // Color coding by score band
  const badgeColors =
    score >= 80
      ? 'border-emerald-400/40 bg-emerald-500/15 text-emerald-300 hover:bg-emerald-500/25'
      : score >= 50
      ? 'border-[#a7d0d2]/40 bg-[#a7d0d2]/15 text-[#a7d0d2] hover:bg-[#a7d0d2]/25'
      : 'border-amber-400/40 bg-amber-500/15 text-amber-300 hover:bg-amber-500/25';

  return (
    <div className="relative inline-block text-left" data-testid="confidence-container">
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 font-mono text-xs transition-all cursor-pointer shadow-sm ${badgeColors}`}
        data-testid="confidence-badge"
        aria-expanded={isOpen}
        aria-haspopup="dialog"
        title="Click to view confidence breakdown"
      >
        <Gauge className="h-3.5 w-3.5" aria-hidden="true" />
        <span>Confidence {score}%</span>
        {isOpen ? (
          <ChevronUp className="h-3 w-3 opacity-70" aria-hidden="true" />
        ) : (
          <ChevronDown className="h-3 w-3 opacity-70" aria-hidden="true" />
        )}
      </button>

      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
            aria-hidden="true"
          />

          {/* Breakdown Popover Panel */}
          <div
            className="absolute right-0 top-full z-50 mt-2 w-80 rounded-xl border border-[#4d728e]/40 bg-[#0f1721] p-4 shadow-2xl backdrop-blur-md"
            data-testid="confidence-breakdown"
            role="dialog"
            aria-label="Confidence Score Breakdown"
          >
            <div className="flex items-center justify-between border-b border-white/10 pb-2.5">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-[#a7d0d2]" aria-hidden="true" />
                <h4 className="text-xs font-semibold uppercase tracking-wider text-white">
                  Score Breakdown
                </h4>
              </div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-bold text-white">{score}%</span>
                <button
                  type="button"
                  onClick={() => setIsOpen(false)}
                  className="rounded p-1 text-[#f3faf0]/50 hover:bg-white/10 hover:text-white transition-colors"
                  aria-label="Close breakdown"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>

            {breakdown ? (
              <div className="mt-3 space-y-3">
                {/* 1. Evidence Coverage */}
                <div data-testid="breakdown-coverage">
                  <div className="flex items-center justify-between text-[11px] font-mono">
                    <span className="flex items-center gap-1.5 text-[#f3faf0]/75">
                      <FileCheck className="h-3.5 w-3.5 text-sky-400" />
                      Evidence Coverage
                    </span>
                    <span className="text-sky-300 font-semibold">
                      {breakdown.evidence_coverage}
                    </span>
                  </div>
                  <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-white/10">
                    <div
                      className="h-full bg-sky-400 rounded-full transition-all duration-300"
                      style={{ width: `${Math.min(100, Math.max(0, breakdown.evidence_coverage * 100))}%` }}
                    />
                  </div>
                </div>

                {/* 2. Source Agreement */}
                <div data-testid="breakdown-agreement">
                  <div className="flex items-center justify-between text-[11px] font-mono">
                    <span className="flex items-center gap-1.5 text-[#f3faf0]/75">
                      <Users className="h-3.5 w-3.5 text-emerald-400" />
                      Source Agreement
                    </span>
                    <span className="text-emerald-300 font-semibold">
                      {breakdown.source_agreement}
                    </span>
                  </div>
                  <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-white/10">
                    <div
                      className="h-full bg-emerald-400 rounded-full transition-all duration-300"
                      style={{ width: `${Math.min(100, Math.max(0, breakdown.source_agreement * 100))}%` }}
                    />
                  </div>
                </div>

                {/* 3. Source Quality */}
                <div data-testid="breakdown-quality">
                  <div className="flex items-center justify-between text-[11px] font-mono">
                    <span className="flex items-center gap-1.5 text-[#f3faf0]/75">
                      <Award className="h-3.5 w-3.5 text-purple-400" />
                      Source Quality
                    </span>
                    <span className="text-purple-300 font-semibold">
                      {breakdown.source_quality}
                    </span>
                  </div>
                  <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-white/10">
                    <div
                      className="h-full bg-purple-400 rounded-full transition-all duration-300"
                      style={{ width: `${Math.min(100, Math.max(0, breakdown.source_quality * 100))}%` }}
                    />
                  </div>
                </div>

                {/* 4. Claim Support */}
                <div data-testid="breakdown-support">
                  <div className="flex items-center justify-between text-[11px] font-mono">
                    <span className="flex items-center gap-1.5 text-[#f3faf0]/75">
                      <ShieldCheck className="h-3.5 w-3.5 text-amber-400" />
                      Claim Support
                    </span>
                    <span className="text-amber-300 font-semibold">
                      {breakdown.claim_support}
                    </span>
                  </div>
                  <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-white/10">
                    <div
                      className="h-full bg-amber-400 rounded-full transition-all duration-300"
                      style={{ width: `${Math.min(100, Math.max(0, breakdown.claim_support * 100))}%` }}
                    />
                  </div>
                </div>
              </div>
            ) : (
              <div className="py-4 text-center text-xs text-[#f3faf0]/50">
                Detailed breakdown not provided by endpoint.
              </div>
            )}

            <div className="mt-3.5 border-t border-white/5 pt-2 text-[10px] text-[#f3faf0]/40 font-mono flex justify-between">
              <span>Formula: UNKNOWN v1.0</span>
              <span>Deterministic API score</span>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
