import { AnimatePresence, motion } from 'framer-motion';
import { useState } from 'react';
import type {
  CurrentComparison,
  CurrentCondition,
  CurrentDecisionView,
  CurrentEvaluation,
} from '../../../shared/api';
import { observedLabel, safeUrl } from '../../../shared/lib';
import { usePreferences } from '../../../shared/preferences';
import {
  conditionState,
  conditionText,
  evaluationsForOffer,
  failedDetailsForOffer,
  fieldLabel,
  mostFailedField,
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
    return offer?.price == null || offer.price_basis === 'contact' || !offer.currency.trim()
      ? null
      : `${offer.currency.toUpperCase()}:${offer.price}`;
  }
  if (field === 'departure_date') return offer?.departure_date || null;
  if (field === 'duration_days') return tour?.duration_days ?? null;
  if (field === 'tour_name') return tour?.name.toLocaleLowerCase() || null;
  return null;
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
    evaluation.state === 'pass'
      ? t('Đạt', 'Pass')
      : evaluation.state === 'fail'
        ? t('Không đạt', 'Fail')
        : t('Chưa rõ', 'Unknown');
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
  const details = evaluationsForOffer(comparison, offer.id);
  const failed = failedDetailsForOffer(comparison, offer.id);
  const priceLabel =
    offer.price == null
      ? t('Liên hệ', 'Contact')
      : [
          offer.price_basis === 'from' ? t('Từ ', 'From ') : '',
          offer.price.toLocaleString(locale === 'vi' ? 'vi-VN' : 'en-GB'),
          offer.currency ? ` ${offer.currency}` : ` · ${t('chưa rõ tiền tệ', 'currency unknown')}`,
        ].join('');
  const label = missing
    ? t(`Gần đạt · thiếu ${failed.length}`, `Near miss · missing ${failed.length}`)
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
          {t('Chưa đạt:', 'Not met:')}{' '}
          {failed
            .map(({ evaluation, condition }) =>
              condition ? fieldLabel(condition.field, t) : evaluation.condition_id,
            )
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
  const rankingKeys = comparison.requirement.ranking?.order_by ?? (softConditions.length
    ? [{ field: 'soft_fit', direction: 'desc' as const }, { field: 'price', direction: 'asc' as const }]
    : [{ field: 'price', direction: 'asc' as const }]);
  const softFitIndex = rankingKeys.findIndex((key) => key.field === 'soft_fit');
  const precedingKeys = rankingKeys.slice(0, softFitIndex < 0 ? rankingKeys.length : softFitIndex);
  const tourById = new Map(comparison.tour_snapshots.map((tour) => [tour.id, tour]));
  const offerById = new Map(
    comparison.tour_snapshots.flatMap((tour) => tour.offers.map((offer) => [offer.id, offer] as const)),
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
  const samePrimaryRank = (left: (typeof rankedOriginal)[number], right: (typeof rankedOriginal)[number]) =>
    precedingKeys.every((key) => rankingValue(
      key.field,
      tourById.get(left.tour_id),
      offerById.get(left.offer_id),
    ) === rankingValue(
      key.field,
      tourById.get(right.tour_id),
      offerById.get(right.offer_id),
    ));
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
    while (end < rankedOriginal.length && samePrimaryRank(rankedOriginal[start], rankedOriginal[end])) end += 1;
    ranked.push(...rankedOriginal.slice(start, end).sort((left, right) => (
      weightedScore(right) - weightedScore(left) ||
      (originalOrder.get(left.offer_id) ?? 0) - (originalOrder.get(right.offer_id) ?? 0)
    )));
    start = end;
  }
  const worst = mostFailedField(comparison);
  const empty = ranked.length === 0 && nearMiss.length === 0;
  const customOrder = softConditions.some((condition) => (weights[condition.id] ?? 1) !== 1);

  if (comparison.decision_views?.length === 3) {
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
        {comparison.ranking_currencies && comparison.ranking_currencies.length > 1 &&
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
                : t(
                    'theo thứ tự xếp hạng của yêu cầu',
                    'ordered by the request ranking',
                  )}
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

function DecisionViews({
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
  const views = comparison.decision_views ?? [];
  const hasSoft = comparison.requirement.conditions.some((condition) => condition.strength === 'soft');
  const [activeKind, setActiveKind] = useState<CurrentDecisionView['kind']>(hasSoft ? 'best_fit' : 'cheapest');
  const [selected, setSelected] = useState<ComparedOffer[]>([]);
  const [compareOpen, setCompareOpen] = useState(false);
  const activeView = views.find((view) => view.kind === activeKind) ?? views[0];
  const entries = activeView.candidates;
  const entryGroups = (() => {
    if (activeView.kind === 'best_fit' || activeView.currencies.length < 2)
      return [{ currency: '', entries }];
    const groups = new Map<string, typeof entries>();
    for (const entry of entries) {
      const tour = comparison.tour_snapshots.find((item) => item.id === entry.tour_id);
      const offer = tour?.offers.find((item) => item.id === entry.offer_id);
      const currency = offer?.currency.toUpperCase() || t('Chưa rõ tiền tệ', 'Currency unknown');
      groups.set(currency, [...(groups.get(currency) ?? []), entry]);
    }
    return [...groups].map(([currency, grouped]) => ({ currency, entries: grouped }));
  })();
  const nearMiss = uniqueTours(comparison.near_miss ?? []).filter(
    (candidate) => !comparison.ranked.some((ranked) => ranked.tour_id === candidate.tour_id),
  );
  const worst = mostFailedField(comparison);
  const labels: Record<CurrentDecisionView['kind'], [string, string]> = {
    cheapest: ['Giá thấp nhất', 'Lowest exact price'],
    best_fit: ['Hợp ưu tiên nhất', 'Best fit'],
    balanced: ['Cân bằng', 'Balanced'],
  };

  function toggleCompare(tourId: string, offerId: string) {
    setSelected((current) => {
      const existing = current.some((item) => item.tourId === tourId && item.offerId === offerId);
      if (existing) return current.filter((item) => item.tourId !== tourId || item.offerId !== offerId);
      if (current.length >= 3) return current;
      return [...current, { tourId, offerId }];
    });
  }

  const prompt = t(
    'Giải thích các điểm phù hợp, chưa rõ và đánh đổi trong góc nhìn này bằng dữ kiện của từng tour.',
    'Explain the matches, unknowns and trade-offs in this view using each tour’s evidence.',
  );
  return (
    <section className={`${styles.result} ${styles['decision-workspace']}`} aria-label={t('Không gian so sánh quyết định', 'Decision comparison workspace')}>
      <header className={styles['decision-heading']}>
        <div>
          <span className={styles['brief-eyebrow']}>{t('SO SÁNH THEO NHIỀU GÓC NHÌN', 'COMPARE ACROSS VIEWS')}</span>
          <h2>{t('Các lựa chọn phù hợp', 'Options that meet your criteria')}</h2>
        </div>
        <span className="tag tag-quiet">
          {t(`${comparison.candidates_considered} tour đã quét`, `${comparison.candidates_considered} tours scanned`)}
        </span>
      </header>

      <div className={styles['decision-tabs']} role="tablist" aria-label={t('Góc nhìn so sánh', 'Comparison views')}>
        {views.map((view) => (
          <button
            key={view.kind}
            type="button"
            role="tab"
            aria-selected={view.kind === activeView.kind}
            className={styles['decision-tab']}
            onClick={() => setActiveKind(view.kind)}
          >
            {t(...labels[view.kind])}
            <span>{view.candidates.length}</span>
          </button>
        ))}
      </div>

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

      {entries.length > 0 ? (
        <div className={styles['decision-option-groups']}>
          {entryGroups.map((group) => (
            <section className={styles['decision-option-group']} key={group.currency || activeView.kind}>
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
                    decisionScore={activeView.kind === 'cheapest' ? undefined : entry.score}
                    selectedForCompare={selected.some((item) => item.tourId === entry.tour_id && item.offerId === entry.offer_id)}
                    compareDisabled={selected.length >= 3 && !selected.some((item) => item.tourId === entry.tour_id && item.offerId === entry.offer_id)}
                    isSaved={isSavedTour?.(entry.tour_id, entry.offer_id) ?? false}
                    onToggleCompare={() => toggleCompare(entry.tour_id, entry.offer_id)}
                    onToggleSaved={onToggleSavedTour
                      ? () => onToggleSavedTour(comparison, entry.tour_id, entry.offer_id)
                      : undefined}
                  />
                ))}
              </div>
            </section>
          ))}
        </div>
      ) : (
        <p className={styles['decision-empty']} role="status">
          {activeView.kind === 'best_fit' && !hasSoft
            ? t('Thêm một sở thích mềm để xếp tour theo mức hợp ưu tiên.', 'Add a preference to rank tours by fit.')
            : activeView.kind === 'balanced'
              ? t('Chưa có đủ giá exact cùng tiền tệ để tạo phương án Pareto.', 'There is not enough same-currency exact-price data to form a Pareto set.')
              : t('Chưa có tour qua toàn bộ điều kiện bắt buộc trong phạm vi đã quét.', 'No scanned tours pass every must-have criterion.')}
        </p>
      )}

      {hasSoft && entries.length > 0 && (
        <details className={styles['decision-matrix']}>
          <summary>
            {t(
              `Ma trận tiêu chí · ${comparison.requirement.conditions.filter((condition) => condition.strength === 'soft').length} ưu tiên`,
              `Criteria matrix · ${comparison.requirement.conditions.filter((condition) => condition.strength === 'soft').length} preferences`,
            )}
          </summary>
          <div className={styles['decision-matrix-scroll']}>
            <table>
              <thead>
                <tr>
                  <th scope="col">{t('Tiêu chí / trọng số', 'Preference / weight')}</th>
                  {entries.map((entry) => (
                    <th scope="col" key={entry.offer_id}>
                      {comparison.tour_snapshots.find((tour) => tour.id === entry.tour_id)?.name ?? entry.tour_id}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {comparison.requirement.conditions
                  .filter((condition) => condition.strength === 'soft')
                  .map((condition) => (
                    <tr key={condition.id}>
                      <th scope="row">
                        {String(condition.value)} <span>{condition.weight_percent ?? 0}%</span>
                      </th>
                      {entries.map((entry) => {
                        const evaluation = comparison.evaluations.find((item) =>
                          item.offer_id === entry.offer_id && item.condition_id === condition.id,
                        );
                        const state = evaluation?.state ?? 'unknown';
                        return (
                          <td key={`${entry.offer_id}-${condition.id}`}>
                            <span className={styles['matrix-state']} data-state={state}>
                              {state === 'pass'
                                ? t('Đạt', 'Pass')
                                : state === 'fail'
                                  ? t('Không đạt', 'Fail')
                                  : t('Chưa rõ', 'Unknown')}
                            </span>
                            {evaluation?.quote && <q>{evaluation.quote}</q>}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </details>
      )}

      <div className={styles['result-actions']}>
        {selected.length > 0 && (
          <button type="button" className={`btn ${styles['result-action']}`} disabled={selected.length < 2} onClick={() => setCompareOpen(true)}>
            {t(`So sánh lựa chọn (${selected.length}/3)`, `Compare choices (${selected.length}/3)`)}
          </button>
        )}
        {selected.length > 0 && (
          <button type="button" className={styles['clear-comparison']} onClick={() => setSelected([])}>
            {t('Bỏ chọn', 'Clear selection')}
          </button>
        )}
        {worst && (
          <button type="button" className={`btn ${styles['result-action']}`} disabled={busy} onClick={() => onRelax(worst.field)}>
            {t(`Xem nếu nới ${fieldLabel(worst.field, t)}`, `Explore relaxing ${fieldLabel(worst.field, t)}`)}
          </button>
        )}
      </div>

      {nearMiss.length > 0 && (
        <details className={styles['decision-near-miss']}>
          <summary>{t(`Xem ${nearMiss.length} tour gần đạt`, `Review ${nearMiss.length} near matches`)}</summary>
          <div className={styles['result-grid']}>
            {nearMiss.map((entry, index) => (
              <TourCard
                key={`near-${entry.tour_id}-${entry.offer_id}`}
                comparison={comparison}
                tourId={entry.tour_id}
                offerId={entry.offer_id}
                index={index}
                missing
                selectedForCompare={selected.some((item) => item.tourId === entry.tour_id && item.offerId === entry.offer_id)}
                compareDisabled={selected.length >= 3 && !selected.some(
                  (item) => item.tourId === entry.tour_id && item.offerId === entry.offer_id,
                )}
                isSaved={isSavedTour?.(entry.tour_id, entry.offer_id) ?? false}
                onToggleCompare={() => toggleCompare(entry.tour_id, entry.offer_id)}
                onToggleSaved={onToggleSavedTour
                  ? () => onToggleSavedTour(comparison, entry.tour_id, entry.offer_id)
                  : undefined}
              />
            ))}
          </div>
        </details>
      )}

      {onAsk && (
        <div className={styles['follow-up']}>
          <span>{t('Hỏi về đánh đổi', 'Ask about the trade-offs')}</span>
          <QuickReplies options={[{ label: t('Giải thích góc nhìn này', 'Explain this view'), value: prompt }]} onPick={onAsk} disabled={busy} />
        </div>
      )}

      <DecisionComparisonDialog comparison={comparison} selected={selected} open={compareOpen} onClose={() => setCompareOpen(false)} />
    </section>
  );
}
