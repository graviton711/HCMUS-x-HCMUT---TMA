import { CurrentApiError } from './errors';
import type {
  CurrentCatalog,
  CurrentComparison,
  CurrentHealth,
  CurrentRequirement,
  CurrentSession,
} from './types';
import type { CurrentHistoryPage } from './types';

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

  catalog() {
    return this.request<CurrentCatalog>('/catalog');
  }

  createRequirement(text: string, form?: Record<string, unknown>) {
    return this.request<{ requirement: CurrentRequirement }>('/requirements', 'POST', {
      text,
      ...(form ? { form } : {}),
    });
  }

  requirement(id: string) {
    return this.request<{ requirement: CurrentRequirement }>(
      `/requirements/${encodeURIComponent(id)}`,
    );
  }

  createComparison(requirementId: string, candidateLimit?: number) {
    return this.request<{ comparison: CurrentComparison }>('/comparisons', 'POST', {
      requirement_id: requirementId,
      ...(candidateLimit === undefined ? {} : { candidate_limit: candidateLimit }),
    });
  }

  comparison(id: string) {
    return this.request<{ comparison: CurrentComparison }>(
      `/comparisons/${encodeURIComponent(id)}`,
    );
  }

  history(limit = 100, cursor?: string) {
    const params = new URLSearchParams({ limit: String(limit) });
    if (cursor) params.set('cursor', cursor);
    return this.request<CurrentHistoryPage>(`/history?${params.toString()}`);
  }

  historyItem(id: string) {
    return this.request<{
      id: string;
      kind: 'requirement' | 'comparison';
      created_at: string;
      resource: CurrentRequirement | CurrentComparison;
    }>(`/history/${encodeURIComponent(id)}`);
  }
}
