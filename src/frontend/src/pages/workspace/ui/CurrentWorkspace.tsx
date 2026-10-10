import type { LocalSession } from '../../../features/session-history';
import { usePreferences } from '../../../shared/preferences';
import { useCurrentWorkspace } from '../model/useCurrentWorkspace';
import { ComparisonView } from './ComparisonView';
import { RequirementForm } from './RequirementForm';
import { RequirementView } from './RequirementView';
import styles from './CurrentWorkspace.module.css';

export function CurrentWorkspace({
  session,
  onChangeSession,
}: {
  session: LocalSession;
  onChangeSession: (changes: Partial<LocalSession>) => void;
}) {
  const { t } = usePreferences();
  const {
    catalog,
    requirement,
    comparison,
    busy,
    error,
    stale,
    retry,
    writeDraft,
    interpret,
    search,
  } = useCurrentWorkspace(session, onChangeSession);
  const destinations = catalog?.destinations ?? [];

  return (
    <section className={styles.root} aria-labelledby="current-workspace-title">
      <header className="current-heading">
        <span className="eyebrow">{t('BACKEND HIỆN TẠI', 'CURRENT BACKEND')}</span>
        <h1 id="current-workspace-title">
          {t(
            'Chọn điều quan trọng. Đối chiếu bằng dữ kiện.',
            'Compare tours using the facts available.',
          )}
        </h1>
        <p>
          {t(
            'Mỗi lần tìm được diễn giải riêng. Dữ kiện thiếu, cũ hoặc chưa xác minh sẽ không được xem là đạt.',
            'Each search is interpreted independently. Missing, stale or unverified facts are not treated as a pass.',
          )}
        </p>
      </header>

      {error && (
        <div className="notice error" role="alert">
          <p>{error}</p>
          {!catalog && (
            <button className="btn" disabled={busy} onClick={retry}>
              {t('Thử kết nối lại', 'Try connecting again')}
            </button>
          )}
        </div>
      )}
      {stale && (
        <p className="notice" role="status">
          {t(
            'Nhu cầu đã đổi; hãy diễn giải lại trước khi tìm.',
            'Your criteria changed; interpret them again before searching.',
          )}
        </p>
      )}

      <RequirementForm
        session={session}
        destinations={destinations}
        catalog={catalog}
        requirement={requirement}
        busy={busy}
        writeDraft={writeDraft}
        interpret={interpret}
        search={search}
      />

      {requirement && <RequirementView requirement={requirement} />}

      {comparison && <ComparisonView comparison={comparison} />}
    </section>
  );
}
