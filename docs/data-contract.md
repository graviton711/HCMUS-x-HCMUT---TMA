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

## Cấu trúc entity

```
Provider { id, fields }
Tour     { url, canonical_url, provider, fields, offers: [Offer] }
Offer    { fields }
```

- `Tour` là hồ sơ tương đối ổn định; `Offer` là lựa chọn khởi hành biến động theo ngày.
- `Offer` tồn tại kể cả khi tour có giá cố định (khi đó chỉ có một phần tử).

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
| `departure_city` | str | * | một giá trị, điểm khởi hành |
| `destinations` | list[str] | * | Title Case (`["Mộc Châu", "Sơn La"]`), không viết tắt, lọc từ taxonomy/breadcrumb, dùng để lọc |
| `route` | list[str] | | điểm dừng theo thứ tự, gồm transit, bỏ slogan (không dùng string gộp) |
| `transport` | enum | | `flight` \| `bus` \| `train` \| `cruise` \| `mixed` |
| `accommodation` | str | | `homestay` \| `2_star`–`5_star` \| `mixed` |
| `duration_days` | int | * | trích từ "3 ngày 4 đêm" / `P3D` |
| `duration_nights` | int | | |
| `price` | int | * | giá tham chiếu thấp nhất đã quan sát; bỏ separator nghìn; đơn vị theo `currency` |
| `currency` | str | * | ISO 4217; `đ`, `VNĐ` → `VND` |
| `price_type` | enum | | `fixed` \| `from` \| `contact` |
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
| `price_type` | enum | | `fixed` \| `from` \| `contact` |
| `availability` | enum | | `available` \| `sold_out` \| `unknown` |
| `supplements` | text | | phụ thu nguyên văn của lượt này |
| `tour_code` | str | | mã đặt chỗ; hiển thị xem trực tiếp bằng `url` |
| `price_by_age` | dict | | `{adult, child, small_child, infant}` int/null; dải tuổi theo `child_policy` của Tour |
| `single_supplement` | int | | phụ thu phòng đơn của lượt này |
| `flights` | list[dict] | | `{flight_no, airline, dep_datetime, arr_datetime}` — không có với tour đường bộ |
| `conditions` | text | | điều kiện riêng của lượt (nếu khác chính sách chung) |
| `pickup_point` | text | | điểm/giờ tập trung của lượt |
| `hotel_location` | text | | khách sạn gắn với lượt (tour combo) |

- Khi nguồn không công bố ngày cụ thể: ghi `departure_pattern` ở `Tour.fields` kèm `status: partial`, và `offers` để rỗng.
- Field phụ nguồn không công bố thì bỏ hẳn khỏi dict, không ghi null đoán mò.

## Required policy

`*` = bắt buộc (thiếu thì FAIL nguồn): `tour_name`, `url`, `departure_city`, `destinations`, `duration_days`, `price`, `currency`, `itinerary`, `inclusions`, `exclusions`. Cho phép thiếu (cảnh báo, không FAIL): `canonical_url`, `route`, `duration_nights`, `price_type`, `departure_pattern`, `cancellation_policy`, `availability`, `departure_date`, `offers`, `surcharges`, `child_policy`. Toàn bộ `Provider.fields`: bỏ qua. `status: partial` vẫn so được nhưng phải gắn cảnh báo khi hiển thị.

## Định dạng lưu trữ

JSON Lines (`.jsonl`): mỗi dòng 1 Tour hoàn chỉnh, giữ native types (`int`, `list[str]`, `list[dict]`), stream nối dòng. Catalog runtime là Supabase: bảng `providers`/`tours`/`offers` theo `migrations/001_tour_schema.sql`, cột `evidence` (`002`) và `field_meta` (`003`) giữ bằng chứng + trạng thái từng field. Backend chỉ đọc catalog, không trigger crawl.

## Giao diện backend

Backend mới không còn endpoint compare theo URL. Contract request/response hiện tại ở [backend-contract](backend-contract.md); schema live ở `/openapi.json`.
