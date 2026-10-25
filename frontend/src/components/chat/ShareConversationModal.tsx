import React, { useState } from 'react';
import {
  Share2,
  X,
  Copy,
  Check,
  ShieldCheck,
  Loader2,
  Trash2,
} from 'lucide-react';
import type { Conversation } from '../../types/chat';
import { createShareLink, revokeShareLink, type ShareResponse } from '../../lib/api';

interface ShareConversationModalProps {
  isOpen: boolean;
  onClose: () => void;
  conversation: Conversation;
}

export const ShareConversationModal: React.FC<ShareConversationModalProps> = ({
  isOpen,
  onClose,
  conversation,
}) => {
  const [includeDocContent, setIncludeDocContent] = useState(false);
  const [expiryHours, setExpiryHours] = useState(72);
  const [isGenerating, setIsGenerating] = useState(false);
  const [shareData, setShareData] = useState<ShareResponse | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleGenerateShare = async () => {
    setIsGenerating(true);
    setError(null);
    try {
      const res = await createShareLink(conversation, includeDocContent, expiryHours);
      setShareData(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to generate share link');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleCopyLink = () => {
    if (!shareData) return;
    const fullUrl = `${window.location.origin}${shareData.share_url}`;
    navigator.clipboard.writeText(fullUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  const handleRevoke = async () => {
    if (!shareData) return;
    try {
      await revokeShareLink(shareData.share_token);
      setShareData(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to revoke link');
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-[#111922] border border-[#4d728e]/40 rounded-2xl max-w-md w-full shadow-2xl p-5 space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/10 pb-3">
          <div className="flex items-center gap-2">
            <Share2 className="w-5 h-5 text-[#d2434e]" />
            <div>
              <h3 className="text-sm font-bold text-white">Share Research Conversation</h3>
              <p className="text-[11px] text-[#f3faf0]/50 truncate max-w-[260px]">{conversation.title}</p>
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

        {/* Info notice */}
        <div className="p-3 rounded-xl bg-[#0b1219] border border-white/5 space-y-2 text-xs text-[#f3faf0]/75">
          <div className="flex items-center gap-1.5 text-[#a7d0d2] font-semibold">
            <ShieldCheck className="w-4 h-4" />
            <span>Cryptographically Secure & Revocable</span>
          </div>
          <p className="text-[11px] leading-relaxed">
            Anyone with the link will be able to view this conversation's questions, verified answers, and public source
            citations in read-only mode. Internal server paths and credentials are never exposed.
          </p>
        </div>

        {/* Options */}
        {!shareData ? (
          <div className="space-y-3 pt-1">
            {/* Expiry selector */}
            <div className="space-y-1">
              <label className="text-xs font-medium text-white">Link Expiration</label>
              <select
                value={expiryHours}
                onChange={(e) => setExpiryHours(Number(e.target.value))}
                className="w-full bg-[#16222d] text-xs text-white p-2 rounded-lg border border-white/10 focus:border-[#a7d0d2]/40 focus:outline-none"
              >
                <option value={24}>24 Hours</option>
                <option value={72}>72 Hours (3 Days)</option>
                <option value={168}>7 Days</option>
                <option value={720}>30 Days</option>
              </select>
            </div>

            {/* Include document content toggle */}
            <label className="flex items-start gap-2 text-xs text-[#f3faf0]/80 cursor-pointer pt-1">
              <input
                type="checkbox"
                checked={includeDocContent}
                onChange={(e) => setIncludeDocContent(e.target.checked)}
                className="rounded mt-0.5"
              />
              <span>Include full document excerpts in share payload (optional)</span>
            </label>

            {error && <p className="text-xs text-red-400">{error}</p>}

            <div className="pt-2 flex justify-end gap-2">
              <button
                type="button"
                onClick={onClose}
                className="px-3.5 py-1.5 rounded-lg border border-white/10 text-xs text-[#f3faf0]/75 hover:bg-white/5 cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleGenerateShare}
                disabled={isGenerating}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-[#d2434e] hover:bg-[#b0303b] text-white text-xs font-semibold cursor-pointer disabled:opacity-50"
              >
                {isGenerating && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                <span>Create Share Link</span>
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-3 pt-1">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-white">Your Public Share Link</label>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  readOnly
                  value={`${window.location.origin}${shareData.share_url}`}
                  className="flex-1 bg-[#16222d] text-xs text-white p-2 rounded-lg border border-[#a7d0d2]/40 font-mono"
                />
                <button
                  type="button"
                  onClick={handleCopyLink}
                  className="px-3 py-2 rounded-lg bg-[#1b2734] hover:bg-[#223244] border border-[#a7d0d2]/50 text-[#a7d0d2] text-xs font-medium flex items-center gap-1 cursor-pointer"
                >
                  {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copied ? 'Copied' : 'Copy'}</span>
                </button>
              </div>
            </div>

            <div className="pt-3 border-t border-white/5 flex items-center justify-between">
              <button
                type="button"
                onClick={handleRevoke}
                className="text-xs text-rose-400 hover:text-rose-300 flex items-center gap-1 cursor-pointer"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Revoke this link</span>
              </button>

              <button
                type="button"
                onClick={onClose}
                className="px-3.5 py-1.5 rounded-lg bg-white/10 hover:bg-white/15 text-xs text-white font-medium cursor-pointer"
              >
                Done
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
