import { AnimatePresence, motion } from 'framer-motion';
import { usePreferences } from '../../../shared/preferences';
import { collapse } from './motion';
import styles from './chat.module.css';

export function ToolStatus({ working }: { working: boolean }) {
  const { t } = usePreferences();
  if (!working) return null;

  return (
    <AnimatePresence>
      <motion.div
        {...collapse}
        className={styles['tool-status']}
        role="status"
        aria-label={t('Tiến trình tìm tour', 'Search progress')}
      >
        <span className={`${styles.dot} ${styles['dot-active']}`} aria-hidden="true" />
        <span>{t('Đang trao đổi với tư vấn chuyến đi…', 'Travel agent is working…')}</span>
      </motion.div>
    </AnimatePresence>
  );
}
