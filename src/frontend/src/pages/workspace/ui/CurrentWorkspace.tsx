import type { LocalSession } from '../../../features/session-history';
import { usePreferences } from '../../../shared/preferences';
import { useCurrentWorkspace } from '../model/useCurrentWorkspace';
import { ComparisonView } from './ComparisonView';
import { RequirementForm } from './RequirementForm';
import { RequirementView } from './RequirementView';
import styles from './CurrentWorkspace.module.css';

export function CurrentWorkspace({
  session,
  onStart,
  onChangeSession,
}: {
  session: LocalSession;
  onStart?: (initialText?: string) => void;
  onChangeSession: (changes: Partial<LocalSession>) => void;
}) {
  const { t } = usePreferences();
  const {
    catalog,
    requirement,
    comparison,
    busy,
    error,
    expired,
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
        <span className="eyebrow">{t('Soi tour bằng dữ kiện', 'Evidence-based comparison')}</span>
        <h1 id="current-workspace-title">
          {t(
            'Chọn điều quan trọng. Đối chiếu bằng dữ kiện.',
            'Pick what matters. Compare with facts.',
          )}
        </h1>
        <p className="measure">
          {t(
            'Mỗi lần tìm được diễn giải riêng. Dữ kiện thiếu, cũ hoặc chưa xác minh được ghi rõ là "chưa rõ" và không được tính là đạt.',
            'Each search is interpreted independently. Missing, stale or unverified facts are marked unknown and never counted as a pass.',
          )}
        </p>
      </header>

      {error && (
        <div className="notice notice-error" role="alert">
          <span>{error}</span>
          <span className="row">
            {expired && session.draft.text.trim() && onStart ? (
              <button
                className="btn btn-primary"
                disabled={busy}
                onClick={() => onStart(session.draft.text.trim())}
              >
                {t('Tạo phiên mới và tiếp tục', 'Start a new session and continue')}
              </button>
            ) : null}
            <button className="btn" disabled={busy} onClick={retry}>
              {t('Thử lại', 'Retry')}
            </button>
          </span>
        </div>
      )}
      {stale && (
        <p className="notice notice-warning" role="status">
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
