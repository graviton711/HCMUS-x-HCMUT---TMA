import { AnimatePresence, motion } from 'framer-motion';
import type { CurrentComparison, CurrentCondition, CurrentEvaluation } from '../../../shared/api';
import { safeUrl } from '../../../shared/lib';
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
  const { t } = usePreferences();
  const tour = comparison.tour_snapshots.find((item) => item.id === tourId);
  const offer = tour?.offers.find((item) => item.id === offerId);
  if (!tour || !offer) return null;
  const state = conditionState(comparison, offer.id);
  const url = safeUrl(tour.url || tour.evidence.url);
  const details = evaluationsForOffer(comparison, offer.id);
  const failed = failedDetailsForOffer(comparison, offer.id);
  const label = missing
    ? t(`Gần đạt · thiếu ${failed.length}`, `Near miss · missing ${failed.length}`)
    : state === 'pass'
      ? t('Đã kiểm tra', 'Checked')
      : state === 'fail'
        ? t('Không đạt', 'Does not match')
        : t('Cần xác minh', 'Needs verification');

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
          <dd>
            {offer.price == null
              ? t('Liên hệ', 'Contact')
              : `${offer.price.toLocaleString('vi-VN')} ${offer.currency}`}
          </dd>
        </div>
        <div>
          <dt>{t('Khởi hành', 'Departure')}</dt>
          <dd>
            {offer.departure_date || t('Chưa có ngày', 'No date')} ·{' '}
            {tour.departure_city || t('Chưa rõ nơi đi', 'Unknown city')}
          </dd>
        </div>
        <div>
          <dt>{t('Độ mới', 'Freshness')}</dt>
          <dd>
            {offer.price_freshness}
            {offer.price_trusted
              ? t(' · đã xác thực', ' · trusted')
              : t(' · chưa xác thực', ' · not trusted')}
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
        {url ? (
          <a className={styles['tour-link']} href={url} target="_blank" rel="noreferrer">
            {t('Mở nguồn tour', 'Open tour source')} ↗
          </a>
        ) : (
          <span className="muted">{t('Chưa có nguồn', 'No source')}</span>
        )}
      </div>
    </motion.article>
  );
}

export function ResultCards({
  comparison,
  dropped,
  canUndo,
  busy,
  onRelax,
  onUndo,
}: {
  comparison: CurrentComparison;
  dropped: string[];
  canUndo: boolean;
  busy: boolean;
  onRelax: (field: string) => void;
  onUndo: () => void;
}) {
  const { t } = usePreferences();
  const nearMiss = comparison.near_miss ?? [];
  const worst = mostFailedField(comparison);
  const empty = comparison.ranked.length === 0 && nearMiss.length === 0;

  return (
    <section
      className={styles.result}
      aria-label={t('Kết quả so sánh tour', 'Tour comparison results')}
    >
      <div className={styles['result-summary']}>
        <p className="muted" role="status">
          {empty
            ? t(
                'Chưa có offer nào chứng minh đủ điều kiện. Hãy kiểm tra dữ kiện thiếu hoặc nới 1 điều kiện.',
                'No offer could prove it meets the requirements. Check missing data or relax one condition.',
              )
            : t(
                `${comparison.ranked.length} tour đạt đủ · ${nearMiss.length} tour suýt đạt trong ${comparison.candidates_considered} tour đã xem.`,
                `${comparison.ranked.length} qualified · ${nearMiss.length} near miss of ${comparison.candidates_considered} considered.`,
              )}
        </p>
        <div className={styles['result-counts']}>
          <span className="tag tag-quiet">
            {comparison.ranked.length} {t('đạt đủ', 'qualified')}
          </span>
          {nearMiss.length > 0 && (
            <span className="tag tag-warn">
              {nearMiss.length} {t('gần đạt', 'near miss')}
            </span>
          )}
        </div>
      </div>

      {comparison.ranked.length > 0 && (
        <>
          <h3 className={styles['result-group-title']}>
            {t('Tour đạt đủ điều kiện', 'Qualified tours')}{' '}
            <span>
              {t('xếp theo bậc lọc cứng rồi điểm mềm', 'hard filter first, soft score after')}
            </span>
          </h3>
          <AnimatePresence>
            <motion.div
              variants={staggerParent}
              initial="initial"
              animate="animate"
              className={styles['result-grid']}
            >
              {comparison.ranked.map((entry, index) => (
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
            className="btn btn-primary"
            disabled={busy}
            onClick={() => onRelax(worst.field)}
          >
            {t(
              `Nới điều kiện ${fieldLabel(worst.field, t)} (${worst.count} tour vướng)`,
              `Relax ${fieldLabel(worst.field, t)} (${worst.count} blocked)`,
            )}
          </button>
        )}
        {canUndo && (
          <button type="button" className="btn" disabled={busy} onClick={onUndo}>
            {t('Hoàn tác', 'Undo')}
          </button>
        )}
        {dropped.length > 0 && (
          <span className={styles['result-relaxed']}>
            {t('Đang bỏ qua:', 'Relaxed:')}{' '}
            {dropped.map((field) => fieldLabel(field, t)).join(', ')}
          </span>
        )}
      </div>
    </section>
  );
}
