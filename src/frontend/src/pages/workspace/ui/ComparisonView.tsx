import { useMemo } from "react";
import type {
  CurrentComparison,
  CurrentOffer,
  CurrentTourSnapshot,
} from "../../../shared/api";
import { observedLabel, safeUrl } from "../../../shared/lib";
import { usePreferences } from "../../../shared/preferences";
import {
  conditionState,
  conditionText,
  evaluationsForOffer,
  failedDetailsForOffer,
  fieldLabel,
} from "../../../features/chat";

function TourCard({
  comparison,
  tour,
  offer,
  index,
  nearMiss,
}: {
  comparison: CurrentComparison;
  tour: CurrentTourSnapshot;
  offer: CurrentOffer;
  index: number;
  nearMiss: boolean;
}) {
  const { t, locale } = usePreferences();
  const state = conditionState(comparison, offer.id);
  const url = safeUrl(tour.url || tour.evidence.url);
  const observed = observedLabel(
    offer.evidence.observed_at || tour.observed_at,
    locale,
  );
  const details = evaluationsForOffer(comparison, offer.id);
  const failed = failedDetailsForOffer(comparison, offer.id);
  return (
    <article className="current-tour-card" key={`${tour.id}-${offer.id}`}>
      <div className="current-tour-topline">
        <span className={`current-state ${nearMiss ? "unknown" : state}`}>
          {nearMiss
            ? t(
                `Gần đạt · thiếu ${failed.length}`,
                `Near miss · missing ${failed.length}`,
              )
            : t(
                state === "pass"
                  ? "Đã kiểm tra"
                  : state === "fail"
                    ? "Không đạt"
                    : "Chưa đủ dữ liệu",
                state === "pass"
                  ? "Checked"
                  : state === "fail"
                    ? "Does not match"
                    : "More data needed",
              )}
        </span>
        <span>#{index + 1}</span>
      </div>
      <h3>{tour.name || tour.id}</h3>
      <p className="current-supplier">
        {tour.supplier || t("Chưa rõ nhà cung cấp", "Supplier not listed")}
      </p>
      {nearMiss && failed.length > 0 && (
        <p className="current-missing">
          {t("Chưa đạt:", "Not met:")}{" "}
          {failed
            .map(({ evaluation, condition }) =>
              condition
                ? fieldLabel(condition.field, t)
                : evaluation.condition_id,
            )
            .join(", ")}
        </p>
      )}
      <dl className="current-tour-facts">
        <div>
          <dt>{t("Điểm đến", "Destinations")}</dt>
          <dd>
            {tour.destinations.join(" · ") ||
              t("Chưa có dữ kiện", "Not available")}
          </dd>
        </div>
        <div>
          <dt>{t("Khởi hành", "Departure")}</dt>
          <dd>
            {offer.departure_date || t("Chưa có ngày", "Date unavailable")} ·{" "}
            {tour.departure_city || t("Chưa rõ nơi đi", "City unavailable")}
          </dd>
        </div>
        <div>
          <dt>{t("Giá công bố", "Published price")}</dt>
          <dd>
            {offer.price == null
              ? t("Liên hệ / chưa có giá", "Contact / price unavailable")
              : `${offer.price.toLocaleString("vi-VN")} ${offer.currency || t("chưa rõ tiền tệ", "currency unknown")} (${offer.price_basis})`}
          </dd>
        </div>
        <div>
          <dt>{t("Thời điểm ghi nhận", "Recorded at")}</dt>
          <dd>{observed || t("Chưa rõ", "Unknown")}</dd>
        </div>
      </dl>
      {tour.exclusions && (
        <p>
          <strong>{t("Chưa gồm:", "Exclusions:")}</strong> {tour.exclusions}
        </p>
      )}
      {tour.inclusions && (
        <p>
          <strong>{t("Bao gồm:", "Inclusions:")}</strong> {tour.inclusions}
        </p>
      )}
      {tour.surcharges && (
        <p>
          <strong>{t("Phụ thu:", "Surcharges:")}</strong> {tour.surcharges}
        </p>
      )}
      {details.length > 0 && (
        <details className="current-eval-details">
          <summary>
            {t("Vì sao xếp hạng này", "Why this ranking")} ({details.length})
          </summary>
          <ul className="current-eval-list">
            {details.map(({ evaluation, condition }) => (
              <li key={`${evaluation.offer_id}-${evaluation.condition_id}`}>
                <span className={`current-state ${evaluation.state}`}>
                  {evaluation.state === "pass"
                    ? t("Đạt", "Pass")
                    : evaluation.state === "partial"
                      ? t("Đạt một phần", "Partial")
                      : evaluation.state === "fail"
                        ? t("Không đạt", "Fail")
                        : t("Chưa rõ", "Unknown")}
                </span>
                <span>
                  {condition
                    ? `${fieldLabel(condition.field, t)} ${conditionText(condition.operator, condition.value, t)}`
                    : evaluation.condition_id}
                </span>
                {evaluation.quote && (
                  <q cite={url ?? undefined}>{evaluation.quote}</q>
                )}
                {evaluation.reason_code && (
                  <code>{evaluation.reason_code}</code>
                )}
              </li>
            ))}
          </ul>
        </details>
      )}
      {url && (
        <a href={url} target="_blank" rel="noreferrer">
          {t("Mở nguồn tour", "Open tour source")}
        </a>
      )}
    </article>
  );
}

export function ComparisonView({
  comparison,
}: {
  comparison: CurrentComparison;
}) {
  const { t } = usePreferences();
  const tourById = useMemo(
    () =>
      new Map(
        (comparison?.tour_snapshots ?? []).map((tour) => [tour.id, tour]),
      ),
    [comparison],
  );
  const nearMiss = comparison.near_miss ?? [];

  function cards(
    entries: { tour_id: string; offer_id: string }[],
    isNearMiss: boolean,
  ) {
    return (
      <div className="current-tour-list">
        {entries.map((entry, index) => {
          const tour = tourById.get(entry.tour_id);
          const offer = tour?.offers.find((item) => item.id === entry.offer_id);
          if (!tour || !offer) return null;
          return (
            <TourCard
              key={`${tour.id}-${offer.id}`}
              comparison={comparison}
              tour={tour}
              offer={offer}
              index={index}
              nearMiss={isNearMiss}
            />
          );
        })}
      </div>
    );
  }

  return (
    <section
      className="current-results"
      aria-labelledby="current-results-title"
    >
      <div className="current-results-heading">
        <div>
          <span className="eyebrow">
            {t("KẾT QUẢ CÓ LƯU SNAPSHOT", "PERSISTED SNAPSHOT")}
          </span>
          <h2 id="current-results-title">
            {t("Các tour có thể đối chiếu", "Tours available for comparison")}
          </h2>
        </div>
        <small>
          {comparison.candidates_considered}{" "}
          {t("tour đã xem", "tours considered")}
        </small>
      </div>
      {comparison.ranked.length === 0 && nearMiss.length === 0 ? (
        <p className="notice">
          {t(
            "Chưa có offer nào đáp ứng đủ điều kiện theo dữ liệu hiện có. Điều này không đồng nghĩa không có tour phù hợp; hãy kiểm tra dữ kiện còn thiếu.",
            "No offer meets all requirements based on available data. This does not mean no suitable tour exists; check which information is missing.",
          )}
        </p>
      ) : (
        cards(comparison.ranked, false)
      )}
      {nearMiss.length > 0 && (
        <section aria-labelledby="near-miss-title">
          <h3 id="near-miss-title">
            {t(
              "Gần đạt — thiếu ít điều kiện",
              "Near miss — missing a few conditions",
            )}
          </h3>
          <p className="current-hint">
            {t(
              "Các tour này không vào nhóm đạt đủ, xếp theo số điều kiện đã đạt.",
              "These tours did not fully qualify, ordered by conditions met.",
            )}
          </p>
          {cards(nearMiss, true)}
        </section>
      )}
      <div className="current-analysis">
        {comparison.analysis.conditions.length > 0 && (
          <div>
            <h3>{t("Điều kiện áp dụng", "Applicable conditions")}</h3>
            <ul>
              {comparison.analysis.conditions.map((item, index) => (
                <li key={index}>{item}</li>
              ))}
            </ul>
          </div>
        )}
        {comparison.analysis.benefits.length > 0 && (
          <div>
            <h3>{t("Điểm đáng giá", "Notable benefits")}</h3>
            <ul>
              {comparison.analysis.benefits.map((item, index) => (
                <li key={index}>{item}</li>
              ))}
            </ul>
          </div>
        )}
        {comparison.analysis.risks.length > 0 && (
          <div>
            <h3>{t("Điểm cần lưu ý", "Risks to review")}</h3>
            <ul>
              {comparison.analysis.risks.map((item, index) => (
                <li key={index}>{item}</li>
              ))}
            </ul>
          </div>
        )}
        {comparison.analysis.hidden_costs.length > 0 && (
          <div>
            <h3>{t("Chi phí cần kiểm tra", "Costs to verify")}</h3>
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
