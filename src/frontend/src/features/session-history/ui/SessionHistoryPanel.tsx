import { useId, useState, type MouseEvent, type ReactNode } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { usePreferences } from '../../../shared/preferences';
import { displaySessionTitle } from '../../../shared/lib';
import { Dialog, Icon } from '../../../shared/ui';
import type { AuthProfile, LocalSession } from '../model';
import { SessionHistory } from './SessionHistory';
import { SessionSidebar } from './SessionSidebar';

type AppLink = (url: string) => (event: MouseEvent<HTMLAnchorElement>) => void;

export function SessionHistoryPanel({
  sessions,
  currentId,
  routePath,
  desktopVisible,
  profile,
  mobileOpen,
  onMobileClose,
  onStart,
  sidebarCollapsed,
  sidebarWidth,
  onSidebarWidthChange,
  onSidebarToggle,
  onLink,
  onUpdate,
  onRemove,
  controls,
  railControls,
}: {
  sessions: LocalSession[];
  currentId?: string;
  routePath: string;
  desktopVisible: boolean;
  profile: AuthProfile | null;
  mobileOpen: boolean;
  onMobileClose: () => void;
  onStart: () => void;
  sidebarCollapsed: boolean;
  sidebarWidth: number;
  onSidebarWidthChange: (width: number) => void;
  onSidebarToggle: () => void;
  onLink: AppLink;
  onUpdate: (id: string, changes: Partial<LocalSession>) => void;
  onRemove: (session: LocalSession) => void;
  /** Locale/theme controls owned by the shell; the panel only positions them. */
  controls: ReactNode;
  railControls: ReactNode;
}) {
  const [filter, setFilter] = useState('');
  const [rename, setRename] = useState<LocalSession | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [remove, setRemove] = useState<LocalSession | null>(null);
  const searchId = useId();
  const { t } = usePreferences();
  const reduceMotion = useReducedMotion();
  const closeLabel = t('Đóng hộp thoại', 'Close dialog');
  const fallbackName = t('Chuyến đi mới', 'New trip');
  const accountName = profile?.name?.trim() || t('Phiên ẩn danh', 'Anonymous session');
  const showHistory = routePath === '/' || routePath === '/tours';

  function history(suffix: string) {
    return (
      <SessionHistory
        sessions={sessions}
        currentId={currentId}
        routePath={routePath}
        filter={filter}
        suffix={suffix}
        searchId={searchId}
        onFilterChange={setFilter}
        onLink={onLink}
        onPin={(session) => onUpdate(session.id, { pinned: !session.pinned })}
        onRename={(session) => {
          setRename(session);
          setRenameValue(session.title);
        }}
      />
    );
  }

  function account() {
    return (
      <>
        <span className="sidebar-account">
          <span className="sidebar-avatar" aria-hidden="true">
            {accountName.charAt(0).toLocaleUpperCase()}
          </span>
          <span className="sidebar-account-text">
            <strong>{accountName}</strong>
            <small>{t('Lưu trên trình duyệt', 'Saved on this browser')}</small>
          </span>
        </span>
        <span className="sidebar-controls">{controls}</span>
      </>
    );
  }

  const supportLink = (
    <a className="sidebar-nav-link" href="/support" onClick={onLink('/support')}>
      <Icon name="help" size={17} />
      <span>{t('Hỗ trợ', 'Help')}</span>
    </a>
  );

  return (
    <>
      {showHistory && desktopVisible && (
        <SessionSidebar
          collapsed={sidebarCollapsed}
          width={sidebarWidth}
          onWidthChange={onSidebarWidthChange}
          onToggle={onSidebarToggle}
          onStart={onStart}
          onHome={onLink('/')}
          footer={account()}
          railFooter={railControls}
          supportLink={supportLink}
        >
          {history('desktop')}
        </SessionSidebar>
      )}
      <Dialog
        open={mobileOpen && showHistory}
        onClose={onMobileClose}
        title={t('Lịch sử phiên', 'Session history')}
        closeLabel={closeLabel}
        variant="sidebar"
        footer={<div className="session-account-foot">{account()}</div>}
      >
        <motion.button
          type="button"
          className="sidebar-drawer-new"
          onClick={onStart}
          whileHover={reduceMotion ? undefined : { y: -1 }}
          whileTap={reduceMotion ? undefined : { scale: 0.985 }}
        >
          <Icon name="plus" size={17} />
          <span>{t('Tìm tour mới', 'New search')}</span>
        </motion.button>
        {history('mobile')}
      </Dialog>
      <Dialog
        open={!!rename}
        onClose={() => setRename(null)}
        title={t('Đổi tên phiên', 'Rename session')}
        closeLabel={closeLabel}
      >
        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (rename) onUpdate(rename.id, { title: renameValue.trim() });
            setRename(null);
          }}
        >
          <label className="field">
            {t('Tên phiên', 'Session name')}
            <input
              required
              autoFocus
              maxLength={100}
              value={renameValue}
              onChange={(event) => setRenameValue(event.target.value)}
            />
          </label>
          <div className="dialog-actions">
            <button className="btn" type="button" onClick={() => setRename(null)}>
              {t('Huỷ', 'Cancel')}
            </button>
            <button className="btn btn-primary" type="submit">
              {t('Lưu tên', 'Save name')}
            </button>
            {rename && (
              <button
                className="text-action danger-action"
                type="button"
                onClick={() => {
                  setRemove(rename);
                  setRename(null);
                }}
              >
                {t('Xóa khỏi lịch sử', 'Remove from history')}
              </button>
            )}
          </div>
        </form>
      </Dialog>
      <Dialog
        open={!!remove}
        onClose={() => setRemove(null)}
        title={t('Xóa khỏi lịch sử?', 'Remove from history?')}
        closeLabel={closeLabel}
      >
        <p>
          {t('Xóa bản lưu trên trình duyệt của phiên', 'Remove this browser’s saved session')}{' '}
          <strong>{displaySessionTitle(remove?.title, fallbackName)}</strong>.{' '}
          {t(
            'Tác vụ đang xử lý trên dịch vụ không bị hủy.',
            'Running service tasks will continue.',
          )}
        </p>
        <button
          className="btn btn-danger"
          onClick={() => {
            if (remove) onRemove(remove);
            setRemove(null);
          }}
        >
          {t('Xóa bản lưu', 'Remove saved session')}
        </button>
      </Dialog>
    </>
  );
}
