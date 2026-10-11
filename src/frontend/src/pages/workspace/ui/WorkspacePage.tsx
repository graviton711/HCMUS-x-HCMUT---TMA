import type { LocalSession } from '../../../features/session-history';
import { usePreferences } from '../../../shared/preferences';
import { Icon } from '../../../shared/ui';
import { CurrentWorkspace } from './CurrentWorkspace';
import styles from './WorkspacePage.module.css';

export function WorkspacePage({
  session,
  onStart,
  onChangeSession,
}: {
  session: LocalSession | null;
  onStart: (initialText?: string) => void;
  onChangeSession: (id: string, changes: Partial<LocalSession>) => void;
}) {
  const { t } = usePreferences();

  return (
    <div className={styles.root}>
      {session ? (
        <CurrentWorkspace
          session={session}
          onStart={onStart}
          onChangeSession={(changes) => onChangeSession(session.id, changes)}
        />
      ) : (
        <section className="empty-state">
          <h1>{t('Bắt đầu chuyến đi của bạn.', 'Start your trip.')}</h1>
          <p>
            {t(
              'Tạo một phiên để lưu nhu cầu và các lượt so sánh trên trình duyệt này.',
              'Create a session to keep your requirements and comparisons in this browser.',
            )}
          </p>
          <div className="empty-state-actions">
            <button className="btn btn-primary" onClick={() => onStart()}>
              {t('Tìm tour mới', 'New search')}
              <Icon name="arrow" size={17} />
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
