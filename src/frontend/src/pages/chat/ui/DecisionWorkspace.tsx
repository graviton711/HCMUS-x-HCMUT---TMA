import type { CurrentComparison, CurrentRequirement } from '../../../shared/api';
import type { ChatMsg } from '../../../features/chat';
import { DecisionBrief, ResultCards } from '../../../features/chat';
import { usePreferences } from '../../../shared/preferences';
import { draftForComparison, hasDecisionMetrics, latestDecisionArtifact, sameDecision } from '../lib/decisionArtifacts';
import styles from './DecisionWorkspace.module.css';

export function DecisionWorkspace({
  messages,
  busy,
  clientReady,
  selectedArtifactId,
  onOpenArtifact,
  onUpdateDecisionDraft,
  onRunDecision,
  onRelax,
  onSend,
  isSavedTour,
  onToggleSavedTour,
}: {
  messages: ChatMsg[];
  busy: boolean;
  clientReady: boolean;
  selectedArtifactId: string | null;
  onOpenArtifact: (id: string) => void;
  onUpdateDecisionDraft: (id: string, requirement: CurrentRequirement) => void;
  onRunDecision: (id: string, requirement: CurrentRequirement) => void;
  onRelax: (field: string) => void;
  onSend: (text: string) => void;
  isSavedTour?: (tourId: string, offerId: string) => boolean;
  onToggleSavedTour?: (comparison: CurrentComparison, tourId: string, offerId: string) => void;
}) {
  const { t } = usePreferences();
  const latestArtifact = latestDecisionArtifact(messages);
  const selectedArtifact = messages.find(
    (message) => message.id === selectedArtifactId &&
      (message.kind === 'decision_draft' || message.kind === 'comparison'),
  );
  const artifact = selectedArtifact ?? latestArtifact;
  const latestDraft = [...messages].reverse().find(
    (message): message is Extract<ChatMsg, { kind: 'decision_draft' }> =>
      message.kind === 'decision_draft',
  ) ?? null;
  const latestComparison = [...messages].reverse().find(
    (message): message is Extract<ChatMsg, { kind: 'comparison' }> =>
      message.kind === 'comparison',
  ) ?? null;

  const archivedDraft = artifact?.kind === 'decision_draft' ? artifact : null;
  const activeDraft = archivedDraft ?? latestDraft ?? (
    artifact?.kind === 'comparison' ? draftForComparison(messages, artifact.comparison) : null
  );
  let comparison: CurrentComparison | null = null;
  let comparisonIsStale = false;
  let staleComparison: CurrentComparison | null = null;

  if (artifact?.kind === 'comparison') {
    comparison = artifact.comparison;
    comparisonIsStale = Boolean(
      activeDraft && !sameDecision(activeDraft.requirement, comparison.requirement),
    );
  } else if (activeDraft) {
    const matching = [...messages].reverse().find(
      (message): message is Extract<ChatMsg, { kind: 'comparison' }> =>
        message.kind === 'comparison' && sameDecision(message.comparison.requirement, activeDraft.requirement),
    );
    if (matching) comparison = matching.comparison;
    else if (latestComparison) staleComparison = latestComparison.comparison;
  }

  const isCurrentDraft = Boolean(activeDraft && latestDraft?.id === activeDraft.id);
  const lastMessage = messages[messages.length - 1];
  const lastTurnFailed = lastMessage?.kind === 'error';
  const hasMetrics = comparison ? hasDecisionMetrics(comparison) : true;
  const status = busy
    ? t('Đang xử lý', 'Working')
    : lastTurnFailed
      ? t('Chưa hoàn tất', 'Incomplete')
      : comparison
        ? comparisonIsStale
          ? t('Kết quả cũ', 'Older result')
          : t('Có kết quả', 'Results ready')
        : activeDraft
          ? activeDraft.status === 'complete'
            ? t('Chờ so sánh', 'Ready to compare')
            : t('Chờ bạn duyệt', 'Review needed')
          : t('Chưa có bản yêu cầu', 'No brief yet');

  return (
    <aside className={styles.root} aria-labelledby="decision-workspace-title">
      <header className={styles.header}>
        <div>
          <span className={styles.eyebrow}>{t('KHÔNG GIAN QUYẾT ĐỊNH', 'DECISION WORKSPACE')}</span>
          <h2 id="decision-workspace-title">{t('Review và so sánh', 'Review and compare')}</h2>
        </div>
        <span className={styles.status} data-status={busy ? 'working' : comparisonIsStale ? 'stale' : 'ready'}>
          {status}
        </span>
      </header>

      <div className={styles.content}>
        {lastTurnFailed && (
          <p className={styles.inlineStatus} role="status">
            {t('Lượt vừa rồi chưa hoàn tất. Bản yêu cầu và kết quả trước đó vẫn được giữ.',
              'The last turn did not finish. Your brief and earlier results are still here.')}
          </p>
        )}

        {!activeDraft && !comparison && (
          <section className={styles.empty} aria-live="polite">
            <h3>{t('Chưa có bản yêu cầu để review', 'No structured brief to review yet')}</h3>
            <p>{t(
              'Khi agent tạo được bản yêu cầu có cấu trúc, bản đó sẽ xuất hiện ở đây. Nội dung hội thoại không tự được chuyển thành điều kiện.',
              'A structured brief will appear here when the agent creates one. Chat text is not converted into decision criteria.',
            )}</p>
          </section>
        )}

        {activeDraft && (
          <>
            {archivedDraft && !isCurrentDraft && (
              <p className={styles.inlineStatus} role="status">
                {t('Đang xem bản yêu cầu cũ. Bản này chỉ để đối chiếu lịch sử.',
                  'Viewing an older brief for reference.')}
              </p>
            )}
            <DecisionBrief
              message={activeDraft}
              busy={busy || !clientReady || !isCurrentDraft}
              onChange={(requirement) => onUpdateDecisionDraft(activeDraft.id, requirement)}
              onRun={(requirement) => onRunDecision(activeDraft.id, requirement)}
            />
          </>
        )}

        {staleComparison && !comparison && (
          <p className={styles.inlineStatus} role="status">
            {t('Điều kiện đã đổi nên kết quả trước không còn là kết quả hiện hành.',
              'The criteria changed, so the previous comparison is no longer current.')}{' '}
            <button type="button" onClick={() => onOpenArtifact(latestComparison!.id)}>
              {t('Mở kết quả cũ', 'Open earlier result')}
            </button>
          </p>
        )}

        {comparison && (
          <>
            {comparisonIsStale && (
              <p className={styles.inlineStatus} role="status">
                {t('Kết quả này dùng điều kiện khác với bản đang duyệt; không dùng để xác nhận lựa chọn hiện tại.',
                  'This result uses different criteria from the current brief and is not current.')}
              </p>
            )}
            {!hasMetrics && (
              <div className={styles.inlineStatus} role="status">
                <p>{t('Đây là kết quả cũ, chưa có bộ metric và bằng chứng chi tiết mới.',
                  'This older result does not include the newer metric and evidence details.')}</p>
                {activeDraft && isCurrentDraft && (
                  <button
                    type="button"
                    disabled={busy || !clientReady}
                    onClick={() => onRunDecision(activeDraft.id, activeDraft.requirement)}
                  >
                    {t('Chạy lại với bộ tiêu chí hiện tại', 'Rerun with current criteria')}
                  </button>
                )}
              </div>
            )}
            <ResultCards
              comparison={comparison}
              busy={busy || comparisonIsStale || !hasMetrics}
              onRelax={onRelax}
              isSavedTour={isSavedTour}
              onToggleSavedTour={onToggleSavedTour}
              onAsk={onSend}
            />
          </>
        )}
      </div>
    </aside>
  );
}
