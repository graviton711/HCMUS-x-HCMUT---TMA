import { useCallback, useEffect, useRef, useState } from 'react';
import { validChatMsg, type LocalSession } from '../../../features/session-history';
import type { ChatMsg, ChatPhase } from '../../../features/chat';
import {
  CurrentApiError,
  CurrentBackendClient,
  type CurrentAgentProgressEvent,
  type CurrentAgentResponse,
  type CurrentComparison,
  type CurrentRequirement,
} from '../../../shared/api';
import { accessFor, isSessionExpired } from '../../../features/session-history';
import { sessionTitle } from '../../../shared/lib';
import { usePreferences } from '../../../shared/preferences';
import type { Locale } from '../../../shared/preferences';

const uid = () =>
  typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `msg-${Date.now()}-${Math.floor(Math.random() * 1e9)}`;

function withEqualSoftWeights(requirement: CurrentRequirement): CurrentRequirement {
  const soft = requirement.conditions.filter((condition) => condition.strength === 'soft');
  if (!soft.length || soft.every((condition) => typeof condition.weight_percent === 'number'))
    return requirement;
  const base = Math.floor(100 / soft.length);
  const remainder = 100 % soft.length;
  const weights = new Map(soft.map((condition, index) => [condition.id, base + Number(index < remainder)]));
  return {
    ...requirement,
    conditions: requirement.conditions.map((condition) =>
      condition.strength === 'soft'
        ? { ...condition, weight_percent: weights.get(condition.id) ?? base }
        : condition,
    ),
  };
}

function isChatMsg(value: unknown): value is ChatMsg {
  return validChatMsg(value);
}

function errorText(cause: unknown, fallback: string, locale: Locale) {
  const t = (vi: string, en: string) => (locale === 'vi' ? vi : en);
  if (cause instanceof CurrentApiError) {
    if (cause.code === 'OPENCODE_MODEL_ACCESS_DENIED') {
      return t(
        'Model đang dùng chưa cho phép gửi yêu cầu từ ứng dụng. Hãy chọn model khác hoặc liên hệ quản trị viên.',
        'The current model cannot accept requests from this app. Choose another model or contact your administrator.',
      );
    }
    if (cause.code === 'OPENCODE_RESPONSE_EMPTY') {
      return t(
        'Mình chưa lấy được kết quả lần này.',
        'I couldn’t retrieve the results this time.',
      );
    }
    if (cause.code === 'NETWORK_ERROR') {
      return t(
        'Không kết nối được dịch vụ tìm tour.',
        'Could not connect to the tour service.',
      );
    }
  }
  return fallback;
}

export function useChat(
  session: LocalSession,
  onChangeSession: (changes: Partial<LocalSession>) => void,
) {
  const { locale } = usePreferences();
  const localeRef = useRef(locale);
  localeRef.current = locale;
  const [client, setClient] = useState<CurrentBackendClient | null>(null);
  const [msgs, setMsgs] = useState<ChatMsg[]>([]);
  const [phase, setPhase] = useState<ChatPhase>('idle');
  const [activeToolActivityId, setActiveToolActivityId] = useState<string | null>(null);
  const [initialSendPending, setInitialSendPending] = useState(false);
  const [failedStep, setFailedStep] = useState<'init' | 'message' | 'decision' | null>(null);
  const [sessionExpired, setSessionExpired] = useState(false);
  const [reload, setReload] = useState(0);
  const transcriptRef = useRef<ChatMsg[]>(session.messages.filter(isChatMsg));
  const sessionRef = useRef(session);
  const onChangeSessionRef = useRef(onChangeSession);
  const lastMessageRef = useRef('');
  const lastDecisionRef = useRef<{ messageId: string; requirement: CurrentRequirement } | null>(null);
  const toolActivityIdRef = useRef<string | null>(null);
  const hasLiveToolEventsRef = useRef(false);
  const abortControllerRef = useRef<AbortController | null>(null);
  const mountedRef = useRef(true);
  sessionRef.current = session;
  onChangeSessionRef.current = onChangeSession;
  const busy = phase !== 'idle';

  const push = useCallback((message: ChatMsg) => {
    setMsgs((all) => [...all, message]);
    const transcript = [...transcriptRef.current, message];
    transcriptRef.current = transcript;
    onChangeSessionRef.current({ messages: transcript });
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      abortControllerRef.current?.abort('unmount');
    };
  }, []);

  const upsertToolActivity = useCallback(
    (activity: Extract<ChatMsg, { kind: 'tool_activity' }>) => {
      const transcriptIndex = transcriptRef.current.findIndex(
        (message) => message.id === activity.id && message.kind === 'tool_activity',
      );
      transcriptRef.current =
        transcriptIndex >= 0
          ? transcriptRef.current.map((message, index) =>
              index === transcriptIndex ? activity : message,
            )
          : [...transcriptRef.current, activity];

      setMsgs((all) => {
        const messageIndex = all.findIndex(
          (message) => message.id === activity.id && message.kind === 'tool_activity',
        );
        return messageIndex >= 0
          ? all.map((message, index) => (index === messageIndex ? activity : message))
          : [...all, activity];
      });
    },
    [],
  );

  const recordToolProgress = useCallback(
    (event: CurrentAgentProgressEvent) => {
      if (event.type !== 'tool') return;
      hasLiveToolEventsRef.current = true;
      const activityId = toolActivityIdRef.current ?? uid();
      toolActivityIdRef.current = activityId;
      setActiveToolActivityId(activityId);
      const current = transcriptRef.current.find(
        (message) => message.id === activityId && message.kind === 'tool_activity',
      );
      const tools = current?.kind === 'tool_activity' ? current.tools : [];
      const toolIndex = tools.findIndex((tool) => tool.id === event.id);
      const nextTools = [...tools];
      const previous = toolIndex >= 0 ? nextTools[toolIndex] : undefined;
      const tool = {
        id: event.id,
        name: event.name,
        message: event.message || previous?.message,
        status: event.status,
      } as const;
      if (toolIndex >= 0) nextTools[toolIndex] = tool;
      else nextTools.push(tool);
      upsertToolActivity({
        id: activityId,
        kind: 'tool_activity',
        tools: nextTools,
        outcome: 'running',
      });
    },
    [upsertToolActivity],
  );

  const failRunningTools = useCallback(() => {
    const activity = transcriptRef.current.find(
      (message) => message.id === toolActivityIdRef.current && message.kind === 'tool_activity',
    );
    if (activity?.kind !== 'tool_activity') return;
    const tools = activity.tools.map((tool) =>
      tool.status === 'running' ? { ...tool, status: 'error' as const } : tool,
    );
    upsertToolActivity({ ...activity, tools, outcome: 'error' });
  }, [upsertToolActivity]);

  const cancelRunningTools = useCallback(() => {
    const activity = transcriptRef.current.find(
      (message) => message.id === toolActivityIdRef.current && message.kind === 'tool_activity',
    );
    if (activity?.kind !== 'tool_activity') return;
    const tools = activity.tools.map((tool) =>
      tool.status === 'running' ? { ...tool, status: 'cancelled' as const } : tool,
    );
    upsertToolActivity({ ...activity, tools, outcome: 'cancelled' });
  }, [upsertToolActivity]);

  const completeToolActivity = useCallback(() => {
    const activity = transcriptRef.current.find(
      (message) => message.id === toolActivityIdRef.current && message.kind === 'tool_activity',
    );
    if (activity?.kind !== 'tool_activity') return;
    upsertToolActivity({ ...activity, outcome: 'completed' });
  }, [upsertToolActivity]);

  useEffect(() => {
    const target = sessionRef.current;
    const shouldAutoSendInitial =
      !target.agentSessionId &&
      !target.requirementId &&
      !target.comparisonId &&
      Boolean(target.draft.text.trim());
    let active = true;
    setClient(null);
    const restoredMessages = target.messages.filter(isChatMsg);
    transcriptRef.current = restoredMessages;
    setMsgs(restoredMessages);
    setInitialSendPending(false);
    setSessionExpired(false);
    toolActivityIdRef.current = null;
    setActiveToolActivityId(null);
    hasLiveToolEventsRef.current = false;
    setPhase('thinking');
    setFailedStep(null);
    void (async () => {
      try {
        const access = await accessFor(target);
        const api = new CurrentBackendClient(access.token);
        const health = await api.health();
        if (health.status !== 'ok') throw new Error('Backend is not ready. Try again shortly.');
        let agentSessionId = target.agentSessionId;
        if (!agentSessionId) {
          const created = await api.createAgentSession();
          if (!active) return;
          agentSessionId = created.agent_session_id;
          onChangeSessionRef.current({ agentSessionId });
        }
        if (!active) return;
        setClient(api);
        setInitialSendPending(shouldAutoSendInitial);
        const restoredComparison = restoredMessages.some(
          (message) =>
            message.kind === 'comparison' && message.comparison.id === target.comparisonId,
        );
        if (target.comparisonId && !restoredComparison) {
          const previous = await api.comparison(target.comparisonId);
          if (!active) return;
          push({ id: uid(), kind: 'comparison', comparison: previous.comparison });
        }
      } catch (cause) {
        if (active) {
          const expired = isSessionExpired(cause);
          push({
            id: uid(),
            kind: 'error',
            text: errorText(
              cause,
              localeRef.current === 'vi'
                ? 'Chưa kết nối được dịch vụ tìm tour. Hãy thử lại sau ít phút.'
                : 'Could not connect to the tour service. Try again in a moment.',
              localeRef.current,
            ),
            expired,
          });
          setSessionExpired(expired);
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

  const applyResponse = useCallback(
    (response: CurrentAgentResponse, text: string) => {
      if (response.tool_calls.length && !hasLiveToolEventsRef.current) {
        const activityId = toolActivityIdRef.current ?? uid();
        toolActivityIdRef.current = activityId;
        const existing = transcriptRef.current.find(
          (message) => message.id === activityId && message.kind === 'tool_activity',
        );
        const tools = existing?.kind === 'tool_activity' ? [...existing.tools] : [];
        const finalCalls = new Map<string, 'running' | 'completed' | 'error'>();
        response.tool_calls.forEach((call) => {
          const status =
            call.status === 'completed' || call.status === 'success'
              ? 'completed'
              : call.status === 'error' || call.status === 'failed'
                ? 'error'
                : 'running';
          finalCalls.set(call.name, status);
        });
        [...finalCalls].forEach(([name, status], index) => {
          if (!tools.some((tool) => tool.name === name)) {
            tools.push({ id: `${activityId}-result-${index}`, name, status });
          }
        });
        upsertToolActivity({ id: activityId, kind: 'tool_activity', tools });
      }
      if (response.assistant_text.trim()) {
        push({ id: uid(), kind: 'assistant', text: response.assistant_text.trim() });
      }
      if (response.choices) push({ id: uid(), kind: 'choice', choice: response.choices });
      if (response.decision_draft) {
        const requirement = withEqualSoftWeights(response.decision_draft);
        const message: ChatMsg = {
          id: uid(),
          kind: 'decision_draft',
          requirement,
          status: 'draft',
        };
        onChangeSessionRef.current({
          requirementId: requirement.id,
          comparisonId: null,
          title: sessionTitle(requirement, text),
        });
        push(message);
      }
      if (response.requirement) {
        onChangeSessionRef.current({
          requirementId: response.requirement.id,
          comparisonId: null,
          title: sessionTitle(response.requirement, text),
        });
      }
      if (response.comparison) {
        const comparison: CurrentComparison = response.comparison;
        onChangeSessionRef.current({
          requirementId: comparison.requirement.id,
          comparisonId: comparison.id,
          title: sessionTitle(comparison.requirement, text),
        });
        push({ id: uid(), kind: 'comparison', comparison });
      }
    },
    [push, upsertToolActivity],
  );

  const updateDecisionDraft = useCallback(
    (messageId: string, requirement: CurrentRequirement) => {
      const updated = transcriptRef.current.map((message) =>
        message.id === messageId && message.kind === 'decision_draft'
          ? { ...message, requirement: withEqualSoftWeights(requirement), status: 'draft' as const }
          : message,
      );
      transcriptRef.current = updated;
      setMsgs(updated);
      onChangeSessionRef.current({ messages: updated });
    },
    [],
  );

  const setDecisionDraftStatus = useCallback((messageId: string, status: 'draft' | 'running' | 'complete') => {
    const updated = transcriptRef.current.map((message) =>
      message.id === messageId && message.kind === 'decision_draft'
        ? { ...message, status }
        : message,
    );
    transcriptRef.current = updated;
    setMsgs(updated);
    onChangeSessionRef.current({ messages: updated });
  }, []);

  const sendMessage = useCallback(
    async (text: string, showUserMessage: boolean) => {
      const api = client;
      const agentSessionId = sessionRef.current.agentSessionId;
      if (sessionExpired || !api || !agentSessionId || !text.trim() || abortControllerRef.current)
        return;
      const controller = new AbortController();
      abortControllerRef.current = controller;
      setFailedStep(null);
      setPhase('working');
      toolActivityIdRef.current = null;
      setActiveToolActivityId(null);
      hasLiveToolEventsRef.current = false;
      lastMessageRef.current = text.trim();
      if (showUserMessage) {
        push({ id: uid(), kind: 'user', text: text.trim() });
        const draft = sessionRef.current.draft;
        if (!draft.text.trim()) {
          onChangeSessionRef.current({ draft: { ...draft, text: text.trim() } });
        }
      }
      setInitialSendPending(false);
      try {
        const response = await api.agentMessageStream(
          agentSessionId,
          text.trim(),
          recordToolProgress,
          controller.signal,
        );
        applyResponse(response, text);
        completeToolActivity();
      } catch (cause) {
        if (controller.signal.aborted) {
          if (controller.signal.reason === 'user' && mountedRef.current) {
            cancelRunningTools();
            push({
              id: uid(),
              kind: 'notice',
              text: localeRef.current === 'vi' ? 'Đã dừng lượt tìm.' : 'Response stopped.',
            });
          }
        } else {
          failRunningTools();
          const expired = isSessionExpired(cause);
          push({
            id: uid(),
            kind: 'error',
            text: errorText(
              cause,
              localeRef.current === 'vi'
                ? 'Mình chưa lấy được kết quả lần này.'
                : 'I couldn’t retrieve the results this time.',
              localeRef.current,
            ),
            expired,
          });
          setSessionExpired(expired);
          setFailedStep('message');
        }
      } finally {
        if (abortControllerRef.current === controller) abortControllerRef.current = null;
        if (mountedRef.current) {
          onChangeSessionRef.current({ messages: transcriptRef.current });
          setPhase('idle');
        }
      }
    },
    [
      applyResponse,
      cancelRunningTools,
      completeToolActivity,
      client,
      failRunningTools,
      push,
      recordToolProgress,
      sessionExpired,
    ],
  );

  const send = useCallback((text: string) => void sendMessage(text, true), [sendMessage]);
  const stop = useCallback(() => abortControllerRef.current?.abort('user'), []);

  const runDecision = useCallback(
    (messageId: string, requirementInput: CurrentRequirement) => {
      const api = client;
      const agentSessionId = sessionRef.current.agentSessionId;
      if (sessionExpired || !api || !agentSessionId || abortControllerRef.current) return;
      const requirement = withEqualSoftWeights(requirementInput);
      lastDecisionRef.current = { messageId, requirement };
      const controller = new AbortController();
      abortControllerRef.current = controller;
      setFailedStep(null);
      setDecisionDraftStatus(messageId, 'running');
      setPhase('working');
      toolActivityIdRef.current = null;
      setActiveToolActivityId(null);
      hasLiveToolEventsRef.current = false;
      void (async () => {
        try {
          const response = await api.agentDecisionStream(
            agentSessionId,
            requirement,
            recordToolProgress,
            controller.signal,
          );
          applyResponse(response, requirement.raw_text);
          completeToolActivity();
          setDecisionDraftStatus(messageId, 'complete');
        } catch (cause) {
          if (controller.signal.aborted) {
            setDecisionDraftStatus(messageId, 'draft');
            if (controller.signal.reason === 'user' && mountedRef.current) {
              cancelRunningTools();
              push({
                id: uid(),
                kind: 'notice',
                text: localeRef.current === 'vi' ? 'Đã dừng lượt so sánh.' : 'Comparison stopped.',
              });
            }
          } else {
            failRunningTools();
            setDecisionDraftStatus(messageId, 'draft');
            const expired = isSessionExpired(cause);
            push({
              id: uid(),
              kind: 'error',
              text: errorText(
                cause,
                localeRef.current === 'vi'
                  ? 'Chưa thể hoàn tất lượt so sánh.'
                  : 'The comparison could not be completed.',
                localeRef.current,
              ),
              expired,
            });
            setSessionExpired(expired);
            setFailedStep('decision');
          }
        } finally {
          if (abortControllerRef.current === controller) abortControllerRef.current = null;
          if (mountedRef.current) {
            onChangeSessionRef.current({ messages: transcriptRef.current });
            setPhase('idle');
          }
        }
      })();
    },
    [
      applyResponse,
      cancelRunningTools,
      completeToolActivity,
      client,
      failRunningTools,
      push,
      recordToolProgress,
      sessionExpired,
      setDecisionDraftStatus,
    ],
  );

  const relax = useCallback(
    (field: string) =>
      void sendMessage(`Hãy nới điều kiện ${field.replaceAll('_', ' ')} rồi tìm lại tour.`, true),
    [sendMessage],
  );

  const retry = useCallback(() => {
    if (sessionExpired) return;
    if (failedStep === 'init') setReload((value) => value + 1);
    else if (failedStep === 'decision' && lastDecisionRef.current)
      runDecision(lastDecisionRef.current.messageId, lastDecisionRef.current.requirement);
    else if (lastMessageRef.current) void sendMessage(lastMessageRef.current, false);
  }, [failedStep, runDecision, sendMessage, sessionExpired]);

  return {
    client,
    msgs,
    busy,
    phase,
    activeToolActivityId,
    initialSendPending,
    failedStep,
    sessionExpired,
    retry,
    send,
    stop,
    relax,
    updateDecisionDraft,
    runDecision,
  };
}
