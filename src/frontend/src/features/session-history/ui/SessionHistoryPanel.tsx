import { useId, useState, type MouseEvent } from 'react';
import { usePreferences } from '../../../shared/preferences';
import { Dialog } from '../../../shared/ui';
import type { AuthProfile, LocalSession } from '../model';
import { SessionHistory } from './SessionHistory';
import { SessionSidebar } from './SessionSidebar';

type AppLink = (url: string) => (event: MouseEvent<HTMLAnchorElement>) => void;

export function SessionHistoryPanel({
  sessions,
  currentId,
  routePath,
  profile,
  mobileOpen,
  onMobileClose,
  onStart,
  onLink,
  onUpdate,
  onRemove,
}: {
  sessions: LocalSession[];
  currentId?: string;
  routePath: string;
  profile: AuthProfile | null;
  mobileOpen: boolean;
  onMobileClose: () => void;
  onStart: () => void;
  onLink: AppLink;
  onUpdate: (id: string, changes: Partial<LocalSession>) => void;
  onRemove: (session: LocalSession) => void;
}) {
  const [filter, setFilter] = useState('');
  const [rename, setRename] = useState<LocalSession | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [remove, setRemove] = useState<LocalSession | null>(null);
  const searchId = useId();
  const { t } = usePreferences();
  const closeLabel = t('Đóng hộp thoại', 'Close dialog');

  function history(suffix: string) {
    return (
      <SessionHistory
        sessions={sessions}
        currentId={currentId}
        routePath={routePath}
        profile={profile}
        filter={filter}
        suffix={suffix}
        searchId={searchId}
        onFilterChange={setFilter}
        onStart={onStart}
        onLink={onLink}
        onPin={(session) => onUpdate(session.id, { pinned: !session.pinned })}
        onRename={(session) => {
          setRename(session);
          setRenameValue(session.title);
        }}
        onRemove={setRemove}
      />
    );
  }

  return (
    <>
      {routePath === '/tours' && <SessionSidebar>{history('desktop')}</SessionSidebar>}
      <Dialog
        open={mobileOpen}
        onClose={onMobileClose}
        title={t('Lịch sử phiên', 'Session history')}
        closeLabel={closeLabel}
        variant="sidebar"
      >
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
          <button className="btn btn-primary">{t('Lưu tên', 'Save name')}</button>
        </form>
      </Dialog>
      <Dialog
        open={!!remove}
        onClose={() => setRemove(null)}
        title={t('Xóa khỏi lịch sử?', 'Remove from history?')}
        closeLabel={closeLabel}
      >
        <p>
          {t('Xóa bản lưu trên trình duyệt của phiên', 'Remove this browser’s saved session')} “
          {remove?.title || t('Chuyến đi mới', 'New trip')}”.{' '}
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
