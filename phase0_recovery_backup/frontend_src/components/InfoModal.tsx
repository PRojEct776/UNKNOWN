import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Compass,
  Cpu,
  Share2,
  CheckCircle2,
  Database,
  X,
  Sparkles,
  ArrowRight,
  Shield,
  Gauge,
  Boxes,
  Zap,
  TrainTrack,
} from 'lucide-react';

export type ModalTab = 'how-it-works' | 'domains';

interface InfoModalProps {
  isOpen: boolean;
  activeTab: ModalTab;
  onClose: () => void;
  onTabChange: (tab: ModalTab) => void;
  onSelectPrompt?: (prompt: string) => void;
}

export const InfoModal: React.FC<InfoModalProps> = ({
  isOpen,
  activeTab,
  onClose,
  onTabChange,
  onSelectPrompt,
}) => {
  const navigate = useNavigate();

  // Close on Escape key press
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'unset';
    };
  }, [isOpen, onClose]);

  const handlePromptClick = (prompt: string) => {
    onClose();
    if (onSelectPrompt) {
      onSelectPrompt(prompt);
    } else {
      navigate('/search?q=' + encodeURIComponent(prompt));
    }
  };


  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 overflow-y-auto">
          {/* Backdrop Blur */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-[#070b10]/75 transition-opacity"
          />

          {/* Modal Container */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 15 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 15 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className="relative z-10 flex max-h-[90vh] w-full max-w-4xl flex-col overflow-hidden rounded-xl border border-[#52616c]/35 bg-[#111a22] shadow-xl"
          >
            {/* Modal Header */}
            <div className="flex shrink-0 items-center justify-between border-b border-white/8 bg-[#0c1217] px-5 py-4">
              {/* Tabs Switcher */}
              <div className="flex items-center gap-1 rounded-lg border border-white/8 bg-[#0c1217] p-1">
                <button
                  onClick={() => onTabChange('how-it-works')}
                  className={`flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors cursor-pointer ${
                    activeTab === 'how-it-works'
                      ? 'bg-[#1a252d] text-white'
                      : 'text-[#f3faf0]/70 hover:text-white hover:bg-white/5'
                  }`}
                >
                  <Compass className="w-3.5 h-3.5" />
                  <span>How UNKNOWN Works</span>
                </button>

                <button
                  onClick={() => onTabChange('domains')}
                  className={`flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors cursor-pointer ${
                    activeTab === 'domains'
                      ? 'bg-[#1a252d] text-white'
                      : 'text-[#f3faf0]/70 hover:text-white hover:bg-white/5'
                  }`}
                >
                  <Database className="w-3.5 h-3.5" />
                  <span>Controlled Domains (5)</span>
                </button>
              </div>

              {/* Close Button */}
              <div className="flex items-center gap-2">

                <button
                  onClick={onClose}
                  className="p-1.5 rounded-lg text-[#f3faf0]/60 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
                  aria-label="Close modal"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Modal Body */}
            <div className="p-5 sm:p-7 overflow-y-auto space-y-6 text-[#f3faf0]">
              {activeTab === 'how-it-works' ? (
                /* TAB 1: HOW IT WORKS */
                <div className="space-y-6">
                  {/* Top Intro */}
                  <div className="space-y-2">
                    <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-[#d2434e]/15 border border-[#d2434e]/30 text-[#d2434e] text-[11px] font-mono font-bold">
                      <span className="w-1.5 h-1.5 rounded-full bg-[#d2434e] animate-pulse" />
                      SEPM HYBRID RETRIEVAL ARCHITECTURE
                    </div>
                    <h3 className="text-xl font-semibold text-white sm:text-2xl">
                      From Natural Language to Evidence-Grounded Answers
                    </h3>
                    <p className="text-xs sm:text-sm text-[#f3faf0]/75 leading-relaxed">
                      A user may describe a function or context without knowing a technical name. UNKNOWN is designed to combine query understanding, hybrid retrieval, evidence review, and grounded answer presentation.
                    </p>
                  </div>

                  {/* Comparison Box */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                    <div className="p-4 rounded-xl bg-[#0b1219] border border-rose-500/20 space-y-1.5">
                      <div className="flex items-center justify-between text-rose-400 font-bold font-mono">
                        <span>LEXICAL RETRIEVAL</span>
                        <span>EXACT TERMS</span>
                      </div>
                      <p className="text-[#f3faf0]/70">
                        Matches query terms against document terms. It can miss related passages when the same idea uses different wording.
                      </p>
                    </div>

                    <div className="p-4 rounded-xl bg-[#0b1219] border border-[#a7d0d2]/30 space-y-1.5">
                      <div className="flex items-center justify-between text-[#a7d0d2] font-bold font-mono">
                        <span>HYBRID RETRIEVAL</span>
                        <span className="text-[#d2434e]">LEXICAL + SEMANTIC</span>
                      </div>
                      <p className="text-[#f3faf0]/70">
                        Combines retrieval signals to find candidate passages. Evidence can then be reviewed alongside its source before an answer is presented.
                      </p>
                    </div>
                  </div>

                  {/* 4 Pipeline Steps */}
                  <div className="space-y-3">
                    <h4 className="text-xs font-mono font-bold tracking-wider text-[#a7d0d2] uppercase">
                      The 4-Step Processing Pipeline
                    </h4>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                      {/* Step 1 */}
                      <div className="p-4 rounded-xl bg-[#0b1219]/90 border border-white/5 space-y-1.5 hover:border-[#4d728e]/50 transition-all">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-mono font-bold text-[#d2434e]">STEP 01</span>
                          <Compass className="w-4 h-4 text-[#a7d0d2]" />
                        </div>
                        <h5 className="text-sm font-bold text-white">Query Understanding</h5>
                        <p className="text-xs text-[#f3faf0]/70 leading-relaxed">
                          Accepts unstructured natural language, physical use-case descriptions, or functional clues without requiring technical keywords.
                        </p>
                      </div>

                      {/* Step 2 */}
                      <div className="p-4 rounded-xl bg-[#0b1219]/90 border border-white/5 space-y-1.5 hover:border-[#4d728e]/50 transition-all">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-mono font-bold text-[#d2434e]">STEP 02</span>
                          <Cpu className="w-4 h-4 text-[#a7d0d2]" />
                        </div>
                          <h5 className="text-sm font-bold text-white">Hybrid Evidence Retrieval</h5>
                        <p className="text-xs text-[#f3faf0]/70 leading-relaxed">
                          Searches a document collection using lexical and semantic signals to find passages relevant to the query.
                        </p>
                      </div>

                      {/* Step 3 */}
                      <div className="p-4 rounded-xl bg-[#0b1219]/90 border border-white/5 space-y-1.5 hover:border-[#4d728e]/50 transition-all">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-mono font-bold text-[#a7d0d2]">STEP 03</span>
                          <Share2 className="w-4 h-4 text-[#d2434e]" />
                        </div>
                          <h5 className="text-sm font-bold text-white">Evidence &amp; Reasoning</h5>
                        <p className="text-xs text-[#f3faf0]/70 leading-relaxed">
                          Organizes retrieved passages, compares findings, and keeps supporting or conflicting evidence visible.
                        </p>
                      </div>

                      {/* Step 4 */}
                      <div className="p-4 rounded-xl bg-[#0b1219]/90 border border-white/5 space-y-1.5 hover:border-[#4d728e]/50 transition-all">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-mono font-bold text-[#d2434e]">STEP 04</span>
                          <CheckCircle2 className="w-4 h-4 text-[#d2434e]" />
                        </div>
                          <h5 className="text-sm font-bold text-white">Answer or Abstention</h5>
                        <p className="text-xs text-[#f3faf0]/70 leading-relaxed">
                          Presents a grounded answer with confidence and sources, or indicates when evidence is insufficient.
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                /* TAB 2: CONTROLLED DOMAINS */
                <div className="space-y-6">
                  {/* Top Intro */}
                  <div className="space-y-2">
                    <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-[#a7d0d2]/15 border border-[#a7d0d2]/30 text-[#a7d0d2] text-[11px] font-mono font-bold">
                      <Database className="w-3.5 h-3.5" />
                      ACADEMIC EVALUATION BENCHMARK
                    </div>
                    <h3 className="text-xl font-semibold text-white sm:text-2xl">
                      5 Curated Engineering Taxonomies
                    </h3>
                    <p className="text-xs sm:text-sm text-[#f3faf0]/75 leading-relaxed">
                      These sample domains demonstrate the workspace interaction. <strong className="text-white">Choose a query to prefill the workspace, then submit it:</strong>
                    </p>
                  </div>

                  {/* 5 Domains Grid */}
                  <div className="space-y-4">
                    {/* Domain 1 */}
                    <div className="p-4 rounded-xl bg-[#0b1219] border border-white/8 space-y-2.5 hover:border-[#a7d0d2]/40 transition-colors">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Boxes className="w-4 h-4 text-[#d2434e]" />
                          <h5 className="text-sm font-bold text-white">1. Material Handling Equipment</h5>
                        </div>
                        <span className="text-[10px] font-mono text-[#a7d0d2] bg-[#a7d0d2]/10 px-2 py-0.5 rounded-full border border-[#a7d0d2]/20">
                          Warehousing & Logistics
                        </span>
                      </div>
                      <p className="text-xs text-[#f3faf0]/70">
                        Heavy industrial vehicles, pallet handlers, and lifting machinery used in distribution facilities.
                      </p>
                      <div className="flex flex-wrap gap-2 pt-1">
                        <button
                          onClick={() => handlePromptClick("What's that thing used in warehouses to lift large loads?")}
                          className="text-xs px-3 py-1.5 rounded-lg bg-[#141d26] hover:bg-[#d2434e] hover:text-white text-[#f3faf0]/90 border border-white/10 transition-colors flex items-center gap-1.5 cursor-pointer group"
                        >
                          <Sparkles className="w-3 h-3 text-[#d2434e] group-hover:text-white" />
                          <span>"thing used in warehouses to lift large loads"</span>
                          <ArrowRight className="w-3 h-3 opacity-60 group-hover:opacity-100" />
                        </button>

                        <button
                          onClick={() => handlePromptClick("Vehicle with hydraulic prongs to move wooden pallets")}
                          className="text-xs px-3 py-1.5 rounded-lg bg-[#141d26] hover:bg-[#d2434e] hover:text-white text-[#f3faf0]/90 border border-white/10 transition-colors flex items-center gap-1.5 cursor-pointer group"
                        >
                          <Sparkles className="w-3 h-3 text-[#d2434e] group-hover:text-white" />
                          <span>"vehicle with hydraulic prongs to move pallets"</span>
                          <ArrowRight className="w-3 h-3 opacity-60 group-hover:opacity-100" />
                        </button>
                      </div>
                    </div>

                    {/* Domain 2 */}
                    <div className="p-4 rounded-xl bg-[#0b1219] border border-white/8 space-y-2.5 hover:border-[#a7d0d2]/40 transition-colors">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Gauge className="w-4 h-4 text-[#a7d0d2]" />
                          <h5 className="text-sm font-bold text-white">2. Measurement Instruments</h5>
                        </div>
                        <span className="text-[10px] font-mono text-[#a7d0d2] bg-[#a7d0d2]/10 px-2 py-0.5 rounded-full border border-[#a7d0d2]/20">
                          Metrology & Diagnostics
                        </span>
                      </div>
                      <p className="text-xs text-[#f3faf0]/70">
                        Instruments designed to quantify physical gradients, temperatures, and electrical parameters.
                      </p>
                      <div className="flex flex-wrap gap-2 pt-1">
                        <button
                          onClick={() => handlePromptClick("Device that measures temperature and thermal gradients")}
                          className="text-xs px-3 py-1.5 rounded-lg bg-[#141d26] hover:bg-[#d2434e] hover:text-white text-[#f3faf0]/90 border border-white/10 transition-colors flex items-center gap-1.5 cursor-pointer group"
                        >
                          <Sparkles className="w-3 h-3 text-[#d2434e] group-hover:text-white" />
                          <span>"device that measures temperature and heat"</span>
                          <ArrowRight className="w-3 h-3 opacity-60 group-hover:opacity-100" />
                        </button>
                      </div>
                    </div>

                    {/* Domain 3 */}
                    <div className="p-4 rounded-xl bg-[#0b1219] border border-white/8 space-y-2.5 hover:border-[#a7d0d2]/40 transition-colors">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Shield className="w-4 h-4 text-[#d2434e]" />
                          <h5 className="text-sm font-bold text-white">3. Personal Protective Equipment (PPE)</h5>
                        </div>
                        <span className="text-[10px] font-mono text-[#a7d0d2] bg-[#a7d0d2]/10 px-2 py-0.5 rounded-full border border-[#a7d0d2]/20">
                          Industrial & Road Safety
                        </span>
                      </div>
                      <p className="text-xs text-[#f3faf0]/70">
                        Gear designed to protect the human body against kinetic impact, flying debris, and workplace trauma.
                      </p>
                      <div className="flex flex-wrap gap-2 pt-1">
                        <button
                          onClick={() => handlePromptClick("Thing used to protect your head while riding a bike")}
                          className="text-xs px-3 py-1.5 rounded-lg bg-[#141d26] hover:bg-[#d2434e] hover:text-white text-[#f3faf0]/90 border border-white/10 transition-colors flex items-center gap-1.5 cursor-pointer group"
                        >
                          <Sparkles className="w-3 h-3 text-[#d2434e] group-hover:text-white" />
                          <span>"thing used to protect your head while riding a bike"</span>
                          <ArrowRight className="w-3 h-3 opacity-60 group-hover:opacity-100" />
                        </button>
                      </div>
                    </div>

                    {/* Domain 4 */}
                    <div className="p-4 rounded-xl bg-[#0b1219] border border-white/8 space-y-2.5 hover:border-[#a7d0d2]/40 transition-colors">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Zap className="w-4 h-4 text-[#a7d0d2]" />
                          <h5 className="text-sm font-bold text-white">4. Electromechanical Machinery</h5>
                        </div>
                        <span className="text-[10px] font-mono text-[#a7d0d2] bg-[#a7d0d2]/10 px-2 py-0.5 rounded-full border border-[#a7d0d2]/20">
                          Power & Automation
                        </span>
                      </div>
                      <p className="text-xs text-[#f3faf0]/70">
                        Devices converting electrical energy into mechanical movement, rotary torque, or fluid pressure.
                      </p>
                      <div className="flex flex-wrap gap-2 pt-1">
                        <button
                          onClick={() => handlePromptClick("Converts electrical energy into mechanical movement")}
                          className="text-xs px-3 py-1.5 rounded-lg bg-[#141d26] hover:bg-[#d2434e] hover:text-white text-[#f3faf0]/90 border border-white/10 transition-colors flex items-center gap-1.5 cursor-pointer group"
                        >
                          <Sparkles className="w-3 h-3 text-[#d2434e] group-hover:text-white" />
                          <span>"converts electrical energy into mechanical movement"</span>
                          <ArrowRight className="w-3 h-3 opacity-60 group-hover:opacity-100" />
                        </button>
                      </div>
                    </div>

                    {/* Domain 5 */}
                    <div className="p-4 rounded-xl bg-[#0b1219] border border-white/8 space-y-2.5 hover:border-[#a7d0d2]/40 transition-colors">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <TrainTrack className="w-4 h-4 text-[#d2434e]" />
                          <h5 className="text-sm font-bold text-white">5. Rail Transport Systems</h5>
                        </div>
                        <span className="text-[10px] font-mono text-[#a7d0d2] bg-[#a7d0d2]/10 px-2 py-0.5 rounded-full border border-[#a7d0d2]/20">
                          Heavy Transit
                        </span>
                      </div>
                      <p className="text-xs text-[#f3faf0]/70">
                        Rolling stock, railcars, overhead pantographs, and traction vehicles moving passengers along steel rails.
                      </p>
                      <div className="flex flex-wrap gap-2 pt-1">
                        <button
                          onClick={() => handlePromptClick("Vehicle used for transporting many people on railway tracks")}
                          className="text-xs px-3 py-1.5 rounded-lg bg-[#141d26] hover:bg-[#d2434e] hover:text-white text-[#f3faf0]/90 border border-white/10 transition-colors flex items-center gap-1.5 cursor-pointer group"
                        >
                          <Sparkles className="w-3 h-3 text-[#d2434e] group-hover:text-white" />
                          <span>"vehicle used for transporting many people on railway tracks"</span>
                          <ArrowRight className="w-3 h-3 opacity-60 group-hover:opacity-100" />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="px-5 py-3.5 border-t border-white/10 bg-[#0b1219] flex flex-col sm:flex-row items-center justify-between gap-3 shrink-0">
              <span className="text-xs text-[#f3faf0]/60 font-mono">
                College SEPM & Research Methodology Project
              </span>
              <div className="flex items-center gap-3">
                <button
                  onClick={onClose}
                  className="px-4 py-1.5 rounded-full bg-[#1b2734] hover:bg-[#4d728e]/40 text-white text-xs font-semibold border border-white/10 transition-colors cursor-pointer"
                >
                  Close
                </button>
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};
