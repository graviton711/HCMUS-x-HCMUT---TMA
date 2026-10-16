import { AnimatePresence, motion } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { ReactNode } from 'react';
import type { CurrentComparison } from '../../../shared/api';
import { usePreferences } from '../../../shared/preferences';
import type { ChatMsg } from '../model/types';
import { QuickReplies } from './QuickReplies';
import { rise } from './motion';
import styles from './chat.module.css';

const TOOL_LABEL: Record<string, [string, string]> = {
  ask_choice: ['Làm rõ lựa chọn', 'Clarify a choice'],
  catalog_facets: ['Kiểm tra lựa chọn có trong dữ liệu', 'Check catalog options'],
  discover_destinations: ['Lọc điểm đến theo điều kiện', 'Filter destinations by criteria'],
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
  renderRecovery,
  onOpenArtifact,
  selectedArtifactId,
  renderComparisonExtra,
}: {
  messages: ChatMsg[];
  busy: boolean;
  activeToolActivityId?: string | null;
  onSend: (text: string) => void;
  renderRecovery?: (expired: boolean) => ReactNode;
  onOpenArtifact?: (id: string) => void;
  selectedArtifactId?: string | null;
  renderComparisonExtra?: (comparison: CurrentComparison) => ReactNode;
}) {
  const { t } = usePreferences();
  const latestActivityId = [...messages]
    .reverse()
    .find((message) => message.kind === 'tool_activity')?.id;
  const currentActivityId =
    activeToolActivityId === undefined ? latestActivityId : activeToolActivityId;
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
              const failedCalls = message.tools.filter((tool) => tool.status === 'error').length;
              const cancelledSteps = message.tools.filter(
                (tool) => tool.status === 'cancelled',
              ).length;
              const groupedTools = (() => {
                const groups: {
                  name: string;
                  message: string;
                  count: number;
                  worst: (typeof message.tools)[number]['status'];
                }[] = [];
                const rank = (status: string) =>
                  status === 'error' ? 3 : status === 'cancelled' ? 2 : status === 'running' ? 1 : 0;
                for (const tool of message.tools) {
                  const label =
                    tool.message ||
                    t(
                      ...(TOOL_LABEL[tool.name] ?? ['Đã tra cứu dữ kiện', 'Checked evidence']),
                    );
                  const existing = groups.find((group) => group.message === label);
                  if (!existing) {
                    groups.push({ name: tool.name, message: label, count: 1, worst: tool.status });
                  } else {
                    existing.count += 1;
                    if (rank(tool.status) > rank(existing.worst)) existing.worst = tool.status;
                  }
                }
                return groups;
              })();
              const distinctSteps = groupedTools.length;
              const isCurrentActivity = busy && message.id === currentActivityId;
              const state = isCurrentActivity
                ? 'running'
                : message.outcome === 'completed'
                  ? 'completed'
                  : message.outcome === 'cancelled' || cancelledSteps > 0
                    ? 'cancelled'
                    : message.outcome === 'error' || failedCalls > 0
                      ? 'error'
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
                : message.outcome === 'completed'
                  ? failedCalls > 0
                    ? t(
                        `Đã hoàn tất · ${failedCalls} lần gọi chưa thành công`,
                        `Completed · ${failedCalls} tool call${failedCalls === 1 ? '' : 's'} did not succeed`,
                      )
                    : t(
                        `Đã kiểm tra ${distinctSteps} bước${message.tools.length > distinctSteps ? ` · ${message.tools.length} lượt gọi` : ''}`,
                        `Checked ${distinctSteps} steps${message.tools.length > distinctSteps ? ` · ${message.tools.length} calls` : ''}`,
                      )
                  : message.outcome === 'cancelled' || cancelledSteps > 0
                    ? t('Đã dừng lượt tìm', 'Search stopped')
                    : message.outcome === 'error'
                      ? t('Lượt chưa hoàn tất', 'Turn did not complete')
                      : failedCalls > 0
                        ? t(
                            `Có ${failedCalls} lần gọi chưa thành công`,
                            `${failedCalls} tool call${failedCalls === 1 ? '' : 's'} did not succeed`,
                          )
                        : t(
                            `Đã kiểm tra ${distinctSteps} bước${message.tools.length > distinctSteps ? ` · ${message.tools.length} lượt gọi` : ''}`,
                            `Checked ${distinctSteps} steps${message.tools.length > distinctSteps ? ` · ${message.tools.length} calls` : ''}`,
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
                      {groupedTools.map((group) => (
                        <li key={group.message} data-state={group.worst}>
                          <span
                            className={`${styles.dot} ${
                              group.worst === 'running'
                                ? styles['dot-active']
                                : group.worst === 'error'
                                  ? styles['dot-error']
                                  : group.worst === 'cancelled'
                                    ? styles['dot-cancelled']
                                    : styles['dot-done']
                            }`}
                            aria-hidden="true"
                          />
                          <span className={styles['tool-step-message']}>
                            {group.message}
                            {group.count > 1 ? ` ×${group.count}` : ''}
                          </span>
                          <span className={styles['tool-state']}>
                            {group.worst === 'running'
                              ? t('Đang chạy', 'Working')
                              : group.worst === 'error'
                                ? t('Chưa hoàn tất', 'Incomplete')
                                : group.worst === 'cancelled'
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
                <motion.div key={message.id} {...rise} className={styles['decision-link-wrap']}>
                  {renderComparisonExtra?.(message.comparison)}
                  <button
                    type="button"
                    className={styles['decision-link']}
                    aria-pressed={selectedArtifactId === message.id}
                    onClick={() => onOpenArtifact?.(message.id)}
                  >
                    <span className={styles['decision-link-title']}>
                      {t('Mở bảng so sánh', 'Open comparison workspace')}
                    </span>
                    <span className={styles['decision-link-detail']}>
                      {t(
                        `${message.comparison.decision_views?.length ?? 0} góc nhìn · ${message.comparison.candidates_considered} tour đã quét`,
                        `${message.comparison.decision_views?.length ?? 0} views · ${message.comparison.candidates_considered} tours scanned`,
                      )}
                    </span>
                  </button>
                </motion.div>
              );
            case 'decision_draft':
              return (
                <motion.div key={message.id} {...rise} className={styles['decision-link-wrap']}>
                  <button
                    type="button"
                    className={styles['decision-link']}
                    aria-pressed={selectedArtifactId === message.id}
                    onClick={() => onOpenArtifact?.(message.id)}
                  >
                    <span className={styles['decision-link-title']}>
                      {message.status === 'complete'
                        ? t('Mở bản yêu cầu đã so sánh', 'Open compared brief')
                        : t('Mở bản yêu cầu để duyệt', 'Open brief for review')}
                    </span>
                    <span className={styles['decision-link-detail']}>
                      {t(
                        `${message.requirement.conditions.length + (message.requirement.alternatives ?? []).reduce((sum, item) => sum + item.conditions.length, 0)} điều kiện${(message.requirement.alternatives ?? []).length ? ` · ${message.requirement.alternatives!.length} phương án` : ''}`,
                        `${message.requirement.conditions.length + (message.requirement.alternatives ?? []).reduce((sum, item) => sum + item.conditions.length, 0)} criteria${(message.requirement.alternatives ?? []).length ? ` · ${message.requirement.alternatives!.length} options` : ''}`,
                      )}
                    </span>
                  </button>
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
