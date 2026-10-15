import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { CSSProperties } from 'react';
import type { LocalSession } from '../../../features/session-history';
import { Composer, QuickReplies, Thread, ToolStatus } from '../../../features/chat';
import type { CurrentComparison } from '../../../shared/api';
import { usePreferences } from '../../../shared/preferences';
import { useChat } from '../model/useChat';
import { latestDecisionArtifact } from '../lib/decisionArtifacts';
import { DecisionWorkspace } from './DecisionWorkspace';
import styles from './ChatPage.module.css';

const SUGGESTIONS: [string, string][] = [
  ['Đà Lạt 3 ngày, đi từ TP.HCM, tối đa 8 triệu mỗi người', 'điểm đến · ngân sách'],
  ['Tour Tết từ Hải Phòng đi Đà Nẵng 4 ngày', 'điểm đến · lịch khởi hành'],
  ['Phú Quốc 4 ngày đi từ Hà Nội, đi bằng máy bay', 'điểm đến · phương tiện'],
];

const SPLIT_STORAGE_KEY = 'tourlens:decision-split:v1';
const DEFAULT_CHAT_SPLIT = 0.42;
const MIN_CHAT_SPLIT = 0.28;
const MAX_CHAT_SPLIT = 0.58;
const SPLITTER_WIDTH = 10;
const MIN_CHAT_WIDTH = 320;
const MIN_DECISION_WIDTH = 420;

function readChatSplit() {
  try {
    const saved = Number(localStorage.getItem(SPLIT_STORAGE_KEY));
    return Number.isFinite(saved) && saved >= MIN_CHAT_SPLIT && saved <= MAX_CHAT_SPLIT
      ? saved
      : DEFAULT_CHAT_SPLIT;
  } catch {
    return DEFAULT_CHAT_SPLIT;
  }
}

function splitBounds(layoutWidth: number) {
  if (layoutWidth <= 0) return { min: MIN_CHAT_SPLIT, max: MAX_CHAT_SPLIT };
  const usableWidth = Math.max(1, layoutWidth - SPLITTER_WIDTH);
  const min = Math.max(MIN_CHAT_SPLIT, MIN_CHAT_WIDTH / usableWidth);
  const max = Math.min(MAX_CHAT_SPLIT, (usableWidth - MIN_DECISION_WIDTH) / usableWidth);
  return {
    min,
    max: Math.max(min, max),
  };
}

export function ChatPage({
  session,
  onStart,
  onChangeSession,
  isSavedTour,
  onToggleSavedTour,
}: {
  session: LocalSession | null;
  onStart: (initialText?: string) => void;
  onChangeSession: (id: string, changes: Partial<LocalSession>) => void;
  isSavedTour?: (tourId: string, offerId: string) => boolean;
  onToggleSavedTour?: (comparison: CurrentComparison, tourId: string, offerId: string) => void;
}) {
  return session ? (
    <ActiveChat
      key={session.id}
      session={session}
      onStart={onStart}
      isSavedTour={isSavedTour}
      onToggleSavedTour={onToggleSavedTour}
      onChangeSession={(changes) => onChangeSession(session.id, changes)}
    />
  ) : (
    <Entry onStart={onStart} />
  );
}

function Entry({ onStart }: { onStart: (initialText?: string) => void }) {
  const { t } = usePreferences();
  return (
    <div className={`${styles.workspace} ${styles.entry}`}>
      <header className={styles['entry-hero']}>
        <h1>{t('Đi đâu tiếp?', 'Where next?')}</h1>
        <p>
          {t(
            'Mô tả chuyến đi bạn muốn. TourLens đối chiếu từng tour theo cùng bộ tiêu chí, ghi rõ điều kiện nào đạt và dữ liệu nào còn thiếu — bạn tự quyết định.',
            'Describe the trip you want. TourLens compares every tour against the same criteria and shows what passes and what information is missing — you decide.',
          )}
        </p>
      </header>

      <div className={styles['entry-prompt']}>
        <Composer busy={false} size="large" onSend={(text) => onStart(text)} />
        <section aria-labelledby="examples-title">
          <h2 className={styles['examples-title']} id="examples-title">
            {t('Thử một yêu cầu', 'Try an example')}
          </h2>
          <div className={styles.examples}>
            {SUGGESTIONS.map(([text, meta]) => (
              <button
                key={text}
                type="button"
                className={styles.example}
                onClick={() => onStart(text)}
              >
                <span>{text}</span>
                <span>{meta}</span>
              </button>
            ))}
          </div>
        </section>
      </div>

      <p className={styles['entry-note']}>
        {t(
          'Mỗi gợi ý được đối chiếu theo dữ kiện có nguồn; tour thiếu thông tin sẽ được ghi rõ.',
          'Suggestions are checked against sourced data; missing tour information stays explicit.',
        )}
      </p>
    </div>
  );
}

function ActiveChat({
  session,
  onStart,
  onChangeSession,
  isSavedTour,
  onToggleSavedTour,
}: {
  session: LocalSession;
  onStart: (initialText?: string) => void;
  onChangeSession: (changes: Partial<LocalSession>) => void;
  isSavedTour?: (tourId: string, offerId: string) => boolean;
  onToggleSavedTour?: (comparison: CurrentComparison, tourId: string, offerId: string) => void;
}) {
  const { t } = usePreferences();
  const chat = useChat(session, onChangeSession);
  const threadRef = useRef<HTMLDivElement>(null);
  const workspaceRef = useRef<HTMLDivElement>(null);
  const layoutRef = useRef<HTMLDivElement>(null);
  const activePointer = useRef<number | null>(null);
  const autoSent = useRef(false);
  const lastArtifactId = useRef<string | null>(null);
  const [compact, setCompact] = useState(true);
  const [mobilePane, setMobilePane] = useState<'chat' | 'decision'>('chat');
  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(null);
  const [chatSplit, setChatSplit] = useState(readChatSplit);
  const [splitDragging, setSplitDragging] = useState(false);
  const latestArtifact = latestDecisionArtifact(chat.msgs);

  useEffect(() => {
    try {
      localStorage.setItem(SPLIT_STORAGE_KEY, String(chatSplit));
    } catch {
      // Resizing remains available when storage is disabled.
    }
  }, [chatSplit]);

  useLayoutEffect(() => {
    const workspace = workspaceRef.current;
    if (!workspace) return;
    const update = () => {
      const style = window.getComputedStyle(workspace);
      const horizontalPadding = Number.parseFloat(style.paddingLeft) + Number.parseFloat(style.paddingRight);
      setCompact(workspace.clientWidth - horizontalPadding < 1040);
    };
    update();
    if (typeof ResizeObserver === 'undefined') {
      if (typeof window.matchMedia !== 'function') return;
      const media = window.matchMedia('(max-width: 1280px)');
      const fallback = () => setCompact(media.matches);
      media.addEventListener('change', fallback);
      return () => media.removeEventListener('change', fallback);
    }
    const observer = new ResizeObserver(update);
    observer.observe(workspace);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const id = latestArtifact?.id ?? null;
    if (id && id !== lastArtifactId.current) {
      lastArtifactId.current = id;
      setSelectedArtifactId(null);
      if (compact) setMobilePane('decision');
    } else if (!id) {
      lastArtifactId.current = null;
    }
  }, [compact, latestArtifact?.id]);

  useEffect(() => {
    const thread = threadRef.current;
    if (!thread) return;
    const canMatchMedia = typeof window.matchMedia === 'function';
    const reduced = canMatchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const documentScroll = window.getComputedStyle(thread).overflowY === 'visible';
    if (documentScroll && mobilePane !== 'chat') return;

    if (documentScroll) {
      const scrollRoot = document.scrollingElement ?? document.documentElement;
      const scrollHeight = Math.max(scrollRoot.scrollHeight, document.body.scrollHeight);
      const nearBottom = scrollHeight - window.scrollY - window.innerHeight < 480;
      if (!nearBottom) return;
      window.scrollTo({ top: scrollHeight, behavior: reduced ? 'auto' : 'smooth' });
      return;
    }

    const nearBottom = thread.scrollHeight - thread.scrollTop - thread.clientHeight < 480;
    if (!nearBottom) return;
    const top = thread.scrollHeight;
    if (typeof thread.scrollTo === 'function') {
      thread.scrollTo({ top, behavior: reduced ? 'auto' : 'smooth' });
    } else {
      thread.scrollTop = top;
    }
  }, [chat.msgs.length, chat.phase, mobilePane]);

  // A session created from an example request sends once on mount.
  useEffect(() => {
    if (
      !autoSent.current &&
      chat.client &&
      chat.msgs.length === 0 &&
      chat.initialSendPending &&
      session.draft.text.trim()
    ) {
      autoSent.current = true;
      chat.send(session.draft.text.trim());
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chat.client, chat.initialSendPending, chat.msgs.length]);

  const hasTurnToolActivity = Boolean(chat.activeToolActivityId);
  const expired = chat.sessionExpired;
  const draftText = session.draft.text.trim();
  const sendFromWorkspace = (text: string) => {
    setMobilePane('chat');
    chat.send(text);
  };
  const openArtifact = (id: string) => {
    setSelectedArtifactId(id);
    if (compact) setMobilePane('decision');
  };
  const setSplitFromPointer = (clientX: number) => {
    const layout = layoutRef.current;
    if (!layout) return;
    const { left, width } = layout.getBoundingClientRect();
    const usableWidth = Math.max(1, width - SPLITTER_WIDTH);
    const requested = (clientX - left) / usableWidth;
    const { min, max } = splitBounds(width);
    setChatSplit(Math.min(max, Math.max(min, requested)));
  };
  const nudgeSplit = (direction: 'narrower' | 'wider' | 'min' | 'max') => {
    const layoutWidth = layoutRef.current?.getBoundingClientRect().width ?? 0;
    const { min, max } = splitBounds(layoutWidth);
    const next = direction === 'min'
      ? min
      : direction === 'max'
        ? max
        : chatSplit + (direction === 'wider' ? 0.02 : -0.02);
    setChatSplit(Math.min(max, Math.max(min, next)));
  };

  return (
    <div className={`${styles.workspace} ${styles.active}`} ref={workspaceRef}>
      <div
        className={styles['active-layout']}
        ref={layoutRef}
        style={{ '--chat-pane-size': `${chatSplit * 100}%` } as CSSProperties}
        data-split-dragging={splitDragging}
      >
        <div className={styles['workspace-switcher']} role="group" aria-label={t('Chế độ xem', 'Workspace view')}>
          <button
            type="button"
            aria-pressed={mobilePane === 'chat'}
            onClick={() => setMobilePane('chat')}
          >
            {t('Trao đổi', 'Chat')}
          </button>
          <button
            type="button"
            aria-pressed={mobilePane === 'decision'}
            onClick={() => setMobilePane('decision')}
          >
            {t('Quyết định', 'Decision')}
          </button>
        </div>

        <div
          className={`${styles['thread-scroll']} ${mobilePane === 'chat' ? '' : styles['pane-hidden']}`}
          ref={threadRef}
        >
        {chat.msgs.length === 0 && !chat.busy && (
          <div className={styles['chat-welcome']}>
            <h1>{t('Bạn muốn đi đâu?', 'Where would you like to go?')}</h1>
            <p>
              {t(
                'Cho mình biết điểm đến, ngày đi hoặc ngân sách. Mình sẽ tìm tour phù hợp cùng bạn.',
                'Share a destination, dates or budget. I’ll help you find trips that fit.',
              )}
            </p>
            <QuickReplies
              options={SUGGESTIONS.map(([text]) => ({ label: text, value: text }))}
              onPick={chat.send}
              disabled={chat.busy || !chat.client}
            />
          </div>
        )}
        <Thread
          messages={chat.msgs}
          busy={chat.busy}
          activeToolActivityId={chat.activeToolActivityId}
          onSend={chat.send}
          onOpenArtifact={openArtifact}
          selectedArtifactId={selectedArtifactId}
          renderRecovery={
            chat.failedStep
              ? (expired) =>
                  expired ? (
                    <>
                      <button
                        type="button"
                        className="btn btn-primary"
                        onClick={() => onStart(draftText || undefined)}
                      >
                        {t('Tạo phiên mới', 'Start a new session')}
                      </button>
                      {draftText && (
                        <span className={styles['error-note']}>
                          {t(
                            'Phiên mới gửi lại bản nháp, không chuyển lịch sử chat.',
                            'The new session resends the draft without the old chat history.',
                          )}
                        </span>
                      )}
                    </>
                  ) : (
                    <button type="button" className="btn" onClick={chat.retry}>
                      {t('Thử lại', 'Retry')}
                    </button>
                  )
              : undefined
          }
        />

        {chat.phase === 'thinking' && !hasTurnToolActivity && <ToolStatus phase="preparing" />}
        {chat.phase === 'working' && !hasTurnToolActivity && <ToolStatus phase="working" />}
        </div>

        <div
          className={styles.splitter}
          role="separator"
          tabIndex={0}
          aria-orientation="vertical"
          aria-label={t('Điều chỉnh độ rộng khung hội thoại và quyết định', 'Resize chat and decision panes')}
          aria-valuemin={Math.round(splitBounds(layoutRef.current?.getBoundingClientRect().width ?? 0).min * 100)}
          aria-valuemax={Math.round(splitBounds(layoutRef.current?.getBoundingClientRect().width ?? 0).max * 100)}
          aria-valuenow={Math.round(chatSplit * 100)}
          aria-valuetext={`${Math.round(chatSplit * 100)}% chat`}
          onDoubleClick={() => setChatSplit(DEFAULT_CHAT_SPLIT)}
          onKeyDown={(event) => {
            if (event.key === 'ArrowLeft') {
              event.preventDefault();
              nudgeSplit('narrower');
            } else if (event.key === 'ArrowRight') {
              event.preventDefault();
              nudgeSplit('wider');
            } else if (event.key === 'Home') {
              event.preventDefault();
              nudgeSplit('min');
            } else if (event.key === 'End') {
              event.preventDefault();
              nudgeSplit('max');
            }
          }}
          onPointerDown={(event) => {
            if (event.button !== 0) return;
            event.preventDefault();
            activePointer.current = event.pointerId;
            setSplitDragging(true);
            event.currentTarget.setPointerCapture(event.pointerId);
          }}
          onPointerMove={(event) => {
            if (activePointer.current === event.pointerId) setSplitFromPointer(event.clientX);
          }}
          onPointerUp={(event) => {
            if (activePointer.current !== event.pointerId) return;
            activePointer.current = null;
            setSplitDragging(false);
            event.currentTarget.releasePointerCapture(event.pointerId);
          }}
          onLostPointerCapture={() => {
            activePointer.current = null;
            setSplitDragging(false);
          }}
        />

        <div className={`${styles['decision-pane']} ${mobilePane === 'decision' ? '' : styles['pane-hidden']}`}>
          <DecisionWorkspace
            messages={chat.msgs}
            busy={chat.busy}
            clientReady={Boolean(chat.client) && !expired}
            selectedArtifactId={selectedArtifactId}
            onOpenArtifact={openArtifact}
            onUpdateDecisionDraft={chat.updateDecisionDraft}
            onRunDecision={chat.runDecision}
            onRelax={(field) => {
              setMobilePane('chat');
              chat.relax(field);
            }}
            onSend={sendFromWorkspace}
            isSavedTour={isSavedTour}
            onToggleSavedTour={onToggleSavedTour}
          />
        </div>

        <div className={styles['composer-dock']}>
          <Composer
            busy={chat.busy || !chat.client || expired}
            canStop={chat.phase === 'working'}
            onSend={sendFromWorkspace}
            onStop={chat.stop}
          />
        </div>
      </div>
    </div>
  );
}
