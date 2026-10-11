import { useCallback, useEffect, useRef, useState } from 'react';
import type { LocalSession } from '../../../features/session-history';
import type { ChatMsg, ChatStep } from '../../../features/chat';
import {
  CurrentBackendClient,
  type CurrentCatalog,
  type CurrentComparison,
  type CurrentRequirement,
} from '../../../shared/api';
import { usePreferences } from '../../../shared/preferences';
import { accessFor, isSessionExpired } from '../../../features/session-history';
import { sessionTitle } from '../../../shared/lib';

const uid = () =>
  typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `msg-${Date.now()}-${Math.floor(Math.random() * 1e9)}`;

const idleSteps: ChatStep[] = [
  { id: 'interpret', state: 'pending' },
  { id: 'compare', state: 'pending' },
];

function setStep(steps: ChatStep[], id: ChatStep['id'], state: ChatStep['state']): ChatStep[] {
  return steps.map((step) => (step.id === id ? { ...step, state } : step));
}

interface UndoFrame {
  length: number;
  dropped: string[];
  requirementId: string | null;
  comparisonId: string | null;
}

/**
 * Chat orchestration over the current backend. Each send re-interprets the
 * accumulated text; compare runs explicitly or auto when nothing is missing.
 */
export function useChat(
  session: LocalSession,
  onChangeSession: (changes: Partial<LocalSession>) => void,
) {
  const [client, setClient] = useState<CurrentBackendClient | null>(null);
  const [catalog, setCatalog] = useState<CurrentCatalog | null>(null);
  const [msgs, setMsgs] = useState<ChatMsg[]>([]);
  const [phase, setPhase] = useState<'idle' | 'thinking' | 'working'>('idle');
  const [steps, setSteps] = useState<ChatStep[]>(idleSteps);
  const [failedStep, setFailedStep] = useState<'init' | 'interpret' | 'compare' | null>(null);
  const [dropped, setDropped] = useState<string[]>([]);
  const [undoStack, setUndoStack] = useState<UndoFrame[]>([]);
  const [reload, setReload] = useState(0);
  const { t } = usePreferences();
  const sessionRef = useRef(session);
  sessionRef.current = session;
  const busy = phase !== 'idle';

  const push = useCallback((msg: ChatMsg) => {
    setMsgs((all) => [...all, msg]);
  }, []);

  // Init: bearer access, catalog, and rebuild of the last persisted result.
  useEffect(() => {
    const target = sessionRef.current;
    let active = true;
    setClient(null);
    setCatalog(null);
    setMsgs([]);
    setPhase('thinking');
    setSteps(idleSteps);
    setFailedStep(null);
    setDropped([]);
    setUndoStack([]);
    void (async () => {
      try {
        const access = await accessFor(target);
        const api = new CurrentBackendClient(access.token);
        const [loadedCatalog, health] = await Promise.all([api.catalog(), api.health()]);
        if (health.status !== 'ok') throw new Error('Backend is not ready. Try again shortly.');
        if (!active) return;
        setClient(api);
        setCatalog(loadedCatalog);
        if (target.requirementId) {
          const loaded = await api.requirement(target.requirementId);
          if (!active) return;
          push({ id: uid(), kind: 'interpretation', requirement: loaded.requirement });
          if (target.comparisonId) {
            const previous = await api.comparison(target.comparisonId);
            if (!active) return;
            push({
              id: uid(),
              kind: 'comparison',
              comparison: previous.comparison,
              dropped: [],
            });
          }
        }
      } catch (cause) {
        if (active) {
          push({
            id: uid(),
            kind: 'error',
            text: cause instanceof Error ? cause.message : 'Could not connect to backend.',
            expired: isSessionExpired(cause),
          });
          setFailedStep('init');
        }
      } finally {
        if (active) setPhase('idle');
      }
    })();
    return () => {
      active = false;
    };
  }, [session.id, reload, push]);

  const interpret = useCallback(
    async (api: CurrentBackendClient, text: string, drop: string[]) => {
      setSteps((all) => setStep(setStep(all, 'interpret', 'active'), 'compare', 'pending'));
      const result = await api.createRequirement(text.trim(), undefined, drop);
      const requirement: CurrentRequirement = result.requirement;
      onChangeSession({
        requirementId: requirement.id,
        comparisonId: null,
        title: sessionTitle(requirement, text),
      });
      push({ id: uid(), kind: 'interpretation', requirement });
      return requirement;
    },
    [onChangeSession, push],
  );

  const compare = useCallback(
    async (api: CurrentBackendClient, requirement: CurrentRequirement, drop: string[]) => {
      setSteps((all) => setStep(all, 'compare', 'active'));
      const result = await api.createComparison(requirement.id);
      const comparison: CurrentComparison = result.comparison;
      onChangeSession({ comparisonId: comparison.id });
      push({ id: uid(), kind: 'comparison', comparison, dropped: [...drop] });
      return comparison;
    },
    [onChangeSession, push],
  );

  const runFlow = useCallback(
    async (
      text: string,
      drop: string[],
      autoCompare: boolean,
      failStep: 'interpret' | 'compare',
    ) => {
      if (!client) return;
      setFailedStep(null);
      setPhase('working');
      setSteps(idleSteps);
      try {
        const requirement = await interpret(client, text, drop);
        setSteps((all) => setStep(all, 'interpret', 'done'));
        if (autoCompare || requirement.missing.length === 0) {
          await compare(client, requirement, drop);
          setSteps((all) => setStep(all, 'compare', 'done'));
        }
      } catch (cause) {
        setSteps((all) =>
          all.map((step) => (step.state === 'active' ? { ...step, state: 'error' } : step)),
        );
        push({
          id: uid(),
          kind: 'error',
          text: cause instanceof Error ? cause.message : 'Could not complete this step.',
        });
        setFailedStep(failStep);
      } finally {
        setPhase('idle');
      }
    },
    [client, compare, interpret, push],
  );

  const send = useCallback(
    (text: string) => {
      if (!client) return;
      const target = sessionRef.current;
      const full = target.draft.text ? `${target.draft.text}\n${text}` : text;
      onChangeSession({ draft: { ...target.draft, text: full } });
      push({ id: uid(), kind: 'user', text });
      setPhase('thinking');
      void runFlow(full, dropped, false, 'interpret');
    },
    [client, dropped, onChangeSession, push, runFlow],
  );

  const compareNow = useCallback(() => {
    if (!client) return;
    const target = sessionRef.current;
    setPhase('thinking');
    void (async () => {
      setFailedStep(null);
      setPhase('working');
      setSteps(idleSteps);
      try {
        let text = target.draft.text;
        if (!text && target.requirementId) {
          const loaded = await client.requirement(target.requirementId);
          text = loaded.requirement.raw_text;
        }
        await runFlow(text, dropped, true, 'compare');
      } catch (cause) {
        push({
          id: uid(),
          kind: 'error',
          text: cause instanceof Error ? cause.message : 'Could not compare tours.',
        });
        setFailedStep('compare');
        setPhase('idle');
      }
    })();
  }, [client, dropped, push, runFlow]);

  const relax = useCallback(
    (field: string) => {
      if (!client) return;
      const target = sessionRef.current;
      setUndoStack((stack) => [
        ...stack,
        {
          length: msgs.length,
          dropped: [...dropped],
          requirementId: target.requirementId,
          comparisonId: target.comparisonId,
        },
      ]);
      const next = [...dropped, field];
      setDropped(next);
      push({
        id: uid(),
        kind: 'assistant',
        text: t(
          `Đã bỏ điều kiện ${field.replaceAll('_', ' ')}, tìm lại nhé.`,
          `Relaxed ${field.replaceAll('_', ' ')}, searching again.`,
        ),
      });
      setPhase('thinking');
      void (async () => {
        let text = target.draft.text;
        if (!text && target.requirementId) {
          const loaded = await client.requirement(target.requirementId);
          text = loaded.requirement.raw_text;
        }
        await runFlow(text, next, true, 'compare');
      })();
    },
    [client, dropped, msgs.length, push, runFlow, t],
  );

  const undo = useCallback(() => {
    setUndoStack((stack) => {
      const frame = stack[stack.length - 1];
      if (!frame) return stack;
      setDropped(frame.dropped);
      onChangeSession({ requirementId: frame.requirementId, comparisonId: frame.comparisonId });
      setMsgs((all) => all.slice(0, frame.length));
      return stack.slice(0, -1);
    });
  }, [onChangeSession]);

  const retry = useCallback(() => {
    if (failedStep === 'init') setReload((value) => value + 1);
    else if (failedStep === 'compare') compareNow();
    else if (sessionRef.current.draft.text) {
      const target = sessionRef.current;
      setPhase('thinking');
      void runFlow(target.draft.text, dropped, false, 'interpret');
    }
  }, [compareNow, dropped, failedStep, runFlow]);

  return {
    client,
    catalog,
    msgs,
    busy,
    phase,
    steps,
    failedStep,
    dropped,
    canUndo: undoStack.length > 0,
    retry,
    send,
    compareNow,
    relax,
    undo,
  };
}
