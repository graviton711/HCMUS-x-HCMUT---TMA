import { emptySearchDraft } from '../../../entities/search-draft';
import type { LocalSession } from './types';
import { validChatMsg, validSession } from './validation';

const historyKey = 'di-cung:history:v1';

function scopedHistoryKey(ownerId?: string) {
  return ownerId ? `${historyKey}:user:${ownerId}` : historyKey;
}

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/** Strip keys outside the current shape so legacy saves load instead of being dropped. */
function migrateSession(session: unknown): unknown {
  if (!record(session) || !record(session.draft)) return session;
  const draft: Record<string, unknown> = {};
  for (const key of Object.keys(emptySearchDraft)) draft[key] = session.draft[key];
  if (draft.mode !== 'structured' && draft.mode !== 'text') draft.mode = 'structured';
  return {
    id: session.id,
    title: session.title,
    pinned: session.pinned,
    createdAt: session.createdAt,
    updatedAt: session.updatedAt,
    draft,
    messages: Array.isArray(session.messages) ? session.messages.filter(validChatMsg) : [],
    requirementId: session.requirementId ?? null,
    comparisonId: session.comparisonId ?? null,
    agentSessionId: session.agentSessionId ?? null,
  };
}

export function loadSessions(ownerId?: string): LocalSession[] {
  try {
    const data: unknown = JSON.parse(localStorage.getItem(scopedHistoryKey(ownerId)) || '[]');
    if (!Array.isArray(data)) return [];
    return data.map(migrateSession).filter(validSession);
  } catch {
    return [];
  }
}

export function saveSessions(sessions: LocalSession[], ownerId?: string) {
  try {
    localStorage.setItem(scopedHistoryKey(ownerId), JSON.stringify(sessions));
    return true;
  } catch {
    return false;
  }
}

export function newSession(): LocalSession {
  const time = new Date().toISOString();
  return {
    id: crypto.randomUUID(),
    title: '',
    pinned: false,
    createdAt: time,
    updatedAt: time,
    draft: structuredClone(emptySearchDraft),
    messages: [],
    requirementId: null,
    comparisonId: null,
    agentSessionId: null,
  };
}
