import { motion, useReducedMotion } from 'framer-motion';
import { usePreferences } from '../../shared/preferences';
import { Icon } from '../../shared/ui';

/**
 * Canvas header. Owns the single sidebar control: collapse on desktop, open the
 * drawer on small screens. It also owns the create action, which belongs to the
 * working surface rather than to navigation.
 */
export function SessionBar({
  title,
  sidebarOpen,
  onToggleSidebar,
  onStart,
  savedCount,
  onOpenSaved,
}: {
  title: string;
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
  onStart: () => void;
  savedCount: number;
  onOpenSaved: () => void;
}) {
  const { t } = usePreferences();
  const reduceMotion = useReducedMotion();
  return (
    <div className="session-bar">
      <button
        type="button"
        className="icon-button"
        aria-label={
          sidebarOpen
            ? t('Thu gọn lịch sử phiên', 'Collapse session history')
            : t('Mở lịch sử phiên', 'Open session history')
        }
        aria-expanded={sidebarOpen}
        title={t('Lịch sử phiên', 'Session history')}
        onClick={onToggleSidebar}
      >
        <Icon name="panel" size={18} />
      </button>
      <p className="session-title truncate" title={title}>
        {title}
      </p>
      <button
        type="button"
        className="session-saved"
        aria-haspopup="dialog"
        aria-label={t(`Tour đã lưu (${savedCount})`, `Saved tours (${savedCount})`)}
        title={t('Tour đã lưu', 'Saved tours')}
        onClick={onOpenSaved}
      >
        <Icon name="bookmark" size={16} />
        <span className="session-saved-label">{t('Đã lưu', 'Saved')}</span>
        {savedCount > 0 && <span className="session-saved-count">{savedCount}</span>}
      </button>
      <motion.button
        type="button"
        className="session-new"
        aria-label={t('Tìm tour mới', 'Start a new search')}
        onClick={onStart}
        whileHover={reduceMotion ? undefined : { y: -1 }}
        whileTap={reduceMotion ? undefined : { scale: 0.96 }}
      >
        <Icon name="plus" size={15} />
        <span>{t('Tìm tour mới', 'New search')}</span>
      </motion.button>
    </div>
  );
}
