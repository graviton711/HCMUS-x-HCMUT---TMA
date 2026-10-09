import { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiClient } from '../../api/client';
import {
  buildCreateRequirement,
  buildEdits,
  formFromRequirement,
  type FormValues,
} from '../../api/form';
import type {
  Catalog,
  Comparison,
  Evidence,
  Job,
  JobEvent,
  Proposal,
  Requirement,
} from '../../api/types';
import { getAccess, putAccess, type LocalSession } from '../../app/storage';

export interface Resources {
  requirement: Requirement | null;
  proposal: Proposal | null;
  comparison: Comparison | null;
  job: Job | null;
  events: JobEvent[];
  busy: boolean;
  error: string | null;
  discardIds: string[];
}
const blank: Resources = {
  requirement: null,
  proposal: null,
  comparison: null,
  job: null,
  events: [],
  busy: false,
  error: null,
  discardIds: [],
};
const terminal = (status: string) =>
  ['succeeded', 'partial', 'failed', 'cancelled'].includes(status);
function pause(signal: AbortSignal, ms = 1000) {
  return new Promise<void>((resolve, reject) => {
    const stop = () => {
      clearTimeout(timer);
      reject(new DOMException('Aborted', 'AbortError'));
    };
    const timer = setTimeout(() => {
      signal.removeEventListener('abort', stop);
      resolve();
    }, ms);
    if (signal.aborted) stop();
    else signal.addEventListener('abort', stop, { once: true });
  });
}
const errorText = (error: unknown) =>
  error instanceof Error ? error.message : 'Không thể hoàn thành yêu cầu.';
type PatchSession = (
  id: string,
  update: Partial<LocalSession> | ((s: LocalSession) => Partial<LocalSession>),
) => void;
interface Operation {
  client: ApiClient;
  signal: AbortSignal;
  id: string;
  saved: LocalSession;
  state: Resources;
}

export function useWorkspace(current: LocalSession | null, patchSession: PatchSession) {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [resources, setResources] = useState<Record<string, Resources>>({});
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [evidenceError, setEvidenceError] = useState<string | null>(null);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const latest = useRef(resources);
  latest.current = resources;
  const currentRef = useRef(current);
  currentRef.current = current;
  const patchRef = useRef(patchSession);
  patchRef.current = patchSession;
  const controllers = useRef(new Map<string, AbortController>());
  const evidenceController = useRef<AbortController | null>(null);
  const resolveMessageRef = useRef<
    (op: Operation, requirement: Requirement, messageId: string) => Promise<void>
  >(async () => {});
  const update = useCallback((id: string, changes: Partial<Resources>) => {
    setResources((all) => ({ ...all, [id]: { ...(all[id] || blank), ...changes } }));
  }, []);

  const loadCatalog = useCallback(async (signal?: AbortSignal) => {
    try {
      setCatalog(await api.catalog({ signal }));
      setCatalogError(null);
    } catch (error) {
      if (!signal?.aborted) setCatalogError(errorText(error));
    }
  }, []);
  useEffect(() => {
    const ctrl = new AbortController();
    void loadCatalog(ctrl.signal);
    return () => ctrl.abort();
  }, [loadCatalog]);

  const poll = useCallback(
    async (client: ApiClient, id: string, jobId: string, signal: AbortSignal) => {
      update(id, { events: [], job: null });
      let cursor = 0;
      const collected: JobEvent[] = [];
      for (;;) {
        const job = await client.job(jobId, { signal });
        let more = true;
        while (more) {
          const batch = await client.events(jobId, cursor, { signal });
          for (const event of batch.items)
            if (!collected.some((x) => x.seq === event.seq)) collected.push(event);
          cursor = batch.next_seq;
          more = batch.has_more;
        }
        signal.throwIfAborted();
        update(id, { job, events: [...collected] });
        if (terminal(job.status)) {
          patchRef.current(id, { jobId: null });
          if (job.status === 'failed')
            throw new Error(job.error?.message || 'Tác vụ chưa hoàn thành. Vui lòng thử lại.');
          if (job.status === 'cancelled') throw new Error('Tác vụ đã được hủy.');
          return job;
        }
        await pause(signal);
      }
    },
    [update],
  );

  const readProposal = useCallback(
    async (op: Operation, proposalId: string, preserveDraft = false) => {
      let proposal = await op.client.proposal(proposalId, { signal: op.signal });
      patchRef.current(op.id, { proposalId: proposal.id });
      if (proposal.parse_job_id) {
        const job = await op.client.job(proposal.parse_job_id, { signal: op.signal });
        if (!terminal(job.status)) {
          patchRef.current(op.id, { jobId: job.id });
          await poll(op.client, op.id, job.id, op.signal);
          proposal = await op.client.proposal(proposalId, { signal: op.signal });
        } else if (job.status === 'failed' || job.status === 'cancelled')
          throw new Error(job.error?.message || 'Tác vụ đọc nhu cầu chưa hoàn thành.');
      }
      op.signal.throwIfAborted();
      update(op.id, { proposal });
      patchRef.current(op.id, {
        proposalId: proposal.id,
        ...(!preserveDraft ? { draft: formFromRequirement(proposal.preview) } : {}),
      });
      return proposal;
    },
    [poll, update],
  );

  const run = useCallback(
    async (action: (op: Operation) => Promise<void>) => {
      const saved = currentRef.current;
      if (!saved || controllers.current.has(saved.id)) return;
      const ctrl = new AbortController();
      controllers.current.set(saved.id, ctrl);
      update(saved.id, { busy: true, error: null, discardIds: [] });
      try {
        let access = getAccess(saved.id);
        if (!access) {
          if (saved.requirementId)
            throw new Error(
              'Quyền truy cập phiên đã hết hạn. Hãy tạo phiên mới; bản nháp vẫn được giữ.',
            );
          const session = await api.session({ signal: ctrl.signal });
          access = { token: session.token, expiresAt: session.expires_at, backendId: session.id };
          putAccess(saved.id, access);
        }
        await action({
          id: saved.id,
          saved,
          state: latest.current[saved.id] || blank,
          client: new ApiClient(access.token),
          signal: ctrl.signal,
        });
      } catch (error) {
        if (!ctrl.signal.aborted) update(saved.id, { error: errorText(error) });
      } finally {
        if (controllers.current.get(saved.id) === ctrl) {
          controllers.current.delete(saved.id);
          update(saved.id, { busy: false });
        }
      }
    },
    [update],
  );

  const searchWith = useCallback(
    async (
      op: Operation,
      requirement: Requirement,
      intent: 'initial' | 'next_group' | 'offer_change' = 'initial',
      offer?: { tour_id: string; offer_snapshot_id: string },
    ) => {
      if (requirement.revision < 1 || !requirement.readiness.can_collect_data)
        throw new Error('Cần xác nhận và làm rõ nhu cầu trước khi tìm kiếm.');
      const health = await api.health({ signal: op.signal });
      if (health.data_origin === 'synthetic')
        throw new Error(
          'Nguồn tour chưa được kết nối. Vui lòng thử lại khi dịch vụ dữ liệu sẵn sàng.',
        );
      if (health.status !== 'ok')
        throw new Error('Dịch vụ xử lý đang gián đoạn. Vui lòng thử lại.');
      if (health.worker_enabled === false)
        throw new Error('Dịch vụ xử lý chưa được bật. Vui lòng thử lại khi dịch vụ sẵn sàng.');
      const previous = op.state.comparison?.id || op.saved.comparisonId;
      const selections = offer
        ? [
            ...(op.state.comparison?.result?.columns || []).flatMap((column) =>
              column.tour_id &&
              column.selected_offer_snapshot_id &&
              column.tour_id !== offer.tour_id
                ? [
                    {
                      tour_id: column.tour_id,
                      offer_snapshot_id: column.selected_offer_snapshot_id,
                    },
                  ]
                : [],
            ),
            offer,
          ]
        : [];
      if (intent !== 'initial' && !previous) throw new Error('Cần có một bảng so sánh trước.');
      const accepted = await op.client.createComparison(
        {
          requirement_id: requirement.id,
          revision: requirement.revision,
          round_intent: intent,
          ...(intent !== 'initial' ? { previous_comparison_id: previous! } : {}),
          ...(offer ? { offer_selections: selections } : {}),
        },
        { signal: op.signal },
      );
      patchRef.current(op.id, {
        pendingComparisonId: accepted.comparison_id,
        jobId: accepted.job_id,
      });
      await poll(op.client, op.id, accepted.job_id, op.signal);
      const comparison = await op.client.comparison(accepted.comparison_id, { signal: op.signal });
      op.signal.throwIfAborted();
      update(op.id, { comparison });
      patchRef.current(op.id, (s) => ({
        comparisonId: comparison.id,
        pendingComparisonId: null,
        runs: s.runs.some((x) => x.id === comparison.id)
          ? s.runs
          : [
              ...s.runs,
              {
                id: comparison.id,
                revision: requirement.revision,
                createdAt: new Date().toISOString(),
              },
            ],
      }));
    },
    [poll, update],
  );

  const resume = useCallback(
    async (op: Operation) => {
      if (!op.saved.requirementId) return;
      const requirement = await op.client.requirement(op.saved.requirementId, {
        signal: op.signal,
      });
      let resumed = { ...op.state, requirement };
      update(op.id, { requirement });
      const activeProposal = requirement.active_proposal;
      const proposalId =
        typeof activeProposal === 'string'
          ? activeProposal
          : activeProposal?.id || op.saved.proposalId;
      if (proposalId) {
        const p = await op.client.proposal(proposalId, { signal: op.signal });
        if (['pending', 'needs_clarification'].includes(p.status)) {
          update(op.id, { proposal: p });
          resumed = { ...resumed, proposal: p };
        } else {
          update(op.id, { proposal: null });
          resumed = { ...resumed, proposal: null };
          patchRef.current(op.id, { proposalId: null });
        }
      }
      const comparisonId = op.saved.comparisonId || requirement.latest_comparison_id;
      if (comparisonId) {
        const comparison = await op.client.comparison(comparisonId, { signal: op.signal });
        update(op.id, { comparison });
        resumed = { ...resumed, comparison };
      }
      const pendingMessage = op.saved.pendingMessageId
        ? await op.client.message(requirement.id, op.saved.pendingMessageId, { signal: op.signal })
        : null;
      const jobId =
        pendingMessage && !pendingMessage.result
          ? pendingMessage.accepted.job_id
          : op.saved.jobId ||
            (op.saved.pendingComparisonId ? requirement.latest_comparison_job_id : null) ||
            (proposalId ? resumed.proposal?.parse_job_id : null);
      if (jobId) {
        await poll(op.client, op.id, jobId, op.signal);
        const fresh = await op.client.requirement(requirement.id, { signal: op.signal });
        resumed = { ...resumed, requirement: fresh };
        update(op.id, { requirement: fresh });
        const finishedComparisonId = op.saved.pendingComparisonId || comparisonId;
        if (finishedComparisonId) {
          const comparison = await op.client.comparison(finishedComparisonId, {
            signal: op.signal,
          });
          if (comparison.result) {
            update(op.id, { comparison });
            resumed = { ...resumed, comparison, requirement: fresh };
            patchRef.current(op.id, (saved) => ({
              comparisonId: comparison.id,
              pendingComparisonId: null,
              runs: saved.runs.some((r) => r.id === comparison.id)
                ? saved.runs
                : [
                    ...saved.runs,
                    {
                      id: comparison.id,
                      revision: comparison.result!.revision,
                      createdAt: comparison.result!.evaluated_at,
                    },
                  ],
            }));
          }
        }
        if (proposalId) {
          const proposal = await readProposal(op, proposalId, true);
          resumed = { ...resumed, proposal };
        }
      }
      if (op.saved.pendingMessageId)
        await resolveMessageRef.current(
          { ...op, state: resumed },
          resumed.requirement,
          op.saved.pendingMessageId,
        );
    },
    [poll, readProposal, update],
  );

  const selectedId = current?.id;
  useEffect(() => {
    const activeControllers = controllers.current;
    if (currentRef.current?.requirementId) void run(resume);
    return () => {
      if (selectedId) {
        activeControllers.get(selectedId)?.abort();
        activeControllers.delete(selectedId);
        update(selectedId, { busy: false });
      }
      evidenceController.current?.abort();
      setEvidenceOpen(false);
    };
  }, [selectedId, run, resume, update]);

  const create = (values: FormValues) =>
    run(async (op) => {
      const created = await op.client.createRequirement(
        buildCreateRequirement(values, catalog || undefined),
        { signal: op.signal },
      );
      const requirementId = 'requirement_id' in created ? created.requirement_id : created.id;
      patchRef.current(op.id, {
        requirementId,
        title:
          op.saved.title ||
          catalog?.destinations.find((d) => d.id === values.destinations[0])?.label ||
          values.text.slice(0, 48),
      });
      if ('proposal_id' in created && created.proposal_id) {
        patchRef.current(op.id, { proposalId: created.proposal_id, jobId: created.job_id || null });
        if (created.job_id) await poll(op.client, op.id, created.job_id, op.signal);
        update(op.id, {
          requirement: await op.client.requirement(requirementId, { signal: op.signal }),
        });
        const proposal = await readProposal(op, created.proposal_id);
        if (values.notes.trim() && values.notes !== proposal.preview.notes) {
          const updated = await op.client.createProposal(
            requirementId,
            {
              expected_revision: proposal.base_revision,
              proposal_id: proposal.id,
              expected_proposal_version: proposal.version,
              input: { kind: 'structured', edits: [{ op: 'set_notes', notes: values.notes }] },
            },
            { signal: op.signal },
          );
          await readProposal(op, 'proposal_id' in updated ? updated.proposal_id : updated.id);
        }
      } else {
        const requirement = await op.client.requirement(requirementId, { signal: op.signal });
        update(op.id, { requirement, proposal: null });
        patchRef.current(op.id, { draft: formFromRequirement(requirement) });
      }
    });

  const saveEditsWith = async (op: Operation, values: FormValues) => {
    const requirement = op.state.requirement;
    if (!requirement) throw new Error('Cần tải nhu cầu hiện tại trước.');
    const base = op.state.proposal?.preview || requirement;
    const edits = buildEdits(values, base, catalog || undefined);
    if (!edits.length) return op.state.proposal;
    const pending = op.state.proposal;
    const result = await op.client.createProposal(
      requirement.id,
      {
        expected_revision: requirement.revision,
        ...(pending ? { proposal_id: pending.id, expected_proposal_version: pending.version } : {}),
        input: { kind: 'structured', edits },
      },
      { signal: op.signal },
    );
    return readProposal(op, 'proposal_id' in result ? result.proposal_id : result.id);
  };
  const saveEdits = (values: FormValues) =>
    run(async (op) => {
      await saveEditsWith(op, values);
    });
  const confirm = () =>
    run(async (op) => {
      const p = op.state.proposal;
      if (!p) return;
      const requirement = await op.client.confirmProposal(
        p.id,
        { expected_revision: p.base_revision, expected_proposal_version: p.version },
        { signal: op.signal },
      );
      update(op.id, { requirement, proposal: null });
      patchRef.current(op.id, { proposalId: null, draft: formFromRequirement(requirement) });
      if (p.requested_action)
        await searchWith(
          { ...op, state: { ...op.state, proposal: null } },
          requirement,
          p.requested_action === 'next_group' ? 'next_group' : 'initial',
        );
    });
  const cancelProposal = () =>
    run(async (op) => {
      const p = op.state.proposal;
      const cancelled = p
        ? await op.client.cancelProposal(
            p.id,
            { expected_proposal_version: p.version },
            { signal: op.signal },
          )
        : null;
      const r = cancelled?.committed_requirement || op.state.requirement;
      update(op.id, { proposal: null, requirement: r });
      patchRef.current(op.id, {
        proposalId: null,
        ...(r ? { draft: formFromRequirement(r) } : {}),
      });
    });
  const discard = (changeId: string, relatedIds: string[] = []) =>
    run(async (op) => {
      const p = op.state.proposal;
      if (!p) return;
      try {
        await op.client.discardChanges(
          p.id,
          {
            expected_revision: p.base_revision,
            expected_proposal_version: p.version,
            change_ids: [...new Set([changeId, ...relatedIds])],
          },
          { signal: op.signal },
        );
      } catch (error) {
        if (
          typeof error === 'object' &&
          error !== null &&
          'code' in error &&
          error.code === 'DISCARD_DEPENDENCY' &&
          'details' in error &&
          typeof error.details === 'object' &&
          error.details !== null &&
          'related_change_ids' in error.details &&
          Array.isArray(error.details.related_change_ids)
        ) {
          update(op.id, {
            discardIds: [
              changeId,
              ...error.details.related_change_ids.filter(
                (id): id is string => typeof id === 'string',
              ),
            ],
          });
        }
        throw error;
      }
      await readProposal(op, p.id);
    });
  const clarify = (clarificationId: string, answer: string) =>
    run(async (op) => {
      const p = op.state.proposal;
      if (!p) return;
      const proposed = await op.client.createProposal(
        p.requirement_id,
        {
          expected_revision: p.base_revision,
          proposal_id: p.id,
          expected_proposal_version: p.version,
          input: {
            kind: 'structured',
            edits: [{ op: 'answer_clarification', clarification_id: clarificationId, answer }],
          },
        },
        { signal: op.signal },
      );
      await readProposal(op, 'proposal_id' in proposed ? proposed.proposal_id : proposed.id);
    });
  const search = (intent: 'initial' | 'next_group' = 'initial') =>
    run(async (op) => {
      if (op.state.proposal) throw new Error('Xác nhận hoặc hủy thay đổi trước khi tìm kiếm.');
      if (!op.state.requirement) throw new Error('Cần xác nhận nhu cầu trước.');
      await searchWith(op, op.state.requirement, intent);
    });
  const offerChange = (tourId: string, offerId: string) =>
    run(async (op) => {
      if (!op.state.requirement || op.state.proposal)
        throw new Error('Xác nhận nhu cầu hiện tại trước.');
      await searchWith(op, op.state.requirement, 'offer_change', {
        tour_id: tourId,
        offer_snapshot_id: offerId,
      });
    });

  async function resolveMessage(op: Operation, requirement: Requirement, messageId: string) {
    const message = await op.client.message(requirement.id, messageId, { signal: op.signal });
    const result = message.result;
    if (!result) return;
    patchRef.current(op.id, { pendingMessageId: null });
    if (result.answer?.text)
      patchRef.current(op.id, (s) => ({
        chat: [
          ...s.chat.filter((m) => m.id !== `${messageId}:reply`),
          { id: `${messageId}:reply`, role: 'assistant', text: result.answer!.text },
        ],
      }));
    if (result.proposal_id) {
      const proposal = await readProposal(op, result.proposal_id);
      update(op.id, { proposal });
    } else if (result.requested_action) {
      if (op.state.proposal) throw new Error('Xác nhận hoặc hủy thay đổi trước khi tìm kiếm.');
      await searchWith(
        op,
        requirement,
        result.requested_action === 'next_group' ? 'next_group' : 'initial',
      );
    }
  }
  resolveMessageRef.current = resolveMessage;
  const sendMessage = (text: string) => {
    const saved = currentRef.current;
    if (saved && !latest.current[saved.id]?.requirement)
      return create({ ...saved.draft, mode: 'text', text });
    return run(async (op) => {
      const requirement = op.state.requirement;
      if (!requirement) throw new Error('Cần tải nhu cầu hiện tại trước.');
      const proposal = await saveEditsWith(op, op.saved.draft);
      const clientMessageId = crypto.randomUUID();
      const result = op.state.comparison?.result;
      patchRef.current(op.id, (s) => ({
        pendingMessageId: clientMessageId,
        chat: [...s.chat, { id: clientMessageId, role: 'user', text }],
      }));
      const accepted = await op.client.sendMessage(
        requirement.id,
        {
          text,
          client_message_id: clientMessageId,
          context: {
            requirement_revision: requirement.revision,
            ...(proposal ? { proposal_id: proposal.id, proposal_version: proposal.version } : {}),
            ...(result ? { comparison_id: result.id, result_revision: result.revision } : {}),
          },
        },
        { signal: op.signal },
      );
      patchRef.current(op.id, { jobId: accepted.job_id });
      await poll(op.client, op.id, accepted.job_id, op.signal);
      await resolveMessage(
        { ...op, state: { ...op.state, proposal: proposal || null } },
        requirement,
        clientMessageId,
      );
    });
  };
  const cancelJob = async () => {
    const saved = currentRef.current;
    const job = saved ? latest.current[saved.id]?.job : null;
    const access = saved ? getAccess(saved.id) : null;
    if (!saved || !job || !access) return;
    try {
      await new ApiClient(access.token).cancelJob(job.id);
    } catch (error) {
      update(saved.id, { error: errorText(error) });
    }
  };
  const loadRun = (comparisonId: string) =>
    run(async (op) => {
      update(op.id, {
        comparison: await op.client.comparison(comparisonId, { signal: op.signal }),
      });
      patchRef.current(op.id, { comparisonId });
    });
  const openEvidence = async (evidenceId: string) => {
    const saved = currentRef.current;
    if (!saved) return;
    evidenceController.current?.abort();
    const ctrl = new AbortController();
    evidenceController.current = ctrl;
    setEvidenceOpen(true);
    setEvidence(null);
    setEvidenceError(null);
    try {
      const access = getAccess(saved.id);
      if (!access) throw new Error('Phiên đã hết hạn.');
      const item = await new ApiClient(access.token).evidence(evidenceId, { signal: ctrl.signal });
      ctrl.signal.throwIfAborted();
      setEvidence(item);
    } catch (error) {
      if (!ctrl.signal.aborted) setEvidenceError(errorText(error));
    }
  };
  const closeEvidence = () => {
    evidenceController.current?.abort();
    setEvidenceOpen(false);
  };
  return {
    catalog,
    catalogError,
    reloadCatalog: () => loadCatalog(),
    state: current ? resources[current.id] || blank : blank,
    create,
    saveEdits,
    confirm,
    cancelProposal,
    discard,
    clarify,
    search,
    offerChange,
    sendMessage,
    cancelJob,
    loadRun,
    refresh: () => run(resume),
    openEvidence,
    closeEvidence,
    evidence,
    evidenceError,
    evidenceOpen,
  };
}
