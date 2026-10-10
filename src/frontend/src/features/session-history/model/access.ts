import type { SessionAccess } from './types';

const accessKey = 'di-cung:access:v1';

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
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
