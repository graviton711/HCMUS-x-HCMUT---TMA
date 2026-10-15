import { useEffect, useState } from 'react';
import type {
  CurrentBackendClient,
  CurrentComparison,
  CurrentCostScenario,
  CurrentCostScenarioAssumptions,
  CurrentEliminatedPage,
  CurrentRequirement,
} from '../../../shared/api';
import type { ChatMsg } from '../../../features/chat';
import { DecisionBrief, ResultCards, conditionText, fieldLabel } from '../../../features/chat';
import { usePreferences } from '../../../shared/preferences';
import {
  draftForComparison,
  hasDecisionMetrics,
  latestDecisionArtifact,
  sameDecision,
} from '../lib/decisionArtifacts';
import styles from './DecisionWorkspace.module.css';

export function DecisionWorkspace({
  messages,
  busy,
  clientReady,
  client,
  agentSessionId,
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
  client: CurrentBackendClient | null;
  agentSessionId: string | null;
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
    (message) =>
      message.id === selectedArtifactId &&
      (message.kind === 'decision_draft' || message.kind === 'comparison'),
  );
  const artifact = selectedArtifact ?? latestArtifact;
  const latestDraft =
    [...messages]
      .reverse()
      .find(
        (message): message is Extract<ChatMsg, { kind: 'decision_draft' }> =>
          message.kind === 'decision_draft',
      ) ?? null;
  const latestComparison =
    [...messages]
      .reverse()
      .find(
        (message): message is Extract<ChatMsg, { kind: 'comparison' }> =>
          message.kind === 'comparison',
      ) ?? null;

  const archivedDraft = artifact?.kind === 'decision_draft' ? artifact : null;
  const activeDraft =
    archivedDraft ??
    latestDraft ??
    (artifact?.kind === 'comparison' ? draftForComparison(messages, artifact.comparison) : null);
  let comparison: CurrentComparison | null = null;
  let comparisonIsStale = false;
  let staleComparison: CurrentComparison | null = null;

  if (artifact?.kind === 'comparison') {
    comparison = artifact.comparison;
    comparisonIsStale = Boolean(
      activeDraft && !sameDecision(activeDraft.requirement, comparison.requirement),
    );
  } else if (activeDraft) {
    const matching = [...messages]
      .reverse()
      .find(
        (message): message is Extract<ChatMsg, { kind: 'comparison' }> =>
          message.kind === 'comparison' &&
          sameDecision(message.comparison.requirement, activeDraft.requirement),
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
        <span
          className={styles.status}
          data-status={busy ? 'working' : comparisonIsStale ? 'stale' : 'ready'}
        >
          {status}
        </span>
      </header>

      <div className={styles.content}>
        {lastTurnFailed && (
          <p className={styles.inlineStatus} role="status">
            {t(
              'Lượt vừa rồi chưa hoàn tất. Bản yêu cầu và kết quả trước đó vẫn được giữ.',
              'The last turn did not finish. Your brief and earlier results are still here.',
            )}
          </p>
        )}

        {!activeDraft && !comparison && (
          <section className={styles.empty} aria-live="polite">
            <h3>{t('Chưa có bản yêu cầu để review', 'No structured brief to review yet')}</h3>
            <p>
              {t(
                'Khi agent tạo được bản yêu cầu có cấu trúc, bản đó sẽ xuất hiện ở đây. Nội dung hội thoại không tự được chuyển thành điều kiện.',
                'A structured brief will appear here when the agent creates one. Chat text is not converted into decision criteria.',
              )}
            </p>
          </section>
        )}

        {activeDraft && (
          <>
            {archivedDraft && !isCurrentDraft && (
              <p className={styles.inlineStatus} role="status">
                {t(
                  'Đang xem bản yêu cầu cũ. Bản này chỉ để đối chiếu lịch sử.',
                  'Viewing an older brief for reference.',
                )}
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
            {t(
              'Điều kiện đã đổi nên kết quả trước không còn là kết quả hiện hành.',
              'The criteria changed, so the previous comparison is no longer current.',
            )}{' '}
            <button type="button" onClick={() => onOpenArtifact(latestComparison!.id)}>
              {t('Mở kết quả cũ', 'Open earlier result')}
            </button>
          </p>
        )}

        {comparison && (
          <>
            {comparisonIsStale && (
              <p className={styles.inlineStatus} role="status">
                {t(
                  'Kết quả này dùng điều kiện khác với bản đang duyệt; không dùng để xác nhận lựa chọn hiện tại.',
                  'This result uses different criteria from the current brief and is not current.',
                )}
              </p>
            )}
            {!hasMetrics && (
              <div className={styles.inlineStatus} role="status">
                <p>
                  {t(
                    'Đây là kết quả cũ, chưa có bộ metric và bằng chứng chi tiết mới.',
                    'This older result does not include the newer metric and evidence details.',
                  )}
                </p>
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
            {comparison.decision_trace?.snapshot_available && (
              <ScenarioWorkbench
                comparison={comparison}
                client={client}
                agentSessionId={agentSessionId}
                busy={busy}
                activeDraftId={activeDraft?.id ?? null}
                onApply={(requirement) => {
                  if (activeDraft) onUpdateDecisionDraft(activeDraft.id, requirement);
                }}
                onRunDecision={(requirement) => {
                  if (activeDraft) onRunDecision(activeDraft.id, requirement);
                }}
                onRelax={onRelax}
                onSend={onSend}
                isSavedTour={isSavedTour}
                onToggleSavedTour={onToggleSavedTour}
              />
            )}
            <DecisionTracePanel comparison={comparison} client={client} />
          </>
        )}
      </div>
    </aside>
  );
}

type CostInputState = {
  travelers: string;
  adult: string;
  child: string;
  small_child: string;
  infant: string;
  rooms: string;
  single_rooms: string;
  nights: string;
};

function ScenarioWorkbench({
  comparison,
  client,
  agentSessionId,
  busy,
  activeDraftId,
  onApply,
  onRunDecision,
  onRelax,
  onSend,
  isSavedTour,
  onToggleSavedTour,
}: {
  comparison: CurrentComparison;
  client: CurrentBackendClient | null;
  agentSessionId: string | null;
  busy: boolean;
  activeDraftId: string | null;
  onApply: (requirement: CurrentRequirement) => void;
  onRunDecision: (requirement: CurrentRequirement) => void;
  onRelax: (field: string) => void;
  onSend: (text: string) => void;
  isSavedTour?: (tourId: string, offerId: string) => boolean;
  onToggleSavedTour?: (comparison: CurrentComparison, tourId: string, offerId: string) => void;
}) {
  const { t } = usePreferences();
  const [scenarioRequirement, setScenarioRequirement] = useState<CurrentRequirement>(
    comparison.requirement,
  );
  const [scenarioComparison, setScenarioComparison] = useState<CurrentComparison | null>(null);
  const [costScenario, setCostScenario] = useState<CurrentCostScenario | null>(null);
  const [costInputs, setCostInputs] = useState<CostInputState>(() =>
    initialCostInputs(comparison.requirement),
  );
  const [running, setRunning] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setScenarioRequirement(comparison.requirement);
    setScenarioComparison(null);
    setCostScenario(null);
    setCostInputs(initialCostInputs(comparison.requirement));
    setError('');
  }, [comparison.id, comparison.requirement]);

  const scenarioDraft: Extract<ChatMsg, { kind: 'decision_draft' }> = {
    id: `scenario-${comparison.id}`,
    kind: 'decision_draft',
    requirement: scenarioRequirement,
    status: scenarioComparison ? 'complete' : 'draft',
  };
  const travelerCount = Number(costInputs.travelers);
  const travelerMix = {
    adult: Number(costInputs.adult || 0),
    child: Number(costInputs.child || 0),
    small_child: Number(costInputs.small_child || 0),
    infant: Number(costInputs.infant || 0),
  };
  const mixComplete =
    Object.values(travelerMix).reduce((sum, value) => sum + value, 0) === travelerCount;
  const costInputsValid =
    Number.isInteger(travelerCount) &&
    travelerCount > 0 &&
    mixComplete &&
    Object.values(travelerMix).every((value) => Number.isInteger(value) && value >= 0) &&
    (costInputs.rooms === '' || Number(costInputs.rooms) >= 1) &&
    (costInputs.single_rooms === '' || Number(costInputs.single_rooms) >= 0) &&
    (costInputs.nights === '' || Number(costInputs.nights) >= 0) &&
    (costInputs.rooms === '' ||
      costInputs.single_rooms === '' ||
      Number(costInputs.single_rooms) <= Number(costInputs.rooms));

  async function runCriteria(requirement: CurrentRequirement) {
    if (!client || !agentSessionId || busy || running) return;
    setRunning(true);
    setError('');
    setScenarioComparison(null);
    try {
      const response = await client.criteriaScenario(comparison.id, agentSessionId, requirement);
      if (!response.comparison) throw new Error('SCENARIO_RESULT_MISSING');
      setScenarioComparison(response.comparison);
    } catch {
      setError(
        t(
          'Không chạy được kịch bản điều kiện trên snapshot này.',
          'Could not run the criteria scenario on this snapshot.',
        ),
      );
    } finally {
      setRunning(false);
    }
  }

  async function runCostScenario() {
    if (!client || !costInputsValid || busy || running) return;
    setRunning(true);
    setError('');
    setCostScenario(null);
    const assumptions: CurrentCostScenarioAssumptions = {
      travelers: travelerCount,
      traveler_mix: travelerMix,
      rooms: costInputs.rooms === '' ? null : Number(costInputs.rooms),
      single_rooms: costInputs.single_rooms === '' ? null : Number(costInputs.single_rooms),
      nights: costInputs.nights === '' ? null : Number(costInputs.nights),
    };
    try {
      const response = await client.costScenario(comparison.id, assumptions);
      setCostScenario(response.scenario);
    } catch {
      setError(t('Không tính được kịch bản chi phí.', 'Could not calculate the cost scenario.'));
    } finally {
      setRunning(false);
    }
  }

  return (
    <details className={styles.scenarioPanel}>
      <summary>{t('Thử kịch bản', 'Try a scenario')}</summary>
      <p className={styles.traceNote}>
        {t(
          'Kịch bản giữ nguyên kết quả gốc và dùng cùng snapshot dữ liệu.',
          'Scenarios keep the original result unchanged and use its scan snapshot.',
        )}
      </p>
      <section>
        <h3>{t('Thay điều kiện', 'Change criteria')}</h3>
        <DecisionBrief
          message={scenarioDraft}
          busy={busy || running || !client || !agentSessionId}
          onChange={(requirement) => {
            setScenarioRequirement(requirement);
            setScenarioComparison(null);
          }}
          onRun={runCriteria}
        />
        {scenarioRequirement.conditions.length > 0 && activeDraftId && (
          <button
            type="button"
            disabled={busy || running}
            onClick={() => onApply(scenarioRequirement)}
          >
            {t('Chép điều kiện vào Brief để duyệt', 'Copy criteria to the Brief for review')}
          </button>
        )}
        {scenarioComparison && (
          <>
            <p className={styles.scenarioNotice}>
              {t(
                `Kịch bản có ${scenarioComparison.decision_trace?.eligible_offers ?? scenarioComparison.ranked.length} offer đạt đủ điều kiện. Kết quả gốc vẫn được giữ.`,
                `Scenario has ${scenarioComparison.decision_trace?.eligible_offers ?? scenarioComparison.ranked.length} eligible offers. The baseline is unchanged.`,
              )}
            </p>
            <ResultCards
              comparison={scenarioComparison}
              busy={busy}
              onRelax={onRelax}
              isSavedTour={isSavedTour}
              onToggleSavedTour={onToggleSavedTour}
              onAsk={onSend}
            />
            {activeDraftId && (
              <button
                type="button"
                disabled={busy || running}
                onClick={() => onRunDecision(scenarioRequirement)}
              >
                {t('Duyệt Brief này và chạy chính thức', 'Approve this Brief and run officially')}
              </button>
            )}
          </>
        )}
      </section>
      <section>
        <h3>{t('Thay giả định chi phí', 'Change cost assumptions')}</h3>
        <div className={styles.scenarioInputs}>
          {scenarioNumberField(
            t('Số khách', 'Travelers'),
            costInputs.travelers,
            (value) => setCostInputs((current) => ({ ...current, travelers: value })),
            1,
          )}
          {(['adult', 'child', 'small_child', 'infant'] as const).map((age) =>
            scenarioNumberField(
              {
                adult: t('Người lớn', 'Adults'),
                child: t('Trẻ em', 'Children'),
                small_child: t('Trẻ nhỏ', 'Small children'),
                infant: t('Em bé', 'Infants'),
              }[age],
              costInputs[age],
              (value) => setCostInputs((current) => ({ ...current, [age]: value })),
              0,
            ),
          )}
          {scenarioNumberField(
            t('Số phòng (nếu biết)', 'Rooms (if known)'),
            costInputs.rooms,
            (value) => setCostInputs((current) => ({ ...current, rooms: value })),
            1,
          )}
          {scenarioNumberField(
            t('Phòng đơn', 'Single rooms'),
            costInputs.single_rooms,
            (value) => setCostInputs((current) => ({ ...current, single_rooms: value })),
            0,
          )}
          {scenarioNumberField(
            t('Số đêm (nếu biết)', 'Nights (if known)'),
            costInputs.nights,
            (value) => setCostInputs((current) => ({ ...current, nights: value })),
            0,
          )}
        </div>
        {!mixComplete && (
          <p className={styles.traceNote}>
            {t('Cơ cấu độ tuổi phải bằng tổng số khách.', 'Age mix must equal the traveler count.')}
          </p>
        )}
        <button
          type="button"
          disabled={!client || !costInputsValid || busy || running}
          onClick={() => void runCostScenario()}
        >
          {running ? t('Đang tính…', 'Calculating…') : t('Tính lại chi phí', 'Recalculate costs')}
        </button>
        {costScenario && <CostScenarioResults scenario={costScenario} />}
      </section>
      {error && (
        <p role="status" className={styles.scenarioNotice}>
          {error}
        </p>
      )}
    </details>
  );
}

function initialCostInputs(requirement: CurrentRequirement): CostInputState {
  const mix = requirement.traveler_mix ?? {};
  return {
    travelers: String(requirement.travelers),
    adult: mix.adult == null ? '' : String(mix.adult),
    child: mix.child == null ? '' : String(mix.child),
    small_child: mix.small_child == null ? '' : String(mix.small_child),
    infant: mix.infant == null ? '' : String(mix.infant),
    rooms: '',
    single_rooms: '',
    nights: '',
  };
}

function scenarioNumberField(
  label: string,
  value: string,
  onChange: (value: string) => void,
  min: number,
) {
  return (
    <label key={label}>
      <span>{label}</span>
      <input
        type="number"
        min={min}
        step="1"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function CostScenarioResults({ scenario }: { scenario: CurrentCostScenario }) {
  const { t } = usePreferences();
  return (
    <div className={styles.scenarioCosts}>
      {scenario.items.map((item) => (
        <article key={item.offer_id}>
          <strong>{item.tour_name}</strong>
          <span>
            {item.known_total == null
              ? t('Chưa tính được tổng nhóm', 'Group total unavailable')
              : `${item.known_total.toLocaleString()} ${item.currency}`}
            {item.state !== 'observed' &&
              item.known_total != null &&
              ` · ${t('còn khoản chưa rõ', 'some costs remain unknown')}`}
          </span>
          {item.delta_from_original != null && (
            <small>
              {t('Thay đổi so với tổng trước:', 'Change from prior total:')}{' '}
              {item.delta_from_original > 0 ? '+' : ''}
              {item.delta_from_original.toLocaleString()} {item.currency}
            </small>
          )}
          {item.unresolved_exposures.length > 0 && (
            <ul>
              {item.unresolved_exposures.map((exposure, index) => (
                <li key={`${exposure.source_field}-${index}`}>
                  {exposure.name}
                  {exposure.amount != null
                    ? ` · ${exposure.amount.toLocaleString()} ${exposure.currency}/${exposure.unit}`
                    : ` · ${t('chưa có đơn giá', 'no unit price')}`}
                  {exposure.quote && ` · “${exposure.quote}”`}
                </li>
              ))}
            </ul>
          )}
        </article>
      ))}
    </div>
  );
}

function DecisionTracePanel({
  comparison,
  client,
}: {
  comparison: CurrentComparison;
  client: CurrentBackendClient | null;
}) {
  const { t } = usePreferences();
  const trace = comparison.decision_trace;
  const [open, setOpen] = useState(false);
  const [page, setPage] = useState<CurrentEliminatedPage | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function load(cursor?: string | null) {
    if (!client || loading) return;
    setLoading(true);
    setError('');
    try {
      const next = await client.eliminatedOffers(comparison.id, cursor, 20);
      setPage((current) =>
        cursor && current ? { ...next, items: [...current.items, ...next.items] } : next,
      );
    } catch {
      setError(t('Không tải được danh sách tour bị loại.', 'Could not load excluded tours.'));
    } finally {
      setLoading(false);
    }
  }

  const criterionLabel = (conditionId: string) => {
    const branch = (comparison.requirement.alternatives ?? []).find((item) =>
      item.conditions.some((condition) => condition.id === conditionId),
    );
    const condition = [
      ...comparison.requirement.conditions,
      ...(comparison.requirement.alternatives ?? []).flatMap((item) => item.conditions),
    ].find((item) => item.id === conditionId);
    if (!condition) return conditionId;
    const text = `${fieldLabel(condition.field, t)} ${conditionText(condition.operator, condition.value, t)}`;
    return branch ? `${branch.label} · ${text}` : text;
  };

  return (
    <details className={styles.tracePanel}>
      <summary>{t('Cách lọc', 'How filtering worked')}</summary>
      {trace ? (
        <div className={styles.traceContent}>
          <p>
            {t(
              `${trace.scanned_tours} tour · ${trace.scanned_offers} offer đã quét; ${trace.eligible_tours} tour / ${trace.eligible_offers} offer đạt đủ điều kiện.`,
              `${trace.scanned_tours} tours · ${trace.scanned_offers} offers scanned; ${trace.eligible_tours} tours / ${trace.eligible_offers} offers passed all criteria.`,
            )}
          </p>
          {trace.sequential_funnel.length > 0 && (
            <ol className={styles.traceList}>
              {trace.sequential_funnel.map((step) => (
                <li key={step.condition_id || `stage-${step.stage}`}>
                  <span>{step.label || criterionLabel(step.condition_id)}</span>
                  <strong>
                    {step.offers_before} → {step.offers_after} {t('offer còn lại', 'offers remain')}
                  </strong>
                </li>
              ))}
            </ol>
          )}
          {(trace.alternative_counts ?? []).length > 0 && (
            <div className={styles.traceCounts}>
              <strong>
                {t(
                  'Kết quả theo từng phương án (các phương án dùng phép OR)',
                  'Eligibility by option (options are ORed)',
                )}
              </strong>
              {trace.alternative_counts!.map((item) => (
                <div key={item.alternative_id}>
                  <span>{item.label}</span>
                  <strong>
                    {item.eligible_tours} {t('tour', 'tours')} · {item.eligible_offers}{' '}
                    {t('offer', 'offers')}
                  </strong>
                </div>
              ))}
            </div>
          )}
          <p className={styles.traceNote}>
            {t(
              'Bộ đếm theo từng điều kiện có thể chồng lấp. “Chưa rõ” là thiếu bằng chứng, không phải trượt.',
              'Per-criterion counts may overlap. “Unknown” means evidence is missing, not that the tour failed.',
            )}
          </p>
          {trace.condition_counts.length > 0 && (
            <div className={styles.traceCounts}>
              {trace.condition_counts.map((item) => (
                <div key={item.condition_id}>
                  <strong>{criterionLabel(item.condition_id)}</strong>
                  <span>
                    {t('Đạt', 'Pass')} {item.pass_offers} · {t('Trượt', 'Fail')} {item.fail_offers}{' '}
                    · {t('Chưa rõ', 'Unknown')} {item.unknown_offers}
                  </span>
                </div>
              ))}
            </div>
          )}
          {trace.first_blockers.length > 0 && (
            <div className={styles.traceCounts}>
              <strong>
                {t('Lý do chặn đầu tiên theo thứ tự điều kiện', 'First blocker in criterion order')}
              </strong>
              {trace.first_blockers.map((item) => (
                <div key={`${item.condition_id}-${item.state}`}>
                  <span>
                    {criterionLabel(item.condition_id)} ·{' '}
                    {item.state === 'unknown' ? t('chưa rõ', 'unknown') : t('không đạt', 'failed')}
                  </span>
                  <strong>
                    {item.offers} {t('offer', 'offers')} / {item.tours} {t('tour', 'tours')}
                  </strong>
                </div>
              ))}
            </div>
          )}
          {trace.snapshot_available ? (
            <section className={styles.traceEliminated}>
              {!open ? (
                <button
                  type="button"
                  disabled={!client}
                  onClick={() => {
                    setOpen(true);
                    void load();
                  }}
                >
                  {t(
                    `Xem ${trace.excluded_offers} offer bị loại`,
                    `Inspect ${trace.excluded_offers} excluded offers`,
                  )}
                </button>
              ) : (
                <>
                  {page?.items.map((item) => (
                    <article key={item.offer.id}>
                      <strong>{item.tour_name}</strong>
                      <span>
                        {item.supplier} ·{' '}
                        {item.offer.departure_date || t('Chưa rõ ngày', 'Date unknown')}
                      </span>
                      <ul>
                        {item.conditions
                          .filter((condition) => condition.state !== 'pass')
                          .map((condition) => (
                            <li key={condition.condition_id}>
                              <b>
                                {condition.state === 'unknown'
                                  ? t('Chưa rõ', 'Unknown')
                                  : t('Không đạt', 'Failed')}
                              </b>{' '}
                              {criterionLabel(condition.condition_id)} · {condition.reason}
                              {condition.quote && <blockquote>{condition.quote}</blockquote>}
                            </li>
                          ))}
                      </ul>
                    </article>
                  ))}
                  {error && <p role="status">{error}</p>}
                  {page?.next_cursor && (
                    <button
                      type="button"
                      disabled={loading}
                      onClick={() => void load(page.next_cursor)}
                    >
                      {loading ? t('Đang tải…', 'Loading…') : t('Xem thêm', 'Load more')}
                    </button>
                  )}
                </>
              )}
            </section>
          ) : (
            <p className={styles.traceNote}>
              {t(
                'Comparison cũ không còn snapshot đầy đủ; hãy chạy lại để mở danh sách bị loại.',
                'This older comparison has no retained scan snapshot. Rerun it to inspect excluded tours.',
              )}
            </p>
          )}
        </div>
      ) : (
        <p className={styles.traceNote}>
          {t(
            'Comparison này chưa có decision trace. Hãy chạy lại để xem đường đi bộ lọc.',
            'This comparison has no decision trace. Rerun it to inspect the filtering path.',
          )}
        </p>
      )}
    </details>
  );
}
