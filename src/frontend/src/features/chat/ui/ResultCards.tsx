import { AnimatePresence, motion } from 'framer-motion';
import { useState } from 'react';
import type {
  CurrentComparison,
  CurrentCondition,
  CurrentCostExposure,
  CurrentDecisionView,
  CurrentEvaluation,
  CurrentMetricProfile,
} from '../../../shared/api';
import { evaluationStateText, observedLabel, priceText, safeUrl } from '../../../shared/lib';
import { usePreferences } from '../../../shared/preferences';
import {
  METRIC_NAMES,
  METRIC_RELATIONS,
  conditionState,
  conditionText,
  failedDetailsForOffer,
  fieldLabel,
  formatMetricValue,
  mostFailedField,
  relevantEvaluationsForOffer,
} from '../lib/format';
import { rise, staggerParent } from './motion';
import { QuickReplies } from './QuickReplies';
import { DecisionComparisonDialog, type ComparedOffer } from './DecisionComparisonDialog';
import styles from './chat.module.css';

function uniqueTours<T extends { tour_id: string }>(candidates: T[]): T[] {
  const seen = new Set<string>();
  return candidates.filter((candidate) => {
    if (seen.has(candidate.tour_id)) return false;
    seen.add(candidate.tour_id);
    return true;
  });
}

function rankingValue(
  field: string,
  tour: CurrentComparison['tour_snapshots'][number] | undefined,
  offer: CurrentComparison['tour_snapshots'][number]['offers'][number] | undefined,
): string | number | null {
  if (field === 'price') {
    return offer?.price == null || !offer.currency.trim()
      ? null
      : `${offer.currency.toUpperCase()}:${offer.price}`;
  }
  if (field === 'departure_date') return offer?.departure_date || null;
  if (field === 'duration_days') return tour?.duration_days ?? null;
  if (field === 'tour_name') return tour?.name.toLocaleLowerCase() || null;
  return null;
}

function metricObject(profile: CurrentMetricProfile, key: string): Record<string, unknown> {
  const value = profile.metrics[key]?.value;
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function metricNumber(profile: CurrentMetricProfile, key: string, nested?: string): number | null {
  const metric = profile.metrics[key];
  const value = nested ? metricObject(profile, key)[nested] : metric?.value;
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function formatCostExposure(
  item: CurrentCostExposure,
  locale: string,
  t: (vi: string, en: string) => string,
) {
  const obligation =
    item.obligation === 'mandatory'
      ? t('Bắt buộc', 'Mandatory')
      : item.obligation === 'optional'
        ? t('Tùy chọn', 'Optional')
        : item.obligation === 'conditional'
          ? t('Có điều kiện', 'Conditional')
          : t('Chưa rõ nghĩa vụ', 'Obligation unknown');
  const amount =
    item.amount == null
      ? t('chưa định giá', 'unpriced')
      : `${item.amount.toLocaleString(locale === 'vi' ? 'vi-VN' : 'en-GB')} ${item.currency || t('chưa rõ tiền tệ', 'currency unknown')}`;
  const unit =
    item.unit === 'per_person'
      ? t('/ người', '/ person')
      : item.unit === 'per_adult'
        ? t('/ người lớn', '/ adult')
        : item.unit === 'per_child'
          ? t('/ trẻ em', '/ child')
          : item.unit === 'per_room'
            ? t('/ phòng', '/ room')
            : item.unit === 'per_night'
              ? t('/ đêm', '/ night')
              : item.unit === 'per_day'
                ? t('/ ngày', '/ day')
                : item.unit === 'per_booking'
                  ? t('/ booking', '/ booking')
                  : '';
  return `${obligation} · ${amount}${unit}`;
}

function EvaluationRow({
  evaluation,
  condition,
  sourceUrl,
}: {
  evaluation: CurrentEvaluation;
  condition?: CurrentCondition | null;
  sourceUrl: string | null;
}) {
  const { t } = usePreferences();
  const label =
    evaluationStateText(evaluation.state, t);
  return (
    <li>
      <div className={styles['evidence-row']}>
        <span className={styles['evidence-state']} data-state={evaluation.state}>
          {label}
        </span>
        <span>
          {condition
            ? `${fieldLabel(condition.field, t)} ${conditionText(condition.operator, condition.value, t)}`
            : evaluation.condition_id}
        </span>
        {evaluation.quote && (
          <q className={styles['evidence-quote']} cite={sourceUrl ?? undefined}>
            {evaluation.quote}
          </q>
        )}
        {evaluation.reason_code && (
          <code className={styles['evidence-code']}>{evaluation.reason_code}</code>
        )}
      </div>
    </li>
  );
}

function TourCard({
  comparison,
  tourId,
  offerId,
  index,
  missing,
  decisionScore,
  selectedForCompare,
  compareDisabled,
  isSaved,
  onToggleCompare,
  onToggleSaved,
}: {
  comparison: CurrentComparison;
  tourId: string;
  offerId: string;
  index: number;
  missing: boolean;
  decisionScore?: number;
  selectedForCompare: boolean;
  compareDisabled: boolean;
  isSaved: boolean;
  onToggleCompare: () => void;
  onToggleSaved?: () => void;
}) {
  const { t, locale } = usePreferences();
  const tour = comparison.tour_snapshots.find((item) => item.id === tourId);
  const offer = tour?.offers.find((item) => item.id === offerId);
  if (!tour || !offer) return null;
  const state = conditionState(comparison, offer.id);
  const url = safeUrl(offer.evidence.url || tour.url || tour.evidence.url);
  const observed = observedLabel(offer.evidence.observed_at || tour.observed_at, locale);
  const details = relevantEvaluationsForOffer(comparison, offer.id);
  const failed = failedDetailsForOffer(comparison, offer.id);
  const failedCount = failed.filter(({ evaluation }) => evaluation.state === 'fail').length;
  const unknownCount = failed.filter(({ evaluation }) => evaluation.state === 'unknown').length;
  const priceLabel = priceText(offer.price, offer.currency, locale, t);
  const label = missing
    ? t(
        `Gần đạt · ${failedCount} không đạt, ${unknownCount} chưa rõ`,
        `Near miss · ${failedCount} failed, ${unknownCount} unknown`,
      )
    : state === 'pass'
      ? t('Đã kiểm tra', 'Checked')
      : state === 'fail'
        ? t('Không đạt', 'Does not match')
        : t('Chưa đủ dữ liệu', 'More data needed');

  return (
    <motion.article
      variants={rise}
      className={styles['tour-card']}
      aria-label={`${tour.name || tour.id} — ${label}`}
    >
      <div>
        <div className={styles['tour-top']}>
          <span
            className={`tag ${
              missing
                ? 'tag-warn'
                : state === 'pass'
                  ? 'tag-pass'
                  : state === 'fail'
                    ? 'tag-danger'
                    : 'tag-warn'
            }`}
          >
            {label}
          </span>
          <span className={styles['tour-rank']}>#{index + 1}</span>
        </div>
        {decisionScore !== undefined && (
          <p className={styles['decision-score']}>
            {t(`${decisionScore}/100 điểm ưu tiên`, `${decisionScore}/100 preference points`)}
          </p>
        )}
        <h3 className={styles['tour-name']}>{tour.name || tour.id}</h3>
        <p className={styles['tour-supplier']}>
          {tour.supplier || t('Chưa rõ nhà cung cấp', 'Supplier not listed')}
        </p>
      </div>

      {missing && failed.length > 0 && (
        <p className={styles['tour-blocked']}>
          {t('Điều kiện còn vướng:', 'Criteria to review:')}{' '}
          {failed
            .map(({ evaluation, condition }) => {
              const stateText =
                evaluation.state === 'unknown' ? t('chưa rõ', 'unknown') : t('không đạt', 'failed');
              return `${condition ? fieldLabel(condition.field, t) : evaluation.condition_id} (${stateText})`;
            })
            .join(', ')}
        </p>
      )}

      <dl className={styles['tour-facts']}>
        <div>
          <dt>{t('Giá', 'Price')}</dt>
          <dd>{priceLabel}</dd>
        </div>
        <div>
          <dt>{t('Khởi hành', 'Departure')}</dt>
          <dd>
            {offer.departure_date || t('Chưa có ngày', 'No date')} ·{' '}
            {tour.departure_city || t('Chưa rõ nơi đi', 'Unknown city')}
          </dd>
        </div>
        <div>
          <dt>{t('Thời lượng', 'Duration')}</dt>
          <dd>
            {tour.duration_days == null
              ? t('Chưa có dữ liệu', 'Not listed')
              : t(`${tour.duration_days} ngày`, `${tour.duration_days} days`)}
          </dd>
        </div>
      </dl>

      {details.length > 0 && (
        <details className={`${styles.evidence} disclosure`}>
          <summary>
            {t('Vì sao xếp hạng này', 'Why this ranking')} ({details.length})
          </summary>
          <ul className={styles['evidence-list']}>
            {details.map(({ evaluation, condition }) => (
              <EvaluationRow
                key={evaluation.condition_id}
                evaluation={evaluation}
                condition={condition}
                sourceUrl={url}
              />
            ))}
          </ul>
        </details>
      )}

      <div className={styles['tour-foot']}>
        <div className={styles['source-meta']}>
          {url ? (
            <a href={url} target="_blank" rel="noreferrer">
              {t('Mở nguồn dữ kiện', 'Open source')} ↗
            </a>
          ) : (
            <span>{t('Chưa có nguồn', 'No source')}</span>
          )}
          <span>
            {observed
              ? t(`Ghi nhận ${observed}`, `Observed ${observed}`)
              : t('Chưa rõ thời điểm ghi nhận', 'Observation time unknown')}
          </span>
        </div>
        <div className={styles['tour-card-actions']}>
          {onToggleSaved && (
            <button
              type="button"
              className={styles['tour-card-action']}
              aria-pressed={isSaved}
              onClick={onToggleSaved}
            >
              {isSaved ? t('Đã lưu', 'Saved') : t('Lưu tour', 'Save tour')}
            </button>
          )}
          <button
            type="button"
            className={styles['tour-card-action']}
            aria-pressed={selectedForCompare}
            disabled={compareDisabled}
            onClick={onToggleCompare}
          >
            {selectedForCompare ? t('Đã chọn', 'Selected') : t('So sánh', 'Compare')}
          </button>
        </div>
      </div>
    </motion.article>
  );
}

export function ResultCards({
  comparison,
  busy,
  onRelax,
  isSavedTour,
  onToggleSavedTour,
  onAsk,
}: {
  comparison: CurrentComparison;
  busy: boolean;
  onRelax: (field: string) => void;
  isSavedTour?: (tourId: string, offerId: string) => boolean;
  onToggleSavedTour?: (comparison: CurrentComparison, tourId: string, offerId: string) => void;
  onAsk?: (text: string) => void;
}) {
  const { t } = usePreferences();
  const [selected, setSelected] = useState<ComparedOffer[]>([]);
  const [compareOpen, setCompareOpen] = useState(false);
  const [weights, setWeights] = useState<Record<string, number>>({});
  const rankedOriginal = uniqueTours(comparison.ranked);
  const rankedTourIds = new Set(rankedOriginal.map((candidate) => candidate.tour_id));
  const nearMiss = uniqueTours(comparison.near_miss ?? []).filter(
    (candidate) => !rankedTourIds.has(candidate.tour_id),
  );
  const softConditions = comparison.requirement.conditions.filter(
    (condition) => condition.strength === 'soft',
  );
  const rankingKeys =
    comparison.requirement.ranking?.order_by ??
    (softConditions.length
      ? [
          { field: 'soft_fit', direction: 'desc' as const },
          { field: 'price', direction: 'asc' as const },
        ]
      : [{ field: 'price', direction: 'asc' as const }]);
  const softFitIndex = rankingKeys.findIndex((key) => key.field === 'soft_fit');
  const precedingKeys = rankingKeys.slice(0, softFitIndex < 0 ? rankingKeys.length : softFitIndex);
  const tourById = new Map(comparison.tour_snapshots.map((tour) => [tour.id, tour]));
  const offerById = new Map(
    comparison.tour_snapshots.flatMap((tour) =>
      tour.offers.map((offer) => [offer.id, offer] as const),
    ),
  );
  const originalOrder = new Map(
    rankedOriginal.map((candidate, index) => [candidate.offer_id, index]),
  );
  const evaluations = new Map<string, Set<string>>();
  for (const evaluation of comparison.evaluations) {
    if (evaluation.state !== 'pass') continue;
    const passed = evaluations.get(evaluation.offer_id) ?? new Set<string>();
    passed.add(evaluation.condition_id);
    evaluations.set(evaluation.offer_id, passed);
  }
  const samePrimaryRank = (
    left: (typeof rankedOriginal)[number],
    right: (typeof rankedOriginal)[number],
  ) =>
    precedingKeys.every(
      (key) =>
        rankingValue(key.field, tourById.get(left.tour_id), offerById.get(left.offer_id)) ===
        rankingValue(key.field, tourById.get(right.tour_id), offerById.get(right.offer_id)),
    );
  const weightedScore = (candidate: (typeof rankedOriginal)[number]) => {
    const passed = evaluations.get(candidate.offer_id) ?? new Set<string>();
    return softConditions.reduce(
      (sum, condition) => sum + (passed.has(condition.id) ? (weights[condition.id] ?? 1) : 0),
      0,
    );
  };
  const ranked: typeof rankedOriginal = [];
  for (let start = 0; start < rankedOriginal.length;) {
    let end = start + 1;
    while (
      end < rankedOriginal.length &&
      samePrimaryRank(rankedOriginal[start], rankedOriginal[end])
    )
      end += 1;
    ranked.push(
      ...rankedOriginal
        .slice(start, end)
        .sort(
          (left, right) =>
            weightedScore(right) - weightedScore(left) ||
            (originalOrder.get(left.offer_id) ?? 0) - (originalOrder.get(right.offer_id) ?? 0),
        ),
    );
    start = end;
  }
  const worst = mostFailedField(comparison);
  const empty = ranked.length === 0 && nearMiss.length === 0;
  const customOrder = softConditions.some((condition) => (weights[condition.id] ?? 1) !== 1);

  if ((comparison.decision_views?.length ?? 0) >= 3) {
    return (
      <DecisionViews
        comparison={comparison}
        busy={busy}
        onRelax={onRelax}
        isSavedTour={isSavedTour}
        onToggleSavedTour={onToggleSavedTour}
        onAsk={onAsk}
      />
    );
  }

  function toggleCompare(tourId: string, offerId: string) {
    setSelected((current) => {
      const existing = current.some((item) => item.tourId === tourId && item.offerId === offerId);
      if (existing)
        return current.filter((item) => item.tourId !== tourId || item.offerId !== offerId);
      if (current.length >= 3) return current;
      return [...current, { tourId, offerId }];
    });
  }

  const suggestions: { label: string; value: string }[] = [];
  const firstTwo = ranked.slice(0, 2).map((entry) => {
    const tour = comparison.tour_snapshots.find((item) => item.id === entry.tour_id);
    return tour?.name || entry.tour_id;
  });
  if (firstTwo.length === 2) {
    suggestions.push({
      label: t('Giải thích khác biệt', 'Explain the difference'),
      value: t(
        `Hãy giải thích khác biệt chính giữa ${firstTwo[0]} và ${firstTwo[1]} theo các điều kiện trong yêu cầu của tôi.`,
        `Explain the main differences between ${firstTwo[0]} and ${firstTwo[1]} against the criteria in my request.`,
      ),
    });
  }
  if (comparison.analysis.hidden_costs.length || comparison.analysis.risks.length) {
    suggestions.push({
      label: t('Xem phụ phí và rủi ro', 'Review costs and risks'),
      value: t(
        'Tóm tắt các phụ phí, khoản chưa bao gồm và rủi ro cần lưu ý ở các tour đạt đủ điều kiện.',
        'Summarize the extra costs, exclusions, and risks to review for the qualified tours.',
      ),
    });
  }
  if (comparison.evaluations.some((evaluation) => evaluation.state === 'unknown')) {
    suggestions.push({
      label: t('Kiểm tra dữ kiện còn thiếu', 'Check missing details'),
      value: t(
        'Dữ kiện nào còn chưa rõ và tôi nên xác nhận điều gì với nhà cung cấp trước khi chọn?',
        'Which details are still unclear, and what should I confirm with the supplier before choosing?',
      ),
    });
  }
  if (suggestions.length === 0) {
    if (ranked.length > 0) {
      suggestions.push({
        label: t('Giải thích kết quả', 'Explain these results'),
        value: t(
          'Hãy giải thích vì sao các tour này đạt yêu cầu và thứ tự xếp hạng dựa trên những dữ kiện nào.',
          'Explain why these tours meet my requirements and which evidence determines their ranking.',
        ),
      });
    } else if (nearMiss.length > 0) {
      suggestions.push({
        label: t('Xem tour gần đạt', 'Review near matches'),
        value: t(
          'Các tour gần đạt còn vướng điều kiện nào? Điều kiện nào có thể nới để mở thêm lựa chọn, và đánh đổi là gì?',
          'Which requirements block the near matches? What could I relax to get more options, and what would the trade-off be?',
        ),
      });
    } else {
      suggestions.push({
        label: t('Điều chỉnh yêu cầu', 'Adjust my request'),
        value: t(
          'Với dữ liệu hiện có chưa có tour phù hợp. Hãy gợi ý một điều kiện có thể nới và giải thích lựa chọn nào có thể xuất hiện.',
          'No tour fits based on the available data. Suggest one requirement I could relax and explain what options that may reveal.',
        ),
      });
    }
  }

  return (
    <section
      className={styles.result}
      aria-label={t('Kết quả so sánh tour', 'Tour comparison results')}
    >
      <div className={styles['result-summary']}>
        <p className="muted" role="status">
          {empty
            ? t(
                'Chưa có offer nào đáp ứng đủ điều kiện theo dữ liệu hiện có. Hãy kiểm tra dữ kiện thiếu hoặc nới một điều kiện.',
                'No offer meets all requirements based on available data. Check missing data or relax one condition.',
              )
            : t(
                `Đang hiển thị ${ranked.length} tour đạt đủ và ${nearMiss.length} tour gần đạt trong ${comparison.candidates_considered} tour đã xem.`,
                `Showing ${ranked.length} qualified tours and ${nearMiss.length} near misses from ${comparison.candidates_considered} tours scanned.`,
              )}
        </p>
        {comparison.ranking_currencies &&
          comparison.ranking_currencies.length > 1 &&
          rankingKeys.some((key) => key.field === 'price') && (
            <p className="muted">
              {t(
                'Giá được xếp riêng theo từng đơn vị tiền tệ; chưa quy đổi để so sánh mức rẻ nhất.',
                'Prices are ranked within each currency; no exchange conversion is applied.',
              )}
            </p>
          )}
        <div className={styles['result-counts']}>
          <span className="tag tag-quiet">
            {ranked.length} {t('đạt đủ · hiển thị', 'qualified · shown')}
          </span>
          {nearMiss.length > 0 && (
            <span className="tag tag-warn">
              {nearMiss.length} {t('gần đạt', 'near miss')}
            </span>
          )}
        </div>
      </div>

      {empty && (comparison.relaxation_options ?? []).length > 0 && (
        <div className={styles['relaxation-options']}>
          <p className={styles['relaxation-title']}>
            {t(
              'Nới điều kiện nào để mở thêm lựa chọn:',
              'Relax a requirement to open more options:',
            )}
          </p>
          <div className={styles['relaxation-chips']}>
            {(comparison.relaxation_options ?? []).map((relax) => {
              const condition = [
                ...comparison.requirement.conditions,
                ...(comparison.requirement.alternatives ?? []).flatMap((branch) => branch.conditions),
              ].find((item) => item.id === relax.condition_id);
              const label = condition
                ? `${fieldLabel(condition.field, t)} ${conditionText(condition.operator, condition.value, t)}`
                : relax.condition_id;
              return (
                <button
                  key={relax.condition_id}
                  type="button"
                  className={`btn ${styles['relaxation-chip']}`}
                  disabled={busy}
                  onClick={() => onRelax(condition?.field ?? '')}
                >
                  <span className={styles['relaxation-chip-label']}>
                    {t('Bỏ', 'Drop')}: {label}
                  </span>
                  <span className={styles['relaxation-chip-gain']}>
                    +{relax.gained_tours} {t('tour', 'tours')}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {softConditions.length > 0 && ranked.length > 1 && (
        <details className={styles['preference-controls']} open>
          <summary>
            <span>{t('Điều chỉnh mức ưu tiên', 'Adjust priorities')}</span>
            <span>
              {t(
                'Chỉ đổi thứ tự khi các khóa ưu tiên trước bằng nhau',
                'Only reorders tours tied on earlier ranking keys',
              )}
            </span>
          </summary>
          <p>
            {t(
              'Các tiêu chí này là ưu tiên mềm do agent nhận diện. Điều kiện bắt buộc và nhóm gần đạt không thay đổi.',
              'These are soft preferences identified by the agent. Required criteria and near misses stay unchanged.',
            )}
          </p>
          <div className={styles['preference-list']}>
            {softConditions.map((condition) => (
              <label className={styles['preference-row']} key={condition.id}>
                <span>
                  {fieldLabel(condition.field, t)}{' '}
                  {conditionText(condition.operator, condition.value, t)}
                </span>
                <input
                  type="range"
                  min="1"
                  max="5"
                  step="1"
                  value={weights[condition.id] ?? 1}
                  aria-label={t(
                    `Mức ưu tiên: ${fieldLabel(condition.field, t)} ${conditionText(condition.operator, condition.value, t)}`,
                    `Priority: ${fieldLabel(condition.field, t)} ${conditionText(condition.operator, condition.value, t)}`,
                  )}
                  onChange={(event) =>
                    setWeights((current) => ({
                      ...current,
                      [condition.id]: Number(event.target.value),
                    }))
                  }
                />
                <output>{weights[condition.id] ?? 1}/5</output>
              </label>
            ))}
          </div>
          {customOrder && (
            <button
              type="button"
              className={styles['preference-reset']}
              onClick={() => setWeights({})}
            >
              {t('Đặt lại mức đều nhau', 'Reset to equal priority')}
            </button>
          )}
        </details>
      )}

      {ranked.length > 0 && (
        <>
          <h3 className={styles['result-group-title']}>
            {t('Tour đạt đủ điều kiện', 'Qualified tours')}{' '}
            <span>
              {customOrder
                ? t(
                    'trọng số chỉ phá hòa trong nhóm cùng thứ tự ưu tiên',
                    'weights only break ties within a ranking group',
                  )
                : t('theo thứ tự xếp hạng của yêu cầu', 'ordered by the request ranking')}
            </span>
          </h3>
          <AnimatePresence>
            <motion.div
              variants={staggerParent}
              initial="initial"
              animate="animate"
              className={styles['result-grid']}
            >
              {ranked.map((entry, index) => (
                <TourCard
                  key={`${entry.tour_id}-${entry.offer_id}`}
                  comparison={comparison}
                  tourId={entry.tour_id}
                  offerId={entry.offer_id}
                  index={index}
                  missing={false}
                  selectedForCompare={selected.some(
                    (item) => item.tourId === entry.tour_id && item.offerId === entry.offer_id,
                  )}
                  compareDisabled={
                    selected.length >= 3 &&
                    !selected.some(
                      (item) => item.tourId === entry.tour_id && item.offerId === entry.offer_id,
                    )
                  }
                  isSaved={isSavedTour?.(entry.tour_id, entry.offer_id) ?? false}
                  onToggleCompare={() => toggleCompare(entry.tour_id, entry.offer_id)}
                  onToggleSaved={
                    onToggleSavedTour
                      ? () => onToggleSavedTour(comparison, entry.tour_id, entry.offer_id)
                      : undefined
                  }
                />
              ))}
            </motion.div>
          </AnimatePresence>
        </>
      )}

      {nearMiss.length > 0 && (
        <>
          <h3 className={styles['result-group-title']}>
            {t('Gần đạt — thiếu ít điều kiện', 'Near miss — missing a few conditions')}{' '}
            <span>{t('xếp theo số điều kiện đã đạt', 'ordered by conditions met')}</span>
          </h3>
          <div className={styles['result-grid']}>
            {nearMiss.map((entry, index) => (
              <TourCard
                key={`${entry.tour_id}-${entry.offer_id}`}
                comparison={comparison}
                tourId={entry.tour_id}
                offerId={entry.offer_id}
                index={index}
                missing
                selectedForCompare={selected.some(
                  (item) => item.tourId === entry.tour_id && item.offerId === entry.offer_id,
                )}
                compareDisabled={
                  selected.length >= 3 &&
                  !selected.some(
                    (item) => item.tourId === entry.tour_id && item.offerId === entry.offer_id,
                  )
                }
                isSaved={isSavedTour?.(entry.tour_id, entry.offer_id) ?? false}
                onToggleCompare={() => toggleCompare(entry.tour_id, entry.offer_id)}
                onToggleSaved={
                  onToggleSavedTour
                    ? () => onToggleSavedTour(comparison, entry.tour_id, entry.offer_id)
                    : undefined
                }
              />
            ))}
          </div>
        </>
      )}

      <div className={styles['result-actions']}>
        {selected.length > 0 && (
          <button
            type="button"
            className={`btn ${styles['result-action']}`}
            disabled={selected.length < 2}
            onClick={() => setCompareOpen(true)}
          >
            {t(`So sánh lựa chọn (${selected.length}/3)`, `Compare choices (${selected.length}/3)`)}
          </button>
        )}
        {selected.length > 0 && (
          <button
            type="button"
            className={styles['clear-comparison']}
            onClick={() => setSelected([])}
          >
            {t('Bỏ chọn', 'Clear selection')}
          </button>
        )}
        {worst && !empty && (
          <button
            type="button"
            className={`btn ${styles['result-action']}`}
            disabled={busy}
            onClick={() => onRelax(worst.field)}
          >
            {t(
              `Nới điều kiện ${fieldLabel(worst.field, t)} (${worst.count} tour vướng)`,
              `Relax ${fieldLabel(worst.field, t)} (${worst.count} blocked)`,
            )}
          </button>
        )}
      </div>

      {suggestions.length > 0 && onAsk && (
        <div className={styles['follow-up']}>
          <span>{t('Gợi ý hỏi tiếp', 'Ask next')}</span>
          <QuickReplies options={suggestions.slice(0, 3)} onPick={onAsk} disabled={busy} />
        </div>
      )}

      <DecisionComparisonDialog
        comparison={comparison}
        selected={selected}
        open={compareOpen}
        onClose={() => setCompareOpen(false)}
      />
    </section>
  );
}

type MetricCandidate = NonNullable<
  CurrentComparison['decision_views']
>[number]['candidates'][number];

function MetricComparisonPanel({
  comparison,
  entries,
}: {
  comparison: CurrentComparison;
  entries: MetricCandidate[];
}) {
  const { t, locale } = usePreferences();
  const profiles = new Map(
    (comparison.metric_profiles ?? []).map((profile) => [
      `${profile.tour_id}:${profile.offer_id}`,
      profile,
    ]),
  );
  const formatNumber = (value: number) => value.toLocaleString(locale === 'vi' ? 'vi-VN' : 'en-GB');

  function displayMetric(profile: CurrentMetricProfile, key: string, value: string) {
    const metric = profile.metrics[key];
    if (!metric || metric.state === 'unknown') return t('Chưa có dữ kiện', 'No evidence yet');
    if (!value) return t('Chưa có giá trị tính được', 'No calculable value');
    return metric.state === 'partial'
      ? `${value} · ${t('dữ kiện một phần', 'partial evidence')}`
      : value;
  }

  function evidenceQuote(profile: CurrentMetricProfile, key: string) {
    const quotes = [
      ...new Set((profile.metrics[key]?.evidence ?? []).map((item) => item.quote).filter(Boolean)),
    ];
    if (quotes.length <= 2) return quotes.join(' · ');
    return `${quotes.slice(0, 2).join(' · ')} · +${quotes.length - 2}`;
  }

  return (
    <details
      className={styles['metric-comparison']}
      aria-label={t('So sánh dữ kiện và chi phí', 'Compare evidence and costs')}
    >
      <summary>
        {t('Đánh đổi và chi phí cần kiểm tra', 'Trade-offs and costs to inspect')}
      </summary>
      <p>
        {t(
          'Khoản chưa bao gồm và phụ thu được tách theo nghĩa vụ và bằng chứng; khoản chưa rõ không được cộng vào tổng.',
          'Exclusions and surcharges are separated by obligation and evidence; unknown items are not added to the total.',
        )}
      </p>
      <div className={styles['metric-choice-grid']}>
        {entries.slice(0, 3).map((entry) => {
          const profile = profiles.get(`${entry.tour_id}:${entry.offer_id}`);
          const tour = comparison.tour_snapshots.find((item) => item.id === entry.tour_id);
          if (!profile || !tour) return null;
          const offer = tour.offers.find((item) => item.id === entry.offer_id);
          const observed = observedLabel(offer?.evidence.observed_at || tour.observed_at, locale);
          const sourceUrl = safeUrl(tour.url || tour.evidence.url);
          const fit = profile.metrics.preference_fit;
          const fitText =
            fit?.lower_bound != null && fit.upper_bound != null
              ? `${Math.round(fit.lower_bound * 100)}–${Math.round(fit.upper_bound * 100)}/100`
              : t('Chưa có dữ kiện', 'No evidence yet');
          const experience = metricNumber(profile, 'experience_density', 'activity_count');
          const legs = metricNumber(profile, 'route_complexity', 'explicit_legs');
          const coverage = metricNumber(profile, 'included_coverage', 'ratio');
          const cancellation = metricNumber(profile, 'cancellation_flexibility');
          const unresolvedCount = metricNumber(profile, 'unpriced_cost_exposures', 'count');
          const familyQuotes = [
            ...new Set(profile.family_facts.map((fact) => fact.evidence.quote).filter(Boolean)),
          ]
            .slice(0, 2)
            .join(' · ');
          const exposures = [
            ...profile.cost.priced_extras,
            ...profile.cost.unpriced_exclusions,
            ...profile.cost.optional_or_conditional,
          ];
          const uniqueExposures = exposures.filter(
            (item, index) =>
              exposures.findIndex(
                (other) =>
                  other.name === item.name &&
                  other.quote === item.quote &&
                  other.source_field === item.source_field,
              ) === index,
          );
          const groupTotal =
            profile.cost.group_total_calculated == null
              ? t('Chưa tính được tổng nhóm', 'Group total not calculable')
              : `${formatNumber(profile.cost.group_total_calculated)} ${profile.cost.currency}`;

          return (
            <article className={styles['metric-choice']} key={entry.offer_id}>
              <h4>{tour.name || tour.id}</h4>
              {sourceUrl && (
                <a
                  className={styles['metric-source-link']}
                  href={sourceUrl}
                  target="_blank"
                  rel="noreferrer"
                >
                  {t('Mở dữ kiện nguồn', 'Open source evidence')} ↗
                </a>
              )}
              {observed && (
                <small className={styles['metric-observed']}>
                  {t(`Ghi nhận ${observed}`, `Observed ${observed}`)}
                </small>
              )}
              <dl>
                <div>
                  <dt>{t('Tổng nhóm tính được', 'Calculated group total')}</dt>
                  <dd>{groupTotal}</dd>
                  {profile.cost.group_total_scope && (
                    <small>{profile.cost.group_total_scope}</small>
                  )}
                </div>
                <div>
                  <dt>{t('Khớp ưu tiên', 'Preference fit')}</dt>
                  <dd>{displayMetric(profile, 'preference_fit', fitText)}</dd>
                </div>
                <div>
                  <dt>{t('Trải nghiệm được nêu', 'Stated experiences')}</dt>
                  <dd>
                    {displayMetric(
                      profile,
                      'experience_density',
                      experience == null
                        ? ''
                        : `${formatNumber(experience)} ${t('hoạt động', 'activities')}`,
                    )}
                  </dd>
                  {evidenceQuote(profile, 'experience_density') && (
                    <small>{evidenceQuote(profile, 'experience_density')}</small>
                  )}
                </div>
                <div>
                  <dt>{t('Chặng được nêu', 'Stated route legs')}</dt>
                  <dd>
                    {displayMetric(
                      profile,
                      'route_complexity',
                      legs == null ? '' : formatNumber(legs),
                    )}
                  </dd>
                  {evidenceQuote(profile, 'route_complexity') && (
                    <small>{evidenceQuote(profile, 'route_complexity')}</small>
                  )}
                </div>
                <div>
                  <dt>{t('Hạng mục bao gồm', 'Included coverage')}</dt>
                  <dd>
                    {displayMetric(
                      profile,
                      'included_coverage',
                      coverage == null ? '' : `${Math.round(coverage * 100)}%`,
                    )}
                  </dd>
                  {evidenceQuote(profile, 'included_coverage') && (
                    <small>{evidenceQuote(profile, 'included_coverage')}</small>
                  )}
                </div>
                <div>
                  <dt>{t('Hoàn 100%', 'Full refund')}</dt>
                  <dd>
                    {displayMetric(
                      profile,
                      'cancellation_flexibility',
                      cancellation == null
                        ? ''
                        : `${formatNumber(cancellation)} ${t('ngày trước ngày đi', 'days before departure')}`,
                    )}
                  </dd>
                  {evidenceQuote(profile, 'cancellation_flexibility') && (
                    <small>{evidenceQuote(profile, 'cancellation_flexibility')}</small>
                  )}
                </div>
                <div>
                  <dt>{t('Điều khoản trẻ em', 'Child policy evidence')}</dt>
                  <dd>
                    {profile.family_facts.length
                      ? `${profile.family_facts.length} ${t('dữ kiện', 'facts')}`
                      : t('Chưa có dữ kiện', 'No evidence yet')}
                  </dd>
                  {familyQuotes && <small>{familyQuotes}</small>}
                </div>
                <div>
                  <dt>{t('Khoản chưa định giá / có điều kiện', 'Unpriced / conditional items')}</dt>
                  <dd>
                    {displayMetric(
                      profile,
                      'unpriced_cost_exposures',
                      unresolvedCount == null ? '' : formatNumber(unresolvedCount),
                    )}
                  </dd>
                </div>
              </dl>
              <details className={styles['metric-cost-details']}>
                <summary>
                  {t(
                    `Loại trừ, phụ thu (${uniqueExposures.length})`,
                    `Exclusions and surcharges (${uniqueExposures.length})`,
                  )}
                </summary>
                {uniqueExposures.length > 0 ? (
                  <ul>
                    {uniqueExposures.map((item, index) => (
                      <li key={`${item.source_field}-${item.name}-${index}`}>
                        <strong>{item.name}</strong>
                        <span>{formatCostExposure(item, locale, t)}</span>
                        {item.calculated_total != null && (
                          <span>
                            {t('Đã cộng vào tổng nhóm:', 'Included in group total:')}{' '}
                            {item.calculated_total.toLocaleString(
                              locale === 'vi' ? 'vi-VN' : 'en-GB',
                            )}{' '}
                            {item.currency}
                          </span>
                        )}
                        {item.applies_when && <span>{item.applies_when}</span>}
                        {item.quote && <q>{item.quote}</q>}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p>
                    {t(
                      'Chưa trích xuất được khoản cụ thể. Điều này không xác nhận tour không có chi phí phát sinh.',
                      'No specific item was extracted. This does not confirm that the tour has no extra costs.',
                    )}
                  </p>
                )}
                {(tour.exclusions || tour.surcharges) && (
                  <div className={styles['metric-source-text']}>
                    {tour.exclusions && (
                      <p>
                        <strong>{t('Chưa bao gồm:', 'Excluded:')}</strong> {tour.exclusions}
                      </p>
                    )}
                    {tour.surcharges && (
                      <p>
                        <strong>{t('Phụ thu:', 'Surcharges:')}</strong> {tour.surcharges}
                      </p>
                    )}
                  </div>
                )}
              </details>
            </article>
          );
        })}
      </div>
    </details>
  );
}

function DecisionViews({  comparison,
  busy,
  onRelax,
  isSavedTour,
  onToggleSavedTour,
  onAsk,
}: {
  comparison: CurrentComparison;
  busy: boolean;
  onRelax: (field: string) => void;
  isSavedTour?: (tourId: string, offerId: string) => boolean;
  onToggleSavedTour?: (comparison: CurrentComparison, tourId: string, offerId: string) => void;
  onAsk?: (text: string) => void;
}) {
  const { t } = usePreferences();
  const views = comparison.decision_views ?? [];
  const hasSoft = comparison.requirement.conditions.some(
    (condition) => condition.strength === 'soft',
  );
  const [activeKind, setActiveKind] = useState<CurrentDecisionView['kind']>(
    hasSoft ? 'best_fit' : 'cheapest',
  );
  const [selected, setSelected] = useState<ComparedOffer[]>([]);
  const [compareOpen, setCompareOpen] = useState(false);
  const activeView =
    views.find((view) => view.kind === activeKind && view.candidates.length > 0) ??
    views.find((view) => view.candidates.length > 0) ??
    views.find((view) => view.kind === activeKind) ??
    views[0];
  const entries = activeView?.candidates ?? [];
  const entryGroups = (() => {
    if (!activeView || activeView.kind === 'best_fit' || activeView.currencies.length < 2)
      return [{ currency: '', entries }];
    const groups = new Map<string, typeof entries>();
    for (const entry of entries) {
      const tour = comparison.tour_snapshots.find((item) => item.id === entry.tour_id);
      const offer = tour?.offers.find((item) => item.id === entry.offer_id);
      const currency = offer?.currency.toUpperCase() || t('Chưa rõ tiền tệ', 'Currency unknown');
      groups.set(currency, [...(groups.get(currency) ?? []), entry]);
    }
    return [...groups].map(([currency, grouped]) => ({
      currency,
      entries: grouped,
    }));
  })();
  const nearMiss = uniqueTours(comparison.near_miss ?? []).filter(
    (candidate) => !comparison.ranked.some((ranked) => ranked.tour_id === candidate.tour_id),
  );
  const worst = mostFailedField(comparison);
  const labels: Record<CurrentDecisionView['kind'], [string, string]> = {
    cheapest: ['Giá thấp nhất', 'Lowest published price'],
    best_fit: ['Hợp ưu tiên nhất', 'Best fit'],
    experience_rich: ['Nhiều trải nghiệm', 'More stated experiences'],
    fewest_legs: ['Ít chặng', 'Fewer route legs'],
    cancellation_flexible: ['Dễ hủy hơn', 'More flexible cancellation'],
    included_value: ['Dịch vụ bao gồm', 'Included services'],
    balanced: ['Cân bằng', 'Balanced'],
  };
  const optimizes: Record<string, [string, string]> = {
    cheapest: [
      'Xếp theo giá công bố thấp nhất; chưa gồm phụ thu và loại trừ.',
      'Ranks by lowest published price; excludes surcharges and exclusions.',
    ],
    best_fit: [
      'Xếp theo điểm khớp ưu tiên có trọng số; khoảng điểm rộng nghĩa là dữ kiện còn thiếu.',
      'Ranks by weighted preference fit; a wide range means missing evidence.',
    ],
    experience_rich: [
      'Xếp theo số hoạt động được nêu rõ; số lượng không khẳng định chất lượng.',
      'Ranks by stated activity count; count does not imply quality.',
    ],
    fewest_legs: [
      'Xếp theo số chặng được nêu rõ; không suy ra thời gian hay quãng đường.',
      'Ranks by stated leg count; not travel time or distance.',
    ],
    cancellation_flexible: [
      'Xếp theo mốc gần ngày đi nhất vẫn được hoàn đủ tiền, khi điều khoản nêu rõ.',
      'Ranks by the latest full-refund cutoff stated in the terms.',
    ],
    included_value: [
      'Xếp theo tỷ lệ hạng mục bao gồm; loại trừ chưa định giá liệt kê riêng.',
      'Ranks by included-category ratio; unpriced exclusions listed separately.',
    ],
    balanced: [
      'Tập Pareto trên các metric có dữ kiện; không cộng thành một điểm tổng.',
      'Pareto set over evidenced metrics; never merged into one score.',
    ],
    multi_objective: [
      'Phương án dự phòng khi metric chưa đủ để xếp hạng riêng.',
      'Fallback option when metrics cannot rank it separately.',
    ],
  };

  function toggleCompare(tourId: string, offerId: string) {
    setSelected((current) => {
      const existing = current.some((item) => item.tourId === tourId && item.offerId === offerId);
      if (existing)
        return current.filter((item) => item.tourId !== tourId || item.offerId !== offerId);
      if (current.length >= 3) return current;
      return [...current, { tourId, offerId }];
    });
  }

  const prompt = t(
    'Giải thích các điểm phù hợp, chưa rõ và đánh đổi trong góc nhìn này bằng dữ kiện của từng tour.',
    'Explain the matches, unknowns and trade-offs in this view using each tour’s evidence.',
  );
  return (
    <section
      className={`${styles.result} ${styles['decision-workspace']}`}
      aria-label={t('Không gian so sánh quyết định', 'Decision comparison workspace')}
    >
      <header className={styles['decision-heading']}>
        <div>
          <span className={styles['brief-eyebrow']}>
            {t('SO SÁNH THEO NHIỀU GÓC NHÌN', 'COMPARE ACROSS VIEWS')}
          </span>
          <h2>{t('Các lựa chọn phù hợp', 'Options that meet your criteria')}</h2>
          <p className={styles['decision-principle']}>
            {t(
              'Mỗi góc nhìn làm rõ một đánh đổi; bạn chọn phương án phù hợp với mình.',
              'Each view makes a different trade-off clear; you choose what fits you.',
            )}
          </p>
        </div>
        <span className="tag tag-quiet">
          {t(
            `${comparison.candidates_considered} tour đã quét`,
            `${comparison.candidates_considered} tours scanned`,
          )}
        </span>
      </header>

      {(comparison.decision_options ?? []).length > 0 && (
        <section
          className={styles['decision-choices']}
          aria-label={t('Các phương án để cân nhắc', 'Decision alternatives')}
        >
          <h3>
            {new Set((comparison.decision_options ?? []).map((option) => option.tour_id)).size <= 1
              ? t('Tour duy nhất đạt điều kiện', 'The only matching tour')
              : (comparison.decision_options ?? []).length >= 3
                ? t('Ba phương án để cân nhắc', 'Three alternatives to consider')
                : t('Phương án có dữ kiện', 'Evidence-backed alternatives')}
          </h3>
          <div className={styles['decision-choice-grid']}>
            {(comparison.decision_options ?? []).slice(0, 3).map((option, index) => {
              const tour = comparison.tour_snapshots.find((item) => item.id === option.tour_id);
              const singleTour =
                new Set((comparison.decision_options ?? []).map((item) => item.tour_id)).size <= 1;
              const objectiveLabel = labels[option.objective as CurrentDecisionView['kind']] ?? [
                'Góc nhìn đa mục tiêu',
                'Multi-objective view',
              ];
              const optimizesLabel = optimizes[option.objective] ?? optimizes.multi_objective;
              const lead = option.tradeoffs.find((tradeoff) => tradeoff.startsWith('Đánh đổi:'));
              const rest = option.tradeoffs.filter((tradeoff) => tradeoff !== lead);
              return (
                <article
                  className={styles['decision-choice']}
                  key={`${option.tour_id}-${option.offer_id}`}
                >
                  <span>
                    {singleTour
                      ? t('Phương án duy nhất', 'The only option')
                      : t(
                          `Phương án ${index + 1} · ${objectiveLabel[0]}`,
                          `Option ${index + 1} · ${objectiveLabel[1]}`,
                        )}
                  </span>
                  <h4>{tour?.name ?? option.tour_id}</h4>
                  <strong>{option.title}</strong>
                  <p>{option.reason}</p>
                  <small>{t(...optimizesLabel)}</small>
                  {lead && <p>{lead}</p>}
                  {rest.length > 0 && (
                    <ul className={styles['decision-hidden-costs']}>
                      {rest
                        .filter(
                          (tradeoff) =>
                            tradeoff.includes('chưa thể định giá') ||
                            tradeoff.includes('chưa cộng vào tổng'),
                        )
                        .map((tradeoff) => (
                          <li key={tradeoff}>{tradeoff}</li>
                        ))}
                    </ul>
                  )}
                  {rest.length > 0 && (
                    <details>
                      <summary>{t('Số liệu chi tiết', 'Detailed figures')}</summary>
                      <ul>
                        {rest.map((tradeoff) => (
                          <li key={tradeoff}>{tradeoff}</li>
                        ))}
                      </ul>
                    </details>
                  )}
                  {(option.metric_comparisons ?? []).length > 0 && (
                    <div className={styles['decision-metric-comparisons']}>
                      {(option.metric_comparisons ?? [])
                        .filter((metric) => metric.relation !== 'unknown' || metric.value != null)
                        .map((metric) => {
                          const name = METRIC_NAMES[metric.key] ?? [metric.key, metric.key];
                          const format = (value: number | null) =>
                            formatMetricValue({ ...metric, value }, t);
                        const relation = METRIC_RELATIONS[metric.relation] ?? METRIC_RELATIONS.unknown;
                        return (
                          <div key={metric.key} data-relation={metric.relation}>
                            <strong>{t(...name)}</strong>
                            <span>
                              {format(metric.value)} · {t(...relation)}
                            </span>
                            {metric.reference_median != null && (
                              <small>
                                {t('Trung vị nhóm:', 'Group median:')}{' '}
                                {format(metric.reference_median)}
                              </small>
                            )}
                            {metric.evidence.length > 0 && (
                              <details>
                                <summary>{t('Bằng chứng', 'Evidence')}</summary>
                                {metric.evidence.map((evidence, evidenceIndex) => (
                                  <blockquote key={`${evidence.source_field}-${evidenceIndex}`}>
                                    {evidence.quote}
                                  </blockquote>
                                ))}
                              </details>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        </section>
      )}

      {activeView && (
        <div
          className={styles['decision-tabs']}
          role="tablist"
          aria-label={t('Góc nhìn so sánh', 'Comparison views')}
        >
          {views.map((view) => (
            <button
              key={view.kind}
              type="button"
              role="tab"
              aria-selected={view.kind === activeView.kind}
              disabled={view.candidates.length === 0}
              className={styles['decision-tab']}
              onClick={() => setActiveKind(view.kind)}
            >
              {t(...labels[view.kind])}
              <span>{view.candidates.length}</span>
            </button>
          ))}
        </div>
      )}

      {activeView && (
        <div className={styles['decision-view-copy']}>
          <p>{activeView.note}</p>
          {activeView.kind !== 'best_fit' && activeView.currencies.length > 1 && (
            <p className="muted">
              {t(
                `Đang chia theo ${activeView.currencies.join(', ')}; không quy đổi để chọn một mức giá chung.`,
                `Grouped by ${activeView.currencies.join(', ')}; currencies are not converted into one price ranking.`,
              )}
            </p>
          )}
        </div>
      )}

      {!activeView ? (
        <p className={styles['decision-empty']} role="status">
          {t(
            'Chưa có metric so sánh cho kết quả này. Chạy lại lượt so sánh để tạo các góc nhìn.',
            'This result has no metric views yet. Re-run the comparison to generate them.',
          )}
        </p>
      ) : entries.length > 0 ? (
        <div className={styles['decision-option-groups']}>
          {entryGroups.map((group) => (
            <section
              className={styles['decision-option-group']}
              key={group.currency || activeView.kind}
            >
              {group.currency && <h3>{group.currency}</h3>}
              <div className={styles['result-grid']}>
                {group.entries.map((entry, index) => (
                  <TourCard
                    key={`${activeView.kind}-${entry.tour_id}-${entry.offer_id}`}
                    comparison={comparison}
                    tourId={entry.tour_id}
                    offerId={entry.offer_id}
                    index={index}
                    missing={false}
                    decisionScore={activeView.kind === 'best_fit' ? entry.score : undefined}
                    selectedForCompare={selected.some(
                      (item) => item.tourId === entry.tour_id && item.offerId === entry.offer_id,
                    )}
                    compareDisabled={
                      selected.length >= 3 &&
                      !selected.some(
                        (item) => item.tourId === entry.tour_id && item.offerId === entry.offer_id,
                      )
                    }
                    isSaved={isSavedTour?.(entry.tour_id, entry.offer_id) ?? false}
                    onToggleCompare={() => toggleCompare(entry.tour_id, entry.offer_id)}
                    onToggleSaved={
                      onToggleSavedTour
                        ? () => onToggleSavedTour(comparison, entry.tour_id, entry.offer_id)
                        : undefined
                    }
                  />
                ))}
              </div>
            </section>
          ))}
        </div>
      ) : (
        <>
          {(comparison.relaxation_options ?? []).length > 0 ? (
            <div className={styles['relaxation-options']}>
              <p className={styles['relaxation-title']}>
                {t(
                  'Nới điều kiện nào để mở thêm lựa chọn:',
                  'Relax a requirement to open more options:',
                )}
              </p>
              <div className={styles['relaxation-chips']}>
                {(comparison.relaxation_options ?? []).map((relax) => {
                  const condition = [
                    ...comparison.requirement.conditions,
                    ...(comparison.requirement.alternatives ?? []).flatMap((branch) => branch.conditions),
                  ].find((item) => item.id === relax.condition_id);
                  const label = condition
                    ? `${fieldLabel(condition.field, t)} ${conditionText(condition.operator, condition.value, t)}`
                    : relax.condition_id;
                  return (
                    <button
                      key={relax.condition_id}
                      type="button"
                      className={`btn ${styles['relaxation-chip']}`}
                      disabled={busy}
                      onClick={() => onRelax(condition?.field ?? '')}
                    >
                      <span className={styles['relaxation-chip-label']}>
                        {t('Bỏ', 'Drop')}: {label}
                      </span>
                      <span className={styles['relaxation-chip-gain']}>
                        +{relax.gained_tours} {t('tour', 'tours')}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          ) : (
            <p className={styles['decision-empty']} role="status">
              {activeView.kind === 'best_fit' && !hasSoft
                ? t(
                    'Thêm một sở thích mềm để xếp tour theo mức hợp ưu tiên.',
                    'Add a preference to rank tours by fit.',
                  )
                : activeView.kind === 'balanced'
                  ? t(
                      'Chưa có đủ giá số cùng tiền tệ để tạo phương án Pareto.',
                      'There is not enough same-currency numeric price data to form a Pareto set.',
                    )
                  : t(
                      'Chưa có tour qua toàn bộ điều kiện bắt buộc trong phạm vi đã quét.',
                      'No scanned tours pass every must-have criterion.',
                    )}
            </p>
          )}
        </>
      )}

      {activeView && entries.length > 0 && (
        <MetricComparisonPanel comparison={comparison} entries={entries} />
      )}

      {hasSoft && entries.length > 0 && (
        <details className={styles['decision-matrix']}>
          <summary>
            {t(
              `Ma trận tiêu chí · ${comparison.requirement.conditions.filter((condition) => condition.strength === 'soft').length} ưu tiên`,
              `Criteria matrix · ${comparison.requirement.conditions.filter((condition) => condition.strength === 'soft').length} preferences`,
            )}
          </summary>
          <div className={styles['decision-matrix-grid']}>
            {entries.map((entry) => {
              const tourName =
                comparison.tour_snapshots.find((tour) => tour.id === entry.tour_id)?.name ??
                entry.tour_id;
              return (
                <section className={styles['decision-matrix-card']} key={entry.offer_id}>
                  <h4>{tourName}</h4>
                  <dl>
                    {comparison.requirement.conditions
                      .filter((condition) => condition.strength === 'soft')
                      .map((condition) => {
                        const evaluation = comparison.evaluations.find(
                          (item) =>
                            item.offer_id === entry.offer_id && item.condition_id === condition.id,
                        );
                        const state = evaluation?.state ?? 'unknown';
                        return (
                          <div key={`${entry.offer_id}-${condition.id}`}>
                            <dt>
                              {String(condition.value)}
                              <span>{condition.weight_percent ?? 0}%</span>
                            </dt>
                            <dd>
                              <span className={styles['matrix-state']} data-state={state}>
                                {evaluationStateText(state, t)}
                              </span>
                              {evaluation?.quote && <q>{evaluation.quote}</q>}
                            </dd>
                          </div>
                        );
                      })}
                  </dl>
                </section>
              );
            })}
          </div>
        </details>
      )}

      <div className={styles['result-actions']}>
        {selected.length > 0 && (
          <button
            type="button"
            className={`btn ${styles['result-action']}`}
            disabled={selected.length < 2}
            onClick={() => setCompareOpen(true)}
          >
            {t(`So sánh lựa chọn (${selected.length}/3)`, `Compare choices (${selected.length}/3)`)}
          </button>
        )}
        {selected.length > 0 && (
          <button
            type="button"
            className={styles['clear-comparison']}
            onClick={() => setSelected([])}
          >
            {t('Bỏ chọn', 'Clear selection')}
          </button>
        )}
        {worst && (
          <button
            type="button"
            className={`btn ${styles['result-action']}`}
            disabled={busy}
            onClick={() => onRelax(worst.field)}
          >
            {t(
              `Xem nếu nới ${fieldLabel(worst.field, t)}`,
              `Explore relaxing ${fieldLabel(worst.field, t)}`,
            )}
          </button>
        )}
      </div>

      {nearMiss.length > 0 && (
        <details className={styles['decision-near-miss']}>
          <summary>
            {t(`Xem ${nearMiss.length} tour gần đạt`, `Review ${nearMiss.length} near matches`)}
          </summary>
          <div className={styles['result-grid']}>
            {nearMiss.map((entry, index) => (
              <TourCard
                key={`near-${entry.tour_id}-${entry.offer_id}`}
                comparison={comparison}
                tourId={entry.tour_id}
                offerId={entry.offer_id}
                index={index}
                missing
                selectedForCompare={selected.some(
                  (item) => item.tourId === entry.tour_id && item.offerId === entry.offer_id,
                )}
                compareDisabled={
                  selected.length >= 3 &&
                  !selected.some(
                    (item) => item.tourId === entry.tour_id && item.offerId === entry.offer_id,
                  )
                }
                isSaved={isSavedTour?.(entry.tour_id, entry.offer_id) ?? false}
                onToggleCompare={() => toggleCompare(entry.tour_id, entry.offer_id)}
                onToggleSaved={
                  onToggleSavedTour
                    ? () => onToggleSavedTour(comparison, entry.tour_id, entry.offer_id)
                    : undefined
                }
              />
            ))}
          </div>
        </details>
      )}

      {onAsk && (
        <div className={styles['follow-up']}>
          <span>{t('Hỏi về đánh đổi', 'Ask about the trade-offs')}</span>
          <QuickReplies
            options={[
              {
                label: t('Giải thích góc nhìn này', 'Explain this view'),
                value: prompt,
              },
            ]}
            onPick={onAsk}
            disabled={busy}
          />
        </div>
      )}

      <DecisionComparisonDialog
        comparison={comparison}
        selected={selected}
        open={compareOpen}
        onClose={() => setCompareOpen(false)}
      />
    </section>
  );
}
