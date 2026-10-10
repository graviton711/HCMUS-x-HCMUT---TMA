import { describe, expect, it, vi } from 'vitest';
import { ApiClient, ApiError } from './client';
import * as contracts from './contracts';
import type { CreateRequirementRequest } from './types';

const response = (data: unknown, status = 200) =>
  new Response(JSON.stringify({ schema_version: '2.0-draft', request_id: 'request_1', data }), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
const accepted = {
  requirement_id: 'req_1',
  revision: 0,
  proposal_id: 'proposal_1',
  status: 'pending',
};

describe('API boundary', () => {
  it('replays exactly the same mutation body and idempotency key after a lost response', async () => {
    const body: CreateRequirementRequest = {
      input: { kind: 'urls' },
      reference_urls: ['https://example.com/tour'],
    };
    const fetcher = vi
      .fn<typeof fetch>()
      .mockImplementationOnce(async () => {
        body.reference_urls?.push('https://example.com/other');
        throw new TypeError('Connection dropped');
      })
      .mockResolvedValueOnce(response(accepted, 201));
    const result = await new ApiClient(
      'session-secret',
      'http://backend',
      fetcher,
    ).createRequirement(body, { idempotencyKey: 'same_action' });
    expect(result).toEqual(accepted);
    const first = fetcher.mock.calls[0][1],
      second = fetcher.mock.calls[1][1];
    expect(first?.body).toBe(second?.body);
    expect(JSON.parse(String(second?.body)).reference_urls).toEqual(['https://example.com/tour']);
    expect(second?.headers).toMatchObject({
      'Idempotency-Key': 'same_action',
      Authorization: 'Bearer session-secret',
    });
    expect(fetcher.mock.calls[1][0]).toBe('http://backend/v2/requirements');
  });

  it('never retries revision conflicts and preserves server details', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          schema_version: '2.0-draft',
          request_id: 'request_1',
          error: {
            code: 'REVISION_CONFLICT',
            message: 'Yêu cầu đã thay đổi.',
            retryable: false,
            details: { current_revision: 2 },
          },
        }),
        { status: 409 },
      ),
    );
    const request = new ApiClient('session', '', fetcher).confirmProposal('proposal_1', {
      expected_revision: 1,
      expected_proposal_version: 1,
    });
    await expect(request).rejects.toMatchObject({
      code: 'REVISION_CONFLICT',
      status: 409,
      details: { current_revision: 2 },
    });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it('honors aborted request before any network operation', async () => {
    const fetcher = vi.fn<typeof fetch>(),
      controller = new AbortController();
    controller.abort();
    await expect(
      new ApiClient('session', '', fetcher).createRequirement(
        { input: { kind: 'urls' }, reference_urls: ['https://example.com'] },
        { signal: controller.signal },
      ),
    ).rejects.toMatchObject({ name: 'AbortError' });
    expect(fetcher).not.toHaveBeenCalled();
  });

  it('rejects an incompatible schema and incomplete accepted resource', async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(
        new Response(
          JSON.stringify({ schema_version: '1.0', request_id: 'request_1', data: accepted }),
        ),
      );
    await expect(
      new ApiClient(undefined, '', fetcher).createRequirement({
        input: { kind: 'urls' },
        reference_urls: ['https://example.com'],
      }),
    ).rejects.toMatchObject({ code: 'RESPONSE_INVALID', retryable: false });
    expect(() => contracts.createRequirement({ ...accepted, proposal_id: null })).toThrow(
      contracts.ContractError,
    );
  });

  it('reads health without a v2 envelope or authentication', async () => {
    const health = {
      status: 'ok',
      data_origin: 'source',
      data_provider: 'supabase',
      worker_enabled: true,
      schema_version: '1.0',
      api_versions: ['v1', 'v2'],
      database_schema_version: 2,
    };
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify(health)));
    expect(await new ApiClient('secret', '', fetcher).health()).toEqual(health);
    expect(fetcher.mock.calls[0][1]?.headers).not.toHaveProperty('Authorization');
  });

  it('does not replay session creation because BE has no idempotency contract', async () => {
    const fetcher = vi.fn<typeof fetch>().mockRejectedValue(new TypeError('Connection dropped'));
    await expect(new ApiClient(undefined, '', fetcher).session()).rejects.toBeInstanceOf(ApiError);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
