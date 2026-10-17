import { describe, expect, it, vi } from 'vitest';
import { CurrentBackendClient } from './client';
import { CurrentApiError } from './errors';

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('CurrentBackendClient', () => {
  it('creates one guest session without a bearer token or legacy envelope', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      jsonResponse(
        {
          id: 'ses_1',
          session_id: 'ses_1',
          token: 'secret',
          token_type: 'Bearer',
          expires_at: '2030-01-01T00:00:00+00:00',
        },
        201,
      ),
    );
    const client = new CurrentBackendClient(undefined, 'https://api.example/', fetcher);

    const result = await client.createSession();
    expect(result.session_id).toBe('ses_1');
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher).toHaveBeenCalledWith(
      'https://api.example/sessions',
      expect.objectContaining({ method: 'POST', credentials: 'omit' }),
    );
  });

  it('uses the active backend path and owner token for scenario posts', async () => {
    const requirement = { id: 'req_1' };
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse({ assistant_text: '', tool_calls: [] }));
    const client = new CurrentBackendClient('guest-token', '', fetcher);

    await client.criteriaScenario('cmp-1', 'agent-1', requirement as never);
    const [url, init] = fetcher.mock.calls[0];
    expect(url).toBe('/comparisons/cmp-1/scenarios');
    expect(init?.headers).toMatchObject({ Authorization: 'Bearer guest-token' });
    expect(JSON.parse(String(init?.body))).toEqual({
      kind: 'criteria',
      agent_session_id: 'agent-1',
      requirement,
    });
  });

  it('sends the reviewed brief to the dedicated decision endpoint', async () => {
    const requirement = {
      id: 'req_reviewed',
      conditions: [
        {
          id: 's1',
          field: 'preference',
          operator: 'contains',
          value: 'thiên nhiên',
          strength: 'soft' as const,
          quote: 'thiên nhiên',
          weight_percent: 100,
        },
      ],
      missing: [],
      raw_text: 'thích thiên nhiên',
      travelers: 1,
    };
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse({ assistant_text: '', tool_calls: [], comparison: {} }));
    const client = new CurrentBackendClient('guest-token', '', fetcher);

    await client.agentDecisionStream('agent-1', requirement, () => {});

    expect(fetcher.mock.calls[0]?.[0]).toBe('/agent/sessions/agent-1/decisions');
    expect(JSON.parse(String(fetcher.mock.calls[0]?.[1]?.body))).toEqual({ requirement });
    expect(fetcher.mock.calls[0]?.[1]?.headers).toMatchObject({
      Authorization: 'Bearer guest-token',
      Accept: 'text/event-stream',
    });
  });

  it('streams the next soft-review group from the selected comparison snapshot', async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse({ assistant_text: '', comparison: { id: 'cmp-next' } }));
    const client = new CurrentBackendClient('guest-token', '', fetcher);
    const onEvent = vi.fn();

    await client.expandComparisonStream('cmp/first', 'agent-1', onEvent);

    expect(fetcher.mock.calls[0]?.[0]).toBe('/comparisons/cmp%2Ffirst/expand');
    expect(fetcher.mock.calls[0]?.[1]).toMatchObject({
      method: 'POST',
      headers: {
        Authorization: 'Bearer guest-token',
        Accept: 'text/event-stream',
      },
    });
    expect(JSON.parse(String(fetcher.mock.calls[0]?.[1]?.body))).toEqual({
      agent_session_id: 'agent-1',
    });
  });

  it('keeps eliminated cursors in the query string and URL-encodes comparison ids', async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ items: [], next_cursor: null }));
    const client = new CurrentBackendClient('guest-token', '', fetcher);

    await client.eliminatedOffers('cmp /one', 'cursor /?', 20, 'h2');
    expect(fetcher.mock.calls[0][0]).toBe(
      '/comparisons/cmp%20%2Fone/eliminated?limit=20&cursor=cursor+%2F%3F&condition_id=h2',
    );
  });

  it('surfaces backend error codes without retrying the mutation', async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(
        jsonResponse({ error: { code: 'SESSION_EXPIRED', message: 'expired' } }, 401),
      );
    const client = new CurrentBackendClient('expired-token', '', fetcher);

    await expect(
      client.criteriaScenario('cmp-1', 'agent-1', { id: 'req_1' } as never),
    ).rejects.toMatchObject({
      code: 'SESSION_EXPIRED',
      status: 401,
    } satisfies Partial<CurrentApiError>);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it('bypasses the ngrok interstitial for ngrok tunnel origins', async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ status: 'ok' }))
      .mockResolvedValue(jsonResponse({ assistant_text: '', tool_calls: [] }));
    const client = new CurrentBackendClient(
      'guest-token',
      'https://unharping-preascetic-alonzo.ngrok-free.dev',
      fetcher,
    );

    await client.health();
    await client.agentMessageStream('agent-1', 'hello', () => {});

    expect(fetcher.mock.calls[0]?.[1]?.headers).toMatchObject({
      'ngrok-skip-browser-warning': 'true',
    });
    expect(fetcher.mock.calls[1]?.[1]?.headers).toMatchObject({
      'ngrok-skip-browser-warning': 'true',
    });
  });

  it('keeps the ngrok interstitial header off for regular origins', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({ status: 'ok' }));
    const client = new CurrentBackendClient('guest-token', 'https://api.example/', fetcher);

    await client.health();

    const headers = fetcher.mock.calls[0]?.[1]?.headers as Record<string, string | undefined>;
    expect(headers['ngrok-skip-browser-warning']).toBeUndefined();
  });
});
