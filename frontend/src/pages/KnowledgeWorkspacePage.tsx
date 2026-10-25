import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  PanelLeft,
  PanelLeftClose,
  Share2,
  AlertCircle,
  RotateCcw,
} from 'lucide-react';
import { SlidingSidebar } from '../components/chat/SlidingSidebar';
import { ChatComposer } from '../components/chat/ChatComposer';
import { ChatMessageItem } from '../components/chat/ChatMessageItem';
import { SourcesDrawer } from '../components/evidence/SourcesDrawer';
import { ShareConversationModal } from '../components/chat/ShareConversationModal';
import { DownloadHistoryModal } from '../components/chat/DownloadHistoryModal';
import { useAuth } from '../context/AuthContext';
import {
  fetchDocuments,
  fetchDocumentOverview,
  uploadDocument,
  uploadDocumentsBatch,
  deleteDocument,
  undoDeleteDocument,
  queryBackend,
  reasonBackend,
  verifyClaimBackend,
  compareBackend,
  findResearchGapsBackend,
  runDebateBackend,
  queryKnowledgeDNA,
  queryKnowledgeMindMap,
  type BackendDocument,
} from '../lib/api';
import {
  getConversations,
  saveConversations,
  getProjects,
  saveProjects,
  getActiveConversationId,
  setActiveConversationId,
  createNewConversation,
  createProject,
} from '../lib/conversationStore';
import {
  buildResultFromQueryResponse,
  buildResultFromReasoningResponse,
  buildResultFromVerifyResponse,
  buildResultFromCompareResponse,
  buildResultFromGapsResponse,
  buildResultFromDebateResponse,
  buildResultFromMindMapResponse,
  buildResultFromDNAResponse,
} from '../lib/workspaceResultBuilder';
import type { ChatMessage, Conversation, Project, ScopeOption } from '../types/chat';
import type { AnalysisMode, WorkspaceResult } from '../types/query';
import type { Source } from '../types/evidence';

export const KnowledgeWorkspacePage: React.FC = () => {
  const { user, logout } = useAuth();
  const userId = user?.id || 'default_user';

  // Sidebar state
  const [isSidebarOpen, setIsSidebarOpen] = useState(() => {
    return window.innerWidth >= 1024;
  });

  // Conversations & Projects state
  const [conversations, setConversations] = useState<Conversation[]>(() => {
    const saved = getConversations(userId);
    if (saved.length > 0) return saved;
    const initial = createNewConversation('New Research Chat');
    return [initial];
  });

  const [activeConvId, setActiveConvId] = useState<string>(() => {
    const stored = getActiveConversationId();
    const saved = getConversations(userId);
    if (stored && saved.some((c) => c.id === stored)) {
      return stored;
    }
    return saved.length > 0 ? saved[0].id : '';
  });

  const [projects, setProjects] = useState<Project[]>(() => getProjects(userId));
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null);

  // Active conversation helper
  const activeConversation = conversations.find((c) => c.id === activeConvId) || conversations[0];

  // Composer inputs and options
  const [queryInput, setQueryInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [abortController, setAbortController] = useState<AbortController | null>(null);

  // Documents
  const [availableDocs, setAvailableDocs] = useState<BackendDocument[]>([]);
  const [isBackendOnline, setIsBackendOnline] = useState<boolean | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgressText, setUploadProgressText] = useState('');

  // Undo delete toast
  const [undoToast, setUndoToast] = useState<{ docName: string; secondsLeft: number } | null>(null);
  const undoTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Modals & Drawers
  const [drawerSources, setDrawerSources] = useState<Source[] | null>(null);
  const [isShareModalOpen, setIsShareModalOpen] = useState(false);
  const [isDownloadModalOpen, setIsDownloadModalOpen] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Save conversations to localStorage whenever they change
  useEffect(() => {
    if (conversations.length > 0) {
      saveConversations(userId, conversations);
    }
  }, [conversations, userId]);

  // Save projects to localStorage
  useEffect(() => {
    saveProjects(userId, projects);
  }, [projects, userId]);

  // Save active conversation id
  useEffect(() => {
    if (activeConvId) {
      setActiveConversationId(activeConvId);
    }
  }, [activeConvId]);

  // Auto-scroll chat to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [activeConversation?.messages, isLoading]);

  // Fetch documents on mount
  const loadDocuments = useCallback(async () => {
    try {
      const res = await fetchDocuments();
      setAvailableDocs(res.documents || []);
      setIsBackendOnline(true);
    } catch {
      setIsBackendOnline(false);
    }
  }, []);

  useEffect(() => {
    void loadDocuments();
  }, [loadDocuments]);

  // Conversation Management Handlers
  const handleNewChat = () => {
    const newConv = createNewConversation(
      'New Research Chat',
      activeProjectId,
      activeConversation ? [...activeConversation.selectedDocIds] : [],
      activeConversation ? activeConversation.activeFeature : 'discover'
    );
    setConversations((prev) => [newConv, ...prev]);
    setActiveConvId(newConv.id);
    setQueryInput('');
  };

  const handleSelectConversation = (id: string) => {
    setActiveConvId(id);
    if (window.innerWidth < 1024) {
      setIsSidebarOpen(false);
    }
  };

  const handlePinConversation = (id: string, isPinned: boolean) => {
    setConversations((prev) =>
      prev.map((c) => (c.id === id ? { ...c, isPinned, updatedAt: new Date().toISOString() } : c))
    );
  };

  const handleRenameConversation = (id: string, newTitle: string) => {
    setConversations((prev) =>
      prev.map((c) => (c.id === id ? { ...c, title: newTitle, updatedAt: new Date().toISOString() } : c))
    );
  };

  const handleDeleteConversation = (id: string) => {
    setConversations((prev) => {
      const next = prev.filter((c) => c.id !== id);
      if (next.length === 0) {
        const fresh = createNewConversation('New Research Chat');
        setActiveConvId(fresh.id);
        return [fresh];
      }
      if (activeConvId === id) {
        setActiveConvId(next[0].id);
      }
      return next;
    });
  };

  const handleClearAllHistory = () => {
    const fresh = createNewConversation('New Research Chat');
    setConversations([fresh]);
    setActiveConvId(fresh.id);
  };

  const handleCreateProject = (name: string) => {
    const newP = createProject(name);
    setProjects((prev) => [...prev, newP]);
    setActiveProjectId(newP.id);
  };

  const handleDeleteProject = (id: string) => {
    setProjects((prev) => prev.filter((p) => p.id !== id));
    if (activeProjectId === id) {
      setActiveProjectId(null);
    }
  };

  // Document selection inside active conversation (Selection Rule 5: independent toggles)
  const handleToggleDoc = (docName: string) => {
    if (!activeConversation) return;
    const current = activeConversation.selectedDocIds;
    const nextDocs = current.includes(docName)
      ? current.filter((d) => d !== docName)
      : [...current, docName];

    setConversations((prev) =>
      prev.map((c) => (c.id === activeConvId ? { ...c, selectedDocIds: nextDocs } : c))
    );
  };

  const handleSelectAllDocs = () => {
    if (!activeConversation) return;
    const all = availableDocs.map((d) => d.name);
    setConversations((prev) =>
      prev.map((c) => (c.id === activeConvId ? { ...c, selectedDocIds: all } : c))
    );
  };

  const handleClearDocSelection = () => {
    if (!activeConversation) return;
    setConversations((prev) =>
      prev.map((c) => (c.id === activeConvId ? { ...c, selectedDocIds: [] } : c))
    );
  };

  // Feature mode change
  const handleFeatureChange = (feature: AnalysisMode) => {
    if (!activeConversation) return;
    setConversations((prev) =>
      prev.map((c) => (c.id === activeConvId ? { ...c, activeFeature: feature } : c))
    );
  };

  // Web search toggle
  const handleToggleWeb = () => {
    if (!activeConversation) return;
    setConversations((prev) =>
      prev.map((c) => (c.id === activeConvId ? { ...c, includeWeb: !c.includeWeb } : c))
    );
  };

  // Document upload of up to 20 files
  const handleUploadFiles = async (files: File[]) => {
    if (files.length === 0) return;
    setIsUploading(true);
    setUploadProgressText(`Uploading ${files.length} document(s)...`);

    try {
      if (files.length === 1) {
        const file = files[0];
        setUploadProgressText(`Indexing ${file.name}...`);
        const res = await uploadDocument(file);

        // Fetch overview automatically after upload
        let overviewData;
        try {
          overviewData = await fetchDocumentOverview(res.filename);
        } catch {
          // ignore overview fetch failure
        }

        // Add overview message to active conversation
        const overviewMessage: ChatMessage = {
          id: `msg_ov_${Date.now()}`,
          sender: 'overview',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          documentName: res.filename,
          overview: overviewData,
        };

        setConversations((prev) =>
          prev.map((c) => {
            if (c.id !== activeConvId) return c;
            const updatedDocs = c.selectedDocIds.includes(res.filename)
              ? c.selectedDocIds
              : [...c.selectedDocIds, res.filename];
            return {
              ...c,
              selectedDocIds: updatedDocs,
              messages: [...c.messages, overviewMessage],
            };
          })
        );
      } else {
        setUploadProgressText(`Batch indexing ${files.length} files...`);
        const batchRes = await uploadDocumentsBatch(files);
        const uploadedNames = batchRes.results
          .filter((r) => r.status === 'ready')
          .map((r) => r.filename);

        // Fetch overview for the primary uploaded file
        if (uploadedNames.length > 0) {
          let overviewData;
          try {
            overviewData = await fetchDocumentOverview(uploadedNames[0]);
          } catch {
            // ignore
          }

          const overviewMessage: ChatMessage = {
            id: `msg_ov_${Date.now()}`,
            sender: 'overview',
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            documentName: uploadedNames[0],
            overview: overviewData,
          };

          setConversations((prev) =>
            prev.map((c) => {
              if (c.id !== activeConvId) return c;
              const mergedDocs = Array.from(new Set([...c.selectedDocIds, ...uploadedNames]));
              return {
                ...c,
                selectedDocIds: mergedDocs,
                messages: [...c.messages, overviewMessage],
              };
            })
          );
        }
      }

      await loadDocuments();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setIsUploading(false);
      setUploadProgressText('');
    }
  };

  // Delete document with 10s undo window
  const handleDeleteDocument = async (docName: string) => {
    try {
      await deleteDocument(docName);
      await loadDocuments();

      if (undoTimerRef.current) clearInterval(undoTimerRef.current);
      setUndoToast({ docName, secondsLeft: 10 });

      undoTimerRef.current = setInterval(() => {
        setUndoToast((prev) => {
          if (!prev || prev.secondsLeft <= 1) {
            if (undoTimerRef.current) clearInterval(undoTimerRef.current);
            return null;
          }
          return { ...prev, secondsLeft: prev.secondsLeft - 1 };
        });
      }, 1000);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Failed to delete document');
    }
  };

  const handleUndoDelete = async (docName: string) => {
    if (undoTimerRef.current) clearInterval(undoTimerRef.current);
    setUndoToast(null);
    try {
      await undoDeleteDocument(docName);
      await loadDocuments();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Failed to restore document');
    }
  };

  // Send research inquiry (Multi-query execution)
  const handleSubmitQuery = async () => {
    if (!queryInput.trim() && activeConversation.activeFeature !== 'knowledge-map' && activeConversation.activeFeature !== 'knowledge-dna' && activeConversation.activeFeature !== 'overview') {
      return;
    }

    const currentText = queryInput.trim();
    const currentFeature = activeConversation.activeFeature;
    const currentDocs = [...activeConversation.selectedDocIds];
    const currentWeb = activeConversation.includeWeb;

    // Build scope tag
    const scopeOption: ScopeOption =
      currentWeb && currentDocs.length > 0
        ? 'documents_web'
        : currentDocs.length === 1
        ? 'this_document'
        : currentDocs.length > 1
        ? 'selected'
        : 'all';

    // 1. Append User Message
    const userMessage: ChatMessage = {
      id: `usr_${Date.now()}`,
      sender: 'user',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      text: currentText,
      feature: currentFeature,
      scope: scopeOption,
      selectedDocIds: currentDocs,
      includeWeb: currentWeb,
    };

    // Auto-update conversation title if it's the first inquiry
    let updatedTitle = activeConversation.title;
    if (activeConversation.messages.length === 0 || activeConversation.title === 'New Research Chat') {
      updatedTitle = currentText.length > 32 ? `${currentText.slice(0, 30)}...` : currentText;
    }

    setConversations((prev) =>
      prev.map((c) => {
        if (c.id !== activeConvId) return c;
        return {
          ...c,
          title: updatedTitle,
          messages: [...c.messages, userMessage],
          updatedAt: new Date().toISOString(),
        };
      })
    );

    setQueryInput('');
    setIsLoading(true);

    const controller = new AbortController();
    setAbortController(controller);

    const targetDocs = currentDocs.length > 0 ? currentDocs : undefined;
    const docOnly = !currentWeb;

    try {
      let workspaceResult: WorkspaceResult;

      switch (currentFeature) {
        case 'overview': {
          const docToOverview = (targetDocs && targetDocs[0]) || availableDocs[0]?.name;
          if (docToOverview) {
            const ovData = await fetchDocumentOverview(docToOverview);
            const overviewMessage: ChatMessage = {
              id: `ov_${Date.now()}`,
              sender: 'overview',
              timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
              documentName: docToOverview,
              overview: ovData,
            };
            setConversations((prev) =>
              prev.map((c) => {
                if (c.id !== activeConvId) return c;
                return {
                  ...c,
                  messages: [...c.messages, overviewMessage],
                  updatedAt: new Date().toISOString(),
                };
              })
            );
            setIsLoading(false);
            return;
          }
          const resp = await queryBackend(currentText || 'Overview of documents', targetDocs, docOnly, scopeOption, controller.signal);
          workspaceResult = buildResultFromQueryResponse(currentText || 'Overview of documents', resp);
          break;
        }
        case 'discover': {
          const resp = await queryBackend(currentText, targetDocs, docOnly, scopeOption, controller.signal);
          workspaceResult = buildResultFromQueryResponse(currentText, resp);
          break;
        }
        case 'reason': {
          const resp = await reasonBackend(currentText, targetDocs, controller.signal);
          workspaceResult = buildResultFromReasoningResponse(currentText, resp);
          break;
        }
        case 'verify': {
          const resp = await verifyClaimBackend(currentText, targetDocs, controller.signal);
          workspaceResult = buildResultFromVerifyResponse(currentText, resp);
          break;
        }
        case 'compare': {
          const resp = await compareBackend(currentText, targetDocs, controller.signal);
          workspaceResult = buildResultFromCompareResponse(currentText, resp);
          break;
        }
        case 'gaps': {
          const resp = await findResearchGapsBackend(currentText, targetDocs, controller.signal);
          workspaceResult = buildResultFromGapsResponse(currentText, resp);
          break;
        }
        case 'debate': {
          const resp = await runDebateBackend(currentText, undefined, undefined, targetDocs, controller.signal);
          workspaceResult = buildResultFromDebateResponse(currentText, resp);
          break;
        }
        case 'knowledge-map': {
          const resp = await queryKnowledgeMindMap(currentText || 'Core Research Concepts', targetDocs, controller.signal);
          workspaceResult = buildResultFromMindMapResponse(currentText || 'Core Research Concepts', resp);
          break;
        }
        case 'knowledge-dna': {
          const resp = await queryKnowledgeDNA(currentText || 'Document Knowledge Architecture', targetDocs, controller.signal);
          workspaceResult = buildResultFromDNAResponse(currentText || 'Document Knowledge Architecture', resp);
          break;
        }
        default: {
          const resp = await queryBackend(currentText, targetDocs, docOnly, scopeOption, controller.signal);
          workspaceResult = buildResultFromQueryResponse(currentText, resp);
          break;
        }
      }

      // 2. Append Assistant Response Message
      const assistantMessage: ChatMessage = {
        id: `asst_${Date.now()}`,
        sender: 'assistant',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        feature: currentFeature,
        scope: scopeOption,
        selectedDocIds: currentDocs,
        includeWeb: currentWeb,
        result: workspaceResult,
      };

      setConversations((prev) =>
        prev.map((c) => {
          if (c.id !== activeConvId) return c;
          return {
            ...c,
            messages: [...c.messages, assistantMessage],
            updatedAt: new Date().toISOString(),
          };
        })
      );
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        // user cancelled
      } else {
        const errorMsg = err instanceof Error ? err.message : 'Inquiry processing failed';
        const errAssistantMessage: ChatMessage = {
          id: `asst_err_${Date.now()}`,
          sender: 'assistant',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          feature: currentFeature,
          selectedDocIds: currentDocs,
          error: errorMsg,
          result: {
            ...buildResultFromQueryResponse(currentText, {
              query: currentText,
              query_type: 'error',
              answer: `Research error: ${errorMsg}. Please try refining your query or re-selecting documents.`,
              sources: [],
            }),
            answerState: 'error',
          },
        };

        setConversations((prev) =>
          prev.map((c) => {
            if (c.id !== activeConvId) return c;
            return {
              ...c,
              messages: [...c.messages, errAssistantMessage],
            };
          })
        );
      }
    } finally {
      setIsLoading(false);
      setAbortController(null);
    }
  };

  const handleCancelQuery = () => {
    if (abortController) {
      abortController.abort();
      setAbortController(null);
      setIsLoading(false);
    }
  };

  // Generate contextual prompt suggestions (strictly non-executing) - Phase 2 Requirement 6
  const getContextualSuggestions = (): string[] => {
    if (!activeConversation) return [];
    const docName = activeConversation.selectedDocIds[0];
    const feature = activeConversation.activeFeature;
    const includeWeb = activeConversation.includeWeb;

    // Web Evidence suggestions when web mode is enabled
    if (includeWeb) {
      return [
        'Research this topic across real academic and web literature',
        'Find relevant recent publications and preprints on this question',
        'Compare document findings with external scholarly sources',
        'Investigate conflicting evidence between internal corpus and web data',
      ];
    }

    switch (feature) {
      case 'overview':
        return [
          docName
            ? `Explain the complete methodology and architecture of ${docName}`
            : 'Explain the complete methodology and experimental workflow',
          'Extract technical contributions, limitations, and future work',
          'Explain theoretical derivations, equations, and mathematical assumptions',
        ];

      case 'discover':
        return [
          docName
            ? `Explain the core conceptual breakthrough introduced in ${docName}`
            : 'Explain the central concept and architectural principles',
          docName
            ? `Answer: How does ${docName} achieve empirical validation?`
            : 'Answer a question using the active document scope',
          'Clarify technical terminology, variable definitions, and boundary conditions',
        ];

      case 'reason':
        return [
          'Trace the algorithmic workflow and step-by-step mathematical proof',
          'Explain fundamental physical assumptions and causal dependencies',
          'Analyze the technical design choices and trade-offs versus alternatives',
        ];

      case 'verify':
        return [
          docName
            ? `Verify whether the primary empirical claim in ${docName} is supported by evidence`
            : 'Verify a specific claim against the indexed documents',
          'Check if the stated conclusions match the experimental data',
          'Identify contradicting passages or unverified assertions in the literature',
        ];

      case 'compare':
        if (activeConversation.selectedDocIds.length >= 2) {
          return [
            `Compare the primary algorithms and metrics between ${activeConversation.selectedDocIds[0]} and ${activeConversation.selectedDocIds[1]}`,
            `What are the conflicting conclusions or trade-offs between these two papers?`,
            'Compare experimental benchmark results and runtime complexity',
          ];
        }
        return [
          'Compare algorithms, computational complexity, and runtime efficiencies',
          'Compare empirical benchmark results across evaluated methodologies',
          'What are the key structural and theoretical differences between approaches?',
        ];

      case 'gaps':
        return [
          'Find evidence-backed limitations and unexamined assumptions in the methodology',
          'Identify unresolved research questions and missing benchmark baselines',
          'Suggest testable future research directions based on stated constraints',
        ];

      case 'debate':
        return [
          'Construct evidence-based supporting and opposing arguments on this approach',
          'Challenge foundational assumptions and evaluate practical feasibility',
          'Assess methodological weaknesses, computational bottlenecks, and counter-evidence',
        ];

      case 'knowledge-map':
        return [
          'Map the research methodology, algorithmic flow, and concept dependencies',
          'Connect foundational concepts to empirical findings and benchmark outcomes',
          'Explore subtopics, mathematical relations, and domain hierarchies',
        ];

      case 'knowledge-dna':
        return [
          'Extract the thematic DNA, core concepts, methods, and structural signals',
          'Identify technical contributions, claim clusters, and uncertainty boundaries',
          'Discover key concept relationships and foundational building blocks',
        ];

      default:
        return [
          'Explain the primary methodologies and empirical findings in the indexed papers',
          'How do the experimental results validate the core hypothesis?',
          'Trace theoretical derivations and system components step by step',
        ];
    }
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#0c1218] text-[#e6ebef]">
      {/* Sliding Sidebar */}
      <SlidingSidebar
        isOpen={isSidebarOpen}
        onToggle={() => setIsSidebarOpen(!isSidebarOpen)}
        conversations={conversations}
        activeConversationId={activeConvId}
        onSelectConversation={handleSelectConversation}
        onNewChat={handleNewChat}
        onPinConversation={handlePinConversation}
        onRenameConversation={handleRenameConversation}
        onDeleteConversation={handleDeleteConversation}
        onClearAllHistory={handleClearAllHistory}
        projects={projects}
        activeProjectId={activeProjectId}
        onSelectProject={setActiveProjectId}
        onCreateProject={handleCreateProject}
        onDeleteProject={handleDeleteProject}
        onOpenDownloadHistory={() => setIsDownloadModalOpen(true)}
        user={user ? { name: user.name, email: user.email } : null}
        onLogout={logout}
      />

      {/* Main Conversation Container */}
      <div
        className={`flex-1 flex flex-col h-full overflow-hidden transition-all duration-300 ease-in-out ${
          isSidebarOpen ? 'lg:pl-72' : 'pl-0'
        }`}
      >
        {/* Top Header Bar */}
        <header className="h-14 border-b border-[#4d728e]/20 bg-[#0e151e]/80 backdrop-blur-md px-4 flex items-center justify-between shrink-0 z-30">
          <div className="flex items-center gap-3 min-w-0">
            <button
              type="button"
              onClick={() => setIsSidebarOpen(!isSidebarOpen)}
              className="p-1.5 rounded-lg text-[#f3faf0]/70 hover:text-white hover:bg-white/5 transition-colors cursor-pointer"
              title={isSidebarOpen ? 'Hide sidebar' : 'Show sidebar'}
              aria-label="Toggle sidebar"
            >
              {isSidebarOpen ? <PanelLeftClose className="w-5 h-5" /> : <PanelLeft className="w-5 h-5" />}
            </button>

            <div className="flex items-center gap-2 truncate">
              <span className="text-sm font-semibold text-white truncate">
                {activeConversation?.title || 'Research Chat'}
              </span>
              {activeConversation?.projectId && (
                <span className="hidden sm:inline-block px-2 py-0.5 rounded-full bg-[#1b2632] text-[10px] text-[#a7d0d2] border border-[#a7d0d2]/30 font-mono">
                  {projects.find((p) => p.id === activeConversation.projectId)?.name || 'Project'}
                </span>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {/* Backend status indicator */}
            <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#141d26] border border-white/5 text-[11px] font-mono">
              <span
                className={`w-2 h-2 rounded-full ${
                  isBackendOnline ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.6)]' : 'bg-amber-400'
                }`}
              />
              <span className="text-[#f3faf0]/60">{isBackendOnline ? 'Hybrid RAG Online' : 'Connecting...'}</span>
            </div>

            {/* Share action */}
            <button
              type="button"
              onClick={() => setIsShareModalOpen(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#4d728e]/35 hover:border-[#a7d0d2]/60 bg-[#16222e] hover:bg-[#1c2c3b] text-xs text-[#a7d0d2] hover:text-white transition-colors cursor-pointer"
              title="Share this conversation"
            >
              <Share2 className="w-3.5 h-3.5 text-[#d2434e]" />
              <span className="hidden sm:inline font-medium">Share</span>
            </button>
          </div>
        </header>

        {/* Central Chat Messages Thread */}
        <main className="flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-white/10 flex flex-col">
          {(!activeConversation || activeConversation.messages.length === 0) ? (
            /* Clean Empty State / New Chat Hero */
            <div className="flex-1 flex flex-col items-center justify-center p-6 text-center max-w-xl mx-auto space-y-4 my-auto select-none">
              <div className="w-14 h-14 rounded-2xl overflow-hidden border border-[#d2434e]/50 shadow-xl bg-[#080d12]">
                <img src="/unknown-logo.jpg" alt="UNKNOWN" className="w-full h-full object-cover" />
              </div>
              <div>
                <h2 className="text-xl font-extrabold text-white tracking-wide">UNKNOWN Research Intelligence</h2>
                <p className="text-xs text-[#f3faf0]/65 mt-1 leading-relaxed">
                  Evidence-grounded dual retrieval across your documents and external scientific sources.
                </p>
              </div>

              {/* Status Chips */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 w-full pt-2 text-xs">
                <div className="p-3 rounded-xl bg-[#121a23] border border-white/5 space-y-1">
                  <p className="font-semibold text-white">Hybrid Retrieval</p>
                  <p className="text-[10px] text-[#f3faf0]/50">BM25 + FAISS Vector index</p>
                </div>
                <div className="p-3 rounded-xl bg-[#121a23] border border-white/5 space-y-1">
                  <p className="font-semibold text-white">Multi-Doc Support</p>
                  <p className="text-[10px] text-[#f3faf0]/50">Attach up to 20 papers</p>
                </div>
                <div className="p-3 rounded-xl bg-[#121a23] border border-white/5 space-y-1">
                  <p className="font-semibold text-white">Evidence Grounding</p>
                  <p className="text-[10px] text-[#f3faf0]/50">Zero hallucinations</p>
                </div>
              </div>
            </div>
          ) : (
            /* Chronological Message Stream */
            <div className="flex-1 py-4 space-y-2">
              {activeConversation.messages.map((msg) => (
                <ChatMessageItem
                  key={msg.id}
                  message={msg}
                  onOpenSourcesDrawer={(srcs) => setDrawerSources(srcs)}
                />
              ))}

              {/* Loading Shimmer Card */}
              {isLoading && (
                <div className="py-5 px-3 sm:px-6 bg-[#0c1218]/40 border-y border-white/5">
                  <div className="max-w-4xl mx-auto flex items-start gap-3 sm:gap-4">
                    <div className="w-8 h-8 rounded-xl overflow-hidden border border-[#d2434e]/50 shrink-0 bg-[#080d12] shadow-sm animate-pulse">
                      <img src="/unknown-logo.jpg" alt="UNKNOWN" className="w-full h-full object-cover" />
                    </div>
                    <div className="flex-1 space-y-3">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-white">UNKNOWN Research</span>
                        <span className="text-[11px] text-[#a7d0d2] font-mono animate-pulse">
                          Retrieving passages and verifying evidence...
                        </span>
                      </div>
                      <div className="h-4 bg-white/5 rounded-md w-3/4 animate-pulse" />
                      <div className="h-4 bg-white/5 rounded-md w-1/2 animate-pulse" />
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </main>

        {/* Persistent Bottom Composer */}
        <footer className="shrink-0 z-20">
          <ChatComposer
            query={queryInput}
            onQueryChange={setQueryInput}
            onSubmit={handleSubmitQuery}
            isLoading={isLoading}
            onCancel={handleCancelQuery}
            activeFeature={activeConversation?.activeFeature || 'discover'}
            onFeatureChange={handleFeatureChange}
            includeWeb={activeConversation?.includeWeb || false}
            onToggleWeb={handleToggleWeb}
            availableDocuments={availableDocs}
            selectedDocIds={activeConversation?.selectedDocIds || []}
            onToggleDoc={handleToggleDoc}
            onSelectAllDocs={handleSelectAllDocs}
            onClearDocSelection={handleClearDocSelection}
            onDeleteDocument={handleDeleteDocument}
            onUploadFiles={handleUploadFiles}
            isUploading={isUploading}
            uploadProgressText={uploadProgressText}
            suggestions={getContextualSuggestions()}
            onSelectSuggestion={(s) => setQueryInput(s)}
          />
        </footer>
      </div>

      {/* Sources Drawer */}
      <SourcesDrawer
        isOpen={drawerSources !== null}
        sources={drawerSources || []}
        onClose={() => setDrawerSources(null)}
      />

      {/* Share Modal */}
      {activeConversation && (
        <ShareConversationModal
          isOpen={isShareModalOpen}
          onClose={() => setIsShareModalOpen(false)}
          conversation={activeConversation}
        />
      )}

      {/* Download History Modal */}
      <DownloadHistoryModal
        isOpen={isDownloadModalOpen}
        onClose={() => setIsDownloadModalOpen(false)}
        conversations={conversations}
        userId={userId}
      />

      {/* 10-Second Undo Delete Toast */}
      {undoToast && (
        <div className="fixed bottom-20 right-6 z-50 flex items-center gap-3 bg-[#131d27] border border-[#a7d0d2]/40 shadow-2xl rounded-xl px-4 py-3 text-xs text-white animate-fade-in">
          <AlertCircle className="w-4 h-4 text-amber-400 shrink-0" />
          <span>
            Deleted <span className="font-mono font-semibold">{undoToast.docName}</span>. Undo available ({undoToast.secondsLeft}s)
          </span>
          <button
            type="button"
            onClick={() => handleUndoDelete(undoToast.docName)}
            className="flex items-center gap-1 px-2.5 py-1 rounded bg-[#d2434e] hover:bg-[#b0303b] text-white font-medium cursor-pointer ml-1"
          >
            <RotateCcw className="w-3 h-3" />
            <span>Undo</span>
          </button>
        </div>
      )}
    </div>
  );
};
