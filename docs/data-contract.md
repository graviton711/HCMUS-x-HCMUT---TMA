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
      "observed_at": "2026-09-27T08:00:00Z",
      "extraction_method": "json_ld",
      "verification_status": "provider_claimed"
    }
  ]
}
```

- `value`: giá trị đã chuẩn hoá để so sánh; `raw_value` giữ giá trị nguồn khi có biến đổi.
- `status`: `observed` | `partial` | `not_observed`.
- `verification_status`: `provider_claimed` hoặc `independently_verified`. Nội dung trên website nhà cung cấp mặc định là tự khai báo.
- `observed_at` ghi thời điểm thu thập, không có nghĩa dữ liệu là thời gian thực.

## Cấu trúc entity

```
Provider { id, fields }
Tour     { url, canonical_url, provider, fields, offers: [Offer] }
Offer    { fields }
```

- `Tour` là hồ sơ tương đối ổn định; `Offer` là lựa chọn khởi hành biến động theo ngày.
- `Offer` tồn tại kể cả khi tour có giá cố định (khi đó chỉ có một phần tử).

## Provider.fields

| Field | Kiểu | Bắt buộc |
|---|---|---|
| `display_name` | str | ✅ |
| `legal_name` | str | |
| `website` | str | |
| `description` | text | |
| `license_claims` | text | |
| `contact` | text | |

`Provider` không bắt buộc điền đầy đủ: đa số website tour không công bố thông tin pháp nhân. Tín hiệu rủi ro cần nguồn độc lập, không suy từ trang bán tour.

## Tour.fields — hard (code lọc/so nhanh)

| Field | Kiểu | Bắt buộc | Ghi chú |
|---|---|---|---|
| `tour_name` | str | ✅ | |
| `departure_city` | str | ✅ | một giá trị, điểm khởi hành |
| `destinations` | list[str] | ✅ | điểm đến thật, đã chuẩn hoá, dùng để lọc |
| `route` | list[str] | | toàn bộ hành trình theo thứ tự, gồm cả transit |
| `duration_days` | int | ✅ | chuẩn hoá từ "3 ngày 4 đêm" / `P3D` |
| `duration_nights` | int | | |
| `price` | int | ✅ | giá tham chiếu (thấp nhất đã quan sát), đơn vị theo `currency` |
| `currency` | str | ✅ | ISO 4217, ví dụ `VND` |
| `price_type` | enum | | `fixed` \| `from` \| `contact` |
| `departure_pattern` | str | | "hàng tuần", "theo yêu cầu" khi không có ngày cụ thể |

## Tour.fields — soft (LLM so sánh)

| Field | Kiểu | Bắt buộc | Ghi chú |
|---|---|---|---|
| `itinerary` | text | ✅ | nguyên văn, không tóm tắt |
| `inclusions` | text | ✅ | nguyên văn |
| `exclusions` | text | ✅ | nguyên văn |
| `cancellation_policy` | text | | cho phép fallback chính sách site-wide, phải ghi rõ nguồn |

## Offer.fields

| Field | Kiểu | Bắt buộc | Ghi chú |
|---|---|---|---|
| `departure_date` | date | ✅ | ISO 8601 |
| `price` | int | ✅ | giá của đúng ngày khởi hành này |
| `price_type` | enum | | `fixed` \| `from` \| `contact` |
| `availability` | enum | | `available` \| `sold_out` \| `unknown` |
| `supplements` | text | | phụ thu phòng đơn, trẻ em... |

- Mỗi ngày khởi hành có giá riêng: giá thật để so nằm ở `Offer`, không ở `Tour`.
- Không gọi `valid_from` là `departure_date` nếu nguồn không nói rõ đó là ngày khởi hành.
- Khi nguồn không công bố ngày cụ thể: ghi `departure_pattern` ở `Tour.fields` kèm `status: partial`, và `offers` để rỗng.

## Required policy

| Mức | Field | Thiếu thì |
|---|---|---|
| Bắt buộc | `tour_name`, `url`, `departure_city`, `destinations`, `duration_days`, `price`, `currency`, `itinerary`, `inclusions`, `exclusions` | FAIL nguồn |
| Cho phép thiếu | `canonical_url`, `route`, `duration_nights`, `price_type`, `departure_pattern`, `cancellation_policy`, `availability`, `departure_date` | cảnh báo, không FAIL |
| Không bắt buộc | toàn bộ `Provider.fields` | bỏ qua |

`status: partial` vẫn dùng được để so, nhưng phải gắn cảnh báo trong kết quả hiển thị.

## Chuẩn hoá giá trị

- `currency`: `đ`, `VNĐ`, `VND` → `VND`.
- `duration_days` / `duration_nights`: parse từ "3 ngày 4 đêm" hoặc ISO 8601 duration `P3D`.
- `departure_date`: chỉ nhận ngày có ngữ cảnh lịch khởi hành; không nhận chuỗi ngày nằm ngoài cửa sổ quanh từ khoá khởi hành/lịch.
- `price`: bỏ dấu phân cách nghìn, giữ phần số.
- `destinations`: chỉ lấy từ chỗ nguồn đã phân loại sẵn (category, breadcrumb, location của structured data). Không suy từ tên tour.

## Giao diện backend–frontend

Backend cung cấp `POST /api/compare`:

```json
{ "tour_urls": ["https://example.test/tour/123", "https://example.test/tour/456"] }
```

Response:

```json
{
  "status": "partial",
  "tours": [],
  "trade_offs": [],
  "issues": [
    {
      "tour_url": "https://example.test/tour/123",
      "code": "unsupported_source",
      "message": "Chưa có dữ liệu cấu trúc cho nguồn này."
    }
  ]
}
```

- `status`: `completed` | `partial` | `error`.
- `partial`: một phần URL lỗi nhưng vẫn có tour so sánh được.
- Field tuỳ chọn thiếu không làm hỏng request: vẫn trả bản ghi với `not_observed`.
- Mỗi trade-off phải tham chiếu field/evidence làm căn cứ; không trả thứ hạng bí mật.

```json
{
  "criterion": "price",
  "summary": "Tour A rẻ hơn theo giá quan sát được; cần kiểm tra phụ thu còn thiếu.",
  "references": [
    {"tour_url": "https://example.test/tour/123", "field": "offers[].price"},
    {"tour_url": "https://example.test/tour/456", "field": "offers[].price"}
  ]
}
```

## Ngoài phạm vi contract

Đã cắt khỏi bộ field chuẩn vì không tạo giá trị so sánh: `tour_code` (user dùng `url` để xem trực tiếp), `route` dạng string gộp, `transport` tách riêng, license claims ép buộc.
