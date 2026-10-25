import React from 'react';
import { BookOpen, Dna, GitCompareArrows, Lightbulb, MessageCircleQuestion, Network, ShieldCheck, Waypoints, type LucideIcon } from 'lucide-react';
import type { AnalysisMode } from '../../types/query';

const modes: { id: AnalysisMode; label: string; description: string; icon: LucideIcon }[] = [
  { id: 'discover', label: 'Assistant', description: 'Ask questions & retrieve citations', icon: BookOpen },
  { id: 'reason', label: 'Reason', description: 'Decompose questions & causal synthesis', icon: Waypoints },
  { id: 'knowledge-map', label: 'Mind Map', description: 'Interactive conceptual graph topology', icon: Network },
  { id: 'verify', label: 'Verify', description: 'Check claims against cited passages', icon: ShieldCheck },
  { id: 'compare', label: 'Compare', description: 'Compare concepts across structured aspects', icon: GitCompareArrows },
  { id: 'gaps', label: 'Find Gaps', description: 'Detect limitations & unaddressed research', icon: Lightbulb },
  { id: 'debate', label: 'Debate', description: 'Evidence-grounded thesis & antithesis', icon: MessageCircleQuestion },
  { id: 'knowledge-dna', label: 'Concept DNA', description: 'Thematic emergence & DNA signals', icon: Dna },
];

interface SearchModeSelectorProps {
  value: AnalysisMode;
  onChange: (mode: AnalysisMode) => void;
  disabled?: boolean;
}

export const SearchModeSelector: React.FC<SearchModeSelectorProps> = ({ value, onChange, disabled = false }) => (
  <fieldset>
    <legend className="mb-2 text-[11px] font-mono uppercase text-[#f3faf0]/55">Choose a research tool</legend>
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-8">
      {modes.map(({ id, label, description, icon: Icon }) => (
        <button
          key={id}
          type="button"
          onClick={() => onChange(id)}
          disabled={disabled}
          aria-pressed={value === id}
          className={`min-h-20 rounded-lg border p-3 text-left transition-colors disabled:cursor-wait disabled:opacity-50 ${value === id ? 'border-[#d2434e]/70 bg-[#d2434e]/10 text-white' : 'border-white/8 bg-[#141d26]/55 text-[#f3faf0]/65 hover:border-[#4d728e] hover:text-white'}`}
        >
          <Icon className={`mb-2 h-4 w-4 ${value === id ? 'text-[#d2434e]' : 'text-[#a7d0d2]'}`} aria-hidden="true" />
          <span className="block text-xs font-semibold">{label}</span>
          <span className="mt-1 hidden text-[10px] leading-tight text-[#f3faf0]/45 xl:block">{description}</span>
        </button>
      ))}
    </div>
  </fieldset>
);