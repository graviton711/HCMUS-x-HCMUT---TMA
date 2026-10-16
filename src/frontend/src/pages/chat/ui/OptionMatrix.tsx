import type { ReactNode } from 'react';
import type {
  CurrentComparison,
  CurrentDecisionOption,
  CurrentMetricProfile,
} from '../../../shared/api';
import { METRIC_NAMES, METRIC_RELATIONS, formatMetricValue } from '../../../features/chat';
import { priceText } from '../../../shared/lib';
import { usePreferences } from '../../../shared/preferences';
import styles from './DecisionWorkspace.module.css';

/** Full-width option × metric matrix. Columns are decision_options in order;
 *  rows read values straight from offer snapshots, cost profiles and the
 *  option's own metric_comparisons. Unknown cells render Chưa rõ, never zeros.
 */
export function OptionMatrix({ comparison }: { comparison: CurrentComparison }) {
  const { t, locale } = usePreferences();
  const options = (comparison.decision_options ?? []).slice(0, 3);
  if (options.length === 0) return null;

  const tours = new Map(comparison.tour_snapshots.map((tour) => [tour.id, tour]));
  const profiles = new Map(
    (comparison.metric_profiles ?? []).map((profile) => [
      `${profile.tour_id}:${profile.offer_id}`,
      profile,
    ]),
  );

  const findOffer = (option: CurrentDecisionOption) =>
    tours.get(option.tour_id)?.offers.find((offer) => offer.id === option.offer_id);
  const findProfile = (option: CurrentDecisionOption): CurrentMetricProfile | undefined =>
    profiles.get(`${option.tour_id}:${option.offer_id}`);
  const findComparison = (option: CurrentDecisionOption, key: string) =>
    (option.metric_comparisons ?? []).find((metric) => metric.key === key);

  const chip = (relation: string | undefined) => {
    if (!relation || relation === 'unknown') return null;
    const label = METRIC_RELATIONS[relation] ?? METRIC_RELATIONS.unknown;
    return (
      <span className={styles['matrix-chip']} data-relation={relation}>
        {t(...label)}
      </span>
    );
  };

  const metricCell = (option: CurrentDecisionOption, key: string) => {
    const metric = findComparison(option, key);
    if (!metric) return t('Chưa rõ', 'Unknown');
    return (
      <>
        {formatMetricValue(metric, t)} {chip(metric.relation)}
      </>
    );
  };

  const hiddenCell = (option: CurrentDecisionOption) => {
    const profile = findProfile(option);
    if (!profile) return t('Chưa rõ', 'Unknown');
    const unpriced = profile.cost.unpriced_exclusions.length;
    const conditional = profile.cost.optional_or_conditional.filter(
      (item) => item.obligation === 'conditional',
    ).length;
    if (unpriced === 0 && conditional === 0)
      return t('Không có khoản ẩn', 'No hidden charges');
    return t(
      `${unpriced} chưa định giá · ${conditional} có điều kiện`,
      `${unpriced} unpriced · ${conditional} conditional`,
    );
  };

  const rows: { key: string; label: [string, string]; render: (option: CurrentDecisionOption) => ReactNode }[] = [
    {
      key: 'price',
      label: ['Giá công bố', 'Published price'],
      render: (option) => {
        const offer = findOffer(option);
        if (!offer) return t('Chưa rõ', 'Unknown');
        return priceText(offer.price, offer.currency, locale, t);
      },
    },
    { key: 'group_total', label: METRIC_NAMES.group_total, render: (option) => metricCell(option, 'group_total') },
    {
      key: 'hidden',
      label: ['Khoản ẩn', 'Hidden charges'],
      render: hiddenCell,
    },
    { key: 'preference_fit', label: METRIC_NAMES.preference_fit, render: (option) => metricCell(option, 'preference_fit') },
    { key: 'experience_density', label: METRIC_NAMES.experience_density, render: (option) => metricCell(option, 'experience_density') },
    { key: 'route_complexity', label: METRIC_NAMES.route_complexity, render: (option) => metricCell(option, 'route_complexity') },
    { key: 'included_coverage', label: METRIC_NAMES.included_coverage, render: (option) => metricCell(option, 'included_coverage') },
  ];

  return (
    <section className={styles.optionMatrix} aria-label={t('Bảng so sánh phương án', 'Option comparison table')}>
      <h3>{t('So kè trực quan', 'Side-by-side comparison')}</h3>
      <div className={styles['optionMatrix-scroll']}>
        <table className={styles['optionMatrix-table']}>
          <thead>
            <tr>
              <th scope="col">
                <span className="sr-only">{t('Tiêu chí', 'Criterion')}</span>
              </th>
              {options.map((option, index) => {
                const tour = tours.get(option.tour_id);
                return (
                  <th scope="col" key={`${option.tour_id}-${option.offer_id}`}>
                    {t(`Phương án ${index + 1}`, `Option ${index + 1}`)}
                    <small>{tour?.name ?? option.tour_id}</small>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key}>
                <th scope="row">{t(...row.label)}</th>
                {options.map((option) => (
                  <td key={`${option.tour_id}-${option.offer_id}`}>{row.render(option)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
