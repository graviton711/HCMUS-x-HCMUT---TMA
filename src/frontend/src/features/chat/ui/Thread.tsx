import { AnimatePresence, motion } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { ReactNode } from 'react';
import type { CurrentComparison, CurrentRequirement } from '../../../shared/api';
import { usePreferences } from '../../../shared/preferences';
import type { ChatMsg } from '../model/types';
import { QuickReplies } from './QuickReplies';
import { rise } from './motion';
import { ResultCards } from './ResultCards';
import { DecisionBrief } from './DecisionBrief';
import styles from './chat.module.css';

const TOOL_LABEL: Record<string, [string, string]> = {
  ask_choice: ['Làm rõ lựa chọn', 'Clarify a choice'],
  catalog_facets: ['Kiểm tra lựa chọn có trong dữ liệu', 'Check catalog options'],
  draft_requirement: ['Chuẩn bị bản tiêu chí để bạn xem', 'Prepare criteria for review'],
  query_tours: ['Đối chiếu tour theo điều kiện', 'Filter tours by requirements'],
  tour_detail: ['Đọc chi tiết và nguồn dữ kiện', 'Read tour details and evidence'],
  score_soft: ['Đánh giá mức độ phù hợp', 'Assess preference fit'],
  relax_criterion: ['Nới điều kiện và tìm lại', 'Relax a requirement and search again'],
  clarify_date: ['Kiểm tra ngày âm lịch', 'Resolve lunar date'],
};

export function Thread({
  messages,
  busy,
  activeToolActivityId,
  onSend,
  onRelax,
  renderRecovery,
  isSavedTour,
  onToggleSavedTour,
  onUpdateDecisionDraft,
  onRunDecision,
}: {
  messages: ChatMsg[];
  busy: boolean;
  activeToolActivityId?: string | null;
  onSend: (text: string) => void;
  onRelax: (field: string) => void;
  renderRecovery?: (expired: boolean) => ReactNode;
  isSavedTour?: (tourId: string, offerId: string) => boolean;
  onToggleSavedTour?: (comparison: CurrentComparison, tourId: string, offerId: string) => void;
  onUpdateDecisionDraft?: (id: string, requirement: CurrentRequirement) => void;
  onRunDecision?: (id: string, requirement: CurrentRequirement) => void;
}) {
  const { t } = usePreferences();
  const latestActivityId = [...messages]
    .reverse()
    .find((message) => message.kind === 'tool_activity')?.id;
  const currentActivityId = activeToolActivityId === undefined
    ? latestActivityId
    : activeToolActivityId;
  return (
    <div className={styles.thread} aria-live="polite">
      <AnimatePresence initial={false}>
        {messages.map((message) => {
          switch (message.kind) {
            case 'user':
              return (
                <motion.div key={message.id} {...rise} className={styles['msg-user']}>
                  {message.text}
                </motion.div>
              );
            case 'assistant':
              return (
                <motion.div key={message.id} {...rise} className={styles['msg-assistant']}>
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    skipHtml
                    components={{
                      a: ({ href, children }) =>
                        href ? (
                          <a href={href} target="_blank" rel="noopener noreferrer">
                            {children}
                          </a>
                        ) : (
                          <span>{children}</span>
                        ),
                    }}
                  >
                    {message.text}
                  </ReactMarkdown>
                </motion.div>
              );
            case 'notice':
              return (
                <motion.p key={message.id} {...rise} className={styles['msg-notice']}>
                  {message.text}
                </motion.p>
              );
            case 'choice':
              return (
                <motion.section key={message.id} {...rise} className={styles.choice}>
                  <p className={styles['choice-question']}>{message.choice.question}</p>
                  <QuickReplies options={message.choice.options} onPick={onSend} disabled={busy} />
                  {message.choice.allow_custom && (
                    <p className={styles['choice-hint']}>
                      {t('Hoặc nhập lựa chọn khác bên dưới.', 'Or type a different answer below.')}
                    </p>
                  )}
                </motion.section>
              );
            case 'tool_activity': {
              if (message.tools.length === 0) return null;

              const activeTool = [...message.tools]
                .reverse()
                .find((tool) => tool.status === 'running');
              const failedSteps = message.tools.filter((tool) => tool.status === 'error').length;
              const cancelledSteps = message.tools.filter((tool) => tool.status === 'cancelled').length;
              const isCurrentActivity = busy && message.id === currentActivityId;
              const state = isCurrentActivity
                ? 'running'
                : failedSteps > 0
                  ? 'error'
                  : cancelledSteps > 0
                    ? 'cancelled'
                    : 'completed';
              const summary = isCurrentActivity
                ? activeTool
                  ? activeTool.message ||
                    t(
                      ...(TOOL_LABEL[activeTool.name] ?? [
                        'Đang tra cứu dữ kiện',
                        'Checking evidence',
                      ]),
                    )
                  : t('Đang tổng hợp kết quả', 'Putting the results together')
                : cancelledSteps > 0
                  ? t('Đã dừng lượt tìm', 'Search stopped')
                  : failedSteps > 0
                  ? t(
                      `Có ${failedSteps} bước tra cứu chưa hoàn tất`,
                      `${failedSteps} search step${failedSteps === 1 ? '' : 's'} did not complete`,
                    )
                  : t(
                      `Đã kiểm tra ${message.tools.length} bước`,
                      `Checked ${message.tools.length} steps`,
                    );

              return (
                <motion.div key={message.id} {...rise} className={styles['tool-progress']}>
                  <details className={styles['tool-progress-details']} data-state={state}>
                    <summary className={styles['tool-progress-summary']}>
                      <span
                        className={styles['activity-copy']}
                        data-active={isCurrentActivity || undefined}
                      >
                        {summary}
                      </span>
                      <span className={styles['activity-chevron']} aria-hidden="true" />
                    </summary>
                    <ol
                      className={styles['tool-steps']}
                      aria-label={t('Các bước đã thực hiện', 'Steps performed')}
                    >
                      {message.tools.map((tool) => (
                        <li key={tool.id} data-state={tool.status}>
                          <span
                            className={`${styles.dot} ${
                              tool.status === 'running'
                                ? styles['dot-active']
                                : tool.status === 'error'
                                  ? styles['dot-error']
                                  : tool.status === 'cancelled'
                                    ? styles['dot-cancelled']
                                  : styles['dot-done']
                            }`}
                            aria-hidden="true"
                          />
                          <span className={styles['tool-step-message']}>
                            {tool.message ||
                              t(
                                ...(TOOL_LABEL[tool.name] ?? [
                                  'Đã tra cứu dữ kiện',
                                  'Checked evidence',
                                ]),
                              )}
                          </span>
                          <span className={styles['tool-state']}>
                            {tool.status === 'running'
                              ? t('Đang chạy', 'Working')
                              : tool.status === 'error'
                                ? t('Chưa hoàn tất', 'Incomplete')
                                : tool.status === 'cancelled'
                                  ? t('Đã dừng', 'Stopped')
                                  : t('Hoàn tất', 'Done')}
                          </span>
                        </li>
                      ))}
                    </ol>
                  </details>
                </motion.div>
              );
            }
            case 'comparison':
              return (
                <motion.div key={message.id} {...rise}>
                  <ResultCards
                    comparison={message.comparison}
                    busy={busy}
                    onRelax={onRelax}
                    isSavedTour={isSavedTour}
                    onToggleSavedTour={onToggleSavedTour}
                    onAsk={onSend}
                  />
                </motion.div>
              );
            case 'decision_draft':
              return (
                <motion.div key={message.id} {...rise}>
                  <DecisionBrief
                    message={message}
                    busy={busy}
                    onChange={(requirement) => onUpdateDecisionDraft?.(message.id, requirement)}
                    onRun={(requirement) => onRunDecision?.(message.id, requirement)}
                  />
                </motion.div>
              );
            case 'error':
              return (
                <motion.div
                  key={message.id}
                  {...rise}
                  className={styles['msg-error']}
                  data-expired={message.expired || undefined}
                  role="alert"
                >
                  <span className={styles['error-copy']}>
                    {message.expired && (
                      <strong className={styles['error-title']}>
                        {t('Phiên hết hạn.', 'Session expired.')}
                      </strong>
                    )}
                    <span className={styles['error-description']}>
                      {message.expired
                        ? t('Bản nháp vẫn còn.', 'Your draft is still here.')
                        : message.text}
                    </span>
                  </span>
                  {renderRecovery && message.id === messages[messages.length - 1]?.id && (
                    <div className={styles['error-actions']}>
                      {renderRecovery(Boolean(message.expired))}
                    </div>
                  )}
                </motion.div>
              );
          }
        })}
      </AnimatePresence>
    </div>
  );
}
