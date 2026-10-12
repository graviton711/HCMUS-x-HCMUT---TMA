import type { SearchDraft } from '../../../entities/search-draft';

export interface LocalSession {
  id: string;
  title: string;
  pinned: boolean;
  createdAt: string;
  updatedAt: string;
  draft: SearchDraft;
  messages: unknown[];
  requirementId: string | null;
  comparisonId: string | null;
  agentSessionId: string | null;
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
