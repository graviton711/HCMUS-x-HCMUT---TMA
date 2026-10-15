// @vitest-environment jsdom
import { useState } from 'react';
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
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
const requirement = {
  id: 'req_dalat',
  conditions: [
    {
      id: 'h1',
      field: 'destination',
      operator: 'contains',
      value: 'Đà Lạt',
      strength: 'hard',
      quote: 'Đà Lạt',
    },
  ],
  missing: [],
  raw_text: 'Đà Lạt, tháng 12',
  travelers: 1,
};
const comparison = {
  id: 'cmp_chat',
  requirement,
  ranked: [],
  near_miss: [],
  tour_snapshots: [],
  evaluations: [],
  analysis: { hidden_costs: [], conditions: [], risks: [], benefits: [] },
  candidates_considered: 1,
};

function makeBackend(modelDenied = false) {
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
    if (path === '/health') return response({ status: 'ok', version: 'test' });
    if (path === '/agent/sessions' && method === 'POST')
      return response({ agent_session_id: 'agt_0123456789abcdef0123456789abcdef' }, 201);
    if (path.endsWith('/decisions') && method === 'POST')
      return response({
        assistant_text: 'Đã so sánh theo tiêu chí đã xác nhận.',
        tool_calls: [
          { name: 'query_tours', status: 'completed' },
          { name: 'score_soft', status: 'completed' },
        ],
        requirement,
        comparison,
      });
    if (path.endsWith('/messages') && method === 'POST') {
      if (modelDenied)
        return response(
          { error: { code: 'OPENCODE_MODEL_ACCESS_DENIED', message: 'OpenCode rejected access.' } },
          502,
        );
      if (body?.message === 'Đà Lạt')
        return response({
          assistant_text: 'Bạn muốn đi vào tháng nào?',
          choices: {
            question: 'Thời gian nào phù hợp?',
            options: [
              { label: 'Tháng 12', value: 'tháng 12' },
              { label: 'Tháng 1', value: 'tháng 1' },
            ],
            allow_custom: true,
          },
          tool_calls: [{ name: 'ask_choice', status: 'completed' }],
        });
      return response({
        assistant_text: 'Mình đã chuẩn bị bản tiêu chí để bạn xem lại.',
        tool_calls: [{ name: 'draft_requirement', status: 'completed' }],
        requirement,
        decision_draft: requirement,
      });
    }
    return response({ error: { code: 'NOT_FOUND', message: 'not found' } }, 404);
  });
}

type ChatApi = ReturnType<typeof useChat>;

function Inner({
  initial,
  apiRef,
  sessionRef,
}: {
  initial: LocalSession;
  apiRef: { current: ChatApi | null };
  sessionRef?: { current: LocalSession | null };
}) {
  const [session, setSession] = useState(initial);
  const chat = useChat(session, (changes) => setSession((current) => ({ ...current, ...changes })));
  apiRef.current = chat;
  if (sessionRef) sessionRef.current = session;
  return (
    <>
      <div data-testid="msgs">{chat.msgs.map((msg) => msg.kind).join(',')}</div>
      <div data-testid="message-texts">
        {chat.msgs.map((msg) => ('text' in msg ? msg.text : '')).join('\n')}
      </div>
      <div data-testid="busy">{chat.busy ? 'busy' : 'idle'}</div>
      <div data-testid="tool-states">
        {chat.msgs
          .filter((message) => message.kind === 'tool_activity')
          .flatMap((message) =>
            message.tools.map((tool) => `${tool.name}:${tool.message ?? ''}:${tool.status}`),
          )
          .join(',')}
      </div>
      <div data-testid="title">{session.title}</div>
      <div data-testid="agent-session">{session.agentSessionId ?? ''}</div>
    </>
  );
}

function Probe({
  initial,
  apiRef,
  sessionRef,
}: {
  initial: LocalSession;
  apiRef: { current: ChatApi | null };
  sessionRef?: { current: LocalSession | null };
}) {
  return (
    <PreferencesProvider>
      <Inner initial={initial} apiRef={apiRef} sessionRef={sessionRef} />
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

describe('useChat OpenCode agent loop', () => {
  it('persists confirmed weight IDs per brief while sending only final requirement weights', async () => {
    vi.stubGlobal('fetch', makeBackend());
    const apiRef: { current: ChatApi | null } = { current: null };
    const sessionRef: { current: LocalSession | null } = { current: null };
    const view = render(<Probe initial={newSession()} apiRef={apiRef} sessionRef={sessionRef} />);
    await waitFor(() => expect(screen.getByTestId('busy').textContent).toBe('idle'));
    act(() => apiRef.current?.send('tháng 12'));
    await waitFor(() => expect(screen.getByTestId('msgs').textContent).toContain('decision_draft'));
    const draft = apiRef.current!.msgs.find((message) => message.kind === 'decision_draft')!;
    if (draft.kind !== 'decision_draft') throw new Error('Brief was not created');
    const reviewed = {
      ...draft.requirement,
      raw_text: `${draft.requirement.raw_text} nhẹ nhàng văn hóa uy tín`,
      conditions: [
        ...draft.requirement.conditions,
        ...['nhẹ nhàng', 'văn hóa', 'uy tín'].map((value, index) => ({
          id: `soft-${index}`, field: 'preference', operator: 'contains', strength: 'soft' as const,
          value, quote: value, weight_percent: [40, 35, 25][index],
        })),
      ],
    };
    act(() => apiRef.current?.updateDecisionDraft(
      draft.id, reviewed, ['soft-0', 'soft-1', 'soft-0', 'h1', 'deleted'],
    ));
    act(() => apiRef.current?.updateDecisionDraft(draft.id, { ...reviewed, travelers: 2 }));
    const saved = sessionRef.current!;
    expect(saved.messages.find((message) => (message as { id: string }).id === draft.id))
      .toMatchObject({ confirmedWeightIds: ['soft-0', 'soft-1'] });
    view.unmount();

    render(<Probe initial={saved} apiRef={apiRef} />);
    await waitFor(() => expect(screen.getByTestId('busy').textContent).toBe('idle'));
    const restored = apiRef.current!.msgs.find((message) => message.id === draft.id)!;
    if (restored.kind !== 'decision_draft') throw new Error('Brief was not restored');
    expect(restored.confirmedWeightIds).toEqual(['soft-0', 'soft-1']);
    act(() => apiRef.current?.runDecision(restored.id, restored.requirement));
    await waitFor(() => expect(calls.some((call) => call.path.endsWith('/decisions'))).toBe(true));
    const body = calls.find((call) => call.path.endsWith('/decisions'))!.body;
    expect(body).toEqual({ requirement: { ...reviewed, travelers: 2 } });
    expect(JSON.stringify(body)).not.toContain('confirmedWeightIds');
    await waitFor(() => expect(screen.getByTestId('busy').textContent).toBe('idle'));
  });

  it('reuses one agent session, reviews a draft, and sends the confirmed requirement to comparison', async () => {
    vi.stubGlobal('fetch', makeBackend());
    const apiRef: { current: ChatApi | null } = { current: null };
    render(<Probe initial={newSession()} apiRef={apiRef} />);

    await waitFor(() => expect(screen.getByTestId('busy').textContent).toBe('idle'));
    expect(screen.getByTestId('agent-session').textContent).toMatch(/^agt_/u);

    apiRef.current?.send('Đà Lạt');
    await waitFor(() =>
      expect(screen.getByTestId('msgs').textContent).toBe('user,tool_activity,assistant,choice'),
    );

    apiRef.current?.send('tháng 12');
    await waitFor(() =>
      expect(screen.getByTestId('msgs').textContent).toBe(
        'user,tool_activity,assistant,choice,user,tool_activity,assistant,decision_draft',
      ),
    );
    expect(screen.getByTestId('title').textContent).toBe('Đà Lạt');

    const draft = apiRef.current?.msgs.find((message) => message.kind === 'decision_draft');
    expect(draft?.kind).toBe('decision_draft');
    if (draft?.kind === 'decision_draft') apiRef.current?.runDecision(draft.id, draft.requirement);
    await waitFor(() => expect(screen.getByTestId('msgs').textContent).toContain('comparison'));

    const messages = calls.filter((call) => call.path.endsWith('/messages'));
    expect(messages.map((call) => (call.body as { message: string }).message)).toEqual([
      'Đà Lạt',
      'tháng 12',
    ]);
    expect(messages[0].path).toBe(messages[1].path);
    const decisions = calls.filter((call) => call.path.endsWith('/decisions'));
    expect(decisions).toHaveLength(1);
    expect((decisions[0]?.body as { requirement: { id: string } }).requirement.id).toBe('req_dalat');
  });

  it('restores the full transcript after remount without sending the prompt again', async () => {
    vi.stubGlobal('fetch', makeBackend());
    const sessionRef: { current: LocalSession | null } = { current: null };
    const firstApiRef: { current: ChatApi | null } = { current: null };
    const firstRender = render(
      <Probe initial={newSession()} apiRef={firstApiRef} sessionRef={sessionRef} />,
    );

    await waitFor(() => expect(screen.getByTestId('busy').textContent).toBe('idle'));
    firstApiRef.current?.send('Đà Lạt');
    await waitFor(() =>
      expect(screen.getByTestId('msgs').textContent).toContain('assistant,choice'),
    );
    firstApiRef.current?.send('tháng 12');
    await waitFor(() => expect(screen.getByTestId('msgs').textContent).toContain('decision_draft'));
    const draft = firstApiRef.current?.msgs.find((message) => message.kind === 'decision_draft');
    if (draft?.kind === 'decision_draft') firstApiRef.current?.runDecision(draft.id, draft.requirement);
    await waitFor(() => expect(screen.getByTestId('msgs').textContent).toContain('comparison'));

    const saved = sessionRef.current;
    expect(saved?.messages.map((message) => (message as { kind: string }).kind)).toEqual([
      'user',
      'tool_activity',
      'assistant',
      'choice',
      'user',
      'tool_activity',
      'assistant',
      'decision_draft',
      'tool_activity',
      'assistant',
      'comparison',
    ]);
    const sentBeforeReload = calls.filter((call) => call.path.endsWith('/messages')).length;
    firstRender.unmount();

    const restoredApiRef: { current: ChatApi | null } = { current: null };
    render(<Probe initial={saved!} apiRef={restoredApiRef} />);
    await waitFor(() =>
      expect(screen.getByTestId('msgs').textContent).toBe(
        'user,tool_activity,assistant,choice,user,tool_activity,assistant,decision_draft,tool_activity,assistant,comparison',
      ),
    );
    expect(calls.filter((call) => call.path.endsWith('/messages'))).toHaveLength(sentBeforeReload);
  });

  it('renders tool progress as soon as an SSE event arrives, before the final response', async () => {
    const fallback = makeBackend();
    let finishStream = () => {};
    const fetcher = vi.fn<typeof fetch>(async (input, init) => {
      const path = new URL(String(input), 'http://local').pathname;
      if (!path.endsWith('/messages')) return fallback(input, init);

      const encoder = new TextEncoder();
      return new Response(
        new ReadableStream<Uint8Array>({
          start(controller) {
            const emit = (name: string, payload: unknown) =>
              controller.enqueue(
                encoder.encode(`event: ${name}\ndata: ${JSON.stringify(payload)}\n\n`),
              );
            emit('progress', { status: 'working' });
            emit('tool', {
              id: 'call-1',
              name: 'catalog_facets',
              message: 'Kiểm tra điểm đến, giá và ngày khởi hành trong dữ liệu',
              status: 'running',
            });
            finishStream = () => {
              emit('tool', {
                id: 'call-1',
                name: 'catalog_facets',
                message: 'Kiểm tra điểm đến, giá và ngày khởi hành trong dữ liệu',
                status: 'completed',
              });
              emit('result', { assistant_text: 'Đã kiểm tra.', tool_calls: [] });
              controller.close();
            };
          },
        }),
        { headers: { 'Content-Type': 'text/event-stream' } },
      );
    });
    vi.stubGlobal('fetch', fetcher);
    const apiRef: { current: ChatApi | null } = { current: null };
    render(<Probe initial={newSession()} apiRef={apiRef} />);
    await waitFor(() => expect(screen.getByTestId('busy').textContent).toBe('idle'));

    apiRef.current?.send('Tìm tour');
    await waitFor(() =>
      expect(screen.getByTestId('tool-states').textContent).toBe(
        'catalog_facets:Kiểm tra điểm đến, giá và ngày khởi hành trong dữ liệu:running',
      ),
    );
    expect(screen.getByTestId('busy').textContent).toBe('busy');

    finishStream();
    await waitFor(() =>
      expect(screen.getByTestId('tool-states').textContent).toBe(
        'catalog_facets:Kiểm tra điểm đến, giá và ngày khởi hành trong dữ liệu:completed',
      ),
    );
    expect(screen.getByTestId('message-texts').textContent).toContain('Đã kiểm tra.');
  });

  it('explains when OpenCode rejects the configured free model', async () => {
    vi.stubGlobal('fetch', makeBackend(true));
    const apiRef: { current: ChatApi | null } = { current: null };
    render(<Probe initial={newSession()} apiRef={apiRef} />);

    await waitFor(() => expect(screen.getByTestId('busy').textContent).toBe('idle'));
    apiRef.current?.send('chào');

    await waitFor(() =>
      expect(screen.getByTestId('message-texts').textContent).toContain(
        'Model đang dùng chưa cho phép gửi yêu cầu từ ứng dụng. Hãy chọn model khác hoặc liên hệ quản trị viên.',
      ),
    );
  });
});
