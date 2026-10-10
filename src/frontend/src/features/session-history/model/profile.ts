import type { AuthProfile } from './types';

const identityKey = 'di-cung-identity-v2';
const configuredService = (
  import.meta.env.VITE_AUTH_BASE_URL ??
  import.meta.env.VITE_API_BASE_URL ??
  ''
).trim();

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function serviceUrl() {
  const url = new URL(configuredService || '/', window.location.origin);
  if (
    !['https:', 'http:'].includes(url.protocol) ||
    url.username ||
    url.password ||
    url.search ||
    url.hash
  )
    return null;
  return url.href.replace(/\/$/u, '');
}

/** Reads identity metadata only so existing account-scoped browser history remains visible. */
export function readAuthProfile(): AuthProfile | null {
  try {
    const service = serviceUrl();
    const saved: unknown = JSON.parse(sessionStorage.getItem(identityKey) ?? 'null');
    if (!service || !isRecord(saved) || saved.service !== service) return null;
    if (
      typeof saved.access_token !== 'string' ||
      !saved.access_token ||
      typeof saved.refresh_token !== 'string' ||
      !saved.refresh_token ||
      typeof saved.expires_at !== 'number' ||
      !Number.isFinite(saved.expires_at) ||
      !isRecord(saved.user)
    )
      return null;

    const { id, name, username } = saved.user;
    if (typeof id !== 'string' || typeof name !== 'string' || typeof username !== 'string')
      return null;
    return { id, name, username };
  } catch {
    return null;
  }
}
