import { useEffect, useRef } from 'react';
import type { LocalSession } from '../../../features/session-history';
import { Composer, QuickReplies, Thread, ToolStatus } from '../../../features/chat';
import { usePreferences } from '../../../shared/preferences';
import { slotPrompt } from '../lib/slots';
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
}: {
  session: LocalSession | null;
  onStart: (initialText?: string) => void;
  onChangeSession: (id: string, changes: Partial<LocalSession>) => void;
}) {
  return session ? (
    <ActiveChat
      key={session.id}
      session={session}
      onStart={onStart}
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
        <span className="eyebrow">{t('Soi tour bằng dữ kiện', 'Evidence-based tour search')}</span>
        <h1>{t('Đi đâu tiếp?', 'Where next?')}</h1>
        <p>
          {t(
            'Mô tả chuyến đi bạn muốn. TourLens đối chiếu từng tour theo cùng bộ tiêu chí, ghi rõ điều kiện nào đạt, thiếu hay chưa xác minh — bạn tự quyết định.',
            'Describe the trip you want. TourLens compares every tour against the same criteria and marks what passes, what is missing and what is unverified — you decide.',
          )}
        </p>
      </header>

      <Composer busy={false} size="large" onSend={(text) => onStart(text)} />

      <dl className={styles['entry-facts']}>
        <div>
          <dt>{t('So sánh', 'Comparison')}</dt>
          <dd>{t('Cùng bộ tiêu chí, không điểm số bí mật', 'Same criteria, no hidden score')}</dd>
        </div>
        <div>
          <dt>{t('Bằng chứng', 'Evidence')}</dt>
          <dd>
            {t(
              'Mỗi dữ kiện kèm nguồn và thời điểm lấy',
              'Every fact has a source and an observation time',
            )}
          </dd>
        </div>
        <div>
          <dt>{t('Thiếu dữ liệu', 'Missing data')}</dt>
          <dd>{t('Ghi rõ "chưa rõ", không tự điền', 'Marked unknown, never invented')}</dd>
        </div>
      </dl>

      <section aria-labelledby="examples-title">
        <h2 className={styles['examples-title']} id="examples-title">
          {t('Ví dụ yêu cầu', 'Example requests')}
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
  );
}

function ActiveChat({
  session,
  onStart,
  onChangeSession,
}: {
  session: LocalSession;
  onStart: (initialText?: string) => void;
  onChangeSession: (changes: Partial<LocalSession>) => void;
}) {
  const { t } = usePreferences();
  const chat = useChat(session, onChangeSession);
  const bottomRef = useRef<HTMLDivElement>(null);
  const autoSent = useRef(false);

  useEffect(() => {
    const anchor = bottomRef.current;
    if (!anchor) return;
    const nearBottom =
      window.innerHeight + window.scrollY > document.body.scrollHeight - 480;
    if (!nearBottom) return;
    const reduced =
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    anchor.scrollIntoView({ block: 'end', behavior: reduced ? 'auto' : 'smooth' });
  }, [chat.msgs.length, chat.phase]);

  // A session created from an example request sends once on mount.
  useEffect(() => {
    if (
      !autoSent.current &&
      chat.client &&
      chat.msgs.length === 0 &&
      !session.requirementId &&
      !session.comparisonId &&
      session.draft.text.trim()
    ) {
      autoSent.current = true;
      chat.send(session.draft.text.trim());
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chat.client, chat.msgs.length]);

  const lastComparison = chat.msgs.map((msg) => msg.kind).lastIndexOf('comparison');
  const lastInterpretation = [...chat.msgs]
    .map((msg, index) => ({ msg, index }))
    .filter(({ msg }) => msg.kind === 'interpretation')
    .pop();
  const pendingSlot =
    lastInterpretation && lastInterpretation.index > lastComparison
      ? lastInterpretation.msg.kind === 'interpretation'
        ? lastInterpretation.msg.requirement.missing[0]
        : undefined
      : undefined;
  const prompt = pendingSlot ? slotPrompt(pendingSlot, chat.catalog) : null;
  const hasResult = chat.msgs.some((msg) => msg.kind === 'comparison');
  const lastError = [...chat.msgs].reverse().find((msg) => msg.kind === 'error');
  const expired = lastError?.kind === 'error' && lastError.expired === true;
  const draftText = session.draft.text.trim();

  return (
    <div className={`${styles.workspace} ${hasResult ? styles['workspace-wide'] : ''}`}>
      <Thread
        messages={chat.msgs}
        busy={chat.busy}
        onCompare={chat.compareNow}
        onRelax={chat.relax}
        onUndo={chat.undo}
        canUndo={chat.canUndo}
        compareLabel={t('Tìm và so sánh tour', 'Find and compare tours')}
      />

      {prompt && (
        <section className={styles.slot} aria-label={t('Câu hỏi còn thiếu', 'Missing detail')}>
          <p className={styles['slot-question']}>{t(...prompt.question)}</p>
          <QuickReplies
            options={prompt.options}
            onPick={(value) => chat.send(value)}
            disabled={chat.busy}
          />
          {prompt.hint && <p className={styles['slot-hint']}>{t(...prompt.hint)}</p>}
        </section>
      )}

      {(chat.phase === 'thinking' || chat.phase === 'working') && (
        <ToolStatus steps={chat.steps} working={chat.phase === 'working'} />
      )}

      {chat.failedStep && !chat.busy && (
        <div className={styles.recovery}>
          {expired && draftText ? (
            <>
              <button type="button" className="btn btn-primary" onClick={() => onStart(draftText)}>
                {t('Tạo phiên mới và tiếp tục', 'Start a new session and continue')}
              </button>
              <button type="button" className="btn" onClick={chat.retry}>
                {t('Thử lại', 'Retry')}
              </button>
            </>
          ) : (
            <button type="button" className="btn" onClick={chat.retry}>
              {t('Thử lại', 'Retry')}
            </button>
          )}
          {expired && (
            <span className={styles['recovery-note']}>
              {t('Bản nháp vẫn còn; không mất nội dung.', 'Your draft is kept; nothing is lost.')}
            </span>
          )}
        </div>
      )}

      <div className={styles['composer-dock']}>
        <Composer busy={chat.busy || !chat.client} onSend={chat.send} />
      </div>
      <div ref={bottomRef} />
    </div>
  );
}
