import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Search,
  ArrowRight,
  Database,
  Share2,
  Compass,
  Cpu,
  CheckCircle2,
} from 'lucide-react';

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchQuery, setSearchQuery] = useState('');

  // Smooth scroll handler for #how-it-works or #domains
  useEffect(() => {
    const hash = location.hash || window.location.hash;
    if (hash) {
      const targetId = hash.replace('#', '');
      const el = document.getElementById(targetId);
      if (el) {
        const timer = setTimeout(() => {
          el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 150);
        return () => clearTimeout(timer);
      }
    }
  }, [location.hash]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    navigate(`/search?mode=discover&q=${encodeURIComponent(searchQuery.trim())}&run=${Date.now()}`);
  };

  const handleTestQuery = (query: string) => {
    navigate(`/search?mode=discover&q=${encodeURIComponent(query)}&run=${Date.now()}`);
  };

  const domainList = [
    { name: 'Material Handling Equipment', sample: "What's that thing used in warehouses to lift large loads?" },
    { name: 'Measurement Instruments', sample: 'Device that measures temperature and thermal gradients' },
    { name: 'Personal Protective Equipment', sample: 'Thing used to protect your head while riding a bike' },
    { name: 'Electromechanical Machinery', sample: 'Converts electrical energy into mechanical movement' },
    { name: 'Rail Transport Systems', sample: 'Vehicle used for transporting many people on railway tracks' },
  ];

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-[#0b1219] text-[#f3faf0] overflow-y-auto">
      {/* ========================================================
          HERO SECTION: Clean, subtle, no unwanted badges
          ======================================================== */}
      <section className="relative max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-12 pb-16 lg:py-20">
        {/* Soft background ambient glow matching palette */}
        <div className="absolute top-1/3 left-1/4 -translate-x-1/2 -translate-y-1/2 w-[480px] h-[480px] bg-[#d2434e]/6 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute top-1/2 right-10 w-[380px] h-[380px] bg-[#a7d0d2]/5 rounded-full blur-3xl pointer-events-none" />

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-8 items-center relative z-10">
          {/* Left Column: Clean Sans Typography & Clear Purpose */}
          <div className="lg:col-span-6 space-y-6">
            {/* Title: UNKNOWN: Discover concepts you can't name. */}
            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-black text-white tracking-tight leading-[1.15]">
              <span className="text-[#a7d0d2] block text-xl sm:text-2xl font-mono font-semibold mb-1">
                UNKNOWN:
              </span>
              Discover concepts you{' '}
              <span className="text-[#d2434e]">can't name.</span>
            </h1>

            {/* Subtle Subtitle */}
            <p className="text-sm sm:text-base text-[#f3faf0]/75 leading-relaxed max-w-lg">
              Describe what a tool or machine does, how it operates, or where it's used. UNKNOWN bridges the lexical gap using dense vector semantics and knowledge graph verification.
            </p>

            {/* Clean CTA Buttons */}
            <div className="flex flex-wrap items-center gap-3 pt-1">
              <button
                onClick={() => navigate('/search')}
                className="px-6 py-2.5 rounded-full bg-[#d2434e] hover:bg-[#b83842] text-white font-semibold text-xs sm:text-sm tracking-wide shadow-md transition-all flex items-center gap-2 cursor-pointer"
              >
                <span>Launch Search Engine</span>
                <ArrowRight className="w-4 h-4" />
              </button>

              <a
                href="#how-it-works"
                className="px-5 py-2.5 rounded-full bg-[#141d26] hover:bg-[#1b2734] border border-[#4d728e]/35 text-[#f3faf0]/80 hover:text-white text-xs font-medium transition-all"
              >
                How it works ↓
              </a>
            </div>
          </div>

          {/* Right Column: Clean, Subtle Interactive Mockup Window */}
          <div className="lg:col-span-6">
            <div className="rounded-2xl bg-[#141d26]/80 border border-[#4d728e]/30 shadow-xl p-5 sm:p-6 backdrop-blur-md space-y-4">
              {/* Window Header */}
              <div className="flex items-center justify-between pb-3 border-b border-white/5 text-xs font-mono text-[#f3faf0]/50">
                <div className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full bg-rose-500/70" />
                  <div className="w-2.5 h-2.5 rounded-full bg-amber-500/70" />
                  <div className="w-2.5 h-2.5 rounded-full bg-emerald-500/70" />
                  <span className="ml-2 text-[#f3faf0]/70">unknown.ai / concept-discovery</span>
                </div>
                <span className="text-[#a7d0d2] text-[10px]">96% match</span>
              </div>

              {/* Real Interactive Search Form inside the Dashboard Window */}
              <form onSubmit={handleSearchSubmit} className="relative group">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-[#d2434e]">
                  <Search className="w-4 h-4" />
                </div>
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Describe any concept... (e.g. machine to lift heavy loads)"
                  className="w-full pl-10 pr-24 py-2.5 bg-[#0b1219] border border-[#4d728e]/40 rounded-xl text-xs sm:text-sm text-white placeholder-[#f3faf0]/45 focus:outline-none focus:border-[#d2434e] focus:ring-1 focus:ring-[#d2434e]/40 transition-all shadow-inner"
                />
                <button
                  type="submit"
                  disabled={!searchQuery.trim()}
                  className="absolute inset-y-1.5 right-1.5 px-3 bg-[#d2434e] hover:bg-[#b83842] text-white font-semibold text-xs rounded-lg flex items-center gap-1 transition-all disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer shadow-sm"
                >
                  <span>Search</span>
                  <ArrowRight className="w-3 h-3" />
                </button>
              </form>

              {/* Resolved Concept Preview Card */}
              <div className="p-4 rounded-xl bg-[#0b1219]/60 border border-white/5 space-y-2.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-[#d2434e]" />
                    <h3 className="text-base font-bold text-white tracking-wide">Forklift</h3>
                  </div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-[#a7d0d2]/15 text-[#a7d0d2] border border-[#a7d0d2]/30">
                    Material Handling Equipment
                  </span>
                </div>

                <p className="text-xs text-[#f3faf0]/70 leading-relaxed">
                  A powered industrial vehicle equipped with hydraulic forks used to lift, transport, and stack heavy pallet loads.
                </p>

                {/* Subtle Tags */}
                <div className="flex flex-wrap gap-1.5 pt-1">
                  <span className="text-[10px] px-2 py-0.5 rounded-md bg-[#141d26] text-[#f3faf0]/70 border border-white/5">
                    Warehouses
                  </span>
                  <span className="text-[10px] px-2 py-0.5 rounded-md bg-[#141d26] text-[#f3faf0]/70 border border-white/5">
                    Lifting Loads
                  </span>
                  <span className="text-[10px] px-2 py-0.5 rounded-md bg-[#141d26] text-[#f3faf0]/70 border border-white/5">
                    Pallets
                  </span>
                </div>
              </div>

              {/* Window Footer with Test Query Link */}
              <div className="flex items-center justify-between pt-2 border-t border-white/5 text-xs">
                <span className="text-[11px] font-mono text-[#f3faf0]/50">
                  S-BERT + Knowledge Graph
                </span>
                <button
                  type="button"
                  onClick={() => handleTestQuery("What's that thing used in warehouses to lift large loads?")}
                  className="text-xs text-[#a7d0d2] hover:text-white transition-colors flex items-center gap-1 font-medium cursor-pointer"
                >
                  <span>Test query in engine</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ========================================================
          HOW UNKNOWN WORKS: 4-Step Technical Architecture
          ======================================================== */}
      <section id="how-it-works" className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-16 border-t border-white/5">
        <div className="text-center max-w-2xl mx-auto mb-12 space-y-2">
          <p className="text-xs font-mono text-[#a7d0d2] tracking-wider uppercase font-semibold">
            ARCHITECTURE
          </p>
          <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
            How UNKNOWN Resolves The Lexical Gap
          </h2>
          <p className="text-xs sm:text-sm text-[#f3faf0]/70 leading-relaxed">
            Traditional keyword search requires users to already know the exact technical term. UNKNOWN projects functional descriptions into vector space and traverses structured entity graphs to retrieve the precise concept.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {/* Step 1 */}
          <div className="p-5 rounded-2xl bg-[#141d26]/60 border border-[#4d728e]/25 hover:border-[#4d728e]/50 transition-all space-y-3 shadow-md">
            <div className="w-9 h-9 rounded-xl bg-[#0b1219] border border-[#d2434e]/30 flex items-center justify-center text-[#d2434e]">
              <Database className="w-4 h-4" />
            </div>
            <div className="space-y-1">
              <span className="text-[10px] font-mono text-[#a7d0d2] block">STEP 01</span>
              <h3 className="text-sm font-bold text-white">Semantic Embedding</h3>
            </div>
            <p className="text-xs text-[#f3faf0]/70 leading-relaxed">
              Query is encoded into a high-dimensional dense vector space using fine-tuned sentence transformers, capturing functional intent.
            </p>
          </div>

          {/* Step 2 */}
          <div className="p-5 rounded-2xl bg-[#141d26]/60 border border-[#4d728e]/25 hover:border-[#4d728e]/50 transition-all space-y-3 shadow-md">
            <div className="w-9 h-9 rounded-xl bg-[#0b1219] border border-[#a7d0d2]/30 flex items-center justify-center text-[#a7d0d2]">
              <Compass className="w-4 h-4" />
            </div>
            <div className="space-y-1">
              <span className="text-[10px] font-mono text-[#a7d0d2] block">STEP 02</span>
              <h3 className="text-sm font-bold text-white">Dense Vector Retrieval</h3>
            </div>
            <p className="text-xs text-[#f3faf0]/70 leading-relaxed">
              Fast approximate nearest-neighbour search (HNSW Cosine index) retrieves top candidate concepts across benchmark engineering domains.
            </p>
          </div>

          {/* Step 3 */}
          <div className="p-5 rounded-2xl bg-[#141d26]/60 border border-[#4d728e]/25 hover:border-[#4d728e]/50 transition-all space-y-3 shadow-md">
            <div className="w-9 h-9 rounded-xl bg-[#0b1219] border border-[#4d728e]/40 flex items-center justify-center text-[#f3faf0]">
              <Cpu className="w-4 h-4" />
            </div>
            <div className="space-y-1">
              <span className="text-[10px] font-mono text-[#a7d0d2] block">STEP 03</span>
              <h3 className="text-sm font-bold text-white">Cross-Encoder Reranking</h3>
            </div>
            <p className="text-xs text-[#f3faf0]/70 leading-relaxed">
              A deep cross-attention transformer computes fine-grained lexical and contextual relevance scores to eliminate ambiguous matches.
            </p>
          </div>

          {/* Step 4 */}
          <div className="p-5 rounded-2xl bg-[#141d26]/60 border border-[#4d728e]/25 hover:border-[#4d728e]/50 transition-all space-y-3 shadow-md">
            <div className="w-9 h-9 rounded-xl bg-[#0b1219] border border-[#d2434e]/40 flex items-center justify-center text-[#d2434e]">
              <Share2 className="w-4 h-4" />
            </div>
            <div className="space-y-1">
              <span className="text-[10px] font-mono text-[#a7d0d2] block">STEP 04</span>
              <h3 className="text-sm font-bold text-white">Graph Verification</h3>
            </div>
            <p className="text-xs text-[#f3faf0]/70 leading-relaxed">
              Knowledge graph traversal validates ontological relations (USED-IN, FUNCTION, CATEGORY) and renders an interactive 3D WebGL orbit graph.
            </p>
          </div>
        </div>
      </section>

      {/* ========================================================
          DOMAINS SECTION: 5 Benchmark Domains
          ======================================================== */}
      <section id="domains" className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-16 border-t border-white/5 mb-12">
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-8">
          <div>
            <p className="text-xs font-mono text-[#a7d0d2] tracking-wider uppercase font-semibold">
              EVALUATION
            </p>
            <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              Benchmark Domains
            </h2>
            <p className="text-xs sm:text-sm text-[#f3faf0]/70 mt-1">
              5 pre-indexed academic benchmark datasets for lexical-gap retrieval evaluation.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {domainList.map((domain, index) => (
            <div
              key={domain.name}
              className="p-5 rounded-2xl bg-[#141d26]/60 border border-[#4d728e]/25 hover:border-[#a7d0d2]/40 transition-all space-y-3 flex flex-col justify-between"
            >
              <div className="space-y-2">
                <div className="flex items-center justify-between text-[11px] font-mono text-[#a7d0d2]">
                  <span>DOMAIN 0{index + 1}</span>
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                </div>
                <h3 className="text-sm font-bold text-white leading-snug">{domain.name}</h3>
                <p className="text-xs text-[#f3faf0]/65 italic bg-[#0b1219]/60 p-2.5 rounded-xl border border-white/5">
                  &ldquo;{domain.sample}&rdquo;
                </p>
              </div>

              <button
                type="button"
                onClick={() => handleTestQuery(domain.sample)}
                className="w-full mt-3 py-2 px-3 rounded-xl bg-[#0b1219] hover:bg-[#1b2734] border border-[#4d728e]/35 hover:border-[#a7d0d2]/50 text-xs text-[#a7d0d2] hover:text-white font-medium flex items-center justify-between transition-all cursor-pointer"
              >
                <span>Try this query</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
};

export default DashboardPage;