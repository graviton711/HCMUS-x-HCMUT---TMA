import { useMemo } from 'react';
import type { CurrentComparison } from '../../../shared/api';
import { safeUrl } from '../../../shared/lib';
import { usePreferences } from '../../../shared/preferences';
import { conditionState } from '../lib/format';

export function ComparisonView({ comparison }: { comparison: CurrentComparison }) {
  const { t } = usePreferences();
  const tourById = useMemo(
    () => new Map((comparison?.tour_snapshots ?? []).map((tour) => [tour.id, tour])),
    [comparison],
  );

  return (
    <section className="current-results" aria-labelledby="current-results-title">
      <div className="current-results-heading">
        <div>
          <span className="eyebrow">{t('KẾT QUẢ CÓ LƯU SNAPSHOT', 'PERSISTED SNAPSHOT')}</span>
          <h2 id="current-results-title">
            {t('Các tour có thể đối chiếu', 'Tours available for comparison')}
          </h2>
        </div>
        <small>
          {comparison.candidates_considered} {t('tour đã xem', 'tours considered')}
        </small>
      </div>
      {comparison.ranked.length === 0 ? (
        <p className="notice">
          {t(
            'Chưa có offer nào chứng minh đủ điều kiện. Đây không đồng nghĩa không có tour phù hợp; hãy kiểm tra dữ kiện thiếu hoặc chưa xác minh.',
            'No offer could prove it meets the requirements. This does not prove no suitable tour exists; check missing or unverified data.',
          )}
        </p>
      ) : (
        <div className="current-tour-list">
          {comparison.ranked.map((ranked, index) => {
            const tour = tourById.get(ranked.tour_id);
            const offer = tour?.offers.find((item) => item.id === ranked.offer_id);
            if (!tour || !offer) return null;
            const state = conditionState(comparison, offer.id);
            const url = safeUrl(tour.url || tour.evidence.url);
            return (
              <article className="current-tour-card" key={`${tour.id}-${offer.id}`}>
                <div className="current-tour-topline">
                  <span className={`current-state ${state}`}>
                    {t(
                      state === 'pass'
                        ? 'Đã kiểm tra'
                        : state === 'fail'
                          ? 'Không đạt'
                          : 'Cần xác minh',
                      state === 'pass'
                        ? 'Checked'
                        : state === 'fail'
                          ? 'Does not match'
                          : 'Needs verification',
                    )}
                  </span>
                  <span>#{index + 1}</span>
                </div>
                <h3>{tour.name || tour.id}</h3>
                <p className="current-supplier">
                  {tour.supplier || t('Chưa rõ nhà cung cấp', 'Supplier not listed')}
                </p>
                <dl className="current-tour-facts">
                  <div>
                    <dt>{t('Điểm đến', 'Destinations')}</dt>
                    <dd>
                      {tour.destinations.join(' · ') || t('Chưa có dữ kiện', 'Not available')}
                    </dd>
                  </div>
                  <div>
                    <dt>{t('Khởi hành', 'Departure')}</dt>
                    <dd>
                      {offer.departure_date || t('Chưa có ngày', 'Date unavailable')} ·{' '}
                      {tour.departure_city || t('Chưa rõ nơi đi', 'City unavailable')}
                    </dd>
                  </div>
                  <div>
                    <dt>{t('Giá công bố', 'Published price')}</dt>
                    <dd>
                      {offer.price == null
                        ? t('Liên hệ / chưa có giá', 'Contact / price unavailable')
                        : `${offer.price.toLocaleString()} ${offer.currency} (${offer.price_basis})`}
                    </dd>
                  </div>
                  <div>
                    <dt>{t('Độ mới / tin cậy', 'Freshness / trust')}</dt>
                    <dd>
                      {offer.price_freshness} ·{' '}
                      {offer.price_trusted
                        ? t('đã xác thực metadata', 'metadata trusted')
                        : t('chưa xác thực', 'not trusted')}
                    </dd>
                  </div>
                </dl>
                {tour.exclusions && (
                  <p>
                    <strong>{t('Chưa gồm:', 'Exclusions:')}</strong> {tour.exclusions}
                  </p>
                )}
                {tour.inclusions && (
                  <p>
                    <strong>{t('Bao gồm:', 'Inclusions:')}</strong> {tour.inclusions}
                  </p>
                )}
                {tour.surcharges && (
                  <p>
                    <strong>{t('Phụ thu:', 'Surcharges:')}</strong> {tour.surcharges}
                  </p>
                )}
                {url && (
                  <a href={url} target="_blank" rel="noreferrer">
                    {t('Mở nguồn tour', 'Open tour source')}
                  </a>
                )}
              </article>
            );
          })}
        </div>
      )}
      <div className="current-analysis">
        {comparison.analysis.risks.length > 0 && (
          <div>
            <h3>{t('Điểm cần lưu ý', 'Risks to review')}</h3>
            <ul>
              {comparison.analysis.risks.map((item, index) => (
                <li key={index}>{item}</li>
              ))}
            </ul>
          </div>
        )}
        {comparison.analysis.hidden_costs.length > 0 && (
          <div>
            <h3>{t('Chi phí cần kiểm tra', 'Costs to verify')}</h3>
            <ul>
              {comparison.analysis.hidden_costs.map((item, index) => (
                <li key={index}>{item}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </section>
  );
}
