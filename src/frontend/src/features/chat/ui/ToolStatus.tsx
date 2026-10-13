import { AnimatePresence, motion } from 'framer-motion';
import { usePreferences } from '../../../shared/preferences';
import { collapse } from './motion';
import styles from './chat.module.css';

export function ToolStatus({ phase }: { phase: 'preparing' | 'working' }) {
  const { t } = usePreferences();

  return (
    <AnimatePresence>
      <motion.div {...collapse} className={styles['tool-status']} data-phase={phase} role="status">
        <span className={styles['activity-copy']} data-active="true">
          {phase === 'preparing'
            ? t('Đang chuẩn bị phiên tư vấn', 'Preparing your travel session')
            : t('Đang tìm và đối chiếu tour', 'Searching and matching tours')}
        </span>
      </motion.div>
    </AnimatePresence>
  );
}
