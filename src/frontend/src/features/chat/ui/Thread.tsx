import { AnimatePresence, motion } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { usePreferences } from '../../../shared/preferences';
import type { ChatMsg } from '../model/types';
import { QuickReplies } from './QuickReplies';
import { rise } from './motion';
import { ResultCards } from './ResultCards';
import styles from './chat.module.css';

const TOOL_LABEL: Record<string, [string, string]> = {
  ask_choice: ['Làm rõ lựa chọn', 'Clarify a choice'],
  catalog_facets: ['Kiểm tra lựa chọn có trong dữ liệu', 'Check catalog options'],
  query_tours: ['Đối chiếu tour theo điều kiện', 'Filter tours by requirements'],
  tour_detail: ['Đọc chi tiết và nguồn dữ kiện', 'Read tour details and evidence'],
  score_soft: ['Đánh giá mức độ phù hợp', 'Assess preference fit'],
  relax_criterion: ['Nới điều kiện và tìm lại', 'Relax a requirement and search again'],
  clarify_date: ['Kiểm tra ngày âm lịch', 'Resolve lunar date'],
};

type ToolStep = Extract<ChatMsg, { kind: 'tool_activity' }>['tools'][number];

function groupToolSteps(tools: ToolStep[]) {
  const groups = new Map<string, { tool: ToolStep; count: number; status: ToolStep['status'] }>();
  for (const tool of tools) {
    const message = tool.message?.trim() ?? '';
    const key = `${tool.name}\u0000${message}`;
    const current = groups.get(key);
    if (!current) {
      groups.set(key, { tool, count: 1, status: tool.status });
      continue;
    }
    current.count += 1;
    if (tool.status === 'running' || (tool.status === 'error' && current.status === 'completed')) {
      current.status = tool.status;
    }
  }
  return [...groups.values()];
}

export function Thread({
  messages,
  busy,
  onSend,
  onRelax,
}: {
  messages: ChatMsg[];
  busy: boolean;
  onSend: (text: string) => void;
  onRelax: (field: string) => void;
}) {
  const { t } = usePreferences();
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
            case 'tool_activity':
              return (
                <motion.ul
                  key={message.id}
                  {...rise}
                  className={styles['tool-steps']}
                  aria-live="polite"
                  aria-relevant="additions text"
                >
                  {groupToolSteps(message.tools).map(({ tool, count, status }) => (
                    <li key={`${tool.name}:${tool.message ?? ''}`} data-state={status}>
                      <span
                        className={`${styles.dot} ${
                          status === 'running'
                            ? styles['dot-active']
                            : status === 'error'
                              ? styles['dot-error']
                              : styles['dot-done']
                        }`}
                        aria-hidden="true"
                      />
                      <span>
                        {tool.message ||
                          t(
                            ...(TOOL_LABEL[tool.name] ?? [
                              'Đã tra cứu dữ kiện',
                              'Checked evidence',
                            ]),
                          )}
                        {count > 1 && (
                          <span
                            className={styles['tool-count']}
                            aria-label={t(`${count} lần`, `${count} times`)}
                          >
                            ×{count}
                          </span>
                        )}
                        {status === 'running' && (
                          <span className={styles['tool-state']}>
                            {t(' · đang chạy', ' · working')}
                          </span>
                        )}
                        {status === 'error' && (
                          <span className={styles['tool-state']}>
                            {t(' · chưa hoàn tất', ' · did not complete')}
                          </span>
                        )}
                      </span>
                    </li>
                  ))}
                </motion.ul>
              );
            case 'comparison':
              return (
                <motion.div key={message.id} {...rise}>
                  <ResultCards comparison={message.comparison} busy={busy} onRelax={onRelax} />
                </motion.div>
              );
            case 'error':
              return (
                <motion.div key={message.id} {...rise} className={styles['msg-error']} role="alert">
                  {message.text}
                </motion.div>
              );
          }
        })}
      </AnimatePresence>
    </div>
  );
}
