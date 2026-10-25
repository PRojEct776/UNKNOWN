import React, { useState } from 'react';
import {
  Download,
  X,
  FileText,
  FileCode,
  Archive,
} from 'lucide-react';
import type { Conversation } from '../../types/chat';
import { exportAllConversationsJson } from '../../lib/conversationStore';
import { exportSessionToMarkdown, exportSessionToHtml } from '../../lib/exportUtils';
import type { WorkspaceHistoryItem } from '../../types/query';

interface DownloadHistoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  conversations: Conversation[];
  userId: string;
}

export const DownloadHistoryModal: React.FC<DownloadHistoryModalProps> = ({
  isOpen,
  onClose,
  conversations,
  userId,
}) => {
  const [downloadingFormat, setDownloadingFormat] = useState<string | null>(null);

  if (!isOpen) return null;

  // Convert active conversation messages to WorkspaceHistoryItem for session exports
  const handleExportMarkdown = () => {
    setDownloadingFormat('markdown');
    try {
      const historyItems: WorkspaceHistoryItem[] = [];
      conversations.forEach((conv) => {
        conv.messages.forEach((msg) => {
          if (msg.result) {
            historyItems.push({
              id: msg.id,
              query: msg.text || msg.result.request.query,
              mode: msg.feature || msg.result.request.mode,
              result: msg.result,
              timestamp: msg.timestamp,
            });
          }
        });
      });
      exportSessionToMarkdown(historyItems, userId);
    } finally {
      setDownloadingFormat(null);
    }
  };

  const handleExportHtml = () => {
    setDownloadingFormat('html');
    try {
      const historyItems: WorkspaceHistoryItem[] = [];
      conversations.forEach((conv) => {
        conv.messages.forEach((msg) => {
          if (msg.result) {
            historyItems.push({
              id: msg.id,
              query: msg.text || msg.result.request.query,
              mode: msg.feature || msg.result.request.mode,
              result: msg.result,
              timestamp: msg.timestamp,
            });
          }
        });
      });
      exportSessionToHtml(historyItems, userId);
    } finally {
      setDownloadingFormat(null);
    }
  };

  const handleExportJson = () => {
    setDownloadingFormat('json');
    try {
      exportAllConversationsJson(conversations, userId);
    } finally {
      setDownloadingFormat(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-[#111922] border border-[#4d728e]/40 rounded-2xl max-w-md w-full shadow-2xl p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-white/10 pb-3">
          <div className="flex items-center gap-2">
            <Download className="w-5 h-5 text-[#d2434e]" />
            <div>
              <h3 className="text-sm font-bold text-white">Download Research History</h3>
              <p className="text-[11px] text-[#f3faf0]/50 font-mono">
                {conversations.length} {conversations.length === 1 ? 'conversation' : 'conversations'} recorded
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 text-white/50 hover:text-white rounded-lg cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <p className="text-xs text-[#f3faf0]/75 leading-relaxed">
          Export your complete evidence-grounded research transcripts, cited documents, and confidence metadata.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 pt-1">
          {/* Markdown (.md) */}
          <button
            type="button"
            onClick={handleExportMarkdown}
            disabled={downloadingFormat !== null}
            className="flex flex-col items-center justify-center p-3 rounded-xl bg-[#16222e] hover:bg-[#1c2c3b] border border-white/10 hover:border-[#a7d0d2]/40 transition-colors cursor-pointer text-center group"
          >
            <FileText className="w-6 h-6 text-[#a7d0d2] mb-1.5 group-hover:scale-110 transition-transform" />
            <span className="text-xs font-semibold text-white">Markdown</span>
            <span className="text-[10px] text-[#f3faf0]/50 font-mono">.md format</span>
          </button>

          {/* Styled Printable HTML (.html) */}
          <button
            type="button"
            onClick={handleExportHtml}
            disabled={downloadingFormat !== null}
            className="flex flex-col items-center justify-center p-3 rounded-xl bg-[#16222e] hover:bg-[#1c2c3b] border border-white/10 hover:border-[#a7d0d2]/40 transition-colors cursor-pointer text-center group"
          >
            <FileCode className="w-6 h-6 text-emerald-300 mb-1.5 group-hover:scale-110 transition-transform" />
            <span className="text-xs font-semibold text-white">Printable HTML</span>
            <span className="text-[10px] text-[#f3faf0]/50 font-mono">Print to PDF</span>
          </button>

          {/* Structured JSON (.json) */}
          <button
            type="button"
            onClick={handleExportJson}
            disabled={downloadingFormat !== null}
            className="flex flex-col items-center justify-center p-3 rounded-xl bg-[#16222e] hover:bg-[#1c2c3b] border border-white/10 hover:border-[#a7d0d2]/40 transition-colors cursor-pointer text-center group"
          >
            <Archive className="w-6 h-6 text-amber-300 mb-1.5 group-hover:scale-110 transition-transform" />
            <span className="text-xs font-semibold text-white">Raw JSON</span>
            <span className="text-[10px] text-[#f3faf0]/50 font-mono">Structured data</span>
          </button>
        </div>

        <div className="pt-2 border-t border-white/5 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-3.5 py-1.5 rounded-lg border border-white/10 text-xs text-[#f3faf0]/75 hover:bg-white/5 cursor-pointer"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
