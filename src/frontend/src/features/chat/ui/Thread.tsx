import { AnimatePresence, motion } from 'framer-motion';
import type { CurrentRequirement } from '../../../shared/api';
import { usePreferences } from '../../../shared/preferences';
import { conditionText, fieldLabel } from '../lib/format';
import type { ChatMsg } from '../model/types';
import { rise } from './motion';
import { ResultCards } from './ResultCards';
import styles from './chat.module.css';

function CriteriaPanel({
  requirement,
  busy,
  onCompare,
  compareLabel,
}: {
  requirement: CurrentRequirement;
  busy: boolean;
  onCompare: () => void;
  compareLabel: string;
}) {
  const { t } = usePreferences();
  return (
    <motion.section
      {...rise}
      className={styles.criteria}
      aria-label={t('Điều kiện đã hiểu', 'Understood criteria')}
    >
      <div className={styles['criteria-head']}>
        <h2>{t('Đã hiểu như sau', 'Understood as')}</h2>
      </div>
      {requirement.missing.length > 0 && (
        <p className={styles['criteria-missing']}>
          {t('Còn thiếu:', 'Still missing:')} {requirement.missing.join(', ')}
        </p>
      )}
      {requirement.conditions.length > 0 ? (
        <dl className={styles['criteria-list']}>
          {requirement.conditions.map((condition) => (
            <div className={styles['criteria-row']} key={condition.id}>
              <dt className={styles['criteria-field']}>{fieldLabel(condition.field, t)}</dt>
              <dd className={styles['criteria-value']}>
                {conditionText(condition.operator, condition.value, t)}
              </dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="muted" style={{ marginTop: 10 }}>
          {t('Chưa trích xuất được điều kiện.', 'No criteria extracted yet.')}
        </p>
      )}
      <div className={styles['criteria-actions']}>
        <button type="button" className="btn btn-primary" disabled={busy} onClick={onCompare}>
          {compareLabel}
        </button>
      </div>
    </motion.section>
  );
}

export function Thread({
  messages,
  busy,
  onCompare,
  onRelax,
  onUndo,
  canUndo,
  compareLabel,
}: {
  messages: ChatMsg[];
  busy: boolean;
  onCompare: () => void;
  onRelax: (field: string) => void;
  onUndo: () => void;
  canUndo: boolean;
  compareLabel: string;
}) {
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
                <motion.p key={message.id} {...rise} className={styles['msg-assistant']}>
                  {message.text}
                </motion.p>
              );
            case 'interpretation':
              return (
                <motion.div key={message.id} {...rise}>
                  <CriteriaPanel
                    requirement={message.requirement}
                    busy={busy}
                    onCompare={onCompare}
                    compareLabel={compareLabel}
                  />
                </motion.div>
              );
            case 'comparison':
              return (
                <motion.div key={message.id} {...rise}>
                  <ResultCards
                    comparison={message.comparison}
                    dropped={message.dropped}
                    canUndo={canUndo}
                    busy={busy}
                    onRelax={onRelax}
                    onUndo={onUndo}
                  />
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
