/** HTTP client for the active src/backend API. No legacy envelope or /v2 fallbacks. */

export interface CurrentSession {
  id: string;
  session_id: string;
  token: string;
  token_type: 'Bearer';
  expires_at: string;
}

export interface CurrentCatalog {
  destinations: string[];
}

export interface CurrentHealth {
  status: 'ok';
  version: string;
}

export interface CurrentCondition {
  id: string;
  field: string;
  operator: string;
  value: unknown;
  strength: 'hard' | 'soft';
  quote: string;
}

export interface CurrentRequirement {
  id: string;
  conditions: CurrentCondition[];
  missing: string[];
  raw_text: string;
  travelers: number;
}

export interface CurrentOffer {
  id: string;
  tour_id: string;
  departure_date: string;
  price: number | null;
  currency: string;
  price_basis: 'exact' | 'from' | 'contact';
  price_trusted: boolean;
  price_freshness: 'fresh' | 'stale' | 'unknown';
  departure_freshness: 'fresh' | 'stale' | 'unknown';
  pricing_metadata_state: 'missing' | 'validated' | 'invalid' | 'untrusted';
  availability: string;
  conditions: string;
  evidence: { url: string; method: string; observed_at: string; record_ref: string };
}

export interface CurrentTourSnapshot {
  id: string;
  supplier: string;
  name: string;
  url: string;
  destinations: string[];
  raw_destinations: string[];
  route: string[];
  destination_countries: string[];
  destination_country_complete: boolean;
  departure_city: string;
  duration_days: number | null;
  transport: string;
  accommodation: string;
  itinerary: string;
  inclusions: string;
  exclusions: string;
  cancellation_policy: string;
  surcharges: string;
  child_policy: string;
  evidence: { url: string; method: string; observed_at: string; record_ref: string };
  observed_at: string;
  verification: string;
  offers: CurrentOffer[];
}

export interface CurrentEvaluation {
  offer_id: string;
  condition_id: string;
  state: 'pass' | 'fail' | 'unknown';
  quote: string;
  reason_code: string;
}

export interface CurrentComparison {
  id: string;
  requirement: CurrentRequirement;
  ranked: { tour_id: string; offer_id: string; score: number }[];
  tour_snapshots: CurrentTourSnapshot[];
  evaluations: CurrentEvaluation[];
  analysis: {
    hidden_costs: string[];
    conditions: string[];
    risks: string[];
    benefits: string[];
  };
  candidates_considered: number;
}

export interface CurrentHistoryItem {
  id: string;
  kind: 'requirement' | 'comparison';
  created_at: string;
}

export interface CurrentHistoryPage {
  items: CurrentHistoryItem[];
  next_cursor: string | null;
}

export class CurrentApiError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = 'CurrentApiError';
  }
}

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
