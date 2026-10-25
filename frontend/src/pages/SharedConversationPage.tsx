import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Loader2, AlertCircle } from 'lucide-react';
import { getSharedConversation } from '../lib/api';
import type { ChatMessage } from '../types/chat';
import { ChatMessageItem } from '../components/chat/ChatMessageItem';
import { SourcesDrawer } from '../components/evidence/SourcesDrawer';
import type { Source } from '../types/evidence';

export const SharedConversationPage: React.FC = () => {
  const { token } = useParams<{ token: string }>();
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sharedData, setSharedData] = useState<{
    title: string;
    createdAt: string;
    messages: ChatMessage[];
  } | null>(null);
  const [drawerSources, setDrawerSources] = useState<Source[] | null>(null);

  useEffect(() => {
    if (!token) return;
    setIsLoading(true);
    getSharedConversation(token)
      .then((data) => {
        setSharedData(data as { title: string; createdAt: string; messages: ChatMessage[] });
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Shared conversation not found or expired.');
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [token]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#0c1218] flex items-center justify-center p-4">
        <div className="flex flex-col items-center gap-3 text-[#a7d0d2]">
          <Loader2 className="w-8 h-8 animate-spin" />
          <span className="text-sm font-medium">Loading shared research transcript...</span>
        </div>
      </div>
    );
  }

  if (error || !sharedData) {
    return (
      <div className="min-h-screen bg-[#0c1218] flex items-center justify-center p-4">
        <div className="bg-[#121922] border border-red-500/30 rounded-2xl p-6 max-w-md w-full text-center space-y-4 shadow-2xl">
          <AlertCircle className="w-8 h-8 text-red-400 mx-auto" />
          <h2 className="text-base font-bold text-white">Conversation Unavailable</h2>
          <p className="text-xs text-[#f3faf0]/70 leading-relaxed">{error || 'This link has expired or was revoked.'}</p>
          <Link
            to="/search"
            className="inline-block px-4 py-2 rounded-xl bg-[#d2434e] text-white text-xs font-semibold hover:bg-[#b0303b] transition-colors"
          >
            Go to UNKNOWN Research
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0c1218] text-white flex flex-col">
      {/* Top Bar */}
      <header className="sticky top-0 z-40 h-14 border-b border-[#4d728e]/25 bg-[#0e161f]/90 backdrop-blur-md px-4 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-6 h-6 rounded-lg overflow-hidden border border-[#d2434e]/50 bg-[#080d12]">
            <img src="/unknown-logo.jpg" alt="UNKNOWN" className="w-full h-full object-cover" />
          </div>
          <span className="font-extrabold tracking-wider text-white text-sm">UNKNOWN</span>
          <span className="text-xs text-[#f3faf0]/40 font-mono">/ Shared Transcript</span>
        </div>

        <Link
          to="/search"
          className="px-3 py-1.5 rounded-lg border border-[#4d728e]/40 hover:border-[#a7d0d2]/60 bg-[#16222d] text-xs font-medium text-[#a7d0d2] hover:text-white transition-colors"
        >
          Open App
        </Link>
      </header>

      {/* Main Conversation Thread */}
      <main className="flex-1 max-w-4xl w-full mx-auto p-4 sm:p-6 space-y-4">
        <div className="border-b border-white/10 pb-4 mb-2">
          <h1 className="text-lg font-bold text-white">{sharedData.title}</h1>
          <p className="text-xs text-[#f3faf0]/50 font-mono mt-1">Shared read-only research transcript</p>
        </div>

        <div className="space-y-4">
          {sharedData.messages.map((msg) => (
            <ChatMessageItem
              key={msg.id}
              message={msg}
              onOpenSourcesDrawer={(srcs) => setDrawerSources(srcs)}
            />
          ))}
        </div>
      </main>

      {/* Sources Drawer */}
      <SourcesDrawer
        isOpen={drawerSources !== null}
        sources={drawerSources || []}
        onClose={() => setDrawerSources(null)}
      />
    </div>
  );
};
