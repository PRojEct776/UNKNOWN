import React from 'react';
import { Gauge } from 'lucide-react';

interface ConfidenceBadgeProps {
  value?: number;
}

export const ConfidenceBadge: React.FC<ConfidenceBadgeProps> = ({ value }) => {
  if (value === undefined || value === null || !Number.isFinite(value)) return null;

  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-[#a7d0d2]/30 bg-[#a7d0d2]/10 px-2.5 py-1 font-mono text-xs text-[#a7d0d2]">
      <Gauge className="h-3.5 w-3.5" aria-hidden="true" />
      Confidence {Math.round(value * 100)}%
    </span>
  );
};