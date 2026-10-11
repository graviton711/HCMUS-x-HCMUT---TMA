import { AnimatePresence, motion } from 'framer-motion';
import { usePreferences } from '../../../shared/preferences';
import type { ChatStep } from '../model/types';
import { collapse } from './motion';
import styles from './chat.module.css';

const STEP_LABEL: Record<ChatStep['id'], [string, string]> = {
  interpret: ['Diễn giải nhu cầu', 'Interpreting requirements'],
  compare: ['Đối chiếu tour', 'Comparing tours'],
};

const DOT: Record<ChatStep['state'], string> = {
  pending: styles.dot,
  active: `${styles.dot} ${styles['dot-active']}`,
  done: `${styles.dot} ${styles['dot-done']}`,
  error: `${styles.dot} ${styles['dot-error']}`,
};

export function ToolStatus({ steps, working }: { steps: ChatStep[]; working: boolean }) {
  const { t } = usePreferences();
  if (!working && steps.every((step) => step.state !== 'active')) return null;
  const active = steps.some((step) => step.state === 'active');

  return (
    <AnimatePresence>
      <motion.div
        {...collapse}
        className={styles['tool-status']}
        role="status"
        aria-label={t('Tiến trình tìm tour', 'Search progress')}
      >
        {!active ? (
          <>
            <span className={`${styles.dot} ${styles['dot-active']}`} aria-hidden="true" />
            <span>{t('Đang hiểu yêu cầu…', 'Understanding…')}</span>
          </>
        ) : (
          <ol className={styles['tool-steps']}>
            {steps.map((step) => (
              <li key={step.id} data-state={step.state}>
                <span className={DOT[step.state]} aria-hidden="true" />
                <span>{t(...STEP_LABEL[step.id])}</span>
              </li>
            ))}
          </ol>
        )}
      </motion.div>
    </AnimatePresence>
  );
}
