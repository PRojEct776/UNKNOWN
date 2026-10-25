/**
 * UNKNOWN — Conversation and Project Persistence Store
 *
 * Implements user-scoped durable persistence for multi-query conversations,
 * per-message document & feature scopes, projects, pins, and exports.
 */

import type { Conversation, Project } from '../types/chat';
import type { AnalysisMode } from '../types/query';

const CONV_PREFIX = 'unknown_conversations_';
const PROJ_PREFIX = 'unknown_projects_';
const ACTIVE_CONV_KEY = 'unknown_active_conv_id';

export function getConversations(userId: string = 'default_user'): Conversation[] {
  try {
    const raw = localStorage.getItem(`${CONV_PREFIX}${userId}`);
    if (!raw) return [];
    return JSON.parse(raw) as Conversation[];
  } catch (err) {
    console.error('Failed to load conversations:', err);
    return [];
  }
}

export function saveConversations(userId: string = 'default_user', conversations: Conversation[]): void {
  try {
    localStorage.setItem(`${CONV_PREFIX}${userId}`, JSON.stringify(conversations));
  } catch (err) {
    console.error('Failed to save conversations:', err);
  }
}

export function getProjects(userId: string = 'default_user'): Project[] {
  try {
    const raw = localStorage.getItem(`${PROJ_PREFIX}${userId}`);
    if (!raw) return [];
    return JSON.parse(raw) as Project[];
  } catch (err) {
    console.error('Failed to load projects:', err);
    return [];
  }
}

export function saveProjects(userId: string = 'default_user', projects: Project[]): void {
  try {
    localStorage.setItem(`${PROJ_PREFIX}${userId}`, JSON.stringify(projects));
  } catch (err) {
    console.error('Failed to save projects:', err);
  }
}

export function getActiveConversationId(): string | null {
  try {
    return localStorage.getItem(ACTIVE_CONV_KEY);
  } catch {
    return null;
  }
}

export function setActiveConversationId(id: string | null): void {
  try {
    if (id) {
      localStorage.setItem(ACTIVE_CONV_KEY, id);
    } else {
      localStorage.removeItem(ACTIVE_CONV_KEY);
    }
  } catch {
    // ignore
  }
}

export function createNewConversation(
  title: string = 'New Research Chat',
  projectId: string | null = null,
  initialDocIds: string[] = [],
  initialFeature: AnalysisMode = 'discover',
): Conversation {
  const now = new Date().toISOString();
  return {
    id: `conv_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
    title,
    createdAt: now,
    updatedAt: now,
    isPinned: false,
    projectId,
    selectedDocIds: initialDocIds,
    activeFeature: initialFeature,
    includeWeb: false,
    messages: [],
  };
}

export function createProject(name: string, description: string = ''): Project {
  return {
    id: `proj_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
    name: name.trim(),
    description: description.trim(),
    createdAt: new Date().toISOString(),
  };
}

/** Export entire conversation history as structured JSON */
export function exportAllConversationsJson(conversations: Conversation[], userId: string): void {
  const payload = {
    exportedAt: new Date().toISOString(),
    userId,
    totalConversations: conversations.length,
    conversations,
  };
  const jsonStr = JSON.stringify(payload, null, 2);
  const blob = new Blob([jsonStr], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `unknown_history_export_${Date.now()}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
