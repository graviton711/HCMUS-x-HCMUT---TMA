import { AnimatePresence, motion } from 'framer-motion';
import type { CurrentComparison, CurrentCondition, CurrentEvaluation } from '../../../shared/api';
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
import styles from './chat.module.css';

function uniqueTours<T extends { tour_id: string }>(candidates: T[]): T[] {
  const seen = new Set<string>();
  return candidates.filter((candidate) => {
    if (seen.has(candidate.tour_id)) return false;
    seen.add(candidate.tour_id);
    return true;
  });
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
}: {
  comparison: CurrentComparison;
  tourId: string;
  offerId: string;
  index: number;
  missing: boolean;
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
          offer.currency
            ? ` ${offer.currency}`
            : ` · ${t('chưa rõ tiền tệ', 'currency unknown')}`,
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
      </div>
    </motion.article>
  );
}

export function ResultCards({
  comparison,
  busy,
  onRelax,
}: {
  comparison: CurrentComparison;
  busy: boolean;
  onRelax: (field: string) => void;
}) {
  const { t } = usePreferences();
  const ranked = uniqueTours(comparison.ranked);
  const rankedTourIds = new Set(ranked.map((candidate) => candidate.tour_id));
  const nearMiss = uniqueTours(comparison.near_miss ?? []).filter(
    (candidate) => !rankedTourIds.has(candidate.tour_id),
  );
  const worst = mostFailedField(comparison);
  const empty = ranked.length === 0 && nearMiss.length === 0;

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
                `${ranked.length} tour đạt đủ · ${nearMiss.length} tour suýt đạt trong ${comparison.candidates_considered} tour đã xem.`,
                `${ranked.length} qualified · ${nearMiss.length} near miss of ${comparison.candidates_considered} considered.`,
              )}
        </p>
        <div className={styles['result-counts']}>
          <span className="tag tag-quiet">
            {ranked.length} {t('đạt đủ', 'qualified')}
          </span>
          {nearMiss.length > 0 && (
            <span className="tag tag-warn">
              {nearMiss.length} {t('gần đạt', 'near miss')}
            </span>
          )}
        </div>
      </div>

      {ranked.length > 0 && (
        <>
          <h3 className={styles['result-group-title']}>
            {t('Tour đạt đủ điều kiện', 'Qualified tours')}{' '}
            <span>
              {t('xếp theo số tiêu chí phù hợp rồi giá', 'ordered by fit verdicts, then price')}
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
              />
            ))}
          </div>
        </>
      )}

      <div className={styles['result-actions']}>
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
    </section>
  );
}
