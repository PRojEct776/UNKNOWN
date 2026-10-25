import React, { useEffect } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Files, X } from 'lucide-react';
import type { Evidence, Source } from '../../types/evidence';
import { SourceList } from './SourceList';

interface SourcesDrawerProps {
  isOpen: boolean;
  sources: Source[];
  evidence?: Evidence[];
  onClose: () => void;
}

export const SourcesDrawer: React.FC<SourcesDrawerProps> = ({ isOpen, sources, onClose }) => {
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-[60] flex justify-end">
          <motion.button
            type="button"
            aria-label="Close sources drawer"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="absolute inset-0 bg-[#07090e]/75 backdrop-blur-sm"
          />
          <motion.aside
            role="dialog"
            aria-modal="true"
            aria-labelledby="sources-title"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className="relative flex h-full w-full max-w-lg flex-col border-l border-[#4d728e]/35 bg-[#0f1721] shadow-2xl"
          >
            <header className="flex items-center justify-between border-b border-white/10 px-5 py-4">
              <div className="flex items-center gap-2">
                <Files className="h-4 w-4 text-[#a7d0d2]" aria-hidden="true" />
                <div>
                  <h2 id="sources-title" className="text-sm font-semibold text-white">Sources</h2>
                  <p className="text-[11px] text-[#f3faf0]/50">Canonical sources in deterministic reliability order</p>
                </div>
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close sources"
                className="rounded-md p-2 text-[#f3faf0]/65 hover:bg-white/10 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </header>
            <div className="flex-1 space-y-3 overflow-y-auto p-5">
              <SourceList sources={sources} />
            </div>
            <footer className="border-t border-white/10 px-5 py-3 text-[11px] text-[#f3faf0]/45">
              Deterministic source ranking via UNKNOWN engine.
            </footer>
          </motion.aside>
        </div>
      )}
    </AnimatePresence>
  );
};
