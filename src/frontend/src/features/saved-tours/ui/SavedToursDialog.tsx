import { usePreferences } from "../../../shared/preferences";
import { safeUrl } from "../../../shared/lib";
import { Dialog, Icon } from "../../../shared/ui";
import type { SavedTour } from "../model";
import styles from "./SavedToursDialog.module.css";

const FIELD_LABEL: Record<string, [string, string]> = {
  destination: ["Điểm đến", "Destination"],
  departure_city: ["Nơi khởi hành", "Departure city"],
  transport: ["Phương tiện", "Transport"],
  accommodation: ["Lưu trú", "Accommodation"],
  duration_days: ["Thời lượng", "Duration"],
  date_from: ["Khởi hành từ", "Departure from"],
  date_to: ["Khởi hành đến", "Departure by"],
  budget_max: ["Ngân sách", "Budget"],
  preference: ["Ưu tiên", "Preference"],
};

function valueText(value: unknown, locale: string): string {
  if (typeof value === "string") return value;
  if (typeof value === "number")
    return value.toLocaleString(locale === "vi" ? "vi-VN" : "en-GB");
  if (Array.isArray(value))
    return value.map((item) => valueText(item, locale)).join(", ");
  return value == null ? "" : String(value);
}

function dateText(value: string, locale: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!match) return value;
  return new Date(
    Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])),
  ).toLocaleDateString(locale === "vi" ? "vi-VN" : "en-GB", {
    timeZone: "UTC",
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function dateTimeText(value: string, locale: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(locale === "vi" ? "vi-VN" : "en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function priceText(
  tour: SavedTour,
  locale: string,
  t: (vi: string, en: string) => string,
) {
  if (tour.price == null)
    return t("Liên hệ", "Contact");
  const amount = tour.price.toLocaleString(locale === "vi" ? "vi-VN" : "en-GB");
  const currency = tour.currency
    ? ` ${tour.currency}`
    : t(" · chưa rõ tiền tệ", " · currency unknown");
  return `${amount}${currency}`;
}

export function SavedToursDialog({
  open,
  savedTours,
  onClose,
  onRemove,
}: {
  open: boolean;
  savedTours: SavedTour[];
  onClose: () => void;
  onRemove: (id: string) => void;
}) {
  const { t, locale } = usePreferences();
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={t("Tour đã lưu", "Saved tours")}
      description={t(
        "Các lựa chọn được lưu trên trình duyệt này, kèm dữ kiện và nguồn lúc bạn lưu.",
        "Tours saved in this browser with the details and source available when you saved them.",
      )}
      closeLabel={t("Đóng danh mục đã lưu", "Close saved tours")}
    >
      {savedTours.length ? (
        <ul className={styles.list}>
          {savedTours.map((tour) => {
            const url = safeUrl(tour.sourceUrl);
            return (
              <li key={tour.id} className={styles.item}>
                <div className={styles.top}>
                  <div className={styles.heading}>
                    <h3>{tour.name}</h3>
                    {tour.supplier && <p>{tour.supplier}</p>}
                  </div>
                  <button
                    className={styles.remove}
                    type="button"
                    aria-label={t(
                      `Bỏ lưu ${tour.name}`,
                      `Remove ${tour.name} from saved tours`,
                    )}
                    title={t("Bỏ lưu", "Remove saved tour")}
                    onClick={() => onRemove(tour.id)}
                  >
                    <Icon name="trash" size={16} />
                  </button>
                </div>

                <p className={styles.route}>
                  {[...tour.destinations].join(" · ") ||
                    tour.route.join(" → ") ||
                    t("Chưa rõ điểm đến", "Destination not listed")}
                </p>

                <dl className={styles.facts}>
                  <div>
                    <dt>{t("Khởi hành", "Departure")}</dt>
                    <dd>
                      {tour.departureDate
                        ? dateText(tour.departureDate, locale)
                        : t("Chưa có ngày", "No date")}
                    </dd>
                  </div>
                  <div>
                    <dt>{t("Giá", "Price")}</dt>
                    <dd>{priceText(tour, locale, t)}</dd>
                  </div>
                  {tour.durationDays != null && (
                    <div>
                      <dt>{t("Thời lượng", "Duration")}</dt>
                      <dd>
                        {t(
                          `${tour.durationDays} ngày`,
                          `${tour.durationDays} days`,
                        )}
                      </dd>
                    </div>
                  )}
                  {tour.departureCity && (
                    <div>
                      <dt>{t("Nơi đi", "From")}</dt>
                      <dd>{tour.departureCity}</dd>
                    </div>
                  )}
                  {tour.availability && (
                    <div>
                      <dt>{t("Tình trạng", "Availability")}</dt>
                      <dd>{tour.availability}</dd>
                    </div>
                  )}
                </dl>

                {tour.evaluations.length > 0 && (
                  <details className={styles.evidence}>
                    <summary>
                      {t("Điều kiện đã đối chiếu", "Compared criteria")}
                    </summary>
                    <ul>
                      {tour.evaluations.map((evaluation) => (
                        <li key={evaluation.condition.id}>
                          <span
                            data-state={evaluation.state}
                            className={styles.state}
                          >
                            {evaluation.state === "pass"
                              ? t("Đạt", "Pass")
                              : evaluation.state === "partial"
                                ? t("Đạt một phần", "Partial")
                                : evaluation.state === "fail"
                                  ? t("Không đạt", "Fail")
                                  : t("Chưa rõ", "Unknown")}
                          </span>
                          <span>
                            {t(
                              ...(FIELD_LABEL[evaluation.condition.field] ?? [
                                evaluation.condition.field,
                                evaluation.condition.field,
                              ]),
                            )}
                            {evaluation.condition.value != null && (
                              <>
                                {" "}
                                ·{" "}
                                {valueText(evaluation.condition.value, locale)}
                              </>
                            )}
                          </span>
                          {evaluation.quote && <q>{evaluation.quote}</q>}
                        </li>
                      ))}
                    </ul>
                  </details>
                )}

                <div className={styles.foot}>
                  {url ? (
                    <a href={url} target="_blank" rel="noreferrer">
                      {t("Mở nguồn", "Open source")}{" "}
                      <span aria-hidden="true">↗</span>
                    </a>
                  ) : (
                    <span>
                      {t("Không có liên kết nguồn", "Source link unavailable")}
                    </span>
                  )}
                  <span>
                    {tour.observedAt
                      ? t(
                          `Ghi nhận ${dateTimeText(tour.observedAt, locale)}`,
                          `Observed ${dateTimeText(tour.observedAt, locale)}`,
                        )
                      : t(
                          "Chưa rõ thời điểm ghi nhận",
                          "Observation time unknown",
                        )}
                  </span>
                </div>
              </li>
            );
          })}
        </ul>
      ) : (
        <div className={styles.empty}>
          <Icon name="bookmark" size={22} />
          <h3>{t("Chưa có tour nào được lưu", "No saved tours yet")}</h3>
          <p>
            {t(
              "Dùng nút Lưu trên một kết quả để thêm tour vào đây.",
              "Use Save on a result to add a tour here.",
            )}
          </p>
        </div>
      )}
    </Dialog>
  );
}
