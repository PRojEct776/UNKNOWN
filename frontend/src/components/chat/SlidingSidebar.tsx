import React, { useState, useEffect, useRef } from 'react';
import {
  Plus,
  Search,
  Pin,
  PinOff,
  Trash2,
  Edit2,
  FolderPlus,
  Folder,
  Download,
  PanelLeftClose,
  X,
  MessageSquare,
  Check,
  ChevronDown,
  ChevronRight,
  User,
  LogOut,
  AlertTriangle,
} from 'lucide-react';
import type { Conversation, Project } from '../../types/chat';

interface SlidingSidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  conversations: Conversation[];
  activeConversationId: string | null;
  onSelectConversation: (id: string) => void;
  onNewChat: () => void;
  onPinConversation: (id: string, isPinned: boolean) => void;
  onRenameConversation: (id: string, newTitle: string) => void;
  onDeleteConversation: (id: string) => void;
  onClearAllHistory: () => void;
  projects: Project[];
  activeProjectId: string | null;
  onSelectProject: (projectId: string | null) => void;
  onCreateProject: (name: string) => void;
  onDeleteProject: (id: string) => void;
  onOpenDownloadHistory: () => void;
  user: { name?: string; email?: string } | null;
  onLogout: () => void;
}

export const SlidingSidebar: React.FC<SlidingSidebarProps> = ({
  isOpen,
  onToggle,
  conversations,
  activeConversationId,
  onSelectConversation,
  onNewChat,
  onPinConversation,
  onRenameConversation,
  onDeleteConversation,
  onClearAllHistory,
  projects,
  activeProjectId,
  onSelectProject,
  onCreateProject,
  onDeleteProject,
  onOpenDownloadHistory,
  user,
  onLogout,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [isCreatingProject, setIsCreatingProject] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [showProjectsList, setShowProjectsList] = useState(true);
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);

  const sidebarRef = useRef<HTMLDivElement>(null);
  const userMenuRef = useRef<HTMLDivElement>(null);

  // Close on Escape on mobile / compact
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (showClearConfirm) {
          setShowClearConfirm(false);
          return;
        }
        if (isCreatingProject) {
          setIsCreatingProject(false);
          return;
        }
        if (editingId) {
          setEditingId(null);
          return;
        }
        if (window.innerWidth < 1024 && isOpen) {
          onToggle();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onToggle, showClearConfirm, isCreatingProject, editingId]);

  // Click outside user menu
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setShowUserMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Filter conversations by active project and search query
  const filteredConversations = conversations.filter((c) => {
    const matchesProject = !activeProjectId || c.projectId === activeProjectId;
    const matchesQuery =
      !searchQuery.trim() ||
      c.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.messages.some((m) => m.text?.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchesProject && matchesQuery;
  });

  const pinnedConversations = filteredConversations.filter((c) => c.isPinned);
  const recentConversations = filteredConversations.filter((c) => !c.isPinned);

  const handleStartRename = (c: Conversation, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(c.id);
    setEditTitle(c.title);
  };

  const handleSaveRename = (id: string, e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (editTitle.trim()) {
      onRenameConversation(id, editTitle.trim());
    }
    setEditingId(null);
  };

  const handleCreateProjectSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (newProjectName.trim()) {
      onCreateProject(newProjectName.trim());
      setNewProjectName('');
      setIsCreatingProject(false);
    }
  };

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-xs z-40 lg:hidden transition-opacity"
          onClick={onToggle}
          aria-hidden="true"
        />
      )}

      {/* Main Sliding Sidebar */}
      <aside
        ref={sidebarRef}
        aria-label="Sidebar navigation"
        className={`fixed top-0 bottom-0 left-0 z-50 flex flex-col bg-[#0d141b] border-r border-[#4d728e]/20 transition-all duration-300 ease-in-out select-none
          ${isOpen ? 'w-72 translate-x-0' : 'w-0 -translate-x-full lg:w-0 lg:-translate-x-full overflow-hidden'}
        `}
      >
        {/* Top Header: Logo + New Chat + Close */}
        <div className="p-3 border-b border-[#4d728e]/20 flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <button
              type="button"
              onClick={onNewChat}
              className="flex items-center gap-2.5 text-left group cursor-pointer focus:outline-none focus:ring-1 focus:ring-[#d2434e]"
              title="Return to Home / New Chat"
            >
              <div className="w-7 h-7 rounded-lg overflow-hidden border border-[#d2434e]/50 group-hover:border-[#d2434e] transition-colors bg-[#080d12]">
                <img src="/unknown-logo.jpg" alt="UNKNOWN" className="w-full h-full object-cover" />
              </div>
              <span className="font-extrabold tracking-wider text-white text-base">UNKNOWN</span>
            </button>

            <button
              type="button"
              onClick={onToggle}
              className="p-1.5 rounded-lg text-[#f3faf0]/60 hover:text-white hover:bg-white/5 transition-colors cursor-pointer"
              title="Collapse sidebar"
              aria-label="Collapse sidebar"
            >
              <PanelLeftClose className="w-5 h-5" />
            </button>
          </div>

          {/* New Chat Primary Button */}
          <button
            type="button"
            onClick={onNewChat}
            className="w-full mt-1.5 flex items-center justify-between px-3 py-2 rounded-lg bg-[#151f28] hover:bg-[#1a2732] border border-[#4d728e]/30 hover:border-[#a7d0d2]/50 text-white font-medium text-xs transition-all shadow-xs cursor-pointer group"
          >
            <div className="flex items-center gap-2">
              <Plus className="w-4 h-4 text-[#d2434e] group-hover:scale-110 transition-transform" />
              <span>New Chat</span>
            </div>
            <span className="text-[10px] text-[#f3faf0]/40 font-mono">Ctrl+K</span>
          </button>
        </div>

        {/* Search bar */}
        <div className="px-3 pt-3 pb-1">
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-[#f3faf0]/40" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search conversations..."
              className="w-full bg-[#121a22] text-xs text-white placeholder-[#f3faf0]/40 rounded-lg pl-8 pr-3 py-1.5 border border-white/5 focus:border-[#a7d0d2]/50 focus:outline-none"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="absolute right-2.5 top-2 text-[#f3faf0]/40 hover:text-white"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>
        </div>

        {/* Middle Scrollable Section */}
        <div className="flex-1 overflow-y-auto px-2 py-2 space-y-4 text-xs scrollbar-thin scrollbar-thumb-white/10">
          {/* Projects Section */}
          <div className="space-y-1">
            <div className="flex items-center justify-between px-2 py-1 text-[11px] font-mono text-[#f3faf0]/60 uppercase tracking-wider">
              <button
                type="button"
                onClick={() => setShowProjectsList(!showProjectsList)}
                className="flex items-center gap-1 hover:text-white cursor-pointer"
              >
                {showProjectsList ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                <span>Projects</span>
              </button>
              <button
                type="button"
                onClick={() => setIsCreatingProject(true)}
                className="p-1 hover:text-[#a7d0d2] text-[#f3faf0]/50 rounded cursor-pointer"
                title="Create project"
              >
                <FolderPlus className="w-3.5 h-3.5" />
              </button>
            </div>

            {showProjectsList && (
              <div className="space-y-0.5">
                <button
                  type="button"
                  onClick={() => onSelectProject(null)}
                  className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-md text-left transition-colors cursor-pointer ${
                    activeProjectId === null
                      ? 'bg-[#1b2632] text-white font-medium border border-white/5'
                      : 'text-[#f3faf0]/70 hover:bg-white/5 hover:text-white'
                  }`}
                >
                  <span className="truncate">All Conversations</span>
                  <span className="text-[10px] text-[#f3faf0]/40 font-mono">{conversations.length}</span>
                </button>

                {projects.map((p) => (
                  <div
                    key={p.id}
                    className={`group w-full flex items-center justify-between px-2.5 py-1.5 rounded-md text-left transition-colors cursor-pointer ${
                      activeProjectId === p.id
                        ? 'bg-[#1b2632] text-white font-medium border border-[#a7d0d2]/30'
                        : 'text-[#f3faf0]/70 hover:bg-white/5 hover:text-white'
                    }`}
                    onClick={() => onSelectProject(p.id)}
                  >
                    <div className="flex items-center gap-1.5 truncate">
                      <Folder className="w-3.5 h-3.5 text-[#a7d0d2] shrink-0" />
                      <span className="truncate">{p.name}</span>
                    </div>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteProject(p.id);
                      }}
                      className="opacity-0 group-hover:opacity-100 p-1 text-[#f3faf0]/40 hover:text-red-400 rounded transition-opacity"
                      title="Delete project"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                ))}

                {isCreatingProject && (
                  <form onSubmit={handleCreateProjectSubmit} className="p-1 flex items-center gap-1">
                    <input
                      type="text"
                      autoFocus
                      placeholder="Project name"
                      value={newProjectName}
                      onChange={(e) => setNewProjectName(e.target.value)}
                      className="flex-1 bg-[#121a22] text-xs text-white px-2 py-1 rounded border border-[#a7d0d2]/40 focus:outline-none"
                    />
                    <button
                      type="submit"
                      disabled={!newProjectName.trim()}
                      className="p-1 bg-[#d2434e] text-white rounded hover:bg-[#b0303b] disabled:opacity-40"
                    >
                      <Check className="w-3 h-3" />
                    </button>
                    <button
                      type="button"
                      onClick={() => setIsCreatingProject(false)}
                      className="p-1 text-[#f3faf0]/60 hover:text-white"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </form>
                )}
              </div>
            )}
          </div>

          {/* Pinned Conversations */}
          {pinnedConversations.length > 0 && (
            <div className="space-y-1">
              <div className="px-2 py-1 text-[11px] font-mono text-[#f3faf0]/60 uppercase tracking-wider flex items-center gap-1">
                <Pin className="w-3 h-3 text-[#d2434e]" />
                <span>Pinned</span>
              </div>
              <div className="space-y-0.5">
                {pinnedConversations.map((c) => (
                  <ConversationRow
                    key={c.id}
                    conversation={c}
                    isActive={activeConversationId === c.id}
                    isEditing={editingId === c.id}
                    editTitle={editTitle}
                    onSelect={() => onSelectConversation(c.id)}
                    onStartRename={(e) => handleStartRename(c, e)}
                    onEditTitleChange={setEditTitle}
                    onSaveRename={(e) => handleSaveRename(c.id, e)}
                    onCancelRename={() => setEditingId(null)}
                    onTogglePin={(e) => {
                      e.stopPropagation();
                      onPinConversation(c.id, false);
                    }}
                    onDelete={(e) => {
                      e.stopPropagation();
                      onDeleteConversation(c.id);
                    }}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Recent Conversations */}
          <div className="space-y-1">
            <div className="px-2 py-1 text-[11px] font-mono text-[#f3faf0]/60 uppercase tracking-wider flex items-center justify-between">
              <span>Recent</span>
              <span className="text-[10px] text-[#f3faf0]/40 font-mono">{recentConversations.length}</span>
            </div>

            {recentConversations.length === 0 ? (
              <div className="px-3 py-6 text-center text-[#f3faf0]/40 text-xs">
                <MessageSquare className="w-5 h-5 mx-auto mb-1 opacity-40" />
                <p>No conversations yet</p>
              </div>
            ) : (
              <div className="space-y-0.5">
                {recentConversations.map((c) => (
                  <ConversationRow
                    key={c.id}
                    conversation={c}
                    isActive={activeConversationId === c.id}
                    isEditing={editingId === c.id}
                    editTitle={editTitle}
                    onSelect={() => onSelectConversation(c.id)}
                    onStartRename={(e) => handleStartRename(c, e)}
                    onEditTitleChange={setEditTitle}
                    onSaveRename={(e) => handleSaveRename(c.id, e)}
                    onCancelRename={() => setEditingId(null)}
                    onTogglePin={(e) => {
                      e.stopPropagation();
                      onPinConversation(c.id, true);
                    }}
                    onDelete={(e) => {
                      e.stopPropagation();
                      onDeleteConversation(c.id);
                    }}
                  />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Download History action */}
        <div className="px-3 py-2 border-t border-[#4d728e]/20">
          <button
            type="button"
            onClick={onOpenDownloadHistory}
            className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs text-[#a7d0d2] hover:bg-white/5 hover:text-white transition-colors cursor-pointer"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Download History</span>
          </button>
        </div>

        {/* Bottom Profile / Account Area */}
        <div className="p-3 border-t border-[#4d728e]/20 relative" ref={userMenuRef}>
          <button
            type="button"
            onClick={() => setShowUserMenu(!showUserMenu)}
            className="w-full flex items-center justify-between p-2 rounded-lg hover:bg-white/5 transition-colors cursor-pointer group text-left"
          >
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-7 h-7 rounded-full bg-[#1b2632] border border-[#4d728e]/40 flex items-center justify-center text-white shrink-0">
                <User className="w-4 h-4 text-[#a7d0d2]" />
              </div>
              <div className="min-w-0 truncate">
                <p className="text-xs font-medium text-white truncate">{user?.name || 'Researcher'}</p>
                <p className="text-[10px] text-[#f3faf0]/50 truncate">{user?.email || 'Active Workspace'}</p>
              </div>
            </div>
            <ChevronDown className="w-3.5 h-3.5 text-[#f3faf0]/40 group-hover:text-white shrink-0" />
          </button>

          {/* User popup menu */}
          {showUserMenu && (
            <div className="absolute bottom-16 left-3 right-3 bg-[#131b23] border border-[#4d728e]/35 rounded-xl shadow-2xl p-1.5 space-y-1 z-50 text-xs">
              <button
                type="button"
                onClick={() => {
                  setShowUserMenu(false);
                  setShowClearConfirm(true);
                }}
                className="w-full flex items-center gap-2 px-3 py-2 text-rose-300 hover:bg-rose-500/10 rounded-lg text-left transition-colors cursor-pointer"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Clear all history</span>
              </button>
              <div className="border-t border-white/5 my-1" />
              <button
                type="button"
                onClick={() => {
                  setShowUserMenu(false);
                  onLogout();
                }}
                className="w-full flex items-center gap-2 px-3 py-2 text-[#f3faf0]/80 hover:bg-white/5 hover:text-white rounded-lg text-left transition-colors cursor-pointer"
              >
                <LogOut className="w-3.5 h-3.5" />
                <span>Sign out</span>
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* Confirmation Modal for Clear All History */}
      {showClearConfirm && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-xs flex items-center justify-center z-50 p-4">
          <div className="bg-[#10171e] border border-red-500/30 rounded-2xl p-5 max-w-sm w-full space-y-4 shadow-2xl">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-xl bg-red-500/10 text-red-400">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <h3 className="text-sm font-semibold text-white">Clear all conversation history?</h3>
            </div>
            <p className="text-xs text-[#f3faf0]/70 leading-relaxed">
              This action will delete all saved conversations and messages from this device. Stored source documents
              and their search indexes will remain intact.
            </p>
            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowClearConfirm(false)}
                className="px-3 py-1.5 rounded-lg border border-white/10 text-xs text-[#f3faf0]/75 hover:bg-white/5 cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowClearConfirm(false);
                  onClearAllHistory();
                }}
                className="px-3 py-1.5 rounded-lg bg-red-600 hover:bg-red-700 text-xs font-semibold text-white cursor-pointer"
              >
                Clear History
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

interface ConversationRowProps {
  conversation: Conversation;
  isActive: boolean;
  isEditing: boolean;
  editTitle: string;
  onSelect: () => void;
  onStartRename: (e: React.MouseEvent) => void;
  onEditTitleChange: (val: string) => void;
  onSaveRename: (e?: React.FormEvent) => void;
  onCancelRename: () => void;
  onTogglePin: (e: React.MouseEvent) => void;
  onDelete: (e: React.MouseEvent) => void;
}

const ConversationRow: React.FC<ConversationRowProps> = ({
  conversation,
  isActive,
  isEditing,
  editTitle,
  onSelect,
  onStartRename,
  onEditTitleChange,
  onSaveRename,
  onCancelRename,
  onTogglePin,
  onDelete,
}) => {
  if (isEditing) {
    return (
      <form onSubmit={onSaveRename} className="p-1 flex items-center gap-1">
        <input
          type="text"
          autoFocus
          value={editTitle}
          onChange={(e) => onEditTitleChange(e.target.value)}
          className="flex-1 bg-[#121a22] text-xs text-white px-2 py-1 rounded border border-[#a7d0d2]/40 focus:outline-none"
        />
        <button type="submit" className="p-1 text-emerald-400 hover:text-emerald-300">
          <Check className="w-3 h-3" />
        </button>
        <button type="button" onClick={onCancelRename} className="p-1 text-[#f3faf0]/60 hover:text-white">
          <X className="w-3 h-3" />
        </button>
      </form>
    );
  }

  return (
    <div
      onClick={onSelect}
      className={`group w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-left transition-all cursor-pointer ${
        isActive
          ? 'bg-[#18232f] text-white border border-[#4d728e]/40 shadow-xs'
          : 'text-[#f3faf0]/75 hover:bg-white/5 hover:text-white border border-transparent'
      }`}
    >
      <div className="flex items-center gap-2 min-w-0 flex-1 pr-1">
        <MessageSquare className={`w-3.5 h-3.5 shrink-0 ${isActive ? 'text-[#d2434e]' : 'text-[#f3faf0]/40'}`} />
        <span className="text-xs truncate">{conversation.title}</span>
      </div>

      <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
        <button
          type="button"
          onClick={onTogglePin}
          className="p-1 text-[#f3faf0]/40 hover:text-[#a7d0d2] rounded"
          title={conversation.isPinned ? 'Unpin' : 'Pin'}
        >
          {conversation.isPinned ? <PinOff className="w-3 h-3" /> : <Pin className="w-3 h-3" />}
        </button>
        <button
          type="button"
          onClick={onStartRename}
          className="p-1 text-[#f3faf0]/40 hover:text-white rounded"
          title="Rename"
        >
          <Edit2 className="w-3 h-3" />
        </button>
        <button
          type="button"
          onClick={onDelete}
          className="p-1 text-[#f3faf0]/40 hover:text-rose-400 rounded"
          title="Delete"
        >
          <Trash2 className="w-3 h-3" />
        </button>
      </div>
    </div>
  );
};
