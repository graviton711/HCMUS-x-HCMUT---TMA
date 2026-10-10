import { usePreferences } from '../../../shared/preferences';
import { Icon } from '../../../shared/ui';
import type { AuthProfile, LocalSession } from '../../../features/session-history';
import { CurrentWorkspace } from './CurrentWorkspace';
import styles from './WorkspacePage.module.css';

export function WorkspacePage({
  session,
  profile,
  onStart,
  onChangeSession,
  onOpenHistory,
  historyOpen,
}: {
  session: LocalSession | null;
  profile: AuthProfile | null;
  onStart: () => void;
  onChangeSession: (id: string, changes: Partial<LocalSession>) => void;
  onOpenHistory: () => void;
  historyOpen: boolean;
}) {
  const { t } = usePreferences();
  const sessionName = session?.title || t('Chuyến đi mới', 'New trip');

  return (
    <div className={styles.root}>
      <div className="workspace-toolbar">
        <button
          className="icon-button history-toggle"
          aria-label={t('Ẩn / hiện lịch sử phiên', 'Toggle session history')}
          aria-expanded={historyOpen}
          onClick={onOpenHistory}
        >
          <Icon name="menu" />
        </button>
        <span>{session ? sessionName : t('Tìm tour', 'Find tours')}</span>
        <small>{profile ? profile.name : t('Phiên ẩn danh', 'Anonymous session')}</small>
      </div>
      {session ? (
        <CurrentWorkspace
          session={session}
          onChangeSession={(changes) => onChangeSession(session.id, changes)}
        />
      ) : (
        <section className="empty-state">
          <h1>{t('Bắt đầu chuyến đi của bạn.', 'Start your trip.')}</h1>
          <p>
            {t(
              'Tạo một phiên để lưu nhu cầu và các lượt so sánh.',
              'Create a session for your requirements and comparisons.',
            )}
          </p>
          <button className="btn btn-primary" onClick={onStart}>
            {t('Phiên mới', 'New session')}
            <Icon name="plus" />
          </button>
        </section>
      )}
    </div>
  );
}
