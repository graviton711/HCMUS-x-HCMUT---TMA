import { useEffect, useRef } from 'react';
import type { LocalSession } from '../../../features/session-history';
import { Composer, QuickReplies, Thread, ToolStatus } from '../../../features/chat';
import type { CurrentComparison } from '../../../shared/api';
import { usePreferences } from '../../../shared/preferences';
import { useChat } from '../model/useChat';
import styles from './ChatPage.module.css';

const SUGGESTIONS: [string, string][] = [
  ['Đà Lạt 3 ngày, đi từ TP.HCM, tối đa 8 triệu mỗi người', 'điểm đến · ngân sách'],
  ['Tour Tết từ Hải Phòng đi Đà Nẵng 4 ngày', 'điểm đến · lịch khởi hành'],
  ['Phú Quốc 4 ngày đi từ Hà Nội, đi bằng máy bay', 'điểm đến · phương tiện'],
];

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
  const autoSent = useRef(false);

  useEffect(() => {
    const thread = threadRef.current;
    if (!thread) return;
    const canMatchMedia = typeof window.matchMedia === 'function';
    const reduced = canMatchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (canMatchMedia && window.matchMedia('(max-width: 1000px)').matches) {
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
  }, [chat.msgs.length, chat.phase]);

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

  const hasResult = chat.msgs.some((msg) => msg.kind === 'comparison');
  const hasTurnToolActivity = Boolean(chat.activeToolActivityId);
  const expired = chat.sessionExpired;
  const draftText = session.draft.text.trim();

  return (
    <div className={`${styles.workspace} ${hasResult ? styles['workspace-wide'] : ''}`}>
      <div className={styles['thread-scroll']} ref={threadRef}>
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
          onRelax={chat.relax}
          isSavedTour={isSavedTour}
          onToggleSavedTour={onToggleSavedTour}
          onUpdateDecisionDraft={chat.updateDecisionDraft}
          onRunDecision={chat.runDecision}
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

      <div className={styles['composer-dock']}>
        <Composer
          busy={chat.busy || !chat.client || expired}
          canStop={chat.phase === 'working'}
          onSend={chat.send}
          onStop={chat.stop}
        />
      </div>
    </div>
  );
}
