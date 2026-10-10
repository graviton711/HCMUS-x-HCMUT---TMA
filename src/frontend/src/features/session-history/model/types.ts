import type { SearchDraft } from '../../../entities/search-draft';

export interface ChatLine {
  id: string;
  role: 'user' | 'assistant';
  text: string;
}

export interface SavedRun {
  id: string;
  revision: number;
  createdAt: string;
}

export interface LocalSession {
  id: string;
  title: string;
  pinned: boolean;
  createdAt: string;
  updatedAt: string;
  draft: SearchDraft;
  requirementId: string | null;
  proposalId: string | null;
  comparisonId: string | null;
  pendingComparisonId: string | null;
  jobId: string | null;
  analysisId?: string | null;
  historyVersion?: number;
  serverHydrated?: boolean;
  pendingMessageId: string | null;
  runs: SavedRun[];
  chat: ChatLine[];
}

export interface SessionAccess {
  token: string;
  expiresAt: string;
  backendId: string;
}

export interface AuthProfile {
  id: string;
  name: string;
  username: string;
}
