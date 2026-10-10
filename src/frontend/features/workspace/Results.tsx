import { useId, useRef, useState, type KeyboardEvent } from 'react';
import type {
  Comparison,
  ComparisonCell,
  ComparisonColumn,
  ComparisonResult,
  ComparisonRow,
  Job,
  JobEvent,
  Metric,
  Offer,
  Recommendation,
} from '../../api/types';
import { usePreferences, type Locale } from '../../app/preferences';
import { Icon } from '../../components/Icon';

type Translate = (vi: string, en: string) => string;

const labels: Record<string, [string, string]> = {
  present: ['Có dữ kiện', 'Data available'],
  missing: ['Chưa có dữ kiện', 'Missing data'],
  conflicting: ['Dữ kiện mâu thuẫn', 'Conflicting data'],
  invalid: ['Dữ kiện không hợp lệ', 'Invalid data'],
  unsupported: ['Chưa hỗ trợ', 'Unsupported'],
  supplier_published: ['Nhà cung cấp công bố', 'Supplier published'],
  catalog_validated: ['Đã kiểm tra bản ghi catalog', 'Catalog record validated'],
  independently_verified: ['Đã xác minh độc lập', 'Independently verified'],
  unverified: ['Chưa xác minh', 'Unverified'],
  complete: ['Đầy đủ', 'Complete'],
  partial: ['Một phần', 'Partial'],
  unknown: ['Chưa rõ', 'Unknown'],
  fresh: ['Còn mới theo nguồn', 'Fresh under source policy'],
  stale: ['Dữ liệu đã cũ', 'Stale data'],
  pass: ['Đạt', 'Pass'],
  fail: ['Không đạt', 'Fail'],
  not_evaluated: ['Chưa đánh giá', 'Not evaluated'],
  matched: ['Đáp ứng', 'Matched'],
  not_matched: ['Chưa đáp ứng', 'Not matched'],
  per_adult: ['người lớn', 'adult'],
  per_child: ['trẻ em', 'child'],
  per_infant: ['em bé', 'infant'],
  per_person: ['người', 'person'],
  per_room: ['phòng', 'room'],
  per_group: ['nhóm', 'group'],
  group_total: ['cả nhóm', 'group total'],
  tour_price: ['Giá tour', 'Tour price'],
  trip_total: ['Tổng chuyến đi', 'Trip total'],
  unspecified: ['Chưa rõ phạm vi giá', 'Price coverage unspecified'],
  cost: ['Chi phí', 'Cost'],
  estimated_cost: ['Chi phí', 'Cost'],
  comfort: ['Tiện nghi', 'Comfort'],
  pace: ['Nhịp đi', 'Pace'],
  culture: ['Văn hóa', 'Culture'],
  departure_date: ['Ngày khởi hành', 'Departure date'],
  return_date: ['Ngày về', 'Return date'],
  departure_origin: ['Nơi khởi hành', 'Departure origin'],
  duration_days: ['Thời lượng', 'Duration'],
  duration_nights: ['Số đêm', 'Nights'],
  destinations: ['Điểm đến', 'Destinations'],
  hotel_stars_min: ['Khách sạn', 'Hotel stars'],
  shopping_stops: ['Điểm mua sắm', 'Shopping stops'],
  flight_stops: ['Chặng dừng', 'Flight stops'],
  transport: ['Phương tiện', 'Transport'],
  included_services: ['Dịch vụ bao gồm', 'Included services'],
  supplier: ['Nhà cung cấp', 'Supplier'],
  tour_type: ['Loại tour', 'Tour type'],
  route: ['Hành trình', 'Route'],
  nature: ['Gần thiên nhiên', 'Nature'],
  supplier_reputation: ['Uy tín nhà cung cấp', 'Supplier reputation'],
  service_quality: ['Chất lượng dịch vụ', 'Service quality'],
  price_value: ['Giá hợp lý', 'Price value'],
  availability: ['Số chỗ công bố', 'Published availability'],
  availability_status: ['Trạng thái đặt chỗ công bố', 'Published booking status'],
  published_price: ['Giá tour công bố', 'Published tour price'],
  itinerary: ['Lịch trình công bố', 'Published itinerary'],
  price_quotes: ['Giá công bố', 'Published prices'],
  listed_price_quotes: ['Giá tour niêm yết / người lớn', 'Listed tour price / adult'],
  extra_charges: ['Phụ thu', 'Extra charges'],
  pricing_complete: ['Độ đầy đủ giá', 'Pricing completeness'],
  unclassified_prices: [
    'Giá theo nhóm tuổi — chưa rõ điều kiện',
    'Age group prices — conditions unclear',
  ],
  single_supplement: [
    'Phụ thu phòng đơn — chưa rõ điều kiện',
    'Single supplement — conditions unclear',
  ],
  'policies.cancellation': ['Chính sách hủy', 'Cancellation policy'],
  days: ['ngày', 'days'],
  nights: ['đêm', 'nights'],
  adults: ['Người lớn', 'Adults'],
  children_count: ['Số trẻ em', 'Children'],
  rooming: ['Điều kiện phòng', 'Rooming'],
  unresolved: ['Điều kiện chưa rõ', 'Unresolved condition'],
  'party.adults': ['Số người lớn đã xác nhận', 'Confirmed adults'],
  ordered: ['Theo thứ tự ưu tiên', 'Ordered by preference'],
  tied: ['Đồng hạng', 'Tied'],
  no_preferences: ['Chưa có ưu tiên để xếp hạng', 'No ranking preferences'],
  insufficient_preferences: ['Chưa đủ dữ kiện ưu tiên', 'Insufficient preference data'],
  conservative_lower_bound: [
    'Xếp theo cận dưới của điểm ưu tiên, giữ phần chưa biết trong khoảng điểm',
    'Ordered by the lower preference bound, with unknown data retained in the score interval',
  ],
  queued: ['Đang chờ xử lý', 'Queued'],
  running: ['Đang xử lý', 'Processing'],
  succeeded: ['Hoàn thành', 'Completed'],
  failed: ['Xử lý thất bại', 'Failed'],
  cancelled: ['Đã hủy', 'Cancelled'],
  started: ['Đã bắt đầu', 'Started'],
  completed: ['Hoàn thành', 'Completed'],
  skipped: ['Bỏ qua', 'Skipped'],
  ok: ['Đọc được nguồn', 'Source available'],
  blocked: ['Nguồn bị chặn', 'Source blocked'],
  timeout: ['Nguồn phản hồi quá hạn', 'Source timed out'],
  error: ['Lỗi nguồn', 'Source error'],
  requirement: ['Hiểu yêu cầu', 'Understand request'],
  parse: ['Hiểu yêu cầu', 'Understand request'],
  parsing: ['Hiểu yêu cầu', 'Understand request'],
  retrieval: ['Tìm và đọc nguồn', 'Find and read sources'],
  crawl: ['Đọc dữ liệu tour', 'Read tour data'],
  normalization: ['Chuẩn hóa dữ kiện', 'Normalize data'],
  evaluation: ['Đối chiếu điều kiện', 'Evaluate conditions'],
  ranking: ['Sắp xếp gợi ý', 'Rank recommendations'],
  comparison: ['Dựng bảng so sánh', 'Build comparison'],
  analysis: ['Phân tích dữ kiện', 'Analyze facts'],
  semantic_assessment: ['Đánh giá ưu tiên', 'Assess preferences'],
  conversation: ['Trả lời trao đổi', 'Answer conversation'],
  reference_collection: ['Thu thập nguồn tour', 'Collect tour sources'],
  orchestration: ['Tiếp nhận và xử lý', 'Request processing'],
  publication: ['Lưu kết quả', 'Save result'],
  hard_filter: ['Kiểm tra điều kiện bắt buộc', 'Check required conditions'],
  candidates: ['Tour đã đánh giá', 'Evaluated tours'],
  recommended: ['Tour gợi ý', 'Recommended tours'],
  columns: ['Tour đối chiếu', 'Compared tours'],
  cells: ['Dữ kiện', 'Facts'],
  requested: ['Ưu tiên cần đánh giá', 'Requested assessments'],
  assessed: ['Ưu tiên đã đánh giá', 'Completed assessments'],
  errors: ['Nguồn lỗi', 'Source errors'],
  hard_pass: ['Tour đạt điều kiện bắt buộc', 'Tours meeting required conditions'],
  tours: ['Tour', 'Tours'],
  offers: ['Lịch khởi hành / giá', 'Departure offers'],
  published_price_difference: ['Chênh lệch giá công bố', 'Published price difference'],
  adult_subtotal: ['Tạm tính giá cho người lớn', 'Published adult subtotal'],
  computed: ['Đã tính', 'Computed'],
};

function label(value: string, locale: Locale): string {
  return labels[value]?.[locale === 'vi' ? 0 : 1] ?? value;
}
function object(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}
function textValue(value: unknown): string | null {
  return typeof value === 'string' ? value : null;
}
function evidenceIds(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string')
    : [];
}

export function formatAmount(value: number | string, currency: string, locale: Locale): string {
  const raw = String(value);
  if (!/^-?\d+(\.\d+)?$/.test(raw)) return `${raw} ${currency}`;
  // Keep large decimal strings intact rather than rounding source amounts through Number.
  if (raw.replace(/[.-]/g, '').length > 15) return `${raw} ${currency}`;
  const amount = new Intl.NumberFormat(locale === 'vi' ? 'vi-VN' : 'en-GB', {
    maximumFractionDigits: 20,
  }).format(Number(raw));
  return `${amount} ${currency === 'VND' ? '₫' : currency}`;
}

function dateLabel(value: string, locale: Locale, withTime = false): string {
  const date = new Date(/^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T12:00:00Z` : value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(locale === 'vi' ? 'vi-VN' : 'en-GB', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    ...(withTime ? { hour: '2-digit', minute: '2-digit', timeZoneName: 'short' as const } : {}),
    timeZone: 'Asia/Ho_Chi_Minh',
  }).format(date);
}

function amountValue(value: unknown): value is number | string {
  return typeof value === 'number' || typeof value === 'string';
}

/** Present source values only; callers must keep missing/conflicting/invalid states separate. */
export function formatResultValue(
  value: unknown,
  locale: Locale,
  unit: string | null = null,
): string {
  if (value === null || value === undefined)
    return locale === 'vi' ? 'Chưa có dữ kiện' : 'Missing data';
  if (typeof value === 'boolean')
    return locale === 'vi' ? (value ? 'Có' : 'Không') : value ? 'Yes' : 'No';
  if (typeof value === 'number')
    return `${new Intl.NumberFormat(locale === 'vi' ? 'vi-VN' : 'en-GB', { maximumFractionDigits: 20 }).format(value)}${unit ? ` ${label(unit, locale)}` : ''}`;
  if (typeof value === 'string')
    return /^\d{4}-\d{2}-\d{2}$/.test(value) ? dateLabel(value, locale) : value;
  if (Array.isArray(value))
    return value.length
      ? value.map((item) => formatResultValue(item, locale)).join('\n')
      : locale === 'vi'
        ? 'Không có mục được ghi nhận'
        : 'No recorded entries';
  const record = object(value);
  if (!record) return '';
  if (record.kind === 'set' && Array.isArray(record.items))
    return formatResultValue(record.items, locale);
  if (record.kind === 'date' && typeof record.value === 'string')
    return `${formatResultValue(record.value, locale)}${typeof record.upper === 'string' ? ` – ${formatResultValue(record.upper, locale)}` : ''}`;
  if (record.kind === 'number' && amountValue(record.amount))
    return `${formatResultValue(record.amount, locale)}${amountValue(record.upper) ? ` – ${formatResultValue(record.upper, locale)}` : ''}`;
  if (record.kind === 'entities' && Array.isArray(record.members))
    return record.members
      .map((member) => {
        const entity = object(member);
        return typeof entity?.raw === 'string'
          ? entity.raw +
              (entity.status === 'catalog_missing'
                ? ` (${locale === 'vi' ? 'chưa có trong danh mục' : 'not in catalog'})`
                : '')
          : '';
      })
      .filter(Boolean)
      .join(', ');
  if (
    ['unresolved', 'qualitative', 'temporal'].includes(String(record.kind)) &&
    typeof record.raw === 'string'
  )
    return `${record.raw}${typeof record.resolved_date === 'string' ? ` · ${formatResultValue(record.resolved_date, locale)}` : ''}`;
  if (amountValue(record.amount) && typeof record.currency === 'string') {
    const price = formatAmount(record.amount, record.currency, locale);
    const range =
      record.kind === 'range' && amountValue(record.upper_amount)
        ? `${price} – ${formatAmount(record.upper_amount, record.currency, locale)}`
        : record.kind === 'from'
          ? `${locale === 'vi' ? 'Từ' : 'From'} ${price}`
          : price;
    const parts = [
      range + (typeof record.basis === 'string' ? ` / ${label(record.basis, locale)}` : ''),
    ];
    if (typeof record.coverage === 'string') parts.push(label(record.coverage, locale));
    if (typeof record.age_min === 'number' && typeof record.age_max_exclusive === 'number')
      parts.push(
        `${record.age_min} ≤ ${locale === 'vi' ? 'tuổi' : 'age'} < ${record.age_max_exclusive}`,
      );
    if ('required' in record)
      parts.push(
        locale === 'vi'
          ? record.required === true
            ? 'Bắt buộc'
            : record.required === false
              ? 'Tùy chọn'
              : 'Chưa rõ bắt buộc'
          : record.required === true
            ? 'Required'
            : record.required === false
              ? 'Optional'
              : 'Requirement unknown',
      );
    if (Array.isArray(record.applicability))
      for (const item of record.applicability) {
        const condition = object(item);
        if (typeof condition?.field === 'string')
          parts.push(
            `${label(condition.field, locale)}: ${formatResultValue(condition.value, locale)}`,
          );
      }
    return parts.join(' · ');
  }
  return Object.entries(record)
    .map(([key, item]) => `${label(key, locale)}: ${formatResultValue(item, locale)}`)
    .join('\n');
}

function safeUrl(value: string): string | null {
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password
      ? url.href
      : null;
  } catch {
    return null;
  }
}

function columnTitle(column: ComparisonColumn, t: Translate): string {
  return column.title ?? t('Tour chưa có tên từ nguồn', 'Tour title unavailable');
}
function rowTitle(row: ComparisonRow, locale: Locale): string {
  return locale === 'en' ? (labels[row.field]?.[1] ?? row.label) : row.label;
}
function conditionTitle(id: string, result: ComparisonResult, locale: Locale): string {
  const condition = result.requirement_snapshot.conditions.find((item) => item.id === id);
  return condition ? label(condition.field, locale) : id;
}

function reasonLabel(code: string | null, t: Translate): string {
  const reasons: Record<string, [string, string]> = {
    ONLY_UNVERIFIED: [
      'Các tour còn thiếu dữ kiện để xác nhận điều kiện bắt buộc.',
      'Tours need more data to verify required conditions.',
    ],
    ALL_INELIGIBLE: [
      'Chưa có tour đạt các điều kiện bắt buộc đã xác nhận.',
      'No tour currently meets the confirmed required conditions.',
    ],
    NO_SUPPORTED_TARGETS: [
      'Chưa đọc được nguồn phù hợp trong phạm vi hỗ trợ.',
      'No supported source could be read.',
    ],
    NO_CANDIDATES: [
      'Chưa tìm thấy tour trong phạm vi tìm kiếm.',
      'No tours were found in the search scope.',
    ],
    PARTY_ADULTS_MISSING: [
      'Chưa rõ số người lớn để tạm tính giá.',
      'An adult count is required for this subtotal.',
    ],
    SELECTED_OFFER_REQUIRED: [
      'Cần chọn lịch khởi hành để tính giá.',
      'A selected departure offer is required.',
    ],
    USABLE_EXACT_PRICE_REQUIRED: [
      'Chưa có giá chính xác, còn mới và đủ chứng cứ để tính.',
      'A usable, fresh and evidenced exact price is required.',
    ],
    TWO_COMPARABLE_OFFERS_REQUIRED: [
      'Cần hai lịch có giá so sánh được.',
      'Two comparable offers are required.',
    ],
    PRICE_CURRENCY_BASIS_COVERAGE_MISMATCH: [
      'Giá khác đơn vị, tiền tệ hoặc phạm vi nên chưa thể so sánh.',
      'Price currency, basis or coverage differ.',
    ],
    FIELD_MISSING: ['Nguồn chưa cung cấp dữ kiện này.', 'The source does not provide this fact.'],
    TITLE_NOT_PROVIDED: [
      'Nguồn chưa cung cấp tên tour.',
      'The source does not provide a tour title.',
    ],
    OFFER_MISSING: [
      'Chưa có lịch khởi hành từ nguồn.',
      'No departure offers are available from the source.',
    ],
    MULTIPLE_OFFERS_UNSELECTED: [
      'Cần chọn một lịch khởi hành để xem dữ kiện và đánh giá đúng lịch.',
      'Select a departure offer to view and evaluate its facts.',
    ],
    FIELD_FRESHNESS_POLICY_MISSING: [
      'Nguồn chưa cấu hình thời hạn dữ liệu còn mới.',
      'Source freshness policy is not configured.',
    ],
    FIELD_STALE: [
      'Dữ liệu đã quá thời hạn; cần cập nhật lại từ nguồn.',
      'Data has expired and needs refreshing from the source.',
    ],
    DEPARTURE_ALREADY_PASSED: [
      'Lịch này đã khởi hành, dù vẫn thuộc tháng bạn chọn.',
      'This offer has already departed, even if it belongs to your selected month.',
    ],
    FIELD_OBSERVATION_IN_FUTURE: [
      'Thời điểm thu thập dữ liệu không hợp lệ.',
      'The data observation time is invalid.',
    ],
    FIELD_STALE_OR_FRESHNESS_UNKNOWN: [
      'Dữ liệu đã cũ hoặc chưa xác nhận được độ mới.',
      'Data is stale or its freshness is unknown.',
    ],
    PRICE_COVERAGE_UNCONFIRMED: [
      'Chưa xác nhận đầy đủ phạm vi giá và các điều kiện áp dụng.',
      'Price coverage and applicable terms are not fully confirmed.',
    ],
    LISTED_PRICE_MISSING_OR_AMBIGUOUS: [
      'Chưa có giá tour niêm yết áp dụng rõ ràng.',
      'Applicable listed tour price is missing or ambiguous.',
    ],
    LISTED_PRICE_BASIS_UNSUPPORTED: [
      'Chưa có giá niêm yết cho đơn vị ngân sách này.',
      'Listed pricing for this budget basis is unavailable.',
    ],
    DEPARTURE_WINDOW_PAST: [
      'Lịch khởi hành đã qua. Chọn lại tháng/năm hoặc ngày.',
      'Departure window has passed. Choose a new month/year or date.',
    ],
    PRICE_MISSING_OR_AMBIGUOUS: [
      'Chưa có bảng giá áp dụng rõ ràng cho thành viên trong đoàn.',
      'An applicable price for the party is missing or ambiguous.',
    ],
    BUDGET_BOUNDS: [
      'Giá từ hoặc khoảng giá chưa chứng minh được trần ngân sách.',
      'The starting price or price interval does not establish the budget cap.',
    ],
    FIELD_UNSUPPORTED: [
      'Nguồn chưa có dữ kiện được chuẩn hóa cho điều kiện này.',
      'A normalized source fact is not available for this condition.',
    ],
    ENTITY_FACT_CATALOG_MISSING: [
      'Một số địa danh chưa được chuẩn hóa; chưa thể kết luận.',
      'Some place names are not normalized, so a conclusion is unavailable.',
    ],
    NO_ELIGIBLE_SEMANTIC_INPUT: [
      'Chưa có tour đạt điều kiện bắt buộc để đánh giá ưu tiên bằng AI.',
      'No tour meets the required conditions for AI preference assessment.',
    ],
  };
  const known = code ? reasons[code] : null;
  return known
    ? t(...known)
    : t('Chưa đủ dữ kiện để kết luận.', 'There is not enough data for a conclusion.');
}

export function SearchDiagnostics({
  result,
}: {
  result: Pick<ComparisonResult, 'recommendations' | 'analysis' | 'columns' | 'evaluations'>;
}) {
  const { locale, t } = usePreferences();
  const needs = new Set(result.recommendations.needs_verification);
  const blockers = new Map<string, { field: string; reason: string; candidates: Set<string> }>();
  for (const column of result.columns) {
    if (!needs.has(column.id)) continue;
    const all = result.evaluations.filter(
      (e) => e.candidate_id === column.id && e.strength === 'hard',
    );
    const perOffer = all.filter((e) => e.offer_snapshot_id !== null);
    for (const e of perOffer.length ? perOffer : all) {
      if (e.status !== 'unknown') continue;
      const key = `${e.field}:${e.reason_code}`;
      const group = blockers.get(key) ?? {
        field: e.field,
        reason: e.reason_code,
        candidates: new Set<string>(),
      };
      group.candidates.add(column.id);
      blockers.set(key, group);
    }
  }
  const runs = Array.isArray(result.analysis.retrieval.runs)
    ? result.analysis.retrieval.runs.flatMap((run) => {
        const value = object(run);
        return value ? [value] : [];
      })
    : [];
  const limited =
    result.recommendations.truncated ||
    runs.some((run) => run.scan_truncated || run.pool_truncated || run.offer_truncated);
  const semantic = result.analysis.semantic_assessment;
  if (!needs.size && !limited && semantic.reason_code !== 'NO_ELIGIBLE_SEMANTIC_INPUT') return null;
  return (
    <section
      className="notice"
      aria-label={t('Chi tiết kết quả tìm kiếm', 'Search result details')}
    >
      {needs.size > 0 && (
        <p>
          {t(
            `${needs.size} tour cần xác nhận thêm điều kiện bắt buộc. Đây là các tour để kiểm tra, chưa phải gợi ý phù hợp.`,
            `${needs.size} tours need verification of required conditions. These are review candidates, not confirmed recommendations.`,
          )}
        </p>
      )}
      {blockers.size > 0 && (
        <ul>
          {[...blockers.entries()].map(([key, group]) => (
            <li key={key}>
              <strong>{label(group.field, locale)}</strong> ·{' '}
              {t(`${group.candidates.size} tour`, `${group.candidates.size} tours`)}:{' '}
              {reasonLabel(group.reason, t)}
            </li>
          ))}
        </ul>
      )}
      {limited && (
        <p>
          {t(
            'Phạm vi dữ liệu bị giới hạn; kết quả này chưa đại diện toàn bộ kho tour.',
            'The data scope is limited; this result does not represent the entire tour catalog.',
          )}
        </p>
      )}
      {runs.map((run, index) => (
        <p key={index}>
          {t('Lượt đọc', 'Retrieval run')} {index + 1}: {t('đã quét', 'scanned')}{' '}
          {typeof run.scanned_count === 'number' ? run.scanned_count : '—'}{' '}
          {t('bản ghi; giữ', 'records; retained')}{' '}
          {typeof run.retained_count === 'number' ? run.retained_count : '—'} {t('tour', 'tours')}.
          {run.offer_truncated
            ? ' ' +
              t('Danh sách lịch khởi hành chưa đầy đủ.', 'Departure offer coverage is incomplete.')
            : ''}
        </p>
      ))}
      {semantic.reason_code === 'NO_ELIGIBLE_SEMANTIC_INPUT' && (
        <p>{reasonLabel(semantic.reason_code, t)}</p>
      )}
    </section>
  );
}

function EvidenceButtons({
  ids,
  context,
  onEvidence,
}: {
  ids: string[];
  context: string;
  onEvidence: (id: string) => void;
}) {
  const { t } = usePreferences();
  return (
    <div className="evidence-links">
      {ids.map((id, index) => (
        <button
          key={id}
          type="button"
          className="evidence-button"
          onClick={() => onEvidence(id)}
          aria-label={`${t('Xem nguồn', 'View evidence')} ${context}${ids.length > 1 ? ` · ${index + 1}` : ''}`}
        >
          <Icon name="source" size={14} />
          {ids.length > 1
            ? t(`Nguồn ${index + 1}`, `Source ${index + 1}`)
            : t('Xem nguồn', 'View source')}
        </button>
      ))}
    </div>
  );
}

function DataCell({
  cell,
  row,
  column,
  onEvidence,
}: {
  cell: ComparisonCell | undefined;
  row: ComparisonRow;
  column: ComparisonColumn;
  onEvidence: (id: string) => void;
}) {
  const { locale, t } = usePreferences();
  if (!cell)
    return <span className="missing">{t('Chưa nhận được dữ kiện', 'Data was not received')}</span>;
  return (
    <>
      <div className={`cell-value ${cell.data_state === 'present' ? '' : 'missing'}`}>
        {cell.data_state === 'present'
          ? formatResultValue(cell.value, locale, row.unit)
          : label(cell.data_state, locale)}
      </div>
      <div className="cell-quality">
        <span className={`data-badge state-${cell.data_state}`}>
          {label(cell.data_state, locale)}
        </span>
        <span>{label(cell.verification, locale)}</span>
        <span>
          {t('Đầy đủ', 'Completeness')}: {label(cell.completeness, locale)}
        </span>
        <span className={`freshness-${cell.freshness.state}`}>
          {cell.freshness.state === 'unknown'
            ? t('Độ mới chưa rõ', 'Freshness unknown')
            : label(cell.freshness.state, locale)}
        </span>
      </div>
      <EvidenceButtons
        ids={cell.evidence_ids}
        context={`${rowTitle(row, locale)} · ${columnTitle(column, t)}`}
        onEvidence={onEvidence}
      />
      <details className="cell-details">
        <summary>{t('Chi tiết dữ kiện', 'Data details')}</summary>
        <dl>
          <div>
            <dt>{t('Ghi nhận', 'Observed')}</dt>
            <dd>
              {cell.observed_at
                ? dateLabel(cell.observed_at, locale, true)
                : t('Chưa có thời điểm', 'No timestamp')}
            </dd>
          </div>
          <div>
            <dt>{t('Kiểm tra độ mới', 'Freshness checked')}</dt>
            <dd>{dateLabel(cell.freshness.checked_at, locale, true)}</dd>
          </div>
          {cell.freshness.expires_at && (
            <div>
              <dt>{t('Hết hạn theo nguồn', 'Source policy expiry')}</dt>
              <dd>{dateLabel(cell.freshness.expires_at, locale, true)}</dd>
            </div>
          )}
          {cell.reason_code && (
            <div>
              <dt>{t('Giới hạn', 'Limitation')}</dt>
              <dd>
                {reasonLabel(cell.reason_code, t)} <code>{cell.reason_code}</code>
              </dd>
            </div>
          )}
        </dl>
        {cell.raw_value.some((value) => value !== null) && (
          <div className="source-values">
            <span>{t('Giá trị nguồn', 'Source value')}</span>
            {cell.raw_value
              .filter((value): value is string => value !== null)
              .map((value, index) => (
                <blockquote key={index}>{value}</blockquote>
              ))}
          </div>
        )}
      </details>
    </>
  );
}

function offerLabel(offer: Offer, locale: Locale, t: Translate): string {
  const date = offer.fields.departure_date;
  const price = (
    offer.listed_price_quotes?.length ? offer.listed_price_quotes : offer.price_quotes
  ).find((item) => item.data_state === 'present' && item.value !== null);
  return [
    date?.data_state === 'present'
      ? formatResultValue(date.value, locale)
      : t('Ngày chưa rõ', 'Date unknown'),
    price?.value ? formatResultValue(price.value, locale) : t('Giá chưa rõ', 'Price unknown'),
  ].join(' · ');
}

function OfferPicker({
  column,
  busy,
  onOfferChange,
}: {
  column: ComparisonColumn;
  busy: boolean;
  onOfferChange: (tourId: string, offerId: string) => void;
}) {
  const { locale, t } = usePreferences();
  const id = useId();
  if (!column.tour_id || column.offer_options.length === 0)
    return <p className="context-note">{reasonLabel(column.offer_reason, t)}</p>;
  return (
    <div className="offer-picker">
      <label htmlFor={id}>{t('Lịch khởi hành / giá', 'Departure offer / price')}</label>
      <select
        id={id}
        disabled={
          busy || (column.offer_options.length < 2 && column.selected_offer_snapshot_id !== null)
        }
        value={column.selected_offer_snapshot_id ?? ''}
        onChange={(event) => {
          const tourId = column.tour_id;
          if (
            tourId &&
            event.target.value &&
            event.target.value !== column.selected_offer_snapshot_id
          )
            onOfferChange(tourId, event.target.value);
        }}
      >
        {!column.selected_offer_snapshot_id && (
          <option value="" disabled>
            {t('Chọn lịch để đánh giá', 'Select an offer to evaluate')}
          </option>
        )}
        {column.offer_options.map((offer) => {
          const assessment = column.offer_assessments.find(
            (item) => item.offer_snapshot_id === offer.snapshot_id,
          );
          return (
            <option key={offer.snapshot_id} value={offer.snapshot_id}>
              {offerLabel(offer, locale, t)}
              {assessment?.hard_status ? ` · ${label(assessment.hard_status, locale)}` : ''}
            </option>
          );
        })}
      </select>
      {!column.offers_complete && (
        <small>
          {t(
            'Nguồn chưa xác nhận đã có đủ mọi lịch.',
            'The source has not confirmed that all offers are available.',
          )}
        </small>
      )}
    </div>
  );
}

function RecommendationCard({
  column,
  item,
  result,
  busy,
  onOfferChange,
  onEvidence,
}: {
  column: ComparisonColumn;
  item: Recommendation | undefined;
  result: ComparisonResult;
  busy: boolean;
  onOfferChange: (tourId: string, offerId: string) => void;
  onEvidence: (id: string) => void;
}) {
  const { locale, t } = usePreferences();
  const prices = result.rows
    .filter((row) => ['listed_price_quotes', 'price_quotes', 'published_price'].includes(row.field))
    .map((row) => ({
      row,
      cell: result.cells.find((cell) => cell.column_id === column.id && cell.row_id === row.id),
    }))
    .filter((entry) => entry.cell?.data_state === 'present');
  const price =
    prices.find((entry) => entry.row.field === 'listed_price_quotes') ??
    prices.find((entry) => entry.row.field === 'price_quotes') ??
    prices[0];
  const publishedQuotes = Array.isArray(price?.cell?.value)
    ? price.cell.value
    : price?.cell
      ? [price.cell.value]
      : [];
  const primaryQuoteIndex = Math.max(
    0,
    publishedQuotes.findIndex((quote) => object(quote)?.basis === 'per_adult'),
  );
  const primaryQuote = publishedQuotes[primaryQuoteIndex];
  const otherQuotes = publishedQuotes.filter((_quote, index) => index !== primaryQuoteIndex);
  const facts = ['departure_date', 'duration_days'].flatMap((field) => {
    const row = result.rows.find((row) => row.field === field);
    const cell = row
      ? result.cells.find((cell) => cell.column_id === column.id && cell.row_id === row.id)
      : null;
    return row && cell?.data_state === 'present' ? [{ row, cell }] : [];
  });
  return (
    <article className="tour-card">
      <div className="tour-body">
        <div className="tour-rank">
          {item && <span className="rank-number">{String(item.rank).padStart(2, '0')}</span>}
          <span>
            {result.recommendations.kind === 'similar'
              ? t('Gợi ý tương tự', 'Similar suggestion')
              : t('Gợi ý theo yêu cầu', 'Recommended for your request')}
          </span>
        </div>
        <h3>{columnTitle(column, t)}</h3>
        <p className="tour-supplier">
          {column.supplier?.display_name ?? t('Nhà cung cấp chưa rõ', 'Supplier unknown')}
        </p>
        <div className="price">
          {price?.cell
            ? formatResultValue(primaryQuote, locale)
            : t('Chưa có giá từ nguồn', 'Published price unavailable')}
        </div>
        {price?.cell && (
          <>
            {price.row.field === 'listed_price_quotes' && (
              <p className="price-unit">
                {t(
                  'Giá tour niêm yết/người lớn. Phụ thu và tổng tiền thực trả cần xác nhận riêng với nhà cung cấp.',
                  'Listed tour price/adult. Confirm surcharges and the final payable total separately with the provider.',
                )}
              </p>
            )}
            <p className="price-unit">
              {label(price.cell.verification, locale)} ·{' '}
              {price.cell.freshness.state === 'unknown'
                ? t('Độ mới chưa rõ', 'Freshness unknown')
                : label(price.cell.freshness.state, locale)}
            </p>
            {otherQuotes.length > 0 && (
              <details className="calculation-details">
                <summary>{t('Các mức giá khác từ nguồn', 'Other published prices')}</summary>
                {otherQuotes.map((quote, index) => (
                  <p key={index} className="price-unit">
                    {formatResultValue(quote, locale)}
                  </p>
                ))}
              </details>
            )}
            <EvidenceButtons
              ids={price.cell.evidence_ids}
              context={`${rowTitle(price.row, locale)} · ${columnTitle(column, t)}`}
              onEvidence={onEvidence}
            />
          </>
        )}
        <dl className="tour-facts">
          {facts.map(({ row, cell }) => (
            <div key={row.id}>
              <dt>{rowTitle(row, locale)}</dt>
              <dd>{formatResultValue(cell.value, locale, row.unit)}</dd>
            </div>
          ))}
        </dl>
        {item && (
          <p className="tour-reason">
            <Icon name="check" size={17} />
            <span>{item.reason}</span>
          </p>
        )}
        <OfferPicker column={column} busy={busy} onOfferChange={onOfferChange} />
      </div>
    </article>
  );
}

function MetricCard({
  metric,
  result,
  onEvidence,
}: {
  metric: Metric;
  result: ComparisonResult;
  onEvidence: (id: string) => void;
}) {
  const { locale, t } = usePreferences();
  const title =
    metric.operation === 'subtract'
      ? t('Chênh lệch giá công bố', 'Published price difference')
      : t('Tạm tính giá cho người lớn', 'Published adult subtotal');
  return (
    <article className="analysis-card">
      <span className="analysis-kicker">{title}</span>
      <strong className="metric-value">
        {metric.comparable && metric.result !== null
          ? formatAmount(metric.result, metric.currency, locale)
          : t('Chưa thể so sánh', 'Not comparable')}
      </strong>
      <p>
        {label(metric.basis, locale)} · {label(metric.coverage, locale)}
      </p>
      <details className="calculation-details">
        <summary>{t('Phép tính và dữ kiện đầu vào', 'Calculation and source inputs')}</summary>
        <div className="metric-operands">
          {metric.operands.map((operand, index) => (
            <div key={`${operand.field}-${index}`}>
              <strong>
                {operand.candidate_id
                  ? (result.columns.find((column) => column.id === operand.candidate_id)?.title ??
                    t('Tour chưa có tên từ nguồn', 'Tour title unavailable'))
                  : label(operand.field, locale)}
              </strong>
              <span>
                {index > 0 ? (metric.operation === 'subtract' ? '− ' : '× ') : ''}
                {formatResultValue(operand.value, locale)}
              </span>
              <span>{label(operand.field, locale)}</span>
              <EvidenceButtons
                ids={operand.evidence_ids}
                context={`${title} · ${label(operand.field, locale)}`}
                onEvidence={onEvidence}
              />
            </div>
          ))}
        </div>
      </details>
      <ul className="analysis-limitations">
        {metric.limitations.map((limitation, index) => (
          <li key={index}>{limitation}</li>
        ))}
      </ul>
      <EvidenceButtons ids={metric.evidence_ids} context={title} onEvidence={onEvidence} />
    </article>
  );
}

function RankingDetails({
  result,
  onEvidence,
}: {
  result: ComparisonResult;
  onEvidence: (id: string) => void;
}) {
  const { locale, t } = usePreferences();
  return (
    <section className="analysis-wide">
      <h3>{t('Căn cứ đề xuất', 'Recommendation basis')}</h3>
      <p>
        {result.recommendations.kind === 'similar'
          ? t(
              'Các gợi ý tương tự chưa khẳng định phù hợp nhu cầu cá nhân.',
              'Similar suggestions do not establish a personal fit.',
            )
          : t(
              'Thứ tự và đánh giá do hệ thống trả về theo yêu cầu của lượt này.',
              'Ranking and evaluations use the confirmed request for this result.',
            )}
      </p>
      <div className="ranking-list">
        {result.recommendations.candidate_ids.map((id) => {
          const column = result.columns.find((column) => column.id === id);
          const item = result.recommendations.items.find((item) => item.candidate_id === id);
          if (!column || !item) return null;
          return (
            <details key={id} className="calculation-details">
              <summary>
                {String(item.rank).padStart(2, '0')} · {columnTitle(column, t)}
              </summary>
              <p>{item.reason}</p>
              <p>{label(item.rank_status, locale)}</p>
              <p>{label(item.ranking_basis, locale)}</p>
              <dl className="ranking-values">
                <div>
                  <dt>{t('Điểm ưu tiên', 'Preference score')}</dt>
                  <dd>
                    {item.score === null
                      ? t('Chưa đủ dữ kiện', 'Insufficient data')
                      : `${formatResultValue(item.score, locale)} / 1`}
                  </dd>
                </div>
                <div>
                  <dt>{t('Khoảng điểm theo phần chưa biết', 'Score interval for unknown data')}</dt>
                  <dd>
                    {item.score_interval.lower === null || item.score_interval.upper === null
                      ? t('Chưa có', 'Unavailable')
                      : `${formatResultValue(item.score_interval.lower, locale)} – ${formatResultValue(item.score_interval.upper, locale)}`}
                  </dd>
                </div>
                <div>
                  <dt>{t('Độ bao phủ ưu tiên', 'Preference coverage')}</dt>
                  <dd>
                    {item.coverage === null
                      ? t('Chưa rõ', 'Unknown')
                      : `${formatResultValue(item.coverage, locale)} / 1`}
                  </dd>
                </div>
              </dl>
              {item.contributions.length > 0 && (
                <ul className="ranking-contributions">
                  {item.contributions.map((contribution, index) => {
                    const conditionId = textValue(contribution.condition_id);
                    return (
                      <li key={conditionId ?? index}>
                        <strong>
                          {conditionId
                            ? conditionTitle(conditionId, result, locale)
                            : t('Ưu tiên chưa rõ', 'Unknown preference')}
                        </strong>
                        <span>
                          {t('Mức đóng góp', 'Utility')}:{' '}
                          {contribution.utility === null
                            ? t('Chưa biết', 'Unknown')
                            : formatResultValue(contribution.utility, locale)}{' '}
                          · {t('Trọng số', 'Weight')}:{' '}
                          {formatResultValue(contribution.weight, locale)}
                        </span>
                        <EvidenceButtons
                          ids={evidenceIds(contribution.evidence_ids)}
                          context={
                            conditionId
                              ? conditionTitle(conditionId, result, locale)
                              : t('Căn cứ đề xuất', 'Recommendation basis')
                          }
                          onEvidence={onEvidence}
                        />
                      </li>
                    );
                  })}
                </ul>
              )}
              {result.evaluations
                .filter((evaluation) => item.evaluation_ids.includes(evaluation.id))
                .map((evaluation) => (
                  <div key={evaluation.id} className="evaluation-row">
                    <strong>{conditionTitle(evaluation.condition_id, result, locale)}</strong>
                    <span>
                      {label(evaluation.status, locale)} ·{' '}
                      {evaluation.strength === 'hard'
                        ? t('Bắt buộc', 'Required')
                        : evaluation.strength === 'soft'
                          ? t('Ưu tiên', 'Preference')
                          : t('Chưa rõ', 'Unresolved')}
                    </span>
                    <p>
                      {t('Yêu cầu', 'Expected')}: {formatResultValue(evaluation.expected, locale)} ·{' '}
                      {t('Ghi nhận', 'Actual')}: {formatResultValue(evaluation.actual, locale)}
                    </p>
                    <EvidenceButtons
                      ids={evaluation.evidence_ids}
                      context={`${conditionTitle(evaluation.condition_id, result, locale)} · ${columnTitle(column, t)}`}
                      onEvidence={onEvidence}
                    />
                  </div>
                ))}
            </details>
          );
        })}
      </div>
      {result.recommendations.unsupported_dimensions.length > 0 && (
        <p className="context-note">
          {t('Các ưu tiên chưa được dùng để xếp hạng', 'Preferences not yet supported in ranking')}:{' '}
          {result.recommendations.unsupported_dimensions
            .map((dimension) => label(dimension, locale))
            .join(', ')}
          .
        </p>
      )}
    </section>
  );
}

function AnalysisPanel({
  result,
  onEvidence,
}: {
  result: ComparisonResult;
  onEvidence: (id: string) => void;
}) {
  const { locale, t } = usePreferences();
  return (
    <div className="analysis-content">
      <div className="analysis-intro">
        <Icon name="info" />
        <div>
          <h2>{t('Hiểu căn cứ, nhìn rõ giới hạn.', 'Understand the basis and its limits.')}</h2>
          <p>
            {t(
              'Dữ kiện, phép tính và nhận định dùng cùng lượt kết quả đang xem.',
              'Facts, calculations and claims use the result currently displayed.',
            )}
          </p>
        </div>
      </div>
      {result.analysis.claims.length > 0 && (
        <section className="analysis-claims">
          <h3>{t('Nhận định và điều cần cân nhắc', 'Findings and considerations')}</h3>
          {result.analysis.claims.map((claim) => (
            <article key={claim.id} className="analysis-claim">
              <p>{claim.text}</p>
              <ul className="analysis-limitations">
                {claim.limitations.map((limitation, index) => (
                  <li key={index}>{limitation}</li>
                ))}
              </ul>
              <EvidenceButtons
                ids={claim.evidence_ids}
                context={t('Nhận định', 'Finding')}
                onEvidence={onEvidence}
              />
            </article>
          ))}
        </section>
      )}
      <div className="analysis-grid">
        {result.analysis.metrics.map((metric) => (
          <MetricCard key={metric.id} metric={metric} result={result} onEvidence={onEvidence} />
        ))}
      </div>
      {result.analysis.metric_availability
        .filter((item) => item.state !== 'computed')
        .map((item, index) => (
          <div key={item.metric ?? index} className="notice">
            <strong>
              {item.metric
                ? label(item.metric, locale)
                : t('Phép tính chưa sẵn sàng', 'Calculation unavailable')}
            </strong>
            <p>{reasonLabel(item.reason_code ?? null, t)}</p>
          </div>
        ))}
      {result.analysis.claims.length === 0 && result.analysis.metrics.length === 0 && (
        <div className="empty-state">
          <h3>{t('Chưa có đủ dữ kiện để phân tích.', 'Not enough data for analysis.')}</h3>
          <p>
            {t(
              'Kiểm tra dữ kiện và các nguồn trong bảng so sánh.',
              'Review the facts and evidence in the comparison table.',
            )}
          </p>
        </div>
      )}
      <RankingDetails result={result} onEvidence={onEvidence} />
      <ul className="analysis-limitations">
        {evidenceIds(result.analysis.semantic_assessment.limitations).map((limitation, index) => (
          <li key={index}>{limitation}</li>
        ))}
      </ul>
      <section className="analysis-wide">
        <h3>
          {t('Đánh giá ưu tiên bằng nội dung nguồn', 'Preference assessment from source content')}
        </h3>
        {result.analysis.semantic_assessment.items.length === 0 ? (
          <p className="context-note">
            {t(
              'Chưa có đánh giá ưu tiên bằng nội dung nguồn cho lượt này.',
              'No source based preference assessment is available for this result.',
            )}
          </p>
        ) : (
          result.analysis.semantic_assessment.items.map((item, index) => (
            <article
              key={`${item.candidate_id}-${item.condition_id}-${index}`}
              className="evaluation-row"
            >
              <strong>
                {result.columns.find((column) => column.id === item.candidate_id)?.title ??
                  t('Tour trong phạm vi tìm kiếm', 'Tour in search scope')}
              </strong>
              <p>
                {conditionTitle(item.condition_id, result, locale)}: {label(item.status, locale)}
              </p>
              {item.explanation && <p>{item.explanation}</p>}
              <small>
                {item.usable_for_ranking
                  ? t('Đã dùng làm căn cứ ưu tiên.', 'Used for preference ranking.')
                  : t('Chưa dùng để xếp hạng.', 'Not used for ranking.')}
              </small>
              <EvidenceButtons
                ids={item.evidence_ids}
                context={conditionTitle(item.condition_id, result, locale)}
                onEvidence={onEvidence}
              />
            </article>
          ))
        )}
      </section>
    </div>
  );
}

export interface ResultsProps {
  comparison: Comparison | null;
  onOfferChange: (tourId: string, offerId: string) => void;
  onEvidence: (evidenceId: string) => void;
  busy: boolean;
}

export function Results({ comparison, onOfferChange, onEvidence, busy }: ResultsProps) {
  const { locale, t } = usePreferences();
  const [tab, setTab] = useState<'facts' | 'analysis'>('facts');
  const id = useId();
  const tableRef = useRef<HTMLDivElement>(null);
  const tabsRef = useRef<HTMLDivElement>(null);
  const result = comparison?.result;
  function switchTab(event: KeyboardEvent<HTMLButtonElement>) {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const next =
      event.key === 'Home'
        ? 'facts'
        : event.key === 'End'
          ? 'analysis'
          : tab === 'facts'
            ? 'analysis'
            : 'facts';
    setTab(next);
    tabsRef.current?.querySelector<HTMLButtonElement>(`[data-tab="${next}"]`)?.focus();
  }
  if (!result)
    return (
      <section className="results-panel empty-state" aria-live="polite">
        <Icon name={busy ? 'route' : 'search'} size={30} />
        <h2>
          {busy
            ? t('Đang chuẩn bị những lựa chọn cho bạn.', 'Preparing your choices.')
            : comparison?.status === 'failed'
              ? t('Chưa tạo được bảng so sánh.', 'The comparison could not be created.')
              : comparison?.status === 'cancelled'
                ? t('Đã hủy tìm kiếm.', 'Search cancelled.')
                : t('Những lựa chọn sẽ xuất hiện ở đây.', 'Your choices will appear here.')}
        </h2>
        <p>
          {busy
            ? t(
                'Nhật ký bên trên cập nhật từng bước xử lý.',
                'The activity log updates as processing continues.',
              )
            : t(
                'Xác nhận yêu cầu rồi tìm kiếm để đối chiếu tour và nguồn.',
                'Confirm your request and search to compare tours and sources.',
              )}
        </p>
      </section>
    );
  if (result.origin !== 'source')
    return (
      <section className="results-panel notice" role="alert">
        <h2>{t('Nguồn tour thật chưa sẵn sàng.', 'Live tour data is not ready.')}</h2>
        <p>
          {t(
            'Dịch vụ chưa trả về dữ liệu từ nguồn thật. Chưa thể hiển thị tour, giá hoặc kết luận cho lượt này.',
            'The service did not return live source data. Tours, prices and conclusions cannot be shown for this result.',
          )}
        </p>
      </section>
    );
  const recommended = result.recommendations.candidate_ids.slice(0, 3).flatMap((candidateId) => {
    const column = result.columns.find((column) => column.id === candidateId);
    return column ? [column] : [];
  });
  const references = result.columns.filter(
    (column) => column.origin === 'reference' || column.origin === 'both',
  );
  const rows = [...result.rows].sort((a, b) => a.order - b.order);
  const cells = new Map(
    result.cells.map((cell) => [`${cell.row_id}\u0000${cell.column_id}`, cell]),
  );
  const partial =
    comparison?.status === 'partial' ||
    result.source_coverage.some((source) => source.status !== 'ok' || source.truncated) ||
    result.warnings.length > 0;
  return (
    <div className="results-panel">
      <section aria-labelledby={`${id}-suggestions`}>
        <div className="section-heading">
          <div>
            <h2 id={`${id}-suggestions`}>
              {result.recommendations.kind === 'similar'
                ? t(
                    `${recommended.length} gợi ý tương tự tour bạn gửi`,
                    `${recommended.length} suggestions similar to your references`,
                  )
                : t(
                    `${recommended.length} tour gợi ý cho bạn`,
                    `${recommended.length} recommended tours`,
                  )}
            </h2>
            <p>
              {t(
                'Đối chiếu theo yêu cầu của lượt này',
                'Compared using the request for this result',
              )}{' '}
              · {dateLabel(result.evaluated_at, locale, true)}
            </p>
          </div>
          <button
            type="button"
            className="text-action"
            onClick={() => {
              setTab('analysis');
              tabsRef.current?.querySelector<HTMLButtonElement>('[data-tab="analysis"]')?.focus();
            }}
          >
            {t('Căn cứ đề xuất', 'Recommendation basis')}
            <Icon name="info" size={16} />
          </button>
        </div>
        {result.recommendations.kind === 'similar' && (
          <p className="notice">
            {t(
              'Gợi ý theo phạm vi tour tham chiếu. Chưa suy ra nhu cầu cá nhân để kết luận phù hợp.',
              'Suggestions use the scope of your reference tours. They do not infer your personal needs.',
            )}
          </p>
        )}
        {partial && (
          <div className="notice" role="status">
            <strong>{t('Một phần dữ liệu chưa đủ.', 'Some data is incomplete.')}</strong>
            <p>
              {t(
                'Các nguồn chưa đọc được và dữ kiện chưa rõ vẫn được giữ để bạn kiểm tra.',
                'Unavailable sources and unknown facts remain visible for review.',
              )}
            </p>
          </div>
        )}
        <SearchDiagnostics result={result} />
        {recommended.length > 0 ? (
          <div className="tour-grid">
            {recommended.map((column) => (
              <RecommendationCard
                key={column.id}
                column={column}
                item={result.recommendations.items.find((item) => item.candidate_id === column.id)}
                result={result}
                busy={busy}
                onOfferChange={onOfferChange}
                onEvidence={onEvidence}
              />
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <h3>{t('Chưa có gợi ý để đối chiếu.', 'No recommendations available.')}</h3>
            <p>{reasonLabel(result.empty_reason, t)}</p>
            <p>
              {t(
                'Bạn có thể điều chỉnh phạm vi tìm qua khung yêu cầu hoặc trao đổi.',
                'You can adjust the search scope in your criteria or conversation.',
              )}
            </p>
          </div>
        )}
        {references.map((column) => (
          <div key={column.id} className="reference-strip">
            <Icon name="source" />
            <div>
              <p className="reference-label">
                {t(
                  'Bạn cung cấp · Tham chiếu để đối chiếu',
                  'Your reference · Included for comparison',
                )}
              </p>
              <strong>{columnTitle(column, t)}</strong>
              {!column.tour_snapshot_id && (
                <p>
                  {t(
                    'Chưa đọc đủ dữ kiện từ URL này; nguồn vẫn được giữ trong bảng.',
                    'This URL could not be fully read and remains in the table.',
                  )}
                </p>
              )}
            </div>
            {safeUrl(column.canonical_url) && (
              <a
                className="text-action"
                href={safeUrl(column.canonical_url)!}
                target="_blank"
                rel="noopener noreferrer"
              >
                {t('Mở nguồn', 'Open source')}
                <Icon name="source" size={16} />
              </a>
            )}
          </div>
        ))}
      </section>
      <div
        className="analysis-tabs"
        role="tablist"
        aria-label={t('Cách xem kết quả', 'Result view')}
        ref={tabsRef}
      >
        {(['facts', 'analysis'] as const).map((value) => (
          <button
            key={value}
            type="button"
            role="tab"
            data-tab={value}
            id={`${id}-${value}-tab`}
            aria-selected={tab === value}
            aria-controls={`${id}-${value}-panel`}
            tabIndex={tab === value ? 0 : -1}
            onClick={() => setTab(value)}
            onKeyDown={switchTab}
          >
            {value === 'facts'
              ? t('Dữ kiện so sánh', 'Comparison facts')
              : t('Phân tích AI', 'AI analysis')}
            <Icon name={value === 'facts' ? 'route' : 'info'} size={17} />
          </button>
        ))}
      </div>
      <div
        id={`${id}-facts-panel`}
        role="tabpanel"
        aria-labelledby={`${id}-facts-tab`}
        hidden={tab !== 'facts'}
        tabIndex={0}
      >
        <section className="comparison-section" aria-labelledby={`${id}-comparison`}>
          <div className="comparison-heading">
            <div>
              <h2 id={`${id}-comparison`}>
                {t('Đặt cạnh nhau để thấy rõ.', 'Compare them side by side.')}
              </h2>
              <p>
                {t(
                  'Cùng tiêu chí. Mở nguồn ở mỗi dữ kiện.',
                  'The same criteria, with evidence for every fact.',
                )}
              </p>
            </div>
            {result.columns.length > 0 && (
              <div className="comparison-nav">
                <span>
                  {t(
                    `${result.columns.length} tour đối chiếu`,
                    `${result.columns.length} comparison columns`,
                  )}
                </span>
                <button
                  type="button"
                  className="icon-button scroll-left"
                  aria-label={t('Cuộn bảng về trái', 'Scroll table left')}
                  onClick={() =>
                    tableRef.current?.scrollBy({
                      left: -300,
                      behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches
                        ? 'instant'
                        : 'smooth',
                    })
                  }
                >
                  <Icon name="arrow" />
                </button>
                <button
                  type="button"
                  className="icon-button"
                  aria-label={t('Cuộn bảng sang phải', 'Scroll table right')}
                  onClick={() =>
                    tableRef.current?.scrollBy({
                      left: 300,
                      behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches
                        ? 'instant'
                        : 'smooth',
                    })
                  }
                >
                  <Icon name="arrow" />
                </button>
              </div>
            )}
          </div>
          {result.columns.length > 0 ? (
            <>
              <p className="mobile-scroll-hint">
                {t(
                  'Vuốt ngang để đối chiếu · giữ tiêu chí và tên tour',
                  'Swipe horizontally · criteria and tour names stay visible',
                )}
              </p>
              <div
                className="compare-wrap"
                role="region"
                aria-label={t(
                  'Bảng so sánh tour có thể cuộn ngang',
                  'Horizontally scrollable tour comparison',
                )}
                tabIndex={0}
                ref={tableRef}
              >
                <table
                  className="compare-table"
                  style={{ minWidth: `${168 + result.columns.length * 230}px` }}
                >
                  <caption className="sr-only">
                    {t(
                      'So sánh tour theo yêu cầu đã xác nhận cho lượt này',
                      'Tour comparison using the confirmed request for this result',
                    )}
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">{t('Tiêu chí', 'Criterion')}</th>
                      {result.columns.map((column) => (
                        <th
                          key={column.id}
                          scope="col"
                          className={
                            column.origin === 'reference' || column.origin === 'both'
                              ? 'table-reference'
                              : ''
                          }
                        >
                          <span className="table-tour-origin">
                            {column.origin === 'reference'
                              ? t('Bạn cung cấp', 'Your reference')
                              : column.origin === 'both'
                                ? t('Tham chiếu và tìm thêm', 'Reference and discovered')
                                : result.recommendations.candidate_ids.includes(column.id)
                                  ? t('Gợi ý từ kết quả', 'Recommended')
                                  : t('Cần kiểm tra thêm', 'Needs verification')}
                          </span>
                          <span className="table-tour-name">{columnTitle(column, t)}</span>
                          <small className="table-tour-date">
                            {column.supplier?.display_name ??
                              t('Nhà cung cấp chưa rõ', 'Supplier unknown')}
                          </small>
                          <OfferPicker column={column} busy={busy} onOfferChange={onOfferChange} />
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => (
                      <tr key={row.id}>
                        <th scope="row">
                          {rowTitle(row, locale)}
                          <span>
                            {row.scope === 'offer'
                              ? t('Theo lịch đang xem', 'Selected offer')
                              : row.scope === 'tour'
                                ? t('Dữ kiện tour', 'Tour fact')
                                : row.scope === 'cost'
                                  ? t('Chi phí', 'Cost')
                                  : t('Đánh giá điều kiện', 'Condition evaluation')}
                          </span>
                        </th>
                        {result.columns.map((column) => (
                          <td
                            key={column.id}
                            className={
                              column.origin === 'reference' || column.origin === 'both'
                                ? 'table-reference'
                                : ''
                            }
                          >
                            <DataCell
                              cell={cells.get(`${row.id}\u0000${column.id}`)}
                              row={row}
                              column={column}
                              onEvidence={onEvidence}
                            />
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="table-note">
                <Icon name="info" size={16} />
                {t(
                  'Giá giữ đúng lịch, đơn vị và phạm vi công bố. Độ mới và xác minh được hiển thị riêng ở từng ô.',
                  'Prices retain their offer, basis and published coverage. Freshness and verification are shown separately in each cell.',
                )}
              </p>
            </>
          ) : (
            <p className="notice">
              {t('Chưa có cột tour từ nguồn để hiển thị.', 'No source tour columns are available.')}
            </p>
          )}
        </section>
      </div>
      <section
        id={`${id}-analysis-panel`}
        role="tabpanel"
        aria-labelledby={`${id}-analysis-tab`}
        hidden={tab !== 'analysis'}
        tabIndex={0}
      >
        <AnalysisPanel result={result} onEvidence={onEvidence} />
      </section>
      <footer className="result-footer">
        <p>{t('Kết quả trong phạm vi nguồn được hỗ trợ.', 'Results cover supported sources.')}</p>
        <details>
          <summary>{t('Phạm vi và giới hạn nguồn', 'Source coverage and limitations')}</summary>
          <ul className="source-coverage">
            {result.source_coverage.map((source, index) => (
              <li key={`${source.source_id}-${source.target_id ?? index}`}>
                <strong>{source.source_id}</strong>
                <span>
                  {label(source.status, locale)}
                  {source.truncated
                    ? ` · ${t('Chưa đủ toàn bộ dữ liệu', 'Data was truncated')}`
                    : ''}
                </span>
                {source.reason_code && (
                  <p>
                    {reasonLabel(source.reason_code, t)} <code>{source.reason_code}</code>
                  </p>
                )}
              </li>
            ))}
          </ul>
          {result.warnings.map((warning, index) => (
            <p key={`${warning.code}-${index}`}>{warning.explanation}</p>
          ))}
          {result.recommendations.truncated && (
            <p>
              {t(
                'Phạm vi ứng viên của lượt này còn giới hạn.',
                'The candidate scope for this result was limited.',
              )}
            </p>
          )}
        </details>
      </footer>
    </div>
  );
}

export function Activity({
  events,
  job,
  onCancel,
}: {
  events: JobEvent[];
  job: Job | null;
  onCancel: () => void;
}) {
  const { locale, t } = usePreferences();
  const id = useId();
  if (!job) return null;
  const active = job.status === 'queued' || job.status === 'running';
  const ordered = events.filter((event) => event.job_id === job.id).sort((a, b) => a.seq - b.seq);
  return (
    <section className="processing-panel" aria-labelledby={`${id}-activity-title`}>
      <div className="processing-head">
        <Icon name={active ? 'route' : job.status === 'succeeded' ? 'check' : 'info'} size={24} />
        <div>
          <span className="eyebrow">{t('Nhật ký xử lý', 'Processing activity')}</span>
          <h2 id={`${id}-activity-title`}>{label(job.status, locale)}</h2>
        </div>
        {active && (
          <button type="button" className="text-action" onClick={onCancel}>
            {t('Hủy xử lý', 'Cancel processing')}
          </button>
        )}
      </div>
      {ordered.length > 0 ? (
        <ol className="activity-log" aria-live="polite" aria-relevant="additions text">
          {ordered.map((event) => (
            <li
              key={`${event.job_id}-${event.seq}`}
              className={`activity-event status-${event.status}`}
            >
              <span className="activity-stage">
                {event.stage === 'queued'
                  ? t('Tiếp nhận yêu cầu', 'Request accepted')
                  : label(event.stage, locale)}
              </span>
              <span className="data-badge">{label(event.status, locale)}</span>
              <p className="activity-summary">{event.summary}</p>
              <time className="activity-time" dateTime={event.occurred_at}>
                {dateLabel(event.occurred_at, locale, true)}
              </time>
              {event.source_id && (
                <span className="activity-source">
                  {t('Nguồn', 'Source')}: {event.source_id}
                </span>
              )}
              {event.counts && (
                <span className="activity-counts">
                  {Object.entries(event.counts)
                    .map(([key, value]) => `${label(key, locale)}: ${value}`)
                    .join(' · ')}
                </span>
              )}
              {event.error_code && <code>{event.error_code}</code>}
            </li>
          ))}
        </ol>
      ) : (
        <p className="context-note" role="status">
          {active
            ? t(
                'Đã tiếp nhận. Đang chờ bước xử lý đầu tiên từ dịch vụ.',
                'Request accepted. Waiting for the first processing event.',
              )
            : t(
                'Dịch vụ chưa cung cấp nhật ký cho lượt này.',
                'No processing events are available for this job.',
              )}
        </p>
      )}
      {job.error && (
        <p className="notice" role="alert">
          {job.error.message}
        </p>
      )}
      {job.status === 'partial' && (
        <p className="context-note">
          {t(
            'Đã hoàn thành với một phần dữ liệu. Kiểm tra các giới hạn ở kết quả.',
            'Processing finished with partial data. Review the result limitations.',
          )}
        </p>
      )}
      {job.status === 'cancelled' && (
        <p className="context-note">
          {t(
            'Yêu cầu và kết quả đã có vẫn được giữ.',
            'Your request and previous results are kept.',
          )}
        </p>
      )}
    </section>
  );
}
