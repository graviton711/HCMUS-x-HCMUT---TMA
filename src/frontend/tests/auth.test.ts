// @vitest-environment jsdom
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';

const session = (id = 'account-a', expires_at = Date.now() / 1000 + 3600) => ({
  access_token: `token-${id}`,
  refresh_token: `refresh-${id}`,
  expires_at,
  user: { id, name: 'Tester', username: 'tester@example.test' },
});
const json = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });
beforeEach(() => {
  vi.resetModules();
  sessionStorage.clear();
  localStorage.clear();
  vi.stubEnv('VITE_AUTH_BASE_URL', '');
  vi.stubEnv('VITE_API_BASE_URL', '');
  window.history.replaceState(null, '', '/auth');
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});
describe('account credentials and PKCE', () => {
  it('rotates one refresh token for concurrent API calls and keeps credentials outside history', async () => {
    const fetcher = vi.fn().mockResolvedValue(json(session()));
    vi.stubGlobal('fetch', fetcher);
    const auth = await import('../app/auth');
    auth.saveAuth(session('account-a', 1));
    const tokens = await Promise.all([
      auth.accountToken('account-a'),
      auth.accountToken('account-a'),
    ]);
    expect(tokens).toEqual(['token-account-a', 'token-account-a']);
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(String(fetcher.mock.calls[0][0])).toContain('/auth/refresh');
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.getItem('di-cung-identity-v2')).toContain('refresh-account-a');
  });
  it('rejects a refresh arriving after switching accounts', async () => {
    let complete!: (r: Response) => void;
    vi.stubGlobal(
      'fetch',
      vi.fn(
        () =>
          new Promise<Response>((resolve) => {
            complete = resolve;
          }),
      ),
    );
    const auth = await import('../app/auth');
    auth.saveAuth(session('account-a', 1));
    const pending = auth.accountToken('account-a');
    const rejected = expect(pending).rejects.toThrow('Tài khoản đã thay đổi');
    auth.clearAuth();
    auth.saveAuth(session('account-b'));
    complete(json(session()));
    await rejected;
    expect(auth.readAuthProfile()?.id).toBe('account-b');
  });
  it('retries an unauthorized request with refreshed credentials and preserves its mutation key', async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(json({}, 401))
      .mockResolvedValueOnce(json(session()))
      .mockResolvedValueOnce(json({ data: 'success' }));
    vi.stubGlobal('fetch', fetcher);
    const auth = await import('../app/auth');
    auth.saveAuth(session());
    const result = await auth.accountFetch('account-a')('/v2/test', {
      method: 'POST',
      body: '{}',
      headers: { 'Idempotency-Key': 'stable' },
    });
    expect(result.ok).toBe(true);
    expect(fetcher).toHaveBeenCalledTimes(3);
    expect(new Headers(fetcher.mock.calls[2][1]?.headers).get('Idempotency-Key')).toBe('stable');
  });
  it('exchanges a callback once, checks state and removes callback secrets from the URL', async () => {
    const fetcher = vi.fn().mockResolvedValue(json(session()));
    vi.stubGlobal('fetch', fetcher);
    const auth = await import('../app/auth');
    sessionStorage.setItem(
      'di-cung-pkce-v1',
      JSON.stringify({
        verifier: 'a'.repeat(43),
        state: 'state-test',
        service: window.location.origin,
        created: Date.now(),
      }),
    );
    window.history.replaceState(null, '', '/auth?code=test-code&oauth_state=state-test');
    const first = auth.finishGoogle();
    expect(auth.finishGoogle()).toBe(first);
    expect((await first)?.id).toBe('account-a');
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(window.location.search).toBe('');
    expect(sessionStorage.getItem('di-cung-pkce-v1')).toBeNull();
  });
  it('rejects corrupt or mismatched callback storage without exchanging a code', async () => {
    const fetcher = vi.fn();
    vi.stubGlobal('fetch', fetcher);
    const auth = await import('../app/auth');
    sessionStorage.setItem('di-cung-pkce-v1', '{bad');
    window.history.replaceState(null, '', '/auth?code=private-code&oauth_state=mismatch');
    await expect(auth.finishGoogle()).rejects.toThrow('không khớp');
    expect(fetcher).not.toHaveBeenCalled();
    expect(window.location.href).not.toContain('private-code');
  });
  it('clears an invalid refresh session and notifies the app', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ error: { message: 'Expired' } }, 401)));
    const listener = vi.fn();
    window.addEventListener('di-cung-auth', listener);
    const auth = await import('../app/auth');
    auth.saveAuth(session('account-a', 1));
    await expect(auth.accountToken('account-a')).rejects.toThrow('Expired');
    expect(auth.readAuthProfile()).toBeNull();
    expect(listener).toHaveBeenCalledOnce();
    window.removeEventListener('di-cung-auth', listener);
  });
});
