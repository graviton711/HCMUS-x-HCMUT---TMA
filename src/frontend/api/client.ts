import * as contracts from './contracts';
import type {
  AcceptedComparison,
  AcceptedMessage,
  ApiErrorPayload,
  CancelProposalResult,
  Catalog,
  Comparison,
  ConfirmProposalRequest,
  ContactRequest,
  ContactTicket,
  CreateComparisonRequest,
  CreateProposalRequest,
  CreateProposalResponse,
  CreateRequirementRequest,
  CreateRequirementResponse,
  DiscardChangesRequest,
  Evidence,
  Health,
  Job,
  JobEvents,
  JobStatus,
  JsonObject,
  MessageResult,
  Proposal,
  Requirement,
  SendMessageRequest,
  Session,
} from './types';

export interface RequestOptions {
  signal?: AbortSignal;
  idempotencyKey?: string;
}
export class ApiError extends Error {
  readonly name = 'ApiError';
  constructor(
    readonly code: string,
    message: string,
    readonly status = 0,
    readonly retryable = false,
    readonly details: JsonObject = {},
    readonly idempotencyKey?: string,
  ) {
    super(message);
  }
}
export const newIdempotencyKey = () => `mutation_${globalThis.crypto.randomUUID()}`;
export const isTerminalJob = (status: JobStatus) =>
  ['succeeded', 'partial', 'failed', 'cancelled'].includes(status);
const base = () => (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '';

/** One instance carries one anonymous session. Tokens never enter URLs or error text. */
export class ApiClient {
  private readonly baseUrl: string;
  constructor(
    private readonly token?: string,
    baseUrl = base(),
    private readonly fetcher: typeof fetch = globalThis.fetch.bind(globalThis),
  ) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
  }

  private async request<T>(
    path: string,
    validate: contracts.Validator,
    options: RequestOptions = {},
    body?: unknown,
    method: 'GET' | 'POST' = 'GET',
    v2 = true,
    retryMutation = true,
  ): Promise<T> {
    // Serialize exactly once: retrying a mutable form must never change the request fingerprint.
    const serialized = body === undefined ? undefined : JSON.stringify(body);
    const key =
      method === 'POST' && retryMutation
        ? (options.idempotencyKey ?? newIdempotencyKey())
        : undefined;
    const headers: Record<string, string> = { Accept: 'application/json' };
    if (this.token && path !== '/v2/sessions' && path !== '/health')
      headers.Authorization = `Bearer ${this.token}`;
    if (serialized !== undefined) headers['Content-Type'] = 'application/json';
    if (key) headers['Idempotency-Key'] = key;
    const attempts = method === 'POST' && retryMutation ? 2 : 1;
    for (let attempt = 0; attempt < attempts; attempt += 1) {
      options.signal?.throwIfAborted();
      try {
        const response = await this.fetcher(`${this.baseUrl}${path}`, {
          method,
          headers,
          body: serialized,
          signal: options.signal,
          credentials: 'omit',
        });
        let raw: unknown;
        try {
          raw = await response.json();
        } catch {
          throw new ApiError(
            'RESPONSE_INVALID',
            'Backend trả response không đọc được.',
            response.status,
            [502, 503, 504].includes(response.status),
            {},
            key,
          );
        }
        options.signal?.throwIfAborted();
        if (!response.ok) {
          let payload: ApiErrorPayload | undefined;
          try {
            const error = contracts.record(raw, 'response').error;
            contracts.errorPayload(error, 'response.error');
            payload = error as ApiErrorPayload;
          } catch {
            /* A proxy may return a non-contract JSON error. */
          }
          throw new ApiError(
            payload?.code ?? 'HTTP_ERROR',
            payload?.message ?? 'Không thể hoàn thành yêu cầu. Vui lòng thử lại.',
            response.status,
            payload?.retryable ?? [502, 503, 504].includes(response.status),
            payload?.details ?? {},
            key,
          );
        }
        const data = v2 ? contracts.envelope(raw).data : raw;
        validate(data);
        options.signal?.throwIfAborted();
        return data as T;
      } catch (error) {
        if (
          options.signal?.aborted ||
          (error instanceof DOMException && error.name === 'AbortError')
        )
          throw error;
        const apiError =
          error instanceof ApiError
            ? error
            : error instanceof contracts.ContractError
              ? new ApiError('RESPONSE_INVALID', error.message, 0, false, {}, key)
              : new ApiError(
                  'NETWORK_ERROR',
                  'Không kết nối được backend. Kiểm tra kết nối rồi thử lại.',
                  0,
                  true,
                  {},
                  key,
                );
        if (
          attempt + 1 < attempts &&
          (apiError.code === 'NETWORK_ERROR' || [502, 503, 504].includes(apiError.status))
        )
          continue;
        throw apiError;
      }
    }
    throw new ApiError('NETWORK_ERROR', 'Không kết nối được backend.', 0, true, {}, key);
  }

  health(options?: RequestOptions) {
    return this.request<Health>('/health', contracts.health, options, undefined, 'GET', false);
  }
  // Session creation has no idempotency support on BE, so it never auto-retries.
  session(options?: RequestOptions) {
    return this.request<Session>(
      '/v2/sessions',
      contracts.session,
      options,
      undefined,
      'POST',
      true,
      false,
    );
  }
  catalog(options?: RequestOptions) {
    return this.request<Catalog>('/v2/catalog', contracts.catalog, options);
  }
  requirement(id: string, options?: RequestOptions) {
    return this.request<Requirement>(
      `/v2/requirements/${encodeURIComponent(id)}`,
      contracts.requirement,
      options,
    );
  }
  revision(id: string, revision: number, options?: RequestOptions) {
    return this.request<Requirement>(
      `/v2/requirements/${encodeURIComponent(id)}/revisions/${revision}`,
      contracts.requirement,
      options,
    );
  }
  createRequirement(body: CreateRequirementRequest, options?: RequestOptions) {
    return this.request<CreateRequirementResponse>(
      '/v2/requirements',
      contracts.createRequirement,
      options,
      body,
      'POST',
    );
  }
  proposal(id: string, options?: RequestOptions) {
    return this.request<Proposal>(
      `/v2/proposals/${encodeURIComponent(id)}`,
      contracts.proposal,
      options,
    );
  }
  createProposal(requirementId: string, body: CreateProposalRequest, options?: RequestOptions) {
    return this.request<CreateProposalResponse>(
      `/v2/requirements/${encodeURIComponent(requirementId)}/proposals`,
      contracts.createProposal,
      options,
      body,
      'POST',
    );
  }
  confirmProposal(id: string, body: ConfirmProposalRequest, options?: RequestOptions) {
    return this.request<Requirement>(
      `/v2/proposals/${encodeURIComponent(id)}/confirm`,
      contracts.requirement,
      options,
      body,
      'POST',
    );
  }
  cancelProposal(
    id: string,
    body: { expected_proposal_version: number },
    options?: RequestOptions,
  ) {
    return this.request<CancelProposalResult>(
      `/v2/proposals/${encodeURIComponent(id)}/cancel`,
      contracts.cancelProposal,
      options,
      body,
      'POST',
    );
  }
  discardChanges(id: string, body: DiscardChangesRequest, options?: RequestOptions) {
    return this.request<Proposal>(
      `/v2/proposals/${encodeURIComponent(id)}/discard-changes`,
      contracts.proposal,
      options,
      body,
      'POST',
    );
  }
  comparison(id: string, options?: RequestOptions) {
    return this.request<Comparison>(
      `/v2/comparisons/${encodeURIComponent(id)}`,
      contracts.comparison,
      options,
    );
  }
  createComparison(body: CreateComparisonRequest, options?: RequestOptions) {
    return this.request<AcceptedComparison>(
      '/v2/comparisons',
      contracts.acceptedComparison,
      options,
      body,
      'POST',
    );
  }
  job(id: string, options?: RequestOptions) {
    return this.request<Job>(`/v2/jobs/${encodeURIComponent(id)}`, contracts.job, options);
  }
  events(id: string, afterSeq = 0, options?: RequestOptions, limit = 100) {
    return this.request<JobEvents>(
      `/v2/jobs/${encodeURIComponent(id)}/events?after_seq=${afterSeq}&limit=${limit}`,
      contracts.events,
      options,
    );
  }
  cancelJob(id: string, options?: RequestOptions) {
    return this.request<{ job_id: string; status: JobStatus }>(
      `/v2/jobs/${encodeURIComponent(id)}/cancel`,
      contracts.cancelJob,
      options,
      undefined,
      'POST',
    );
  }
  evidence(id: string, options?: RequestOptions) {
    return this.request<Evidence>(
      `/v2/evidence/${encodeURIComponent(id)}`,
      contracts.evidence,
      options,
    );
  }
  sendMessage(requirementId: string, body: SendMessageRequest, options?: RequestOptions) {
    return this.request<AcceptedMessage>(
      `/v2/conversations/${encodeURIComponent(requirementId)}/messages`,
      contracts.acceptedMessage,
      options,
      body,
      'POST',
    );
  }
  message(requirementId: string, clientMessageId: string, options?: RequestOptions) {
    return this.request<MessageResult>(
      `/v2/conversations/${encodeURIComponent(requirementId)}/messages/${encodeURIComponent(clientMessageId)}`,
      contracts.message,
      options,
    );
  }
  contact(body: ContactRequest, options?: RequestOptions) {
    return this.request<ContactTicket>('/v2/contacts', contracts.contact, options, body, 'POST');
  }
}

export const api = new ApiClient();
