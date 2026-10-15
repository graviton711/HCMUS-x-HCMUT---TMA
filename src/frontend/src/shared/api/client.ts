import { CurrentApiError } from './errors';
import type {
  CurrentAgentResponse,
  CurrentAgentProgressEvent,
  CurrentAgentSession,
  CurrentComparison,
  CurrentCostScenario,
  CurrentCostScenarioAssumptions,
  CurrentEliminatedPage,
  CurrentHealth,
  CurrentRequirement,
  CurrentSession,
} from './types';

type Fetcher = typeof fetch;
const defaultBase = () => (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '';
const object = (value: unknown): Record<string, unknown> | null =>
  typeof value === 'object' && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;

/** The backend API client. Mutations are not retried because the API has no idempotency contract. */
export class CurrentBackendClient {
  private readonly baseUrl: string;

  constructor(
    private readonly token?: string,
    baseUrl = defaultBase(),
    private readonly fetcher: Fetcher = globalThis.fetch.bind(globalThis),
  ) {
    this.baseUrl = baseUrl.replace(/\/$/u, '');
  }

  private async request<T>(
    path: string,
    method: 'GET' | 'POST' = 'GET',
    body?: unknown,
  ): Promise<T> {
    const headers: Record<string, string> = { Accept: 'application/json' };
    if (this.token) headers.Authorization = `Bearer ${this.token}`;
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    let response: Response;
    try {
      response = await this.fetcher(`${this.baseUrl}${path}`, {
        method,
        headers,
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
        credentials: 'omit',
      });
    } catch {
      throw new CurrentApiError('NETWORK_ERROR', 'Không kết nối được backend.', 0);
    }
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      throw new CurrentApiError(
        'RESPONSE_INVALID',
        'Backend trả response không đọc được.',
        response.status,
      );
    }
    if (!response.ok) {
      const error = object(object(payload)?.error);
      throw new CurrentApiError(
        typeof error?.code === 'string' ? error.code : 'HTTP_ERROR',
        typeof error?.message === 'string' ? error.message : 'Không thể hoàn thành yêu cầu.',
        response.status,
      );
    }
    return payload as T;
  }

  createSession() {
    return this.request<CurrentSession>('/sessions', 'POST');
  }

  health() {
    return this.request<CurrentHealth>('/health');
  }

  eliminatedOffers(comparisonId: string, cursor?: string | null, limit = 25, conditionId?: string) {
    const params = new URLSearchParams({ limit: String(limit) });
    if (cursor) params.set('cursor', cursor);
    if (conditionId) params.set('condition_id', conditionId);
    return this.request<CurrentEliminatedPage>(
      `/comparisons/${encodeURIComponent(comparisonId)}/eliminated?${params.toString()}`,
    );
  }

  criteriaScenario(
    comparisonId: string,
    agentSessionId: string,
    requirement: CurrentRequirement,
  ) {
    return this.request<CurrentAgentResponse>(
      `/comparisons/${encodeURIComponent(comparisonId)}/scenarios`,
      'POST',
      { kind: 'criteria', agent_session_id: agentSessionId, requirement },
    );
  }

  costScenario(comparisonId: string, assumptions: CurrentCostScenarioAssumptions) {
    return this.request<{ kind: 'cost'; scenario: CurrentCostScenario }>(
      `/comparisons/${encodeURIComponent(comparisonId)}/scenarios`,
      'POST',
      { kind: 'cost', assumptions },
    );
  }

  createAgentSession() {
    return this.request<CurrentAgentSession>('/agent/sessions', 'POST');
  }

  agentMessage(agentSessionId: string, message: string) {
    return this.request<CurrentAgentResponse>(
      `/agent/sessions/${encodeURIComponent(agentSessionId)}/messages`,
      'POST',
      { message },
    );
  }

  agentMessageStream(
    agentSessionId: string,
    message: string,
    onEvent: (event: CurrentAgentProgressEvent) => void,
    signal?: AbortSignal,
  ): Promise<CurrentAgentResponse> {
    return this.agentStream(
      `/agent/sessions/${encodeURIComponent(agentSessionId)}/messages`,
      { message },
      onEvent,
      signal,
    );
  }

  agentDecisionStream(
    agentSessionId: string,
    requirement: CurrentRequirement,
    onEvent: (event: CurrentAgentProgressEvent) => void,
    signal?: AbortSignal,
  ): Promise<CurrentAgentResponse> {
    return this.agentStream(
      `/agent/sessions/${encodeURIComponent(agentSessionId)}/decisions`,
      { requirement },
      onEvent,
      signal,
    );
  }

  private async agentStream(
    path: string,
    body: unknown,
    onEvent: (event: CurrentAgentProgressEvent) => void,
    signal?: AbortSignal,
  ): Promise<CurrentAgentResponse> {
    const headers: Record<string, string> = {
      Accept: 'text/event-stream',
      'Content-Type': 'application/json',
    };
    if (this.token) headers.Authorization = `Bearer ${this.token}`;
    let response: Response;
    try {
      response = await this.fetcher(
        `${this.baseUrl}${path}`,
        {
          method: 'POST',
          headers,
          body: JSON.stringify(body),
          credentials: 'omit',
          signal,
        },
      );
    } catch (cause) {
      if (signal?.aborted) throw cause;
      throw new CurrentApiError('NETWORK_ERROR', 'Không kết nối được backend.', 0);
    }

    if (!response.ok) {
      let payload: unknown;
      try {
        payload = await response.json();
      } catch {
        throw new CurrentApiError(
          'RESPONSE_INVALID',
          'Backend trả response không đọc được.',
          response.status,
        );
      }
      const error = object(object(payload)?.error);
      throw new CurrentApiError(
        typeof error?.code === 'string' ? error.code : 'HTTP_ERROR',
        typeof error?.message === 'string' ? error.message : 'Không thể hoàn thành yêu cầu.',
        response.status,
      );
    }

    if (!response.headers.get('Content-Type')?.includes('text/event-stream')) {
      try {
        return (await response.json()) as CurrentAgentResponse;
      } catch {
        throw new CurrentApiError(
          'RESPONSE_INVALID',
          'Backend trả response không đọc được.',
          response.status,
        );
      }
    }
    if (!response.body) {
      throw new CurrentApiError('STREAM_UNAVAILABLE', 'Backend không mở được luồng tiến độ.', 502);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    const resultHolder: { value: CurrentAgentResponse | null } = { value: null };
    const dispatch = (frame: string) => {
      let eventName = 'message';
      const data: string[] = [];
      for (const line of frame.split(/\r?\n/u)) {
        if (line.startsWith('event:')) eventName = line.slice(6).trim();
        else if (line.startsWith('data:')) data.push(line.slice(5).trimStart());
      }
      if (!data.length) return;
      let payload: unknown;
      try {
        payload = JSON.parse(data.join('\n'));
      } catch {
        throw new CurrentApiError('STREAM_INVALID', 'Tiến độ từ backend không đọc được.', 502);
      }
      const value = object(payload);
      if (!value) return;
      if (eventName === 'error') {
        throw new CurrentApiError(
          typeof value.code === 'string' ? value.code : 'HTTP_ERROR',
          typeof value.message === 'string' ? value.message : 'Không thể hoàn thành yêu cầu.',
          502,
        );
      }
      if (eventName === 'result') {
        resultHolder.value = value as unknown as CurrentAgentResponse;
        return;
      }
      if (eventName === 'progress' || eventName === 'tool') {
        onEvent({ type: eventName, ...value } as CurrentAgentProgressEvent);
      }
    };

    try {
      while (true) {
        const { done, value } = await reader.read();
        buffer += decoder.decode(value, { stream: !done });
        const frames = buffer.split(/\r?\n\r?\n/u);
        buffer = frames.pop() ?? '';
        for (const frame of frames) dispatch(frame);
        if (done) break;
      }
      if (buffer.trim()) dispatch(buffer);
    } finally {
      reader.releaseLock();
    }
    const result = resultHolder.value;
    if (!result) {
      throw new CurrentApiError(
        'STREAM_INCOMPLETE',
        'Backend đã đóng luồng trước khi trả kết quả.',
        502,
      );
    }
    return result;
  }

  requirement(id: string) {
    return this.request<{ requirement: CurrentRequirement }>(
      `/requirements/${encodeURIComponent(id)}`,
    );
  }

  comparison(id: string) {
    return this.request<{ comparison: CurrentComparison }>(
      `/comparisons/${encodeURIComponent(id)}`,
    );
  }
}
