import React from 'react';
import type { WorkspaceHistoryItem } from '../types/query';
import { Plus, History, Trash2, Clock, MessageSquare, ChevronRight, Compass, Database, FileText } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

interface SearchSidebarProps {
  history: WorkspaceHistoryItem[];
  activeId: string | null;
  onSelectHistory: (item: WorkspaceHistoryItem) => void;
  onNewSearch: () => void;
  onClearHistory: () => void;
  onOpenDocuments?: () => void;
}

export const SearchSidebar: React.FC<SearchSidebarProps> = ({
  history,
  activeId,
  onSelectHistory,
  onNewSearch,
  onClearHistory,
  onOpenDocuments,
}) => {
  return (
    <aside className="w-full shrink-0 h-52 border-b border-white/8 bg-[#10171d] flex flex-col justify-between lg:w-64 lg:h-[calc(100vh-4rem)] lg:border-b-0 lg:border-r xl:w-72">
      {/* Top Action: New Inquiry Button in Coral Red */}
      <div className="p-4 border-b border-white/8">
        <button
          onClick={onNewSearch}
          className="w-full rounded-md border border-white/10 bg-[#151f28] px-4 py-2.5 text-sm font-semibold text-white flex items-center justify-center gap-2 transition-colors hover:border-[#a7d0d2]/40 hover:bg-[#1a2731] cursor-pointer"
        >
          <Plus className="w-4 h-4 stroke-[2.5]" />
          <span>New investigation</span>
        </button>
      </div>

      {/* History List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
        <div className="flex items-center justify-between px-2 py-1 text-[11px] font-mono text-[#f3faf0]/70">
          <div className="flex items-center gap-1.5">
            <History className="w-3.5 h-3.5 text-[#d2434e]" />
            <span>SEARCH HISTORY</span>
          </div>
          <span className="text-[10px] text-[#a7d0d2] bg-[#a7d0d2]/15 px-2 py-0.5 rounded-full border border-[#a7d0d2]/30">
            {history.length}
          </span>
        </div>

        {history.length === 0 ? (
          <div className="py-12 px-3 text-center text-[#f3faf0]/50 text-xs">
            <MessageSquare className="w-6 h-6 mx-auto mb-2 text-[#f3faf0]/30" />
            <p className="font-medium text-[#f3faf0]/80">No searches yet</p>
            <p className="text-[11px] mt-1 text-[#f3faf0]/50">
              Inquiries you run will appear here
            </p>
          </div>
        ) : (
          <AnimatePresence initial={false}>
            {history.map((item) => {
              const isActive = activeId === item.id;
              return (
                <motion.button
                  key={item.id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -10 }}
                  transition={{ duration: 0.18 }}
                  onClick={() => onSelectHistory(item)}
                  className={`w-full text-left p-3 rounded-xl transition-all cursor-pointer group flex flex-col gap-1 border ${
                    isActive
                      ? 'bg-[#1b2734] border-[#d2434e] text-white shadow-md'
                      : 'bg-[#141d26] hover:bg-[#1b2734]/70 border-white/5 hover:border-[#a7d0d2]/30 text-[#f3faf0]/80'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-xs font-medium line-clamp-2 leading-relaxed text-white">
                      "{item.query}"
                    </span>
                    <ChevronRight
                      className={`w-3.5 h-3.5 shrink-0 mt-0.5 transition-transform ${
                        isActive
                          ? 'text-[#d2434e] translate-x-0.5'
                          : 'text-stone-400 group-hover:text-[#a7d0d2]'
                      }`}
                    />
                  </div>

                  <div className="flex items-center justify-between text-[10px] text-[#f3faf0]/75 mt-0.5">
                    <span className="font-semibold text-[#d2434e] font-mono">{item.mode} · {item.result.concept.name}</span>
                    <div className="flex items-center gap-1 font-mono text-[9px] text-[#f3faf0]/50">
                      <Clock className="w-2.5 h-2.5" />
                      <span>{item.timestamp}</span>
                    </div>
                  </div>
                </motion.button>
              );
            })}
          </AnimatePresence>
        )}
      </div>

      {/* Sidebar Footer */}
      <div className="p-3 border-t border-white/8 bg-[#0b1219] space-y-2">
        {onOpenDocuments && (
          <button
            onClick={onOpenDocuments}
            className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-lg bg-[#141d26] hover:bg-[#1b2734] border border-[#a7d0d2]/30 text-xs font-semibold text-white transition-all cursor-pointer shadow-sm hover:border-[#a7d0d2]"
            title="Inspect and upload research documents"
          >
            <FileText className="w-3.5 h-3.5 text-[#d2434e]" />
            <span>Corpus Documents</span>
          </button>
        )}

        {/* Quick Architecture & Domains Triggers */}
        <div className="grid grid-cols-2 gap-1.5">
          <button
            onClick={() => window.dispatchEvent(new CustomEvent('open-unknown-info', { detail: 'how-it-works' }))}
            className="flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-lg bg-[#141d26] hover:bg-[#1b2734] border border-[#4d728e]/30 text-[11px] text-[#f3faf0]/80 hover:text-white transition-all cursor-pointer"
            title="How UNKNOWN Works"
          >
            <Compass className="w-3 h-3 text-[#d2434e]" />
            <span>How it works</span>
          </button>

          <button
            onClick={() => window.dispatchEvent(new CustomEvent('open-unknown-info', { detail: 'domains' }))}
            className="flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-lg bg-[#141d26] hover:bg-[#1b2734] border border-[#4d728e]/30 text-[11px] text-[#f3faf0]/80 hover:text-white transition-all cursor-pointer"
            title="Controlled Academic Domains"
          >
            <Database className="w-3 h-3 text-[#a7d0d2]" />
            <span>Domains</span>
          </button>
        </div>

        {history.length > 0 && (
          <button
            onClick={onClearHistory}
            className="w-full py-1.5 px-3 rounded-lg text-[11px] text-[#f3faf0]/60 hover:text-rose-400 hover:bg-rose-500/15 flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
          >
            <Trash2 className="w-3 h-3" />
            <span>Clear History</span>
          </button>
        )}
      </div>
    </aside>
  );
};
