// @vitest-environment jsdom
import { useState } from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { newSession, type LocalSession } from '../../../features/session-history';
import { PreferencesProvider } from '../../../shared/preferences';
import { useChat } from './useChat';

function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

const calls: { path: string; body: unknown }[] = [];

function makeBackend() {
  return vi.fn<typeof fetch>(async (input, init) => {
    const path = new URL(String(input), 'http://local').pathname;
    const method = init?.method ?? 'GET';
    const body = init?.body ? JSON.parse(String(init.body)) : null;
    calls.push({ path, body });
    if (path === '/sessions' && method === 'POST')
      return response(
        {
          id: 'ses_chat',
          session_id: 'ses_chat',
          token: 'chat-secret',
          token_type: 'Bearer',
          expires_at: '2030-01-01T00:00:00+00:00',
        },
        201,
      );
    if (path === '/catalog') return response({ destinations: ['Đà Lạt'] });
    if (path === '/health') return response({ status: 'ok', version: 'test' });
    if (path === '/requirements' && method === 'POST')
      return response({
        requirement: {
          id: `req_${(body?.drop_fields as string[] | undefined)?.join('+') || 'base'}`,
          conditions: [
            { id: 'h1', field: 'destination', operator: 'contains', value: 'Đà Lạt', strength: 'hard', quote: '' },
          ],
          missing: [],
          raw_text: 'Đà Lạt',
          travelers: 1,
        },
      });
    if (path === '/comparisons' && method === 'POST')
      return response({
        comparison: {
          id: 'cmp_chat',
          requirement: { id: 'req_base', conditions: [], missing: [], raw_text: 'Đà Lạt', travelers: 1 },
          ranked: [],
          near_miss: [],
          tour_snapshots: [],
          evaluations: [],
          analysis: { hidden_costs: [], conditions: [], risks: [], benefits: [] },
          candidates_considered: 1,
        },
      });
    if (path.startsWith('/requirements/'))
      return response({
        requirement: { id: 'req_base', conditions: [], missing: [], raw_text: 'Đà Lạt', travelers: 1 },
      });
    return response({ error: { code: 'NOT_FOUND', message: 'not found' } }, 404);
  });
}

type ChatApi = ReturnType<typeof useChat>;

function Inner({ initial, apiRef }: { initial: LocalSession; apiRef: { current: ChatApi | null } }) {
  const [session, setSession] = useState(initial);
  const chat = useChat(session, (changes) =>
    setSession((current) => ({ ...current, ...changes })),
  );
  apiRef.current = chat;
  return (
    <>
      <div data-testid="msgs">{chat.msgs.map((msg) => msg.kind).join(',')}</div>
      <div data-testid="busy">{chat.busy ? 'busy' : 'idle'}</div>
      <div data-testid="dropped">{chat.dropped.join('+')}</div>
      <div data-testid="title">{session.title}</div>
    </>
  );
}

function Probe({ initial, apiRef }: { initial: LocalSession; apiRef: { current: ChatApi | null } }) {
  return (
    <PreferencesProvider>
      <Inner initial={initial} apiRef={apiRef} />
    </PreferencesProvider>
  );
}

afterEach(() => {
  cleanup();
  sessionStorage.clear();
  localStorage.clear();
  calls.length = 0;
  vi.unstubAllGlobals();
});

describe('useChat relax and undo', () => {
  it('sends, compares, relaxes with drop_fields, then undoes', async () => {
    vi.stubGlobal('fetch', makeBackend());
    const apiRef: { current: ChatApi | null } = { current: null };
    render(<Probe initial={newSession()} apiRef={apiRef} />);

    await waitFor(() => expect(screen.getByTestId('busy').textContent).toBe('idle'));
    await waitFor(() => expect(apiRef.current?.catalog).toBeTruthy());

    apiRef.current?.send('Đà Lạt');
    await waitFor(() =>
      expect(screen.getByTestId('msgs').textContent).toBe('user,interpretation,comparison'),
    );
    expect(calls.some((call) => call.path === '/comparisons')).toBe(true);

    apiRef.current?.relax('date_from');
    await waitFor(() => expect(screen.getByTestId('dropped').textContent).toBe('date_from'));
    const relaxed = calls.filter((call) => call.path === '/requirements').pop();
    expect((relaxed?.body as { drop_fields?: string[] }).drop_fields).toEqual(['date_from']);
    await waitFor(() =>
      expect(screen.getByTestId('msgs').textContent).toBe(
        'user,interpretation,comparison,assistant,interpretation,comparison',
      ),
    );

    apiRef.current?.undo();
    await waitFor(() => expect(screen.getByTestId('dropped').textContent).toBe(''));
    expect(screen.getByTestId('msgs').textContent).toBe('user,interpretation,comparison');
  });

  it('names the session from the interpreted destination, not the raw request', async () => {
    vi.stubGlobal('fetch', makeBackend());
    const apiRef: { current: ChatApi | null } = { current: null };
    render(<Probe initial={newSession()} apiRef={apiRef} />);

    await waitFor(() => expect(screen.getByTestId('busy').textContent).toBe('idle'));
    await waitFor(() => expect(apiRef.current?.catalog).toBeTruthy());

    apiRef.current?.send('muốn đi du lịch đâu đó 3 ngày');
    await waitFor(() =>
      expect(screen.getByTestId('msgs').textContent).toBe('user,interpretation,comparison'),
    );
    expect(screen.getByTestId('title').textContent).toBe('Đà Lạt');
  });
});
