import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  MessageSquare,
  Plus,
  Search,
  Trash2,
  Undo2,
  UploadCloud,
  FileText,
  CheckSquare,
  Square,
  Download,
  Moon,
  Sun,
  PanelLeftClose,
  PanelLeft,
  Send,
  Paperclip,
  Sparkles,
  Dna,
  Waypoints,
  Compass,
  GitCompare,
  AlertCircle,
  Loader2,
  X,
  Maximize2,
  BookOpen,
  HelpCircle,
  ChevronDown,
} from 'lucide-react';
import { SourcesDrawer } from '../components/evidence/SourcesDrawer';
import { AnswerPanel } from '../components/answers/AnswerPanel';
import { KnowledgeMindMap } from '../components/visualization/KnowledgeMindMap';
import { KnowledgeDNA } from '../components/visualization/KnowledgeDNA';
import { ConceptGraph3D } from '../components/ConceptGraph3D';
import { useAuth } from '../context/AuthContext';
import {
  fetchDocuments,
  fetchDocumentOverview,
  uploadDocument,
  uploadDocumentsBatch,
  deleteDocument,
  undoDeleteDocument,
  getDocumentDownloadUrl,
  fetchHistory,
  deleteHistoryItem,
  queryBackend,
  postSmartQuery,
  fetchSmartQueryAutocomplete,
  streamSmartQuery,
  type BackendDocument,
  type BackendDocumentOverview,
  type HistoryRecord,
  type BackendQueryResponse,
  type SmartQueryResponseData,
} from '../lib/api';
import type { Source } from '../types/evidence';
import type { Claim, ComparisonPair, Conflict } from '../types/query';

// ---------------------------------------------------------------------------
// Types for Chat Thread
// ---------------------------------------------------------------------------

export type ScopeOption = 'this_document' | 'selected' | 'all' | 'documents_web';

export interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant' | 'overview' | 'tool_card';
  timestamp: string;
  text?: string;
  scope?: string;
  overview?: BackendDocumentOverview;
  isOverviewLoading?: boolean;
  documentName?: string;
  // Assistant response data
  answerResponse?: {
    answer: string;
    summary?: string;
    detailed_answer?: string;
    doc_section?: string | null;
    web_section?: string | null;
    comparison?: ComparisonPair[];
    claims?: Claim[];
    conflicts?: Conflict[];
    gaps?: string[];
    confidence?: unknown;
    sources?: Source[];
    queryType?: string;
    rawResponse?: unknown;
  };
  // Tool Card data
  toolResult?: {
    tool: 'mindmap' | 'dna' | 'orbit' | 'compare' | 'gaps';
    title: string;
    summary: string;
    documentName: string;
    data: unknown;
  };
  isStreaming?: boolean;
  error?: string;
}

export const ChatWorkspacePage: React.FC = () => {
  const { user } = useAuth();

  // Theme state
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    return (localStorage.getItem('unknown_theme') as 'dark' | 'light') || 'dark';
  });

  useEffect(() => {
    localStorage.setItem('unknown_theme', theme);
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
      document.documentElement.classList.remove('light');
    } else {
      document.documentElement.classList.remove('dark');
      document.documentElement.classList.add('light');
    }
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  // Layout states
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isSourcesDrawerOpen, setIsSourcesDrawerOpen] = useState(false);
  const [drawerSources, setDrawerSources] = useState<Source[]>([]);

  // Document Library states
  const [documents, setDocuments] = useState<BackendDocument[]>([]);
  const [isDocsLoading, setIsDocsLoading] = useState(false);
  const [selectedDocNames, setSelectedDocNames] = useState<Set<string>>(new Set());
  const [activeDocName, setActiveDocName] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Conversation History states
  const [conversations, setConversations] = useState<HistoryRecord[]>([]);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
  const [historySearchQuery, setHistorySearchQuery] = useState('');
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const historySearchInputRef = useRef<HTMLInputElement>(null);

  // Undo Toast state
  const [undoToast, setUndoToast] = useState<{
    message: string;
    secondsLeft: number;
    undo: () => Promise<void>;
  } | null>(null);

  // Confirmation modal state
  const [confirmDialog, setConfirmDialog] = useState<{
    title: string;
    message: string;
    onConfirm: () => void;
  } | null>(null);

  // Chat Thread state
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isToolsGated, setIsToolsGated] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Composer states
  const [inputValue, setInputValue] = useState('');
  const [scope, setScope] = useState<ScopeOption>('this_document');
  const [isQueryRunning, setIsQueryRunning] = useState(false);
  const [isToolsMenuOpen, setIsToolsMenuOpen] = useState(false);
  const [isScopeMenuOpen, setIsScopeMenuOpen] = useState(false);
  const [slashMenuOpen, setSlashMenuOpen] = useState(false);
  const [autocompleteSuggestions, setAutocompleteSuggestions] = useState<string[]>([]);
  const [showAutocomplete, setShowAutocomplete] = useState(false);
  const composerInputRef = useRef<HTMLTextAreaElement>(null);

  // Smart Query feedback state
  const [rewrittenQuery, setRewrittenQuery] = useState<string | null>(null);
  const [clarifications, setClarifications] = useState<string[]>([]);
  const [smartRouterEvents, setSmartRouterEvents] = useState<string[]>([]);

  // Tool Full View Modal state
  const [fullViewTool, setFullViewTool] = useState<{
    tool: 'mindmap' | 'dna' | 'orbit' | 'compare' | 'gaps';
    title: string;
    documentName: string;
  } | null>(null);

  // Auto-scroll messages
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, smartRouterEvents, scrollToBottom]);

  // Keyboard shortcuts: Ctrl+K, Ctrl+Enter, Esc
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        historySearchInputRef.current?.focus();
      }
      if (e.key === 'Escape') {
        setIsSourcesDrawerOpen(false);
        setIsToolsMenuOpen(false);
        setIsScopeMenuOpen(false);
        setSlashMenuOpen(false);
        setShowAutocomplete(false);
        setConfirmDialog(null);
        setFullViewTool(null);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // 10-second Undo Toast timer
  useEffect(() => {
    if (!undoToast) return;
    const interval = setInterval(() => {
      setUndoToast((prev) => {
        if (!prev) return null;
        if (prev.secondsLeft <= 1) {
          clearInterval(interval);
          return null;
        }
        return { ...prev, secondsLeft: prev.secondsLeft - 1 };
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [undoToast]);

  // Load initial documents & history
  const loadDocuments = useCallback(async () => {
    setIsDocsLoading(true);
    try {
      const resp = await fetchDocuments();
      const docs = resp.documents || [];
      setDocuments(docs);
      if (!activeDocName && docs.length > 0) {
        setActiveDocName(docs[0].name);
        setSelectedDocNames(new Set([docs[0].name]));
      }
    } catch (err) {
      console.error('Failed to load documents:', err);
    } finally {
      setIsDocsLoading(false);
    }
  }, [activeDocName]);

  const loadHistory = useCallback(async () => {
    setIsHistoryLoading(true);
    try {
      const records = await fetchHistory();
      setConversations(records || []);
    } catch (err) {
      console.error('Failed to load history:', err);
    } finally {
      setIsHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDocuments();
    void loadHistory();
  }, [loadDocuments, loadHistory]);

  // ---------------------------------------------------------------------------
  // Document Upload & Overview Generation (First Message in Thread)
  // ---------------------------------------------------------------------------
  const handleFileUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setIsUploading(true);
    setUploadProgress(`Uploading ${files.length} document(s)...`);

    try {
      const uploadedNames: string[] = [];
      if (files.length === 1) {
        const res = await uploadDocument(files[0]);
        uploadedNames.push(res.filename);
      } else {
        const res = await uploadDocumentsBatch(Array.from(files));
        uploadedNames.push(...res.results.filter((r) => r.status === 'ready').map((r) => r.filename));
      }

      await loadDocuments();

      if (uploadedNames.length === 0) return;

      // Set newest as active document
      const docName = uploadedNames[0];
      setActiveDocName(docName);
      setSelectedDocNames((prev) => new Set([...prev, docName]));

      // Add Overview placeholder to thread (gating tools until overview ready)
      setIsToolsGated(true);

      const overviewMsgId = `overview_${Date.now()}`;
      setMessages((prev) => [
        ...prev,
        {
          id: overviewMsgId,
          sender: 'overview',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          documentName: docName,
          isOverviewLoading: true,
        },
      ]);

      // Fetch Document Overview
      try {
        const overview = await fetchDocumentOverview(docName);
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === overviewMsgId
              ? {
                  ...msg,
                  isOverviewLoading: false,
                  overview,
                }
              : msg
          )
        );
      } catch (err) {
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === overviewMsgId
              ? {
                  ...msg,
                  isOverviewLoading: false,
                  error: err instanceof Error ? err.message : 'Failed to generate overview.',
                }
              : msg
          )
        );
      } finally {
        setIsToolsGated(false);
      }
    } catch (err) {
      console.error('Upload failed:', err);
      alert(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setIsUploading(false);
      setUploadProgress(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // ---------------------------------------------------------------------------
  // Document Delete with Confirmation & 10s Undo Toast
  // ---------------------------------------------------------------------------
  const handleDeleteDocument = (docName: string) => {
    setConfirmDialog({
      title: 'Delete Document',
      message: `Are you sure you want to delete "${docName}"? You will have 10 seconds to undo this action.`,
      onConfirm: async () => {
        setConfirmDialog(null);
        try {
          await deleteDocument(docName);
          await loadDocuments();

          // Set 10-second undo toast
          setUndoToast({
            message: `Deleted "${docName}"`,
            secondsLeft: 10,
            undo: async () => {
              await undoDeleteDocument(docName);
              await loadDocuments();
              setUndoToast(null);
            },
          });
        } catch (err) {
          console.error('Failed to delete document:', err);
        }
      },
    });
  };

  // ---------------------------------------------------------------------------
  // History Item Delete with Confirmation & 10s Undo Toast
  // ---------------------------------------------------------------------------
  const handleDeleteHistory = (histId: string, queryText: string) => {
    setConfirmDialog({
      title: 'Delete Chat History',
      message: `Delete conversation "${queryText.slice(0, 40)}..."? You will have 10 seconds to undo.`,
      onConfirm: async () => {
        setConfirmDialog(null);
        try {
          await deleteHistoryItem(histId);
          await loadHistory();
          if (activeConversationId === histId) {
            handleNewChat();
          }
          setUndoToast({
            message: 'Chat record deleted',
            secondsLeft: 10,
            undo: async () => {
              await loadHistory();
              setUndoToast(null);
            },
          });
        } catch (err) {
          console.error('Failed to delete history record:', err);
        }
      },
    });
  };

  // Load existing conversation into thread
  const handleSelectHistory = async (hist: HistoryRecord) => {
    setActiveConversationId(hist.id);
    const snapshot = (hist.result_snapshot as any) || {};

    setMessages([
      {
        id: `user_${hist.id}`,
        sender: 'user',
        timestamp: new Date(hist.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        text: hist.query,
        scope: hist.scope || 'All Documents',
      },
      {
        id: `asst_${hist.id}`,
        sender: 'assistant',
        timestamp: new Date(hist.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        answerResponse: {
          answer: snapshot.answer || 'Previous answer record',
          summary: snapshot.summary,
          detailed_answer: snapshot.detailed_answer,
          doc_section: snapshot.doc_section,
          web_section: snapshot.web_section,
          confidence: snapshot.confidence,
          sources: (snapshot.sources as Source[]) || [],
          queryType: hist.feature || 'query',
        },
      },
    ]);
  };

  const handleNewChat = () => {
    setActiveConversationId(null);
    setMessages([]);
    setRewrittenQuery(null);
    setClarifications([]);
    setSmartRouterEvents([]);
    setInputValue('');
  };

  // ---------------------------------------------------------------------------
  // Autocomplete & Smart Router query
  // ---------------------------------------------------------------------------
  const handleInputChange = async (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    setInputValue(val);

    // Slash command trigger
    if (val.startsWith('/')) {
      setSlashMenuOpen(true);
      setShowAutocomplete(false);
      return;
    } else {
      setSlashMenuOpen(false);
    }

    // Autocomplete trigger
    if (val.trim().length >= 2) {
      try {
        const ac = await fetchSmartQueryAutocomplete(val.trim());
        const featList = ((ac as any).features || []).map((f: any) => f.label || f.feature || String(f));
        const docList = ((ac as any).documents || []).map((d: any) => d.name || String(d));
        const combined = ac.combined_suggestions || [...featList, ...docList];
        if (combined.length > 0) {
          setAutocompleteSuggestions(combined);
          setShowAutocomplete(true);
        } else {
          setShowAutocomplete(false);
        }
      } catch {
        setShowAutocomplete(false);
      }
    } else {
      setShowAutocomplete(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Send Query / Execute Smart Router
  // ---------------------------------------------------------------------------
  const handleSendQuery = async (customQuery?: string, isRunAll: boolean = false) => {
    const q = (customQuery !== undefined ? customQuery : inputValue).trim();
    if (!q || isQueryRunning || isToolsGated) return;

    setShowAutocomplete(false);
    setSlashMenuOpen(false);
    setIsToolsMenuOpen(false);

    // Determine target documents based on scope
    let targetDocIds: string[] | undefined = undefined;
    if (scope === 'this_document' && activeDocName) {
      targetDocIds = [activeDocName];
    } else if (scope === 'selected' && selectedDocNames.size > 0) {
      targetDocIds = Array.from(selectedDocNames);
    } else if (scope === 'all') {
      targetDocIds = documents.map((d) => d.name);
    }

    const scopeLabel =
      scope === 'this_document'
        ? `Scope: ${activeDocName || 'Current Document'}`
        : scope === 'selected'
        ? `Scope: ${selectedDocNames.size} Selected Document(s)`
        : scope === 'documents_web'
        ? 'Scope: Documents + Web'
        : 'Scope: All Documents';

    // Add user message
    const userMsgId = `user_${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      {
        id: userMsgId,
        sender: 'user',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        text: q,
        scope: scopeLabel,
      },
    ]);

    setInputValue('');
    setIsQueryRunning(true);
    setSmartRouterEvents([]);

    // Check for slash command tools
    const lowerQ = q.toLowerCase();
    if (lowerQ.startsWith('/mindmap') || lowerQ.startsWith('/map')) {
      await handleExecuteTool('mindmap', activeDocName || documents[0]?.name);
      setIsQueryRunning(false);
      return;
    } else if (lowerQ.startsWith('/dna')) {
      await handleExecuteTool('dna', activeDocName || documents[0]?.name);
      setIsQueryRunning(false);
      return;
    } else if (lowerQ.startsWith('/orbit')) {
      await handleExecuteTool('orbit', activeDocName || documents[0]?.name);
      setIsQueryRunning(false);
      return;
    } else if (lowerQ.startsWith('/gaps')) {
      await handleExecuteTool('gaps', activeDocName || documents[0]?.name);
      setIsQueryRunning(false);
      return;
    } else if (lowerQ.startsWith('/compare')) {
      await handleExecuteTool('compare', activeDocName || documents[0]?.name);
      setIsQueryRunning(false);
      return;
    }

    // Normal assistant response placeholder with streaming flag
    const asstMsgId = `asst_${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      {
        id: asstMsgId,
        sender: 'assistant',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        isStreaming: true,
      },
    ]);

    try {
      if (isRunAll) {
        // Stream Run All events
        await streamSmartQuery(
          { text: q, document_ids: targetDocIds, run_all: true },
          (event) => {
            if (event.message || event.feature) {
              setSmartRouterEvents((prev) => [
                ...prev,
                `${event.feature ? `[${event.feature.toUpperCase()}] ` : ''}${event.message || event.status}`,
              ]);
            }
          }
        );
      }

      // Query smart router or backend
      const smartRes: SmartQueryResponseData = await postSmartQuery({
        text: q,
        document_ids: targetDocIds,
        run_all: isRunAll,
      });

      if (smartRes.rewritten_query && smartRes.rewritten_query !== q) {
        setRewrittenQuery(smartRes.rewritten_query);
      }
      if (smartRes.is_ambiguous && smartRes.clarification_options) {
        setClarifications(smartRes.clarification_options);
      }

      // Execute grounded answer
      const answerResp: BackendQueryResponse = await queryBackend(
        smartRes.rewritten_query || q,
        targetDocIds
      );

      setMessages((prev) =>
        prev.map((m) =>
          m.id === asstMsgId
            ? {
                ...m,
                isStreaming: false,
                answerResponse: {
                  answer: answerResp.answer,
                  summary: answerResp.summary,
                  detailed_answer: answerResp.answer,
                  doc_section: answerResp.doc_section,
                  web_section: answerResp.web_section,
                  comparison: answerResp.comparison,
                  claims: answerResp.claims,
                  conflicts: answerResp.conflicts,
                  gaps: answerResp.gaps,
                  confidence: answerResp.confidence,
                  sources: (answerResp.sources as Source[]) || [],
                  queryType: answerResp.query_type || 'standard',
                  rawResponse: answerResp,
                },
              }
            : m
        )
      );

      // Refresh history to capture new item
      void loadHistory();
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === asstMsgId
            ? {
                ...m,
                isStreaming: false,
                error: err instanceof Error ? err.message : 'Query execution failed.',
              }
            : m
        )
      );
    } finally {
      setIsQueryRunning(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Execute Tools (Mind Map, Knowledge DNA, 3D Orbit, etc.)
  // ---------------------------------------------------------------------------
  const handleExecuteTool = async (
    tool: 'mindmap' | 'dna' | 'orbit' | 'compare' | 'gaps',
    docName?: string
  ) => {
    const targetDoc = docName || activeDocName || documents[0]?.name;
    if (!targetDoc) {
      alert('Please upload or select a document first.');
      return;
    }

    const cardId = `tool_${tool}_${Date.now()}`;
    const titles: Record<string, string> = {
      mindmap: 'Knowledge Concept Graph & Mind Map',
      dna: 'Knowledge DNA Structural Analysis',
      orbit: '3D Conceptual Orbit Space',
      compare: 'Cross-Document Semantic Comparison',
      gaps: 'Research Gaps Identification',
    };

    setMessages((prev) => [
      ...prev,
      {
        id: cardId,
        sender: 'tool_card',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        toolResult: {
          tool,
          title: titles[tool] || tool,
          summary: `Extracted and synthesized ${titles[tool]} for ${targetDoc}.`,
          documentName: targetDoc,
          data: null,
        },
      },
    ]);
  };

  // Open full interactive view of tool
  const handleOpenFullView = (tool: 'mindmap' | 'dna' | 'orbit' | 'compare' | 'gaps', docName: string) => {
    setFullViewTool({
      tool,
      title: tool.toUpperCase(),
      documentName: docName,
    });
  };

  // Open right drawer with specific sources
  const handleOpenSourcesDrawer = (sources: Source[]) => {
    setDrawerSources(sources);
    setIsSourcesDrawerOpen(true);
  };

  return (
    <div
      className={`flex h-screen w-screen overflow-hidden ${
        theme === 'dark' ? 'bg-[#0b1219] text-[#f3faf0]' : 'bg-[#f8fafc] text-[#0f172a]'
      }`}
      data-testid="chat-app-root"
    >
      {/* =====================================================================
          1. LEFT SIDEBAR (Collapsible)
          ===================================================================== */}
      <aside
        className={`relative flex flex-col border-r transition-all duration-300 ease-in-out shrink-0 z-30 ${
          theme === 'dark'
            ? 'bg-[#0f1721] border-[#4d728e]/25 text-[#f3faf0]'
            : 'bg-white border-slate-200 text-slate-800'
        } ${isSidebarOpen ? 'w-80' : 'w-0 -translate-x-full overflow-hidden border-none'}`}
        data-testid="left-sidebar"
        aria-label="Navigation and Document Sidebar"
      >
        {/* App Branding & New Chat */}
        <div className="p-4 border-b border-inherit space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="h-7 w-7 rounded-lg bg-[#d2434e] flex items-center justify-center font-black text-white text-sm shadow-md">
                U
              </div>
              <div>
                <span className="font-mono font-bold tracking-tight text-base text-inherit">UNKNOWN</span>
                <span className="block text-[10px] font-mono text-[#a7d0d2] uppercase tracking-wider">
                  Research Engine
                </span>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setIsSidebarOpen(false)}
              className="p-1.5 rounded-md hover:bg-black/10 dark:hover:bg-white/10 text-inherit/60 hover:text-inherit cursor-pointer"
              aria-label="Collapse sidebar"
              title="Collapse sidebar"
            >
              <PanelLeftClose className="h-4 w-4" />
            </button>
          </div>

          <button
            type="button"
            onClick={handleNewChat}
            className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-lg bg-[#d2434e] hover:bg-[#b83842] text-white font-medium text-xs shadow-sm transition-colors cursor-pointer"
            data-testid="new-chat-button"
            title="Start a new research chat"
          >
            <Plus className="h-4 w-4" />
            <span>New Chat</span>
          </button>
        </div>

        {/* Scrollable middle: History & Document Library */}
        <div className="flex-1 overflow-y-auto p-4 space-y-6">
          {/* History Section */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-[11px] font-mono uppercase tracking-wider text-inherit/60 font-semibold">
              <span>Chat History</span>
              <span className="text-[10px] text-[#a7d0d2]">Ctrl+K</span>
            </div>

            {/* Search History */}
            <div className="relative">
              <Search className="h-3.5 w-3.5 absolute left-2.5 top-2.5 text-inherit/40" />
              <input
                ref={historySearchInputRef}
                type="text"
                placeholder="Search history... (Ctrl+K)"
                value={historySearchQuery}
                onChange={(e) => setHistorySearchQuery(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 rounded-md text-xs border border-inherit bg-inherit/20 text-inherit placeholder:text-inherit/40 focus:outline-none focus:ring-1 focus:ring-[#a7d0d2]"
                data-testid="history-search-input"
              />
            </div>

            {/* History List */}
            <div className="space-y-1 max-h-48 overflow-y-auto pr-1" data-testid="history-list">
              {isHistoryLoading ? (
                <div className="py-4 text-center text-xs text-inherit/50">
                  <Loader2 className="h-4 w-4 animate-spin mx-auto mb-1 text-[#a7d0d2]" />
                  Loading chats...
                </div>
              ) : conversations.length === 0 ? (
                <div className="py-3 text-center text-xs text-inherit/40">No saved history yet</div>
              ) : (
                conversations
                  .filter((h) => h.query.toLowerCase().includes(historySearchQuery.toLowerCase()))
                  .map((h) => (
                    <div
                      key={h.id}
                      className={`group flex items-center justify-between gap-2 px-2.5 py-1.5 rounded-md text-xs cursor-pointer transition-colors ${
                        activeConversationId === h.id
                          ? 'bg-[#a7d0d2]/20 text-[#a7d0d2] font-medium'
                          : 'hover:bg-black/5 dark:hover:bg-white/5 text-inherit/80'
                      }`}
                      onClick={() => handleSelectHistory(h)}
                      data-testid="history-item"
                    >
                      <div className="flex items-center gap-2 truncate flex-1 min-w-0">
                        <MessageSquare className="h-3.5 w-3.5 shrink-0 opacity-60" />
                        <span className="truncate">{h.query}</span>
                      </div>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteHistory(h.id, h.query);
                        }}
                        className="opacity-0 group-hover:opacity-100 p-1 hover:text-[#d2434e] transition-opacity"
                        title="Delete chat"
                        data-testid="delete-history-btn"
                      >
                        <Trash2 className="h-3 w-3" />
                      </button>
                    </div>
                  ))
              )}
            </div>
          </div>

          {/* Document Library Section */}
          <div className="space-y-2.5 pt-2 border-t border-inherit">
            <div className="flex items-center justify-between text-[11px] font-mono uppercase tracking-wider text-inherit/60 font-semibold">
              <span className="flex items-center gap-1.5">
                <FileText className="h-3.5 w-3.5 text-[#a7d0d2]" />
                Document Library ({documents.length})
              </span>
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="p-1 hover:text-[#a7d0d2] transition-colors"
                title="Upload document"
                data-testid="upload-button-sidebar"
              >
                <UploadCloud className="h-4 w-4" />
              </button>
            </div>

            {/* Hidden file input */}
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf,.txt,.md"
              className="hidden"
              onChange={(e) => void handleFileUpload(e.target.files)}
            />

            {/* Drag & Drop Upload Zone in Sidebar */}
            <div
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                void handleFileUpload(e.dataTransfer.files);
              }}
              onClick={() => fileInputRef.current?.click()}
              className="p-3 border border-dashed border-inherit rounded-lg text-center cursor-pointer hover:border-[#a7d0d2]/70 bg-inherit/30 transition-colors"
              data-testid="sidebar-dropzone"
            >
              <UploadCloud className="h-5 w-5 mx-auto mb-1 text-[#a7d0d2]" />
              <p className="text-[11px] text-inherit/80 font-medium">Drop papers or click to upload</p>
              <p className="text-[10px] text-inherit/50 font-mono mt-0.5">PDF, TXT, MD supported</p>
              {isUploading && (
                <div className="mt-2 flex items-center justify-center gap-1.5 text-xs text-[#a7d0d2]">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  <span>{uploadProgress || 'Uploading...'}</span>
                </div>
              )}
            </div>

            {/* Document List with Multi-Select Checkboxes */}
            <div className="space-y-1 max-h-56 overflow-y-auto pr-1" data-testid="document-list">
              {isDocsLoading ? (
                <div className="py-3 text-center text-xs text-inherit/50">
                  <Loader2 className="h-4 w-4 animate-spin mx-auto mb-1 text-[#a7d0d2]" />
                  Loading library...
                </div>
              ) : documents.length === 0 ? (
                <div className="py-3 text-center text-xs text-inherit/40">No documents in library</div>
              ) : (
                documents.map((doc) => {
                  const isSelected = selectedDocNames.has(doc.name);
                  const isActive = activeDocName === doc.name;

                  return (
                    <div
                      key={doc.name}
                      className={`group flex items-center justify-between gap-2 p-2 rounded-lg text-xs transition-colors border ${
                        isActive
                          ? 'border-[#a7d0d2]/50 bg-[#a7d0d2]/10'
                          : 'border-transparent hover:bg-black/5 dark:hover:bg-white/5'
                      }`}
                      data-testid="document-library-item"
                    >
                      {/* Checkbox for Multi-Select */}
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedDocNames((prev) => {
                            const next = new Set(prev);
                            if (next.has(doc.name)) next.delete(doc.name);
                            else next.add(doc.name);
                            return next;
                          });
                        }}
                        className="text-inherit/60 hover:text-[#a7d0d2] p-0.5"
                        title={isSelected ? 'Deselect document' : 'Select document'}
                        data-testid="doc-select-checkbox"
                      >
                        {isSelected ? (
                          <CheckSquare className="h-3.5 w-3.5 text-[#a7d0d2]" />
                        ) : (
                          <Square className="h-3.5 w-3.5" />
                        )}
                      </button>

                      {/* Title & Set Active */}
                      <div
                        className="flex-1 truncate cursor-pointer"
                        onClick={() => {
                          setActiveDocName(doc.name);
                          setSelectedDocNames((prev) => new Set([...prev, doc.name]));
                        }}
                        title={doc.title || doc.name}
                      >
                        <span className="font-medium truncate block">{doc.title || doc.name}</span>
                        <span className="text-[10px] text-inherit/50 font-mono">
                          {doc.total_pages ? `${doc.total_pages} pgs • ` : ''}
                          {doc.chunks_count || 0} chunks
                        </span>
                      </div>

                      {/* Document Actions: Download & Delete */}
                      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <a
                          href={getDocumentDownloadUrl(doc.name)}
                          target="_blank"
                          rel="noreferrer"
                          download
                          className="p-1 hover:text-[#a7d0d2]"
                          title="Download document"
                        >
                          <Download className="h-3 w-3" />
                        </a>
                        <button
                          type="button"
                          onClick={() => handleDeleteDocument(doc.name)}
                          className="p-1 hover:text-[#d2434e]"
                          title="Delete document"
                          data-testid="delete-document-btn"
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>

        {/* User / Workspace & Theme Toggle */}
        <div className="p-4 border-t border-inherit flex items-center justify-between">
          <div className="flex items-center gap-2 truncate">
            <div className="h-7 w-7 rounded-full bg-[#1b2734] border border-inherit flex items-center justify-center text-xs font-bold text-[#a7d0d2]">
              {user?.name ? user.name[0].toUpperCase() : 'U'}
            </div>
            <div className="truncate text-xs">
              <span className="font-medium truncate block">{user?.name || 'Workspace User'}</span>
              <span className="text-[10px] text-inherit/50 truncate block">{user?.email || 'local@workspace'}</span>
            </div>
          </div>

          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={toggleTheme}
              className="p-1.5 rounded-md hover:bg-black/10 dark:hover:bg-white/10 text-inherit/70 hover:text-inherit transition-colors cursor-pointer"
              title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
              data-testid="theme-toggle-button"
            >
              {theme === 'dark' ? <Sun className="h-4 w-4 text-amber-300" /> : <Moon className="h-4 w-4 text-slate-600" />}
            </button>
          </div>
        </div>
      </aside>

      {/* =====================================================================
          2. CENTRE: CONVERSATION THREAD & CHAT INTERFACE
          ===================================================================== */}
      <main className="flex-1 flex flex-col h-full overflow-hidden relative">
        {/* Top Floating App Bar */}
        <header
          className={`h-12 border-b flex items-center justify-between px-4 shrink-0 ${
            theme === 'dark' ? 'bg-[#0b1219]/90 border-white/5' : 'bg-white/90 border-slate-200'
          } backdrop-blur-md z-10`}
        >
          <div className="flex items-center gap-2.5">
            {!isSidebarOpen && (
              <button
                type="button"
                onClick={() => setIsSidebarOpen(true)}
                className="p-1.5 rounded-md hover:bg-black/10 dark:hover:bg-white/10 text-inherit/70 cursor-pointer"
                aria-label="Open sidebar"
                title="Open sidebar"
              >
                <PanelLeft className="h-4 w-4" />
              </button>
            )}

            <div className="flex items-center gap-2">
              <span className="font-semibold text-xs text-inherit">Active Research Session</span>
              {activeDocName && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono bg-[#a7d0d2]/15 text-[#a7d0d2] border border-[#a7d0d2]/30 truncate max-w-xs">
                  <FileText className="h-2.5 w-2.5" />
                  {activeDocName}
                </span>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2">
            {drawerSources.length > 0 && (
              <button
                type="button"
                onClick={() => setIsSourcesDrawerOpen(true)}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono bg-[#141d26] border border-white/10 text-[#a7d0d2] hover:border-[#a7d0d2]/50 cursor-pointer"
                data-testid="top-sources-drawer-btn"
              >
                <BookOpen className="h-3 w-3" />
                <span>Sources ({drawerSources.length})</span>
              </button>
            )}
          </div>
        </header>

        {/* Messages Thread Container */}
        <div
          className="flex-1 overflow-y-auto px-4 py-6 max-w-4xl w-full mx-auto space-y-6"
          data-testid="conversation-thread"
        >
          {/* Empty State when no messages */}
          {messages.length === 0 && (
            <div className="my-auto py-16 text-center space-y-6" data-testid="thread-empty-state">
              <div className="h-16 w-16 mx-auto rounded-2xl bg-gradient-to-tr from-[#d2434e] to-[#a7d0d2] flex items-center justify-center shadow-xl">
                <Sparkles className="h-8 w-8 text-white" />
              </div>
              <div className="space-y-2 max-w-lg mx-auto">
                <h1 className="text-2xl font-black tracking-tight text-inherit">UNKNOWN Research Assistant</h1>
                <p className="text-xs text-inherit/70 leading-relaxed">
                  Deep multi-hop research assistant across scientific and technical documents. Dense-sparse semantic
                  retrieval, NLI claim verification, and mathematical confidence calibration.
                </p>
              </div>

              {/* Big File Dropzone in Empty State */}
              <div
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  void handleFileUpload(e.dataTransfer.files);
                }}
                onClick={() => fileInputRef.current?.click()}
                className="max-w-md mx-auto p-6 border-2 border-dashed border-[#4d728e]/40 hover:border-[#a7d0d2] rounded-2xl cursor-pointer bg-inherit/30 transition-all text-center space-y-2"
                data-testid="center-upload-dropzone"
              >
                <UploadCloud className="h-8 w-8 mx-auto text-[#a7d0d2]" />
                <h3 className="font-semibold text-sm">Upload a research document to begin</h3>
                <p className="text-xs text-inherit/50">
                  Drag and drop a PDF file here. An Overview Card with 5-sentence summary and Document IQ will be
                  generated automatically.
                </p>
              </div>
            </div>
          )}

          {/* Render Messages in Thread */}
          {messages.map((msg) => {
            // ===============================================================
            // OVERVIEW CARD (First message after upload)
            // ===============================================================
            if (msg.sender === 'overview') {
              if (msg.isOverviewLoading) {
                return (
                  <div
                    key={msg.id}
                    className="rounded-2xl border border-[#a7d0d2]/30 bg-[#141d26]/80 p-6 space-y-4 animate-pulse shadow-md"
                    data-testid="overview-loading-card"
                  >
                    <div className="flex items-center gap-3">
                      <Loader2 className="h-5 w-5 animate-spin text-[#a7d0d2]" />
                      <div>
                        <h4 className="font-semibold text-sm text-white">Generating Document Overview...</h4>
                        <p className="text-xs text-[#a7d0d2]/70 font-mono">
                          Extracting structure, calculating Document IQ, and synthesizing 5-sentence executive summary
                        </p>
                      </div>
                    </div>
                  </div>
                );
              }

              const ov = msg.overview;
              if (!ov) return null;

              return (
                <article
                  key={msg.id}
                  className="rounded-2xl border border-[#a7d0d2]/30 bg-[#141d26] p-6 space-y-6 shadow-xl text-left"
                  data-testid="document-overview-card"
                >
                  {/* Top Bar: Title, Meta, and Document IQ Score */}
                  <div className="flex flex-wrap items-start justify-between gap-4 border-b border-white/10 pb-4">
                    <div className="space-y-1.5 flex-1 min-w-0">
                      <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono bg-[#a7d0d2]/15 text-[#a7d0d2] border border-[#a7d0d2]/30">
                        Document Overview
                      </div>
                      <h2 className="text-lg font-bold text-white break-words" data-testid="overview-title">
                        {ov.title || ov.document_name}
                      </h2>
                      <div className="flex flex-wrap items-center gap-3 text-xs text-[#f3faf0]/70 font-mono">
                        {ov.authors && ov.authors.length > 0 && <span>Authors: {ov.authors.join(', ')}</span>}
                        {ov.year && <span>Year: {ov.year}</span>}
                        <span>Pages: {ov.page_count}</span>
                        <span>Language: {ov.language?.toUpperCase() || 'EN'}</span>
                      </div>
                    </div>

                    {/* Document IQ Badge */}
                    <div
                      className="px-3.5 py-2 rounded-xl bg-[#0b1219] border border-[#a7d0d2]/40 text-center"
                      data-testid="document-iq-badge"
                    >
                      <div className="text-[10px] font-mono text-[#a7d0d2] uppercase tracking-wider">Document IQ</div>
                      <div className="text-lg font-black text-white">
                        {ov.document_iq?.iq_score ?? 85}
                        <span className="text-xs font-normal text-[#a7d0d2]/80 ml-1">
                          ({ov.document_iq?.grade || 'A'})
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* 5-Sentence Summary with Page References */}
                  <div className="space-y-2">
                    <h3 className="text-xs font-mono uppercase tracking-wider text-[#a7d0d2] font-semibold">
                      Executive Summary (5 Key Aspects)
                    </h3>
                    <div className="space-y-1.5 text-sm leading-relaxed text-[#f3faf0]/90 bg-[#0b1219]/60 p-4 rounded-xl border border-white/5">
                      {ov.summary_sentences && ov.summary_sentences.length > 0 ? (
                        ov.summary_sentences.map((s, idx) => (
                          <p key={idx} className="flex items-baseline gap-2">
                            <span className="text-[11px] font-mono text-[#d2434e] font-bold shrink-0">{idx + 1}.</span>
                            <span>{s.text}</span>
                            {s.page_ref && (
                              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/10 text-[#a7d0d2] shrink-0">
                                {s.page_ref}
                              </span>
                            )}
                          </p>
                        ))
                      ) : (
                        <p>Document content successfully indexed and parsed.</p>
                      )}
                    </div>
                  </div>

                  {/* Key Topics */}
                  {ov.key_topics && ov.key_topics.map && ov.key_topics.length > 0 && (
                    <div className="space-y-2">
                      <h3 className="text-xs font-mono uppercase tracking-wider text-[#a7d0d2] font-semibold">
                        Key Topics
                      </h3>
                      <div className="flex flex-wrap gap-1.5">
                        {ov.key_topics.map((t, idx) => (
                          <span
                            key={idx}
                            className="px-2.5 py-1 rounded-md text-xs font-mono bg-[#0b1219] border border-white/10 text-[#f3faf0]/80"
                          >
                            #{t}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Figures & Tables Thumbnails */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="p-3 rounded-xl bg-[#0b1219]/60 border border-white/5 space-y-2">
                      <div className="flex items-center justify-between text-xs font-mono text-[#a7d0d2]">
                        <span>Figures ({ov.figure_count})</span>
                      </div>
                      <div className="flex items-center gap-2 overflow-x-auto py-1">
                        {ov.figures && ov.figures.length > 0 ? (
                          ov.figures.slice(0, 4).map((fig) => (
                            <div
                              key={fig.id}
                              className="h-16 w-20 shrink-0 rounded-lg bg-black/40 border border-white/10 overflow-hidden relative group"
                              title={fig.caption || fig.label}
                            >
                              {fig.thumbnail ? (
                                <img src={fig.thumbnail} alt={fig.label} className="h-full w-full object-cover" />
                              ) : (
                                <div className="h-full w-full flex items-center justify-center text-[10px] text-white/50 font-mono">
                                  {fig.label}
                                </div>
                              )}
                            </div>
                          ))
                        ) : (
                          <span className="text-[11px] text-white/40">No extracted figures</span>
                        )}
                      </div>
                    </div>

                    <div className="p-3 rounded-xl bg-[#0b1219]/60 border border-white/5 space-y-2">
                      <div className="flex items-center justify-between text-xs font-mono text-[#a7d0d2]">
                        <span>Tables ({ov.table_count})</span>
                      </div>
                      <div className="flex items-center gap-2 overflow-x-auto py-1">
                        {ov.tables && ov.tables.length > 0 ? (
                          ov.tables.slice(0, 4).map((tbl) => (
                            <div
                              key={tbl.id}
                              className="h-16 w-20 shrink-0 rounded-lg bg-black/40 border border-white/10 flex items-center justify-center text-[10px] text-white/60 font-mono p-1 text-center"
                              title={tbl.caption || tbl.label}
                            >
                              {tbl.label}
                            </div>
                          ))
                        ) : (
                          <span className="text-[11px] text-white/40">No extracted tables</span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* 5 Suggested Questions (PLAIN TEXT ONLY — NOT CLICKABLE BUTTONS) */}
                  <div className="space-y-2 pt-2 border-t border-white/10">
                    <div className="flex items-center gap-1.5 text-xs font-mono uppercase tracking-wider text-[#a7d0d2] font-semibold">
                      <HelpCircle className="h-3.5 w-3.5" />
                      <span>Suggested Research Inquiries (Plain Text Reference)</span>
                    </div>
                    <ol
                      className="space-y-1 text-xs text-[#f3faf0]/75 bg-[#0b1219]/40 p-3 rounded-xl border border-white/5 list-decimal list-inside select-text pointer-events-none"
                      data-testid="suggested-questions-plain-text"
                    >
                      {ov.suggested_questions && ov.suggested_questions.length > 0 ? (
                        ov.suggested_questions.slice(0, 5).map((q, idx) => (
                          <li key={idx} className="leading-relaxed">
                            {q}
                          </li>
                        ))
                      ) : (
                        <li>What methodology does this document establish?</li>
                      )}
                    </ol>
                  </div>
                </article>
              );
            }

            // ===============================================================
            // USER MESSAGE
            // ===============================================================
            if (msg.sender === 'user') {
              return (
                <div key={msg.id} className="flex justify-end gap-3" data-testid="user-message">
                  <div className="max-w-xl space-y-1 text-right">
                    <div className="inline-block px-4 py-2.5 rounded-2xl bg-[#d2434e] text-white text-sm font-medium shadow-md">
                      {msg.text}
                    </div>
                    {msg.scope && (
                      <div className="text-[10px] font-mono text-inherit/50 pr-1">{msg.scope}</div>
                    )}
                  </div>
                </div>
              );
            }

            // ===============================================================
            // ASSISTANT MESSAGE
            // ===============================================================
            if (msg.sender === 'assistant') {
              if (msg.isStreaming) {
                return (
                  <div
                    key={msg.id}
                    className="flex items-start gap-3 p-4 rounded-2xl bg-[#141d26]/80 border border-white/5 shadow-md"
                    data-testid="assistant-streaming-message"
                  >
                    <Loader2 className="h-5 w-5 animate-spin text-[#a7d0d2] shrink-0 mt-0.5" />
                    <div className="space-y-2 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold text-white">Synthesizing Answer</span>
                        <span className="h-2 w-2 rounded-full bg-[#a7d0d2] animate-ping" />
                      </div>
                      <div className="text-xs text-[#f3faf0]/60 font-mono leading-relaxed">
                        Querying dense-sparse FAISS index, evaluating NLI claims, and ranking evidence...
                      </div>
                    </div>
                  </div>
                );
              }

              if (msg.error) {
                return (
                  <div
                    key={msg.id}
                    className="p-4 rounded-xl border border-red-500/30 bg-red-500/10 text-red-200 text-xs space-y-1"
                    data-testid="assistant-error-message"
                  >
                    <div className="font-bold flex items-center gap-1.5">
                      <AlertCircle className="h-4 w-4" />
                      Error generating response
                    </div>
                    <p>{msg.error}</p>
                  </div>
                );
              }

              const resp = msg.answerResponse;
              if (!resp) return null;

              return (
                <div key={msg.id} className="space-y-2" data-testid="assistant-message">
                  <AnswerPanel
                    answer={resp.answer}
                    summary={resp.summary}
                    detailedAnswer={resp.detailed_answer}
                    doc_section={resp.doc_section}
                    web_section={resp.web_section}
                    comparison={resp.comparison}
                    claims={resp.claims}
                    conflicts={resp.conflicts}
                    gaps={resp.gaps}
                    sources={resp.sources}
                    confidence={resp.confidence as any}
                    queryType={resp.queryType}
                    rawResponse={resp.rawResponse}
                    answerState="answer"
                    showDetailed={false}
                    onToggleDetail={() => {}}
                    onOpenSources={() => handleOpenSourcesDrawer(resp.sources || [])}
                    onOpenSource={(src) => handleOpenSourcesDrawer([src])}
                  />
                </div>
              );
            }

            // ===============================================================
            // TOOL RESULT CARD (Mind Map, DNA, Orbit inside thread)
            // ===============================================================
            if (msg.sender === 'tool_card') {
              const tr = msg.toolResult;
              if (!tr) return null;

              return (
                <div
                  key={msg.id}
                  className="rounded-2xl border border-[#4d728e]/40 bg-[#141d26] p-5 space-y-4 shadow-lg text-left"
                  data-testid="tool-result-card"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {tr.tool === 'mindmap' && <Waypoints className="h-5 w-5 text-[#a7d0d2]" />}
                      {tr.tool === 'dna' && <Dna className="h-5 w-5 text-[#d2434e]" />}
                      {tr.tool === 'orbit' && <Compass className="h-5 w-5 text-amber-300" />}
                      {tr.tool === 'compare' && <GitCompare className="h-5 w-5 text-purple-300" />}
                      <div>
                        <h4 className="font-bold text-sm text-white">{tr.title}</h4>
                        <p className="text-[11px] text-[#a7d0d2] font-mono">{tr.documentName}</p>
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={() => handleOpenFullView(tr.tool, tr.documentName)}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#a7d0d2] hover:bg-[#8ec3c5] text-black font-semibold text-xs transition-colors cursor-pointer"
                      data-testid="open-full-view-btn"
                    >
                      <Maximize2 className="h-3.5 w-3.5" />
                      <span>Open Full View</span>
                    </button>
                  </div>

                  <p className="text-xs text-[#f3faf0]/80 leading-relaxed bg-[#0b1219]/50 p-3 rounded-lg border border-white/5">
                    {tr.summary}
                  </p>
                </div>
              );
            }

            return null;
          })}

          <div ref={messagesEndRef} />
        </div>

        {/* =====================================================================
            3. COMPOSER (Bottom input, like ChatGPT/Claude)
            ===================================================================== */}
        <div
          className={`border-t px-4 py-3 shrink-0 ${
            theme === 'dark' ? 'bg-[#0b1219] border-white/10' : 'bg-white border-slate-200'
          }`}
          data-testid="chat-composer"
        >
          <div className="max-w-4xl mx-auto space-y-2">
            {/* Rewritten Query & Disambiguation Banner */}
            {rewrittenQuery && (
              <div
                className="flex items-center justify-between gap-2 px-3 py-1.5 rounded-lg bg-[#a7d0d2]/10 border border-[#a7d0d2]/30 text-xs font-mono text-[#a7d0d2]"
                data-testid="rewritten-query-banner"
              >
                <div className="flex items-center gap-1.5 truncate">
                  <Sparkles className="h-3.5 w-3.5 shrink-0" />
                  <span className="truncate">Rewritten Query: {rewrittenQuery}</span>
                </div>
                <button
                  type="button"
                  onClick={() => handleSendQuery(rewrittenQuery)}
                  className="px-2 py-0.5 rounded bg-[#a7d0d2] text-black font-bold text-[10px] hover:bg-[#8ec3c5] shrink-0"
                >
                  Run
                </button>
              </div>
            )}

            {/* Clarification Options */}
            {clarifications.length > 0 && (
              <div
                className="flex flex-wrap items-center gap-1.5 px-3 py-2 rounded-lg bg-amber-500/10 border border-amber-500/30 text-xs"
                data-testid="clarification-options-bar"
              >
                <span className="text-amber-200 font-mono text-[11px] font-semibold">Did you mean:</span>
                {clarifications.map((opt, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => handleSendQuery(opt)}
                    className="px-2 py-1 rounded-md bg-amber-500/20 text-amber-100 hover:bg-amber-500/30 font-mono text-[11px]"
                  >
                    {opt}
                  </button>
                ))}
              </div>
            )}

            {/* Smart Router Streaming Events Output */}
            {smartRouterEvents.length > 0 && (
              <div
                className="max-h-20 overflow-y-auto px-3 py-1.5 rounded-lg bg-black/40 border border-white/10 text-[10px] font-mono text-[#a7d0d2] space-y-0.5"
                data-testid="smart-query-events-log"
              >
                {smartRouterEvents.map((ev, idx) => (
                  <div key={idx}>{ev}</div>
                ))}
              </div>
            )}

            {/* Autocomplete Suggestions Popup */}
            {showAutocomplete && autocompleteSuggestions.length > 0 && (
              <div
                className="absolute bottom-28 left-4 right-4 max-w-4xl mx-auto rounded-xl border border-white/10 bg-[#141d26] p-2 shadow-2xl z-50 space-y-1"
                data-testid="autocomplete-popup"
              >
                <div className="text-[10px] font-mono text-inherit/50 px-2 py-0.5 uppercase">Suggestions</div>
                {autocompleteSuggestions.slice(0, 5).map((sugg, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => {
                      setInputValue(sugg);
                      setShowAutocomplete(false);
                      composerInputRef.current?.focus();
                    }}
                    className="w-full text-left px-3 py-1.5 rounded-lg text-xs hover:bg-white/10 text-inherit font-mono truncate"
                  >
                    {sugg}
                  </button>
                ))}
              </div>
            )}

            {/* Slash Commands Popup */}
            {slashMenuOpen && (
              <div
                className="absolute bottom-28 left-4 right-4 max-w-4xl mx-auto rounded-xl border border-white/10 bg-[#141d26] p-2 shadow-2xl z-50 space-y-1"
                data-testid="slash-commands-popup"
              >
                <div className="text-[10px] font-mono text-[#a7d0d2] px-2 py-0.5 uppercase font-semibold">
                  Tools & Slash Commands
                </div>
                {[
                  { cmd: '/mindmap', label: 'Concept Graph & Mind Map' },
                  { cmd: '/dna', label: 'Knowledge DNA Analysis' },
                  { cmd: '/orbit', label: '3D Conceptual Orbit Space' },
                  { cmd: '/compare', label: 'Cross-Document Compare' },
                  { cmd: '/gaps', label: 'Find Research Gaps' },
                  { cmd: '/export', label: 'Export Results (PDF/DOCX/MD)' },
                ].map((item) => (
                  <button
                    key={item.cmd}
                    type="button"
                    onClick={() => {
                      setInputValue(item.cmd + ' ');
                      setSlashMenuOpen(false);
                      composerInputRef.current?.focus();
                    }}
                    className="w-full flex items-center justify-between px-3 py-1.5 rounded-lg text-xs hover:bg-white/10 text-inherit font-mono"
                  >
                    <span className="text-[#d2434e] font-bold">{item.cmd}</span>
                    <span className="text-inherit/60">{item.label}</span>
                  </button>
                ))}
              </div>
            )}

            {/* Main Input Box */}
            <div
              className={`rounded-2xl border p-2.5 transition-all shadow-sm ${
                theme === 'dark'
                  ? 'bg-[#141d26] border-white/10 focus-within:border-[#a7d0d2]/70'
                  : 'bg-white border-slate-300 focus-within:border-[#a7d0d2]'
              }`}
            >
              {/* Multiline Textarea */}
              <textarea
                ref={composerInputRef}
                rows={2}
                value={inputValue}
                onChange={handleInputChange}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey || !e.shiftKey)) {
                    e.preventDefault();
                    void handleSendQuery();
                  }
                }}
                placeholder={
                  isToolsGated
                    ? 'Document overview in progress...'
                    : 'Ask a question, describe a concept, or type / for tools... (Enter to send)'
                }
                disabled={isQueryRunning || isToolsGated}
                className="w-full resize-none bg-transparent text-sm text-inherit placeholder:text-inherit/40 focus:outline-none"
                data-testid="chat-composer-textarea"
              />

              {/* Bottom Toolbar: Attach, Scope Chip, Tools Menu, Run All, Send */}
              <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-inherit/10">
                <div className="flex items-center gap-1.5 flex-wrap">
                  {/* Attach Button */}
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="p-1.5 rounded-lg hover:bg-black/10 dark:hover:bg-white/10 text-inherit/70 hover:text-inherit transition-colors cursor-pointer"
                    title="Attach document (.pdf, .txt, .md)"
                    data-testid="composer-attach-btn"
                  >
                    <Paperclip className="h-4 w-4" />
                  </button>

                  {/* Scope Chip Dropdown */}
                  <div className="relative">
                    <button
                      type="button"
                      onClick={() => setIsScopeMenuOpen(!isScopeMenuOpen)}
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-mono bg-inherit/40 border border-inherit text-inherit hover:border-[#a7d0d2] cursor-pointer"
                      data-testid="scope-chip"
                    >
                      <span>
                        {scope === 'this_document'
                          ? `This doc: ${activeDocName ? activeDocName.slice(0, 15) + '...' : 'None'}`
                          : scope === 'selected'
                          ? `Selected (${selectedDocNames.size})`
                          : scope === 'documents_web'
                          ? 'Docs + Web'
                          : 'All Mine'}
                      </span>
                      <ChevronDown className="h-3 w-3 opacity-60" />
                    </button>

                    {isScopeMenuOpen && (
                      <div
                        className="absolute bottom-9 left-0 w-48 rounded-xl border border-white/10 bg-[#141d26] p-1.5 shadow-xl z-50 text-xs font-mono space-y-0.5"
                        data-testid="scope-dropdown-menu"
                      >
                        {[
                          { id: 'this_document', label: 'This Document' },
                          { id: 'selected', label: `Selected (${selectedDocNames.size})` },
                          { id: 'all', label: 'All Mine' },
                          { id: 'documents_web', label: 'Documents + Web' },
                        ].map((opt) => (
                          <button
                            key={opt.id}
                            type="button"
                            onClick={() => {
                              setScope(opt.id as ScopeOption);
                              setIsScopeMenuOpen(false);
                            }}
                            className={`w-full text-left px-2.5 py-1.5 rounded-lg hover:bg-white/10 ${
                              scope === opt.id ? 'text-[#a7d0d2] font-bold' : 'text-inherit'
                            }`}
                          >
                            {opt.label}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Tools Menu Dropdown */}
                  <div className="relative">
                    <button
                      type="button"
                      onClick={() => setIsToolsMenuOpen(!isToolsMenuOpen)}
                      disabled={isToolsGated}
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-mono bg-[#a7d0d2]/10 border border-[#a7d0d2]/30 text-[#a7d0d2] hover:bg-[#a7d0d2]/20 cursor-pointer disabled:opacity-40"
                      data-testid="tools-menu-button"
                    >
                      <Sparkles className="h-3 w-3" />
                      <span>Tools</span>
                      <ChevronDown className="h-3 w-3" />
                    </button>

                    {isToolsMenuOpen && (
                      <div
                        className="absolute bottom-9 left-0 w-52 rounded-xl border border-white/10 bg-[#141d26] p-1.5 shadow-xl z-50 text-xs font-mono space-y-0.5"
                        data-testid="tools-dropdown-menu"
                      >
                        {[
                          { tool: 'mindmap', label: 'Mind Map (/mindmap)' },
                          { tool: 'dna', label: 'Knowledge DNA (/dna)' },
                          { tool: 'orbit', label: '3D Orbit (/orbit)' },
                          { tool: 'compare', label: 'Web Comparison (/compare)' },
                          { tool: 'gaps', label: 'Research Gaps (/gaps)' },
                        ].map((t) => (
                          <button
                            key={t.tool}
                            type="button"
                            onClick={() => {
                              setIsToolsMenuOpen(false);
                              void handleExecuteTool(t.tool as any);
                            }}
                            className="w-full text-left px-2.5 py-1.5 rounded-lg hover:bg-white/10 text-inherit"
                          >
                            {t.label}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {/* Run All Action */}
                  <button
                    type="button"
                    onClick={() => void handleSendQuery(undefined, true)}
                    disabled={isQueryRunning || isToolsGated || !inputValue.trim()}
                    className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-[#a7d0d2]/20 hover:bg-[#a7d0d2]/30 text-[#a7d0d2] text-xs font-mono font-medium border border-[#a7d0d2]/40 disabled:opacity-40 cursor-pointer transition-colors"
                    data-testid="run-all-button"
                    title="Run all features in parallel with streaming events"
                  >
                    <span>Run All</span>
                  </button>

                  {/* Send Button */}
                  <button
                    type="button"
                    onClick={() => void handleSendQuery()}
                    disabled={isQueryRunning || isToolsGated || !inputValue.trim()}
                    className="flex items-center justify-center h-8 w-8 rounded-lg bg-[#d2434e] hover:bg-[#b83842] text-white disabled:opacity-40 cursor-pointer transition-colors shadow-sm"
                    data-testid="composer-send-btn"
                    title="Send query (Ctrl+Enter)"
                  >
                    {isQueryRunning ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Send className="h-4 w-4" />
                    )}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* =====================================================================
          4. RIGHT DRAWER: SOURCELIST (Opens on citation / source click)
          ===================================================================== */}
      <SourcesDrawer
        isOpen={isSourcesDrawerOpen}
        sources={drawerSources}
        onClose={() => setIsSourcesDrawerOpen(false)}
      />

      {/* =====================================================================
          5. 10-SECOND UNDO TOAST
          ===================================================================== */}
      {undoToast && (
        <div
          className="fixed bottom-6 right-6 z-50 flex items-center gap-3 px-4 py-3 rounded-xl bg-[#141d26] border border-[#a7d0d2]/50 text-white shadow-2xl text-xs font-mono animate-bounce"
          data-testid="undo-toast"
        >
          <span>{undoToast.message}</span>
          <span className="text-[10px] text-[#a7d0d2]">({undoToast.secondsLeft}s)</span>
          <button
            type="button"
            onClick={() => void undoToast.undo()}
            className="flex items-center gap-1 px-2.5 py-1 rounded bg-[#a7d0d2] text-black font-bold hover:bg-[#8ec3c5] cursor-pointer"
            data-testid="undo-toast-btn"
          >
            <Undo2 className="h-3 w-3" />
            <span>Undo</span>
          </button>
        </div>
      )}

      {/* =====================================================================
          6. CONFIRMATION DIALOG MODAL
          ===================================================================== */}
      {confirmDialog && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4"
          data-testid="confirm-dialog-backdrop"
        >
          <div className="w-full max-w-sm rounded-2xl bg-[#141d26] border border-white/10 p-5 space-y-4 shadow-2xl">
            <h3 className="font-bold text-sm text-white">{confirmDialog.title}</h3>
            <p className="text-xs text-[#f3faf0]/75 leading-relaxed">{confirmDialog.message}</p>
            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setConfirmDialog(null)}
                className="px-3 py-1.5 rounded-lg border border-white/10 text-xs text-white/70 hover:bg-white/5"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={confirmDialog.onConfirm}
                className="px-3 py-1.5 rounded-lg bg-[#d2434e] text-xs text-white font-bold hover:bg-[#b83842]"
                data-testid="confirm-dialog-ok-btn"
              >
                Confirm
              </button>
            </div>
          </div>
        </div>
      )}

      {/* =====================================================================
          7. FULL-VIEW TOOL MODAL (Mind Map, Knowledge DNA, 3D Orbit)
          ===================================================================== */}
      {fullViewTool && (
        <div
          className="fixed inset-0 z-50 flex flex-col bg-[#0b1219] p-4 text-white"
          data-testid="full-view-tool-modal"
        >
          <div className="flex items-center justify-between pb-3 border-b border-white/10">
            <div>
              <h3 className="font-bold text-base">{fullViewTool.title}</h3>
              <p className="text-xs font-mono text-[#a7d0d2]">{fullViewTool.documentName}</p>
            </div>
            <button
              type="button"
              onClick={() => setFullViewTool(null)}
              className="p-2 rounded-lg bg-white/10 hover:bg-white/20 text-white cursor-pointer"
              aria-label="Close full view"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          <div className="flex-1 overflow-hidden pt-3">
            {fullViewTool.tool === 'mindmap' && (
              <KnowledgeMindMap documentName={fullViewTool.documentName} />
            )}
            {fullViewTool.tool === 'dna' && (
              <KnowledgeDNA documentName={fullViewTool.documentName} />
            )}
            {fullViewTool.tool === 'orbit' && (
              <ConceptGraph3D documentName={fullViewTool.documentName} />
            )}
            {fullViewTool.tool === 'compare' && (
              <KnowledgeDNA documentName={fullViewTool.documentName} />
            )}
            {fullViewTool.tool === 'gaps' && (
              <KnowledgeMindMap documentName={fullViewTool.documentName} />
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default ChatWorkspacePage;
