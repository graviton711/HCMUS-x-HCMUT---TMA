// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { loadSessions, newSession, readAuthProfile, saveSessions } from './index';

function storedIdentity(overrides: Record<string, unknown> = {}) {
  return {
    service: new URL('/', window.location.origin).href.replace(/\/$/u, ''),
    access_token: 'old-access-token',
    refresh_token: 'old-refresh-token',
    expires_at: Math.floor(Date.now() / 1000) + 3600,
    user: { id: 'account-a', name: 'A User', username: 'a-user' },
    ...overrides,
  };
}

describe('read-only profile compatibility', () => {
  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
    vi.stubEnv('VITE_AUTH_BASE_URL', '');
    vi.stubEnv('VITE_API_BASE_URL', '');
  });

  it('selects an existing account-scoped local session without making a request', () => {
    const profile = storedIdentity();
    sessionStorage.setItem('di-cung-identity-v2', JSON.stringify(profile));
    const session = newSession();
    saveSessions([session], 'account-a');
    const fetcher = vi.spyOn(globalThis, 'fetch');

    expect(readAuthProfile()).toEqual({ id: 'account-a', name: 'A User', username: 'a-user' });
    expect(loadSessions(readAuthProfile()?.id)).toEqual([session]);
    expect(fetcher).not.toHaveBeenCalled();
  });

  it('ignores malformed identities and profiles from a different service', () => {
    sessionStorage.setItem(
      'di-cung-identity-v2',
      JSON.stringify(storedIdentity({ service: 'https://other.example' })),
    );
    expect(readAuthProfile()).toBeNull();

    sessionStorage.setItem(
      'di-cung-identity-v2',
      JSON.stringify(storedIdentity({ user: { id: 'account-a', name: 'A User' } })),
    );
    expect(readAuthProfile()).toBeNull();
  });
});
