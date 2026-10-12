import type { LocalSession, SessionAccess } from './types';
import { CurrentBackendClient } from '../../../shared/api';

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

export const EXPIRED_SESSION_MESSAGE =
  'Guest session expired. The draft is still here — start a new session to keep searching.';

/** The stored token no longer grants access; only a new session can continue. */
export class SessionExpiredError extends Error {
  constructor(message = EXPIRED_SESSION_MESSAGE) {
    super(message);
    this.name = 'SessionExpiredError';
  }
}

export function isSessionExpired(cause: unknown): boolean {
  return cause instanceof SessionExpiredError;
}

const accessFlights = new Map<string, Promise<SessionAccess>>();

export async function accessFor(session: LocalSession): Promise<SessionAccess> {
  const saved = getAccess(session.id);
  if (saved) return saved;
  if (session.requirementId || session.agentSessionId) throw new SessionExpiredError();
  const pending = accessFlights.get(session.id);
  if (pending) return pending;
  const request = new CurrentBackendClient()
    .createSession()
    .then((created) => {
      const access = {
        token: created.token,
        expiresAt: created.expires_at,
        backendId: created.session_id || created.id,
      };
      putAccess(session.id, access);
      return access;
    })
    .finally(() => accessFlights.delete(session.id));
  accessFlights.set(session.id, request);
  return request;
}
