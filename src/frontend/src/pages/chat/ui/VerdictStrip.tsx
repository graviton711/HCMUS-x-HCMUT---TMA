import { useState } from 'react';

import type {
  CurrentBackendClient,
  CurrentComparison,
  CurrentRelaxationOption,
} from '../../../shared/api';
import { conditionText, fieldLabel, formatMetricValue, METRIC_NAMES } from '../../../features/chat';
import { priceText } from '../../../shared/lib';
import { usePreferences } from '../../../shared/preferences';
import { relaxRequirement } from '../lib/relaxRequirement';
import styles from './VerdictStrip.module.css';

const OBJECTIVE_KICKER: Record<string, [string, string]> = {
  cheapest: ['Giá thấp nhất', 'Lowest price'],
  best_fit: ['Hợp ưu tiên nhất', 'Best fit'],
  experience_rich: ['Nhiều trải nghiệm', 'Most experiences'],
  fewest_legs: ['Ít chặng', 'Fewest legs'],
  cancellation_flexible: ['Dễ hủy hơn', 'Flexible cancellation'],
  included_value: ['Dịch vụ bao gồm', 'Included value'],
  balanced: ['Cân bằng', 'Balanced'],
  multi_objective: ['Đa mục tiêu', 'Multi-objective'],
};

type ScenarioState =
  | { status: 'idle' }
  | { status: 'running' }
  | { status: 'done'; eligibleTours: number; eligibleOffers: number; names: string[] }
  | { status: 'error'; message: string };

function findCondition(comparison: CurrentComparison, conditionId: string) {
  const all = [
    ...(comparison.requirement.conditions ?? []),
    ...(comparison.requirement.alternatives ?? []).flatMap((branch) => branch.conditions),
  ];
  return all.find((condition) => condition.id === conditionId);
}

function tourName(comparison: CurrentComparison, tourId: string, fallback: string) {
  return comparison.tour_snapshots.find((tour) => tour.id === tourId)?.name || fallback;
}

const short = (value: string) =>
  value.length > 48 ? `${value.slice(0, 47).trimEnd()}…` : value;

function findOffer(comparison: CurrentComparison, tourId: string, offerId: string) {
  return comparison.tour_snapshots
    .find((tour) => tour.id === tourId)
    ?.offers.find((offer) => offer.id === offerId);
}

export function VerdictStrip({
  comparison,
  client,
  agentSessionId,
  onOpenDecision,
  layout = 'grid',
}: {
  comparison: CurrentComparison;
  client: CurrentBackendClient | null;
  agentSessionId: string | null;
  onOpenDecision: () => void;
  layout?: 'grid' | 'stack';
}) {
  const { locale, t } = usePreferences();
  const [scenarios, setScenarios] = useState<Record<string, ScenarioState>>({});

  const seen = new Set<string>();
  const strictSlots = (comparison.decision_options ?? []).filter((option) => {
    if (seen.has(option.tour_id) || seen.size >= 3) return false;
    seen.add(option.tour_id);
    return true;
  });
  const relaxedSlots: { relax: CurrentRelaxationOption; tourId: string }[] = [];
  for (const relax of comparison.relaxation_options ?? []) {
    if (seen.size >= 3) break;
    const example = relax.examples.find((item) => !seen.has(item.tour_id));
    if (!example) continue;
    seen.add(example.tour_id);
    relaxedSlots.push({ relax, tourId: example.tour_id });
  }

  async function runRelaxation(relax: CurrentRelaxationOption) {
    if (!client || !agentSessionId || scenarios[relax.condition_id]?.status === 'running') return;
    setScenarios((current) => ({ ...current, [relax.condition_id]: { status: 'running' } }));
    try {
      const response = await client.criteriaScenario(
        comparison.id,
        agentSessionId,
        relaxRequirement(comparison.requirement, relax.condition_id),
      );
      const scenario = response.comparison;
      const trace = scenario?.decision_trace;
      const names = (scenario?.tour_snapshots ?? [])
        .slice(0, 2)
        .map((tour) => tour.name)
        .filter(Boolean);
      setScenarios((current) => ({
        ...current,
        [relax.condition_id]: {
          status: 'done',
          eligibleTours: trace?.eligible_tours ?? scenario?.ranked.length ?? 0,
          eligibleOffers: trace?.eligible_offers ?? 0,
          names,
        },
      }));
    } catch {
      setScenarios((current) => ({
        ...current,
        [relax.condition_id]: {
          status: 'error',
          message: t('Không chạy được kịch bản này.', 'Could not run this scenario.'),
        },
      }));
    }
  }

  if (strictSlots.length === 0 && relaxedSlots.length === 0) return null;
  const relaxedUsed = relaxedSlots.length > 0;

  return (
    <section
      className={styles.strip}
      data-layout={layout}
      aria-label={t('Ba lựa chọn nổi bật', 'Top three options')}
    >
      {relaxedUsed && (
        <p className={styles.banner} role="status">
          {strictSlots.length === 0
            ? t(
                'Không có tour nào đạt đủ điều kiện. Dưới đây là 3 tour gần nhất — mỗi thẻ ghi rõ đã nới điều kiện nào.',
                'No tour meets every condition. Below are the 3 closest tours — each card states what was relaxed.',
              )
            : t(
                'Chưa đủ 3 tour đạt đủ điều kiện. Các thẻ đánh dấu NỚI cần nới điều kiện ghi trên thẻ.',
                'Fewer than 3 tours meet every condition. Cards marked RELAXED need the stated condition relaxed.',
              )}
        </p>
      )}
      <div className={styles.cards}>
        {strictSlots.map((option, index) => {
          const offer = findOffer(comparison, option.tour_id, option.offer_id);
          const tour = comparison.tour_snapshots.find((item) => item.id === option.tour_id);
          const kicker = OBJECTIVE_KICKER[option.objective] ?? OBJECTIVE_KICKER.multi_objective;
          const comparative = option.tradeoffs.find((line) => line.startsWith('So với'));
          const metricName = (key: string) => {
            const name = METRIC_NAMES[key] ?? [key, key];
            return t(...name);
          };
          const strengths = (option.metric_comparisons ?? [])
            .filter((metric) => metric.relation === 'favorable')
            .slice(0, 3)
            .map((metric) => `${metricName(metric.key)}: ${formatMetricValue(metric, t)}`);
          const sacrifices = (option.metric_comparisons ?? [])
            .filter((metric) => metric.relation === 'tradeoff')
            .slice(0, 3)
            .map((metric) =>
              metric.reference_median != null
                ? `${metricName(metric.key)}: ${formatMetricValue(metric, t)} (${t('trung vị', 'median')} ${formatMetricValue({ ...metric, value: metric.reference_median }, t)})`
                : `${metricName(metric.key)}: ${formatMetricValue(metric, t)}`,
            );
          const softConds = [
            ...comparison.requirement.conditions,
            ...(comparison.requirement.alternatives ?? []).flatMap((branch) => branch.conditions),
          ].filter((condition) => condition.strength === 'soft');
          const softWon: string[] = [];
          const softLost: string[] = [];
          const softUnknown: string[] = [];
          for (const condition of softConds) {
            const label = short(String(condition.value ?? ''));
            if (!label) continue;
            const evaluation = (comparison.evaluations ?? []).find(
              (item) => item.offer_id === option.offer_id && item.condition_id === condition.id,
            );
            if (!evaluation || evaluation.state === 'unknown') softUnknown.push(label);
            else if (evaluation.state === 'fail') softLost.push(label);
            else softWon.push(`${label}${evaluation.state === 'partial' ? ` (${t('một phần', 'partial')})` : ''}`);
          }
          const profile = (comparison.metric_profiles ?? []).find(
            (item) => item.tour_id === option.tour_id && item.offer_id === option.offer_id,
          );
          const unpriced = profile?.cost.unpriced_exclusions.length ?? 0;
          const concerns = [
            ...sacrifices,
            ...softLost.map((label) => `${t('chưa đạt', 'missed')}: ${label}`),
            ...softUnknown.map((label) => `${t('chưa rõ', 'unknown')}: ${label}`),
            ...(unpriced > 0
              ? [
                  t(
                    `${unpriced} khoản nhà cung cấp chưa niêm yết — hỏi trước khi đặt`,
                    `${unpriced} items have no listed price — ask before booking`,
                  ),
                ]
              : []),
          ];
          return (
            <article className={styles.card} key={`${option.tour_id}-${option.offer_id}`}>
              <span className={styles.kicker}>{t(...kicker)}</span>
              <h3>
                {t(`Phương án ${index + 1}`, `Option ${index + 1}`)} · {tourName(comparison, option.tour_id, option.tour_id)}
              </h3>
              <p className={styles.numbers}>
                {offer
                  ? `${priceText(offer.price, offer.currency, locale, t)} · ${offer.departure_date || t('chưa rõ ngày', 'date unknown')}`
                  : t('chưa rõ giá', 'price unknown')}
                {tour?.duration_days != null && ` · ${tour.duration_days}N`}
              </p>
              <p className={styles.verdict}>{option.reason}</p>
              {(strengths.length > 0 || softWon.length > 0) && (
                <p className={styles.tradeoff}>
                  {t('Được', 'Pros')}: {[...strengths, ...softWon.slice(0, 3)].join(' · ')}
                </p>
              )}
              {comparative && <p className={styles.tradeoff}>{comparative}</p>}
              {concerns.length > 0 && (
                <p className={styles.caveat}>
                  {t('Cân nhắc', 'Watch out')}: {concerns.join(' · ')}
                </p>
              )}
            </article>
          );
        })}
        {relaxedSlots.map(({ relax, tourId }) => {
          const condition = findCondition(comparison, relax.condition_id);
          const example = relax.examples.find((item) => item.tour_id === tourId) ?? relax.examples[0];
          const state = scenarios[relax.condition_id] ?? { status: 'idle' as const };
          return (
            <article
              className={`${styles.card} ${styles.relaxed}`}
              key={`relax-${relax.condition_id}`}
            >
              <span className={`${styles.kicker} ${styles.relaxedKicker}`}>
                {t('Nới', 'Relaxed')}:{' '}
                {condition
                  ? `${fieldLabel(condition.field, t)} ${conditionText(condition.operator, condition.value, t)}`
                  : relax.condition_id}
              </span>
              <h3>{example?.tour_name || tourName(comparison, tourId, tourId)}</h3>
              <p className={styles.numbers}>
                {example?.price != null
                  ? priceText(example.price, example.currency, locale, t)
                  : t('chưa rõ giá', 'price unknown')}
                {example?.departure_date ? ` · ${example.departure_date}` : ''}
                {` · +${relax.gained_tours} tour`}
              </p>
              <p className={styles.tradeoff}>
                {t(
                  `Bỏ điều kiện này mở thêm ${relax.gained_tours} tour (${relax.gained_offers} offer).`,
                  `Dropping this condition opens ${relax.gained_tours} more tours (${relax.gained_offers} offers).`,
                )}
              </p>
              {state.status === 'idle' && (
                <button
                  type="button"
                  className="btn"
                  disabled={!client || !agentSessionId}
                  onClick={() => void runRelaxation(relax)}
                >
                  {t('Thử nới này', 'Try this relaxation')}
                </button>
              )}
              {state.status === 'running' && (
                <p className={styles.caveat}>{t('Đang chạy kịch bản…', 'Running scenario…')}</p>
              )}
              {state.status === 'done' && (
                <div>
                  <p className={styles.verdict}>
                    {t(
                      `Có ${state.eligibleTours} tour đạt (${state.eligibleOffers} offer) khi nới.`,
                      `${state.eligibleTours} tours qualify (${state.eligibleOffers} offers) when relaxed.`,
                    )}
                    {state.names.length > 0 && ` ${state.names.join(' · ')}`}
                  </p>
                  <button type="button" className="btn" onClick={onOpenDecision}>
                    {t('Xem trong panel quyết định', 'View in decision panel')}
                  </button>
                </div>
              )}
              {state.status === 'error' && <p className={styles.caveat}>{state.message}</p>}
            </article>
          );
        })}
      </div>
    </section>
  );
}
