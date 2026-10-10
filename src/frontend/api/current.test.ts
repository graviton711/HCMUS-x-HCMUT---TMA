import { describe, expect, it, vi } from 'vitest';
import { CurrentApiError, CurrentBackendClient } from './current';

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

  it('uses the active backend path and owner token for current requirement DTOs', async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(
        jsonResponse({
          requirement: { id: 'req_1', conditions: [], missing: [], raw_text: '', travelers: 1 },
        }),
      );
    const client = new CurrentBackendClient('guest-token', '', fetcher);

    await client.createRequirement('Da Lat', { destinations: ['Đà Lạt'] });
    const [url, init] = fetcher.mock.calls[0];
    expect(url).toBe('/requirements');
    expect(init?.headers).toMatchObject({ Authorization: 'Bearer guest-token' });
    expect(JSON.parse(String(init?.body))).toEqual({
      text: 'Da Lat',
      form: { destinations: ['Đà Lạt'] },
    });
  });

  it('keeps history cursors in the query string and URL-encodes resource ids', async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ items: [], next_cursor: null }))
      .mockResolvedValueOnce(
        jsonResponse({
          id: 'req /one',
          kind: 'requirement',
          created_at: '2026-01-01T00:00:00+00:00',
          resource: { id: 'req /one' },
        }),
      );
    const client = new CurrentBackendClient('guest-token', '', fetcher);

    await client.history(20, 'cursor /?');
    await client.historyItem('req /one');
    expect(fetcher.mock.calls[0][0]).toBe('/history?limit=20&cursor=cursor+%2F%3F');
    expect(fetcher.mock.calls[1][0]).toBe('/history/req%20%2Fone');
  });

  it('surfaces backend error codes without retrying the mutation', async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(
        jsonResponse({ error: { code: 'SESSION_EXPIRED', message: 'expired' } }, 401),
      );
    const client = new CurrentBackendClient('expired-token', '', fetcher);

    await expect(client.createRequirement('Da Lat')).rejects.toMatchObject({
      code: 'SESSION_EXPIRED',
      status: 401,
    } satisfies Partial<CurrentApiError>);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
