# Hợp đồng dữ liệu và API

**Trạng thái:** Contract MVP. Định nghĩa bộ field chuẩn cho mọi tour từ mọi nhà cung cấp.

## Nguyên tắc

1. **Một bộ field chuẩn duy nhất** cho mọi nguồn. Engine không branch theo tên nguồn.
2. **Field luôn có mặt.** Không lấy được → `value: null`, `status: "not_observed"`, `evidence: []`. Không bỏ cột, không bịa.
3. **Hai tầng xử lý:** field cứng so bằng code, field mềm so bằng LLM. Ranh giới này quyết định required policy và cách chấm điểm.
4. **Crawler chỉ lấy nguyên văn + đúng nguồn.** Không tóm tắt, không diễn giải field mềm.

## Wrapper field

Mọi field trong cả ba entity dùng cùng wrapper:

```json
{
  "value": "Hà Nội",
  "raw_value": "Ha Noi",
  "status": "observed",
  "evidence": [
    {
      "source_url": "https://example.test/tour/123",
      "observed_at": "2026-09-27T08:00:00+07:00",
      "extraction_method": "json_ld",
      "verification_status": "provider_claimed"
    }
  ]
}
```

- `value`: giá trị đã chuẩn hoá để so sánh; `raw_value` giữ giá trị nguồn khi có biến đổi.
- `status`: `observed` | `partial` | `not_observed`.
- `verification_status`: `provider_claimed` hoặc `independently_verified`. Nội dung trên website nhà cung cấp mặc định là tự khai báo.
- `observed_at` ghi thời điểm thu thập theo giờ Việt Nam (`Asia/Ho_Chi_Minh`, ISO-8601 kèm offset), không có nghĩa dữ liệu là thời gian thực.

### Kiểm chứng khi ingest

Kiểm tra ingest xác nhận extractor lấy đúng kiểu dữ liệu từ đúng tọa độ nguồn đã khai báo; nó không biến nội dung nhà cung cấp thành xác minh độc lập. Vì thế `verification_status` của dữ liệu crawl vẫn là `provider_claimed`.

- Mỗi tour detail giữ `record_field_checks`: trạng thái và lý do kiểm tra theo từng field. `record_evidence` là kết quả tổng hợp; `record_missing` liệt kê field chưa đạt. Các trường này phục vụ self-test/audit, không thay wrapper field trong catalog.
- Giá trị có dữ liệu phải đúng kiểu/format của contract và được đối chiếu ngữ nghĩa với raw value trích từ rule nguồn tương ứng (ví dụ số giá/thời lượng phải có mặt trong raw, các chặng `route` phải giữ đúng thứ tự). So khớp chuỗi với toàn trang không được dùng để xác nhận field.
- Giá trị rỗng chỉ được xem là `not_observed` nếu profile khai báo rõ và evidence/unknowns ghi cách đã kiểm tra nguồn. Extractor rỗng ngoài trường hợp đó là lỗi chưa giải quyết. Field bắt buộc không quan sát được làm self-test tour fail; crawler không được tự điền.
- `destinations` là danh sách địa điểm riêng. Mỗi phần tử phải khớp một mục taxonomy (rule có thể khai báo `taxonomy_selector`) hoặc node địa điểm structured data của chính nguồn. Tách nhãn ghép chỉ khi nguồn xác nhận riêng từng thành phần. Không tách theo dấu gạch ngang một cách máy móc. `route` giữ toàn bộ chặng theo thứ tự, gồm điểm xuất phát và trung chuyển.

## Cấu trúc entity

```
Provider { id, fields }
Tour     { url, canonical_url, provider, fields, offers: [Offer] }
Offer    { fields }
```

- `Tour` là hồ sơ tương đối ổn định; `Offer` là lựa chọn khởi hành biến động theo ngày.
- `Offer` tồn tại kể cả khi tour có giá cố định (khi đó chỉ có một phần tử).
- `destinations` chứa nơi tham quan; `route` giữ tuyến nguyên thứ tự và có thể chứa điểm xuất phát/điểm trung chuyển. Backend loại origin chỉ khỏi destination chuẩn hóa, không xóa raw value/evidence/route.

## Provider.fields

| Field | Kiểu | Bắt buộc | Ghi chú |
|---|---|---|---|
| `display_name` | str | * | |
| `legal_name` | str | | |
| `website` | str | | |
| `description` | text | | |
| `license_claims` | text | | tự khai báo, không dùng làm bằng chứng xác minh |
| `contact` | text | | |

`Provider` không bắt buộc điền đầy đủ: đa số website tour không công bố thông tin pháp nhân. Tín hiệu rủi ro cần nguồn độc lập, không suy từ trang bán tour.

## Tour.fields — hard (code lọc/so nhanh)

| Field | Kiểu | Bắt buộc | Ghi chú |
|---|---|---|---|
| `tour_name` | str | * | |
| `departure_city` | str | * | một giá trị, điểm khởi hành; condition có thể dùng operator `any` với nhiều nhãn thực trong catalog |
| `destinations` | list[str] | * | Mỗi phần tử là một địa điểm Title Case (`["Mộc Châu", "Sơn La"]`), không viết tắt, xác nhận bằng taxonomy/structured data của nguồn, dùng để lọc |
| `route` | list[str] | | điểm dừng theo thứ tự, gồm transit, bỏ slogan (không dùng string gộp) |
| `transport` | enum | | `flight` \| `bus` \| `train` \| `cruise` \| `mixed` |
| `accommodation` | str | | `homestay` \| `2_star`–`5_star` \| `mixed` |
| `duration_days` | int | * | trích từ "3 ngày 4 đêm" / `P3D` |
| `duration_nights` | int | | |
| `price` | int | * | giá tham chiếu thấp nhất đã quan sát; bỏ separator nghìn; đơn vị theo `currency` |
| `currency` | str | * | ISO 4217; `đ`, `VNĐ` → `VND` |
| `price_type` | enum | | Tour-level reference only: `fixed` \| `from` \| `contact`; must not override offer-level basis. |
| `departure_pattern` | str | | "hàng tuần", "theo yêu cầu" khi không có ngày cụ thể |
| `offers` | list[Offer] | | lượt khởi hành theo ngày (nếu có) |

## Tour.fields — soft (LLM so sánh)

Plain text thuần túy cho cả 6 field: sạch thẻ HTML, giải mã entities (`&amp;`, `&quot;`, `\u003cbr/\u003e`), dòng phân tách bằng `\n- ` hoặc `\n`. Nguyên văn, không tóm tắt.

| Field | Bắt buộc | Ghi chú |
|---|---|---|
| `itinerary` | * | |
| `inclusions` | * | |
| `exclusions` | * | |
| `cancellation_policy` | | cho phép fallback chính sách site-wide, ghi rõ nguồn |
| `surcharges` | | phụ thu: phòng đơn, Tết/lễ, visa, tip |
| `child_policy` | | tuổi, % giá người lớn, giường phụ, trẻ nhỏ |

## Offer.fields

| Field | Kiểu | Bắt buộc | Ghi chú |
|---|---|---|---|
| `departure_date` | date | * | ISO 8601; không gọi `valid_from` là ngày khởi hành nếu nguồn không nói rõ |
| `price` | int | * | giá người lớn/combo của đúng ngày này; `from` → chấm `unknown`, không loại không tin |
| `price_type` | enum | * | Basis for this exact departure: `fixed` \| `from` \| `contact` \| `unknown`. Never inherit silently from Tour. |
| `availability` | enum | | `available` \| `sold_out` \| `unknown` |
| `supplements` | text | | phụ thu nguyên văn của lượt này |
| `tour_code` | str | | mã đặt chỗ; hiển thị xem trực tiếp bằng `url` |
| `price_by_age` | dict | | `{adult, child, small_child, infant}` int/null; preserve in runtime snapshot; age ranges must cite `child_policy`. |
| `single_supplement` | int | | phụ thu phòng đơn của lượt này |
| `flights` | list[dict] | | `{flight_no, airline, dep_datetime, arr_datetime}` — không có với tour đường bộ |
| `conditions` | text | | điều kiện riêng của lượt (nếu khác chính sách chung) |
| `pickup_point` | text | | điểm/giờ tập trung của lượt |
| `hotel_location` | text | | khách sạn gắn với lượt (tour combo) |

- Khi nguồn không công bố ngày cụ thể: ghi `departure_pattern` ở `Tour.fields` kèm `status: partial`, và `offers` để rỗng.
- Field phụ nguồn không công bố thì bỏ hẳn khỏi dict, không ghi null đoán mò.

`offers.field_meta.pricing` có thể bổ sung quote có cấu trúc nhưng không thay các trường chuẩn `offers.price`, `offers.price_type` và currency trong catalog. `tours.price_type` chỉ là tham chiếu cấp tour. Backend dùng basis của offer, không kiểm tra lại host hoặc ràng buộc quote với raw columns. `from` luôn là lower bound; giá thấp hơn ngân sách không chứng minh giá cuối cùng nằm trong ngân sách. Không áp dụng TTL cho giá; `observed_at` vẫn được giữ làm bằng chứng. Freshness của ngày khởi hành tiếp tục được đánh giá theo policy backend.

## Canonical decision metrics

Extracted facts explicitly report which source fields were reviewed (itinerary, route, inclusions, exclusions, surcharges, cancellation_policy, or child_policy). An omitted field or empty fact list does not establish that there are no extra costs, cancellation terms, or child conditions.

Every eligible tour/offer has a metric profile with per-metric value, unit/scale, state (`observed`, `partial`, `unknown`), source field, exact quote, observation time and method/version. Unknown is never coerced to zero or a pass.

| Metric | Canonical measurement |
|---|---|
| `cost` | Offer price basis, currency, age prices, calculable group total, priced mandatory extras and separately listed unpriced costs. `exclusions` and `surcharges` are primary sources; an exclusion is not automatically a mandatory cost. |
| `preference_fit` | Per-user soft condition on `0`, `0.5`, `1`, or `unknown`, with exact evidence. Unknown yields a score interval and separate evidence coverage. |
| `experience_density` | Count of distinct explicitly listed itinerary activities/visits, total and per day. Count is not a quality claim. |
| `route_complexity` | Published route legs and transport changes only when explicit route/itinerary facts support them; no inferred distance or travel duration. |
| `included_coverage` | `transport`, `accommodation`, `meals`, `admission_or_activity`, `guide`, `insurance`; each is `included`, `partial`, `excluded`, or `unknown`. |
| `cancellation_flexibility` | Free-cancellation cutoff and penalty/refund schedule by days before departure, only when explicitly stated and parseable. |
| `family_suitability` | Child age eligibility, child prices/discounts and room/bed conditions; missing age composition stays unknown. |
| `evidence_coverage` | Number of applicable metrics with observed evidence and source age; metadata, not desirability or calibrated confidence. |

Standard objective views use one metric or a disclosed Pareto comparison: lowest exact cost (same currency), best user fit, most listed experiences, fewest published legs, most flexible cancellation, family fit, highest included coverage/lowest unpriced-cost exposure, and balanced Pareto. A view is omitted or marked unavailable when its metric cannot be compared. No universal quality score is computed.

## Required policy

`*` = bắt buộc (thiếu thì FAIL nguồn): `tour_name`, `url`, `departure_city`, `destinations`, `duration_days`, `price`, `currency`, `itinerary`, `inclusions`, `exclusions`. Cho phép thiếu (cảnh báo, không FAIL): `canonical_url`, `route`, `duration_nights`, `price_type`, `departure_pattern`, `cancellation_policy`, `availability`, `departure_date`, `offers`, `surcharges`, `child_policy`. Toàn bộ `Provider.fields`: bỏ qua. `status: partial` vẫn so được nhưng phải gắn cảnh báo khi hiển thị.

## Định dạng lưu trữ

JSON Lines (`.jsonl`): mỗi dòng 1 Tour hoàn chỉnh, giữ native types (`int`, `list[str]`, `list[dict]`), stream nối dòng. Catalog runtime là Supabase: bảng `providers`/`tours`/`offers` theo `migrations/001_tour_schema.sql`, cột `evidence` (`002`) và `field_meta` (`003`) giữ bằng chứng + trạng thái từng field. Backend chỉ đọc catalog, không trigger crawl.

## Giao diện backend

Backend mới không còn endpoint compare theo URL. Contract request/response hiện tại ở [backend-contract](backend-contract.md); schema live ở `/openapi.json`.

## Decision Brief (runtime contract)

Trọng số không phải field catalog và không cần migration database. Trong requirement của một lượt quyết định, `travelers` là tổng khách; `traveler_mix` giữ số `adult`, `child`, `small_child`, `infant` khi người dùng nêu rõ và phải cộng đúng tổng khách. Thiếu mix thì không đoán tuổi hoặc tính tổng theo nhóm. Mỗi soft condition có `weight_percent` là số nguyên từ 0 đến 100; khi có soft condition, tổng phải bằng 100 trước khi chạy. Hard condition không có trọng số. Nếu người dùng sửa giá trị trong Decision Brief, requirement cập nhật `quote` và `raw_text` để trích dẫn vẫn khớp với bản đã review. Comparison bổ sung `metric_profiles`, `decision_options` và `recommendation` tùy chọn, cùng các `decision_views`: `cheapest`, `best_fit`, `experience_rich`, `fewest_legs`, `cancellation_flexible`, `family_friendly`, `included_value`, `balanced`. Model cũ mặc định field mới về rỗng/None. View tham chiếu candidate bằng `tour_id`/`offer_id`; giá và evidence vẫn lấy từ snapshot chuẩn của catalog. Schema lưu offer cần migration cho basis giá và giá theo tuổi.
