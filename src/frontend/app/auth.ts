/** Supabase credentials remain in this tab; the backend verifies account ownership. */
export interface AuthProfile {
  id: string;
  name: string;
  username: string;
  email?: string;
  google_email?: string | null;
  has_password?: boolean;
  phone?: string;
  home_city?: string;
  bio?: string;
  avatar_url?: string | null;
  avatar_kind?: 'initials' | 'google' | 'uploaded';
}
interface Session {
  access_token: string;
  refresh_token: string;
  expires_at: number;
  user: AuthProfile;
}
const key = 'di-cung-identity-v2';
const pkceKey = 'di-cung-pkce-v1';
const configured = (
  import.meta.env.VITE_AUTH_BASE_URL ??
  import.meta.env.VITE_API_BASE_URL ??
  ''
).trim();
let loaded = false;
let active: Session | null = null;
let generation = 0;
let refreshing: Promise<Session> | null = null;
let callback: Promise<AuthProfile | null> | null = null;
class SessionError extends Error {
  readonly status = 401;
}
function base() {
  const url = new URL(configured || '/', window.location.origin);
  if (
    !['https:', 'http:'].includes(url.protocol) ||
    url.username ||
    url.password ||
    url.search ||
    url.hash
  )
    throw new Error('Địa chỉ dịch vụ tài khoản không hợp lệ.');
  return url.href.replace(/\/$/, '');
}
export function profileFrom(value: unknown): AuthProfile {
  if (!value || typeof value !== 'object') throw new Error('Hồ sơ tài khoản không hợp lệ.');
  const record = value as Record<string, unknown>;
  const p = (record.user ?? record) as Record<string, unknown>;
  if (
    !p ||
    typeof p.id !== 'string' ||
    typeof p.name !== 'string' ||
    typeof p.username !== 'string'
  )
    throw new Error('Hồ sơ tài khoản thiếu thông tin.');
  return {
    id: p.id,
    name: p.name,
    username: p.username,
    ...(typeof p.email === 'string' ? { email: p.email } : {}),
    ...(typeof p.has_password === 'boolean' ? { has_password: p.has_password } : {}),
    ...(typeof p.google_email === 'string' || p.google_email === null
      ? { google_email: p.google_email }
      : {}),
    ...Object.fromEntries(
      ['phone', 'home_city', 'bio'].filter((k) => typeof p[k] === 'string').map((k) => [k, p[k]]),
    ),
    ...(p.avatar_url === null ||
    (typeof p.avatar_url === 'string' && /^https:\/\//.test(p.avatar_url))
      ? { avatar_url: p.avatar_url as string | null }
      : {}),
    ...(['initials', 'google', 'uploaded'].includes(String(p.avatar_kind))
      ? { avatar_kind: p.avatar_kind as AuthProfile['avatar_kind'] }
      : {}),
  };
}
function sessionFrom(value: unknown): Session {
  const s = value as Session;
  if (
    !s ||
    typeof s.access_token !== 'string' ||
    !s.access_token ||
    typeof s.refresh_token !== 'string' ||
    !s.refresh_token ||
    !Number.isFinite(s.expires_at)
  )
    throw new Error('Phiên đăng nhập không hợp lệ.');
  return {
    access_token: s.access_token,
    refresh_token: s.refresh_token,
    expires_at: s.expires_at,
    user: profileFrom(s),
  };
}
function read() {
  if (!loaded) {
    loaded = true;
    try {
      const s = JSON.parse(sessionStorage.getItem(key) ?? 'null');
      if (s?.service === base()) active = sessionFrom(s);
    } catch {
      active = null;
    }
  }
  return active;
}
export function clearAuth() {
  generation += 1;
  active = null;
  loaded = true;
  refreshing = null;
  try {
    sessionStorage.removeItem(key);
  } catch {
    /* memory session still cleared */
  }
  window.dispatchEvent(new Event('di-cung-auth'));
}
export function saveAuth(value: unknown) {
  const session = sessionFrom(value);
  generation += 1;
  active = session;
  loaded = true;
  persist();
  return session.user;
}
function persist() {
  try {
    sessionStorage.setItem(key, JSON.stringify({ service: base(), ...active }));
  } catch {
    /* Active session can still work without persistence. */
  }
}
export const readAuthProfile = () => read()?.user ?? null;
async function raw(
  path: string,
  body?: object,
  method = body ? 'POST' : 'GET',
  signal?: AbortSignal,
  token?: string,
): Promise<unknown> {
  const response = await fetch(`${base()}${path}`, {
    method,
    credentials: 'omit',
    signal,
    headers: {
      Accept: 'application/json',
      ...(body ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  const data: unknown = await response.json();
  signal?.throwIfAborted();
  if (!response.ok) {
    const d = data as { error?: { message?: string } };
    const error = new Error(d?.error?.message || 'Dịch vụ tài khoản chưa phản hồi.');
    Object.assign(error, { status: response.status });
    throw error;
  }
  return data;
}
async function refresh() {
  const session = read();
  if (!session) throw new SessionError('Hãy đăng nhập lại để tiếp tục.');
  if (!refreshing) {
    const epoch = generation;
    const task = raw('/auth/refresh', { refresh_token: session.refresh_token })
      .then(sessionFrom)
      .then((next) => {
        if (epoch !== generation) throw new Error('Tài khoản đã thay đổi.');
        if (next.user.id !== session.user.id) {
          clearAuth();
          throw new Error('Phiên làm mới không khớp tài khoản.');
        }
        active = next;
        persist();
        window.dispatchEvent(new Event('di-cung-auth'));
        return next;
      })
      .catch((error: unknown) => {
        if (epoch === generation && (error as { status?: number }).status === 401) clearAuth();
        throw error;
      })
      .finally(() => {
        if (refreshing === task) refreshing = null;
      });
    refreshing = task;
  }
  return refreshing;
}
export async function accountToken(ownerId: string) {
  let session = read();
  if (!session || session.user.id !== ownerId)
    throw new SessionError('Hãy đăng nhập đúng tài khoản để tiếp tục.');
  if (session.expires_at <= Date.now() / 1000 + 45) session = await refresh();
  if (session.user.id !== ownerId || read()?.user.id !== ownerId)
    throw new Error('Tài khoản đã thay đổi.');
  return session.access_token;
}
export function accountFetch(ownerId: string): typeof fetch {
  return async (input, init) => {
    const epoch = generation;
    const token = await accountToken(ownerId);
    init?.signal?.throwIfAborted();
    const headers = new Headers(init?.headers);
    headers.set('Authorization', `Bearer ${token}`);
    let response = await fetch(input, { ...init, headers });
    if (response.status === 401 && epoch === generation) {
      await refresh();
      init?.signal?.throwIfAborted();
      headers.set('Authorization', `Bearer ${await accountToken(ownerId)}`);
      response = await fetch(input, { ...init, headers });
      if (response.status === 401 && epoch === generation) clearAuth();
    }
    if (epoch !== generation) throw new DOMException('Account changed', 'AbortError');
    return response;
  };
}
export async function authRequest(
  path: string,
  body?: object,
  method = body ? 'POST' : 'GET',
  signal?: AbortSignal,
) {
  const epoch = generation;
  const owner = readAuthProfile()?.id;
  const token = owner ? await accountToken(owner) : undefined;
  try {
    const result = await raw(path, body, method, signal, token);
    if (epoch !== generation) throw new DOMException('Account changed', 'AbortError');
    return result;
  } catch (error) {
    if (
      !owner ||
      !(path === '/auth/logout' || path === '/auth/me' || path.startsWith('/auth/me/')) ||
      (error as { status?: number }).status !== 401
    )
      throw error;
    await refresh();
    signal?.throwIfAborted();
    try {
      const result = await raw(path, body, method, signal, await accountToken(owner));
      if (epoch !== generation) throw new DOMException('Account changed', 'AbortError');
      return result;
    } catch (next) {
      if ((next as { status?: number }).status === 401) clearAuth();
      throw next;
    }
  }
}
export function rememberProfile(value: unknown) {
  const profile = profileFrom(value);
  if (!active || active.user.id !== profile.id)
    throw new DOMException('Account changed', 'AbortError');
  active = { ...active, user: profile };
  persist();
  window.dispatchEvent(new Event('di-cung-auth'));
  return profile;
}
export async function currentProfile(signal?: AbortSignal) {
  if (!read()) throw new Error('Bạn đang dùng phiên ẩn danh.');
  const epoch = generation;
  const profile = profileFrom(await authRequest('/auth/me', undefined, 'GET', signal));
  if (epoch !== generation || active?.user.id !== profile.id)
    throw new DOMException('Account changed', 'AbortError');
  active = { ...active, user: profile };
  persist();
  return profile;
}
export async function authConfig(signal?: AbortSignal) {
  const d = (await raw('/auth/config', undefined, 'GET', signal)) as Record<string, unknown>;
  if (
    typeof d.enabled !== 'boolean' ||
    typeof d.email_enabled !== 'boolean' ||
    typeof d.google_enabled !== 'boolean'
  )
    throw new Error('Cấu hình tài khoản không hợp lệ.');
  return { enabled: d.enabled, email_enabled: d.email_enabled, google_enabled: d.google_enabled };
}
export const returnUrl = () =>
  new URL(`${import.meta.env.BASE_URL}auth`, window.location.origin).href;
const encode = (bytes: Uint8Array) =>
  btoa(String.fromCharCode(...bytes))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
export async function startGoogle() {
  const verifier = encode(crypto.getRandomValues(new Uint8Array(32)));
  const state = encode(crypto.getRandomValues(new Uint8Array(24)));
  const challenge = encode(
    new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier))),
  );
  sessionStorage.setItem(
    pkceKey,
    JSON.stringify({ verifier, state, service: base(), created: Date.now() }),
  );
  const url = new URL(returnUrl());
  url.searchParams.set('oauth_state', state);
  const result = (await raw('/auth/google/start', {
    return_url: url.href,
    code_challenge: challenge,
  })) as { redirect_url?: string };
  if (typeof result.redirect_url !== 'string')
    throw new Error('Chưa nhận được địa chỉ đăng nhập Google.');
  const redirect = new URL(result.redirect_url);
  if (redirect.protocol !== 'https:' || redirect.username || redirect.password)
    throw new Error('Địa chỉ đăng nhập không hợp lệ.');
  window.location.assign(redirect.href);
}
export function finishGoogle(): Promise<AuthProfile | null> {
  if (callback) return callback;
  const url = new URL(window.location.href);
  if (url.hash) window.history.replaceState(null, '', url.pathname + url.search);
  if (!url.searchParams.has('code') && !url.searchParams.has('error')) return Promise.resolve(null);
  const code = url.searchParams.get('code'),
    state = url.searchParams.get('oauth_state');
  const providerError = url.searchParams.has('error');
  window.history.replaceState(null, '', url.pathname);
  let pending: { verifier: string; state: string; service: string; created: number } | null = null;
  try {
    pending = JSON.parse(sessionStorage.getItem(pkceKey) ?? 'null');
  } catch {
    /* invalid callback is rejected */
  }
  sessionStorage.removeItem(pkceKey);
  callback = (async () => {
    if (
      providerError ||
      !code ||
      !pending ||
      pending.state !== state ||
      pending.service !== base() ||
      !Number.isFinite(pending.created) ||
      Date.now() - pending.created > 600_000 ||
      pending.created > Date.now()
    )
      throw new Error('Phiên đăng nhập Google đã hết hạn hoặc không khớp. Hãy thử lại.');
    return saveAuth(await raw('/auth/google/exchange', { code, code_verifier: pending.verifier }));
  })();
  return callback;
}
