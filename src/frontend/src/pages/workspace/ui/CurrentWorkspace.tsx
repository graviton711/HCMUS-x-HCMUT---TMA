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
            'Mỗi lần tìm được diễn giải riêng. Dữ kiện thiếu được ghi rõ là "chưa rõ"; ngày khởi hành cũ không được coi là còn hiệu lực.',
            'Each search is interpreted independently. Missing information stays unknown, and stale departure dates are not treated as current.',
          )}
        </p>
      </header>

      {error && (
        <div className="notice notice-error" role="alert">
          <span>
            {expired
              ? t(
                  'Phiên khách đã hết hạn. Bản nháp vẫn được giữ.',
                  'Guest session expired. Your draft is kept.',
                )
              : error}
          </span>
          <span className="row">
            {expired && onStart ? (
              <button
                className="btn btn-primary"
                disabled={busy}
                onClick={() => onStart(session.draft.text.trim() || undefined)}
              >
                {session.draft.text.trim()
                  ? t(
                      'Tạo phiên mới và gửi lại bản nháp',
                      'Start a new session and resend the draft',
                    )
                  : t('Tạo phiên mới', 'Start a new session')}
              </button>
            ) : null}
            {!expired && (
              <button className="btn" disabled={busy} onClick={retry}>
                {t('Thử lại', 'Retry')}
              </button>
            )}
          </span>
          {expired && session.draft.text.trim() && (
            <p>
              {t(
                'Phiên mới gửi lại bản nháp; ngữ cảnh hội thoại cũ không được chuyển sang.',
                'The new session resends the draft; the old conversation context is not transferred.',
              )}
            </p>
          )}
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
        busy={busy || expired}
        disabled={expired}
        writeDraft={writeDraft}
        interpret={interpret}
        search={search}
      />

      {requirement && <RequirementView requirement={requirement} />}

      {comparison && <ComparisonView comparison={comparison} />}
    </section>
  );
}
