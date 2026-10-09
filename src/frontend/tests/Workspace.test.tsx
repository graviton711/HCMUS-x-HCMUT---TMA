// @vitest-environment jsdom
import { useCallback, useState } from 'react';
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useWorkspace } from '../features/workspace/useWorkspace';
import { emptyForm, formFromRequirement } from '../api/form';
import { newSession, putAccess, type LocalSession } from '../app/storage';
import type { Catalog, Comparison, Job, Proposal, Requirement } from '../api/types';

const server = vi.hoisted(() => ({
  catalog: vi.fn(),
  health: vi.fn(),
  session: vi.fn(),
  requirement: vi.fn(),
  proposal: vi.fn(),
  comparison: vi.fn(),
  job: vi.fn(),
  events: vi.fn(),
  createRequirement: vi.fn(),
  createProposal: vi.fn(),
  confirmProposal: vi.fn(),
  cancelProposal: vi.fn(),
  discardChanges: vi.fn(),
  createComparison: vi.fn(),
  sendMessage: vi.fn(),
  message: vi.fn(),
  cancelJob: vi.fn(),
  evidence: vi.fn(),
}));
vi.mock('../api/client', () => ({
  api: server,
  ApiClient: function () {
    return server;
  },
}));

const at = '2026-10-08T08:00:00Z';
const catalog: Catalog = {
  catalog_version: 'test',
  destinations: [],
  origins: [],
  fields: [],
  required_by_input_kind: {},
  defaults: {},
  qualitative_policy: {},
  assessment_policy: {},
  transports: [],
  tour_types: [],
  preference_dimensions: [],
  limits: {
    reference_urls: 5,
    recommendations: 3,
    candidate_limit_default: 20,
    text_characters: 2000,
    contact_characters: 4000,
    page_default: 20,
    page_max: 100,
    body_bytes: 100000,
  },
  upstream_contract: 'test',
};
function requirement(overrides: Partial<Requirement> = {}): Requirement {
  return {
    id: 'requirement-test',
    schema_version: '2.0-draft',
    policy_version: 'test',
    revision: 1,
    input_kind: 'urls',
    mode: 'compare_urls',
    timezone: 'Asia/Ho_Chi_Minh',
    messages: [],
    targets: [{ target_id: 'reference-test', url: 'https://example.test/tour' }],
    party: { adults: null, children: [] },
    conditions: [],
    hard_tree: { kind: 'all', children: [] },
    preference_tree: { kind: 'all', children: [] },
    clarifications: [],
    readiness: {
      status: 'ready',
      can_collect_data: true,
      can_evaluate_hard_constraints: false,
      reasons: [],
      blockers: [],
      scope_coverage: 'complete',
      unassessed_preferences: [],
    },
    issues: [],
    preference_levels: null,
    reference_urls: ['https://example.test/tour'],
    notes: 'Ghi chú đã xác nhận',
    provenance: {},
    created_at: at,
    ...overrides,
  };
}
function comparison(id = 'comparison-old', r = requirement()): Comparison {
  return {
    id,
    status: 'succeeded',
    result: {
      id,
      requirement_id: r.id,
      revision: r.revision,
      requirement_snapshot: r,
      origin: 'source',
      evaluated_at: at,
      policy_versions: {},
      columns: [],
      rows: [],
      cells: [],
      evaluations: [],
      recommendations: {
        kind: 'similar',
        candidate_ids: [],
        items: [],
        ranking_policy_version: 'test',
        unsupported_dimensions: [],
        needs_verification: [],
        excluded_tour_ids: [],
        candidate_limit: 20,
        truncated: false,
        evaluated_count: 0,
      },
      analysis: {
        metrics: [],
        semantic_assessment: { state: 'skipped', items: [] },
        retrieval: {},
        candidate_pool: [],
        metric_availability: [],
        claims: [],
      },
      source_coverage: [],
      warnings: [],
      empty_reason: 'NO_CANDIDATES',
    },
  };
}
function proposal(overrides: Partial<Proposal> = {}): Proposal {
  return {
    id: 'proposal-test',
    version: 4,
    requirement_id: 'requirement-test',
    base_revision: 1,
    status: 'pending',
    expires_at: '2099-10-08T08:00:00Z',
    preview: requirement({ notes: 'Ghi chú trong proposal' }),
    changes: [],
    clarifications: [],
    requested_action: null,
    parse_job_id: null,
    ...overrides,
  };
}
function job(id: string, status: Job['status'] = 'succeeded'): Job {
  return {
    id,
    status,
    resource_id: 'comparison-test',
    kind: 'v2_comparison',
    phase: 'comparison',
    stage: 'comparison',
    resource_ref: 'comparison-test',
    created_at: at,
    deadline_at: '2099-10-08T08:00:00Z',
    completed_at: status === 'running' ? null : at,
    error:
      status === 'failed'
        ? { code: 'SOURCE_FAILED', message: 'Nguồn không đọc được.', retryable: true, details: {} }
        : null,
    metrics: null,
  };
}
function session(overrides: Partial<LocalSession> = {}): LocalSession {
  const result = {
    ...newSession(),
    id: 'local-a',
    requirementId: 'requirement-test',
    draft: formFromRequirement(requirement()),
    ...overrides,
  };
  putAccess(result.id, {
    token: 'test-session-token',
    backendId: 'backend-test',
    expiresAt: '2099-10-08T08:00:00Z',
  });
  return result;
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
}
function useHarness(initial: LocalSession[]) {
  const [sessions, setSessions] = useState(initial);
  const [selectedId, select] = useState(initial[0]?.id ?? '');
  const patch = useCallback(
    (
      id: string,
      update: Partial<LocalSession> | ((value: LocalSession) => Partial<LocalSession>),
    ) => {
      setSessions((all) =>
        all.map((value) =>
          value.id === id
            ? { ...value, ...(typeof update === 'function' ? update(value) : update) }
            : value,
        ),
      );
    },
    [],
  );
  const workspace = useWorkspace(sessions.find((value) => value.id === selectedId) ?? null, patch);
  return { workspace, sessions, select };
}

beforeEach(() => {
  vi.resetAllMocks();
  sessionStorage.clear();
  localStorage.clear();
  server.catalog.mockResolvedValue(catalog);
  server.health.mockResolvedValue({ status: 'ok', data_origin: 'source', worker_enabled: true });
  server.session.mockResolvedValue({
    id: 'backend-test',
    session_id: 'backend-test',
    token: 'test-session-token',
    token_type: 'bearer',
    expires_at: '2099-10-08T08:00:00Z',
  });
  server.requirement.mockResolvedValue(requirement());
  server.proposal.mockResolvedValue(proposal());
  server.comparison.mockImplementation(async (id: string) => comparison(id));
  server.job.mockImplementation(async (id: string) => job(id));
  server.events.mockResolvedValue({ items: [], next_seq: 0, has_more: false });
  server.createComparison.mockResolvedValue({
    comparison_id: 'comparison-new',
    job_id: 'job-new',
    requirement_id: 'requirement-test',
    revision: 1,
    status: 'queued',
  });
  server.createRequirement.mockResolvedValue(requirement());
  server.confirmProposal.mockResolvedValue(
    requirement({ revision: 2, notes: 'Ghi chú trong proposal' }),
  );
  server.cancelProposal.mockResolvedValue({
    proposal_id: 'proposal-test',
    status: 'cancelled',
    committed_requirement: requirement({ revision: 2, notes: 'Bản committed mới từ backend' }),
  });
});
afterEach(cleanup);

describe('workspace lifecycle and persistence', () => {
  it('keeps a newer operation busy when an aborted operation settles after switching A → B → A', async () => {
    const old = deferred<Requirement>();
    const latest = deferred<Requirement>();
    let callsA = 0;
    server.requirement.mockImplementation((id: string) =>
      id === 'requirement-a'
        ? ++callsA === 1
          ? old.promise
          : latest.promise
        : Promise.resolve(requirement({ id })),
    );
    const a = session({ requirementId: 'requirement-a' });
    const b = session({ id: 'local-b', requirementId: 'requirement-b' });
    const { result } = renderHook(() => useHarness([a, b]));
    await waitFor(() => expect(callsA).toBe(1));
    act(() => result.current.select('local-b'));
    await waitFor(() =>
      expect(result.current.workspace.state.requirement?.id).toBe('requirement-b'),
    );
    act(() => result.current.select('local-a'));
    await waitFor(() => expect(callsA).toBe(2));
    await act(async () => {
      old.reject(new DOMException('Aborted', 'AbortError'));
      await Promise.resolve();
    });
    expect(result.current.workspace.state.busy).toBe(true);
    await act(async () => {
      latest.resolve(requirement({ id: 'requirement-a' }));
      await Promise.resolve();
    });
    await waitFor(() => expect(result.current.workspace.state.busy).toBe(false));
    expect(result.current.workspace.state.requirement?.id).toBe('requirement-a');
  });

  it('clears a blank session busy state when its initial create is aborted by navigation', async () => {
    const pending = deferred<Requirement>();
    server.createRequirement.mockReturnValue(pending.promise);
    const a = session({
      requirementId: null,
      draft: {
        ...structuredClone(emptyForm),
        mode: 'urls',
        referenceUrls: ['https://example.test/tour'],
      },
    });
    const b = session({ id: 'local-b', requirementId: null });
    const { result } = renderHook(() => useHarness([a, b]));
    act(() => {
      void result.current.workspace.create(a.draft);
    });
    await waitFor(() => expect(server.createRequirement).toHaveBeenCalled());
    act(() => result.current.select('local-b'));
    await act(async () => {
      pending.reject(new DOMException('Aborted', 'AbortError'));
      await Promise.resolve();
    });
    act(() => result.current.select('local-a'));
    expect(result.current.workspace.state.busy).toBe(false);
  });

  it('retains the prior comparison in memory and persisted history when a new search fails, including reload', async () => {
    server.requirement.mockResolvedValue(requirement({ latest_comparison_job_id: 'job-new' }));
    server.job.mockResolvedValue(job('job-new', 'failed'));
    const { result, unmount } = renderHook(() =>
      useHarness([session({ comparisonId: 'comparison-old' })]),
    );
    await waitFor(() =>
      expect(result.current.workspace.state.comparison?.id).toBe('comparison-old'),
    );
    await waitFor(() => expect(result.current.workspace.state.busy).toBe(false));
    await act(async () => {
      await result.current.workspace.search();
    });
    expect(result.current.workspace.state.comparison?.id).toBe('comparison-old');
    expect(result.current.workspace.state.error).toContain('Nguồn không đọc được');
    expect(result.current.sessions[0].comparisonId).toBe('comparison-old');
    const saved = structuredClone(result.current.sessions);
    unmount();
    const resumed = renderHook(() => useHarness(saved));
    await waitFor(() => expect(resumed.result.current.workspace.state.busy).toBe(false));
    expect(resumed.result.current.workspace.state.comparison?.id).toBe('comparison-old');
  });

  it('resumes the accepted message job rather than an unrelated latest comparison job', async () => {
    server.requirement.mockResolvedValue(
      requirement({ latest_comparison_job_id: 'old-comparison-job' }),
    );
    server.message
      .mockResolvedValueOnce({
        accepted: { message_id: 'server-message', status: 'queued', job_id: 'message-job' },
        result: null,
      })
      .mockResolvedValue({
        accepted: { message_id: 'server-message', status: 'queued', job_id: 'message-job' },
        result: {
          message_id: 'server-message',
          intent: 'answer',
          requested_action: null,
          proposal_id: null,
          answer: { text: 'Câu trả lời đã hoàn thành.' },
        },
      });
    const { result } = renderHook(() =>
      useHarness([session({ pendingMessageId: 'client-message' })]),
    );
    await waitFor(() => expect(result.current.sessions[0].pendingMessageId).toBeNull());
    expect(server.job).toHaveBeenCalledWith(
      'message-job',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(server.job).not.toHaveBeenCalledWith('old-comparison-job', expect.anything());
    expect(result.current.sessions[0].chat.at(-1)?.text).toBe('Câu trả lời đã hoàn thành.');
  });

  it('uses the freshly loaded requirement revision after resuming a message job without an existing comparison', async () => {
    server.requirement
      .mockResolvedValueOnce(requirement())
      .mockResolvedValue(requirement({ revision: 2 }));
    server.message
      .mockResolvedValueOnce({
        accepted: { message_id: 'server-message', status: 'queued', job_id: 'message-job' },
        result: null,
      })
      .mockResolvedValue({
        accepted: { message_id: 'server-message', status: 'queued', job_id: 'message-job' },
        result: {
          message_id: 'server-message',
          intent: 'search',
          requested_action: 'search',
          proposal_id: null,
          answer: null,
        },
      });
    const { result } = renderHook(() =>
      useHarness([session({ pendingMessageId: 'client-message' })]),
    );
    await waitFor(() => expect(result.current.workspace.state.busy).toBe(false));
    expect(server.createComparison).toHaveBeenCalledWith(
      expect.objectContaining({ revision: 2 }),
      expect.anything(),
    );
  });

  it('keeps prior offer selections when changing another tour offer', async () => {
    const old = comparison();
    old.result!.columns = ['tour-a', 'tour-b'].map((id) => ({
      id,
      candidate_id: id,
      tour_id: id,
      tour_snapshot_id: `${id}-snapshot`,
      title: id,
      supplier: null,
      canonical_url: `https://example.test/${id}`,
      origin: 'discovery',
      target_ids: [],
      source_ids: ['source-test'],
      offer_snapshot_id: `${id}-offer-1`,
      selected_offer_snapshot_id: `${id}-offer-1`,
      offer_reason: null,
      offer_options: [1, 2].map((index) => ({
        snapshot_id: `${id}-offer-${index}`,
        offer_id: `${id}-offer-${index}`,
        tour_snapshot_id: `${id}-snapshot`,
        fields: {},
        price_quotes: [],
        extra_charges: [],
        pricing_complete: null,
        catalog_fields: {},
      })),
      eligible_offer_snapshot_ids: [`${id}-offer-1`, `${id}-offer-2`],
      offer_assessments: [],
      offers_complete: true,
    }));
    old.result!.columns[0].selected_offer_snapshot_id = 'tour-a-offer-2';
    old.result!.columns[0].offer_snapshot_id = 'tour-a-offer-2';
    server.comparison.mockImplementation(async (id: string) =>
      id === old.id ? old : comparison(id),
    );
    const { result } = renderHook(() => useHarness([session({ comparisonId: old.id })]));
    await waitFor(() => expect(result.current.workspace.state.busy).toBe(false));
    await act(async () => {
      await result.current.workspace.offerChange('tour-b', 'tour-b-offer-2');
    });
    expect(server.createComparison).toHaveBeenCalledWith(
      expect.objectContaining({
        round_intent: 'offer_change',
        previous_comparison_id: old.id,
        offer_selections: expect.arrayContaining([
          { tour_id: 'tour-a', offer_snapshot_id: 'tour-a-offer-2' },
          { tour_id: 'tour-b', offer_snapshot_id: 'tour-b-offer-2' },
        ]),
      }),
      expect.anything(),
    );
  });

  it('preserves unsent local draft edits while resuming an active proposal parse job', async () => {
    server.requirement.mockResolvedValue(
      requirement({ active_proposal: { id: 'proposal-test', version: 4 } }),
    );
    server.proposal.mockResolvedValue(proposal({ parse_job_id: 'parse-job' }));
    const draft = { ...formFromRequirement(requirement()), notes: 'Bản nháp chưa gửi cần giữ' };
    const { result } = renderHook(() =>
      useHarness([session({ draft, proposalId: 'proposal-test' })]),
    );
    await waitFor(() => expect(result.current.workspace.state.busy).toBe(false));
    expect(result.current.workspace.state.proposal?.id).toBe('proposal-test');
    expect(result.current.sessions[0].draft.notes).toBe('Bản nháp chưa gửi cần giữ');
  });

  it('blocks a resumed search intent when a fresh active proposal still awaits confirmation', async () => {
    server.requirement.mockResolvedValue(
      requirement({ active_proposal: { id: 'proposal-test', version: 4 } }),
    );
    server.message.mockResolvedValue({
      accepted: { message_id: 'server-message', status: 'queued', job_id: 'message-job' },
      result: {
        message_id: 'server-message',
        intent: 'search',
        requested_action: 'search',
        proposal_id: null,
        answer: null,
      },
    });
    const { result } = renderHook(() =>
      useHarness([session({ pendingMessageId: 'client-message' })]),
    );
    await waitFor(() => expect(result.current.workspace.state.busy).toBe(false));
    expect(server.createComparison).not.toHaveBeenCalled();
    expect(result.current.workspace.state.error).toContain('Xác nhận hoặc hủy');
  });

  it('uses the current proposal version for CAS confirmation', async () => {
    server.requirement.mockResolvedValue(
      requirement({ active_proposal: { id: 'proposal-test', version: 4 } }),
    );
    const { result } = renderHook(() => useHarness([session({ proposalId: 'proposal-test' })]));
    await waitFor(() => expect(result.current.workspace.state.busy).toBe(false));
    await act(async () => {
      await result.current.workspace.confirm();
    });
    expect(server.confirmProposal).toHaveBeenCalledWith(
      'proposal-test',
      { expected_revision: 1, expected_proposal_version: 4 },
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(result.current.workspace.state.requirement?.revision).toBe(2);
    expect(result.current.workspace.state.proposal).toBeNull();
    expect(server.createComparison).not.toHaveBeenCalled();
  });

  it('restores the authoritative committed requirement returned by proposal cancellation', async () => {
    server.requirement.mockResolvedValue(
      requirement({ active_proposal: { id: 'proposal-test', version: 4 } }),
    );
    const { result } = renderHook(() => useHarness([session({ proposalId: 'proposal-test' })]));
    await waitFor(() => expect(result.current.workspace.state.busy).toBe(false));
    await act(async () => {
      await result.current.workspace.cancelProposal();
    });
    expect(result.current.workspace.state.requirement?.revision).toBe(2);
    expect(result.current.sessions[0].draft.notes).toBe('Bản committed mới từ backend');
    expect(result.current.workspace.state.proposal).toBeNull();
  });

  it('creates the initial requirement from chat without recursively locking the operation', async () => {
    const { result } = renderHook(() =>
      useHarness([session({ requirementId: null, draft: structuredClone(emptyForm) })]),
    );
    await act(async () => {
      await result.current.workspace.sendMessage('Tôi muốn so sánh tour Nhật Bản');
    });
    expect(server.createRequirement).toHaveBeenCalledWith(
      expect.objectContaining({ input: { kind: 'text', text: 'Tôi muốn so sánh tour Nhật Bản' } }),
      expect.anything(),
    );
    expect(result.current.workspace.state.requirement?.id).toBe('requirement-test');
    expect(result.current.workspace.state.busy).toBe(false);
  });
});
