import type { AnalysisMode, WorkspaceResult } from './query';
import type { BackendDocumentOverview } from '../lib/api';

export type ScopeOption = 'this_document' | 'selected' | 'all' | 'documents_web';

export interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant' | 'overview';
  timestamp: string;
  text?: string;
  feature?: AnalysisMode;
  scope?: ScopeOption;
  selectedDocIds?: string[];
  includeWeb?: boolean;
  overview?: BackendDocumentOverview;
  isOverviewLoading?: boolean;
  documentName?: string;
  result?: WorkspaceResult;
  isLoading?: boolean;
  error?: string;
}

export interface Conversation {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  isPinned: boolean;
  projectId?: string | null;
  selectedDocIds: string[];
  activeFeature: AnalysisMode;
  includeWeb: boolean;
  messages: ChatMessage[];
}

export interface Project {
  id: string;
  name: string;
  description?: string;
  createdAt: string;
}
