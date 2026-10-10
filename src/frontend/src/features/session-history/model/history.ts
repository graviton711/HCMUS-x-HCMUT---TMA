import { emptySearchDraft } from '../../../entities/search-draft';
import type { LocalSession } from './types';
import { validSession } from './validation';

const historyKey = 'di-cung:history:v1';

function scopedHistoryKey(ownerId?: string) {
  return ownerId ? `${historyKey}:user:${ownerId}` : historyKey;
}

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function loadSessions(ownerId?: string): LocalSession[] {
  try {
    const data: unknown = JSON.parse(localStorage.getItem(scopedHistoryKey(ownerId)) || '[]');
    if (!Array.isArray(data)) return [];
    return data
      .map((session: unknown) => {
        if (!record(session) || !record(session.draft)) return session;
        return {
          ...session,
          draft: {
            ...session.draft,
            ...(Object.hasOwn(session.draft, 'departureMonths') ? {} : { departureMonths: [] }),
            ...(Object.hasOwn(session.draft, 'budgetMin') ? {} : { budgetMin: '' }),
          },
        };
      })
      .filter(validSession);
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
    requirementId: null,
    proposalId: null,
    comparisonId: null,
    pendingComparisonId: null,
    jobId: null,
    pendingMessageId: null,
    runs: [],
    chat: [],
  };
}
