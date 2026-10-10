import { emptyForm, type FormValues } from '../api/form';
import { validMonth } from '../api/travelFilters';

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
  draft: FormValues;
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
const historyKey = 'di-cung:history:v1';
const accessKey = 'di-cung:access:v1';
const record = (v: unknown): v is Record<string, unknown> =>
  typeof v === 'object' && v !== null && !Array.isArray(v);

function validDraft(v: unknown): v is FormValues {
  if (!record(v)) return false;
  const levels = v.preferenceLevels;
  return (
    Object.entries(emptyForm).every(([key, original]) => {
      const value = v[key];
      if (Array.isArray(original)) return Array.isArray(value);
      if (record(original)) return record(value);
      return typeof value === typeof original;
    }) &&
    ['structured', 'text', 'urls'].includes(String(v.mode)) &&
    ['destinations', 'transport', 'includedServices', 'referenceUrls'].every(
      (key) => Array.isArray(v[key]) && v[key].every((item) => typeof item === 'string'),
    ) &&
    Array.isArray(v.childAges) &&
    Array.isArray(v.departureMonths) &&
    v.departureMonths.length <= 12 &&
    v.departureMonths.every((month) => typeof month === 'string' && validMonth(month)) &&
    v.childAges.every(
      (age) =>
        age === null || (typeof age === 'number' && Number.isInteger(age) && age >= 0 && age <= 17),
    ) &&
    record(levels) &&
    ['cost', 'comfort', 'pace', 'culture'].every(
      (key) =>
        typeof levels[key] === 'number' &&
        Number.isInteger(levels[key]) &&
        levels[key] >= 0 &&
        levels[key] <= 5,
    ) &&
    record(v.strengths) &&
    Object.values(v.strengths).every((value) => value === 'hard' || value === 'soft') &&
    ['any', 'few', 'none'].includes(String(v.shopping)) &&
    ['per_adult', 'per_person', 'group_total'].includes(String(v.budgetBasis))
  );
}

function validSession(v: unknown): v is LocalSession {
  if (!record(v) || typeof v.id !== 'string' || typeof v.title !== 'string' || !validDraft(v.draft))
    return false;
  return (
    typeof v.pinned === 'boolean' &&
    typeof v.createdAt === 'string' &&
    typeof v.updatedAt === 'string' &&
    [
      'requirementId',
      'proposalId',
      'comparisonId',
      'pendingComparisonId',
      'jobId',
      'pendingMessageId',
    ].every((k) => v[k] === null || typeof v[k] === 'string') &&
    Array.isArray(v.runs) &&
    v.runs.every(
      (r) =>
        record(r) &&
        typeof r.id === 'string' &&
        typeof r.revision === 'number' &&
        typeof r.createdAt === 'string',
    ) &&
    Array.isArray(v.chat) &&
    v.chat.every(
      (m) =>
        record(m) &&
        typeof m.id === 'string' &&
        ['user', 'assistant'].includes(String(m.role)) &&
        typeof m.text === 'string',
    )
  );
}

function scopedHistoryKey(ownerId?: string) {
  return ownerId ? `${historyKey}:user:${ownerId}` : historyKey;
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
            ...(Object.hasOwn(session.draft, 'preferLowerListedPrice')
              ? {}
              : { preferLowerListedPrice: false }),
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
    draft: structuredClone(emptyForm),
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
export function getAccess(id: string): SessionAccess | null {
  try {
    const entries: unknown = JSON.parse(sessionStorage.getItem(accessKey) || '{}');
    const v = record(entries) ? entries[id] : null;
    return record(v) &&
      typeof v.token === 'string' &&
      typeof v.expiresAt === 'string' &&
      typeof v.backendId === 'string' &&
      Date.parse(v.expiresAt) > Date.now()
      ? { token: v.token, expiresAt: v.expiresAt, backendId: v.backendId }
      : null;
  } catch {
    return null;
  }
}
export function putAccess(id: string, access: SessionAccess) {
  let existing: Record<string, unknown> = {};
  try {
    const parsed: unknown = JSON.parse(sessionStorage.getItem(accessKey) || '{}');
    if (record(parsed)) existing = parsed;
  } catch {
    /* empty storage */
  }
  sessionStorage.setItem(accessKey, JSON.stringify({ ...existing, [id]: access }));
}
export function removeAccess(id: string) {
  try {
    const parsed: unknown = JSON.parse(sessionStorage.getItem(accessKey) || '{}');
    if (record(parsed)) {
      delete parsed[id];
      sessionStorage.setItem(accessKey, JSON.stringify(parsed));
    }
  } catch {
    /* no access to remove */
  }
}
export function normalizeSearch(value: string) {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .toLowerCase()
    .trim();
}
