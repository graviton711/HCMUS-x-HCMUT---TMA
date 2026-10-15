import type { CurrentComparison, CurrentCondition, CurrentEvaluation } from '../../../shared/api';
import { safeUrl } from '../../../shared/lib';
import { usePreferences } from '../../../shared/preferences';
import { Dialog } from '../../../shared/ui';
import { conditionText, fieldLabel } from '../lib/format';
import styles from './DecisionComparisonDialog.module.css';

export interface ComparedOffer {
  tourId: string;
  offerId: string;
}

function observedDate(value: string, locale: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!match) return value;
  return new Date(
    Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])),
  ).toLocaleDateString(locale === 'vi' ? 'vi-VN' : 'en-GB', {
    timeZone: 'UTC',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
}

function priceText(
  price: number | null,
  currency: string,
  locale: string,
  t: (vi: string, en: string) => string,
) {
  if (price == null) return t('Liên hệ', 'Contact');
  const amount = price.toLocaleString(locale === 'vi' ? 'vi-VN' : 'en-GB');
  const currencyLabel = currency ? ` ${currency}` : t(' · chưa rõ tiền tệ', ' · currency unknown');
  return `${amount}${currencyLabel}`;
}

function statusText(state: CurrentEvaluation['state'], t: (vi: string, en: string) => string) {
  if (state === 'pass') return t('Đạt', 'Pass');
  if (state === 'partial') return t('Đạt một phần', 'Partial');
  if (state === 'fail') return t('Không đạt', 'Fail');
  return t('Chưa rõ', 'Unknown');
}

export function DecisionComparisonDialog({
  comparison,
  selected,
  open,
  onClose,
}: {
  comparison: CurrentComparison;
  selected: ComparedOffer[];
  open: boolean;
  onClose: () => void;
}) {
  const { t, locale } = usePreferences();
  const candidates = selected.flatMap((entry) => {
    const tour = comparison.tour_snapshots.find((item) => item.id === entry.tourId);
    const offer = tour?.offers.find((item) => item.id === entry.offerId);
    return tour && offer ? [{ entry, tour, offer }] : [];
  });

  const attributeRows: {
    key: string;
    label: string;
    value: (item: (typeof candidates)[number]) => string;
  }[] = [
    {
      key: 'destinations',
      label: t('Điểm đến', 'Destinations'),
      value: ({ tour }) => tour.destinations.join(' · ') || t('Chưa có dữ liệu', 'Not listed'),
    },
    {
      key: 'route',
      label: t('Tuyến', 'Route'),
      value: ({ tour }) => tour.route.join(' → ') || t('Chưa có dữ liệu', 'Not listed'),
    },
    {
      key: 'departure',
      label: t('Khởi hành', 'Departure'),
      value: ({ tour, offer }) =>
        [offer.departure_date, tour.departure_city].filter(Boolean).join(' · ') ||
        t('Chưa có dữ liệu', 'Not listed'),
    },
    {
      key: 'duration',
      label: t('Thời lượng', 'Duration'),
      value: ({ tour }) =>
        tour.duration_days == null
          ? t('Chưa có dữ liệu', 'Not listed')
          : t(`${tour.duration_days} ngày`, `${tour.duration_days} days`),
    },
    {
      key: 'transport',
      label: t('Phương tiện', 'Transport'),
      value: ({ tour }) => tour.transport || t('Chưa có dữ liệu', 'Not listed'),
    },
    {
      key: 'price',
      label: t('Giá', 'Price'),
      value: ({ offer }) => priceText(offer.price, offer.currency, locale, t),
    },
    {
      key: 'availability',
      label: t('Tình trạng', 'Availability'),
      value: ({ offer }) => offer.availability || t('Chưa rõ', 'Unknown'),
    },
  ];

  const alternatives = comparison.requirement.alternatives ?? [];
  const conditions = [
    ...comparison.requirement.conditions,
    ...alternatives.flatMap((alternative) => alternative.conditions),
  ];
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={t('So sánh theo dữ kiện', 'Compare evidence')}
      description={t(
        'Các lựa chọn trong cùng một lượt tìm, đối chiếu theo cùng điều kiện agent đã dùng.',
        'Options from one search, compared against the same criteria used by the agent.',
      )}
      closeLabel={t('Đóng bảng so sánh', 'Close comparison')}
      size="wide"
    >
      <div
        className={styles.scroll}
        role="region"
        aria-label={t(
          'Bảng so sánh tour, cuộn ngang nếu cần',
          'Tour comparison table, scroll horizontally if needed',
        )}
        tabIndex={0}
      >
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col">{t('Tiêu chí', 'Criteria')}</th>
              {candidates.map(({ entry, tour }) => (
                <th scope="col" key={entry.offerId}>
                  <span className={styles.tourName}>{tour.name || tour.id}</span>
                  <span className={styles.supplier}>
                    {tour.supplier || t('Nhà cung cấp chưa rõ', 'Supplier not listed')}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {attributeRows.map((row) => (
              <tr key={row.key}>
                <th scope="row">{row.label}</th>
                {candidates.map((candidate) => (
                  <td key={candidate.entry.offerId}>{row.value(candidate)}</td>
                ))}
              </tr>
            ))}
            {conditions.map((condition: CurrentCondition) => (
              <tr key={condition.id}>
                <th scope="row">
                  <span className={styles.strength} data-strength={condition.strength}>
                    {condition.strength === 'hard'
                      ? t('Bắt buộc', 'Required')
                      : t('Ưu tiên', 'Preference')}
                  </span>
                  <span className={styles.conditionLabel}>
                    {(() => {
                      const branch = alternatives.find((item) =>
                        item.conditions.some(
                          (candidateCondition) => candidateCondition.id === condition.id,
                        ),
                      );
                      return branch ? `${branch.label} · ` : '';
                    })()}
                    {fieldLabel(condition.field, t)}{' '}
                    {conditionText(condition.operator, condition.value, t)}
                  </span>
                </th>
                {candidates.map((candidate) => {
                  const evaluation = comparison.evaluations.find(
                    (item) =>
                      item.offer_id === candidate.entry.offerId &&
                      item.condition_id === condition.id,
                  );
                  const state = evaluation?.state ?? 'unknown';
                  return (
                    <td key={candidate.entry.offerId}>
                      <span className={styles.state} data-state={state}>
                        {statusText(state, t)}
                      </span>
                      {evaluation?.quote && <q className={styles.quote}>{evaluation.quote}</q>}
                    </td>
                  );
                })}
              </tr>
            ))}
            <tr>
              <th scope="row">{t('Nguồn và thời điểm', 'Source and observed')}</th>
              {candidates.map(({ entry, tour, offer }) => {
                const source = safeUrl(offer.evidence.url || tour.url || tour.evidence.url);
                const observed = offer.evidence.observed_at || tour.observed_at;
                return (
                  <td key={entry.offerId}>
                    {source ? (
                      <a className={styles.source} href={source} target="_blank" rel="noreferrer">
                        {t('Mở nguồn', 'Open source')} ↗
                      </a>
                    ) : (
                      <span>{t('Không có liên kết', 'No link')}</span>
                    )}
                    <span className={styles.observed}>
                      {observed
                        ? observedDate(observed, locale)
                        : t('Chưa rõ thời điểm', 'Time unknown')}
                    </span>
                  </td>
                );
              })}
            </tr>
          </tbody>
        </table>
      </div>
    </Dialog>
  );
}
