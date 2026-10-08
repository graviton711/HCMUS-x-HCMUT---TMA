# Hợp đồng dữ liệu và API

**Trạng thái:** Thiết kế field/API trước backend v1, giữ làm danh mục yêu cầu tham khảo; **không phải contract runtime hiện tại**. API `/api/compare`, wrapper observed/partial/not_observed và so sánh field mềm bằng LLM bên dưới chưa được implement theo thiết kế này.

Nguồn runtime chuẩn: [HTTP v1](../src/api/api-contract.md), [backend domain](../src/domain/backend-contracts.md), [crawler exchange](../src/data_access/crawler-contract.md), [schemas sinh từ models](../contracts/README.md). Giữ toàn bộ field/yêu cầu bên dưới để BE + crawler review; không loại bỏ vì backend hiện chưa trả. Khi bổ sung phải cập nhật contract v1, không tạo API chuẩn thứ hai.

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
| `transport` | enum | | `flight` \| `bus` \| `train` \| `cruise` \| `mixed` |
| `accommodation` | str | | tiêu chuẩn khách sạn/lưu trú, vd: `3_star`, `4_star`, `homestay` |
| `duration_days` | int | ✅ | chuẩn hoá từ "3 ngày 4 đêm" / `P3D` |
| `duration_nights` | int | | |
| `price` | int | ✅ | giá tham chiếu (thấp nhất đã quan sát), đơn vị theo `currency` |
| `currency` | str | ✅ | ISO 4217, ví dụ `VND` |
| `price_type` | enum | | `fixed` \| `from` \| `contact` |
| `departure_pattern` | str | | "hàng tuần", "theo yêu cầu" khi không có ngày cụ thể |
| `offers` | list[Offer] | | danh sách các lượt khởi hành theo ngày (nếu có) |

## Tour.fields — soft (LLM so sánh)

| Field | Kiểu | Bắt buộc | Ghi chú |
|---|---|---|---|
| `itinerary` | text | ✅ | nguyên văn, không tóm tắt |
| `inclusions` | text | ✅ | nguyên văn |
| `exclusions` | text | ✅ | nguyên văn |
| `cancellation_policy` | text | | cho phép fallback chính sách site-wide, phải ghi rõ nguồn |
| `surcharges` | text | | phụ thu nguyên văn: phòng đơn, Tết/lễ, tour nước ngoài, tip, visa |
| `child_policy` | text | | giá/điều kiện trẻ em nguyên văn: tuổi, % giá người lớn, giường phụ, trẻ nhỏ |

## Offer.fields

| Field | Kiểu | Bắt buộc | Ghi chú |
|---|---|---|---|
| `departure_date` | date | ✅ | ISO 8601 |
| `price` | int | ✅ | giá người lớn/combo của đúng ngày khởi hành này |
| `price_type` | enum | | `fixed` \| `from` \| `contact` |
| `availability` | enum | | `available` \| `sold_out` \| `unknown` |
| `supplements` | text | | phụ thu nguyên văn của lượt này |
| `tour_code` | str | | mã đặt được của lượt khởi hành |
| `price_by_age` | dict | | `{adult, child, small_child, infant}` int/null; định nghĩa dải tuổi nằm trong `child_policy` của Tour |
| `single_supplement` | int | | phụ thu phòng đơn của lượt này |
| `flights` | list[dict] | | `{flight_no, airline, dep_datetime, arr_datetime}` — không có với tour đường bộ |
| `conditions` | text | | điều kiện hoàn/hủy/đổi riêng của lượt (nếu khác chính sách chung) |
| `pickup_point` | text | | điểm/giờ tập trung của lượt |
| `hotel_location` | text | | khách sạn gắn với lượt (tour combo) |

- Mỗi ngày khởi hành có giá riêng: giá thật để so nằm ở `Offer`, không ở `Tour`.
- Không gọi `valid_from` là `departure_date` nếu nguồn không nói rõ đó là ngày khởi hành.
- Khi nguồn không công bố ngày cụ thể: ghi `departure_pattern` ở `Tour.fields` kèm `status: partial`, và `offers` để rỗng.

## Required policy

| Mức | Field | Thiếu thì |
|---|---|---|
| Bắt buộc | `tour_name`, `url`, `departure_city`, `destinations`, `duration_days`, `price`, `currency`, `itinerary`, `inclusions`, `exclusions` | FAIL nguồn |
| Cho phép thiếu | `canonical_url`, `route`, `duration_nights`, `price_type`, `departure_pattern`, `cancellation_policy`, `availability`, `departure_date`, `offers`, `surcharges`, `child_policy` | cảnh báo, không FAIL |
| Không bắt buộc | toàn bộ `Provider.fields` | bỏ qua |

`status: partial` vẫn dùng được để so, nhưng phải gắn cảnh báo trong kết quả hiển thị.

## Chuẩn hoá giá trị (Target Canonical Formats)

Mọi pipeline thu thập (Agent & Runner) phải làm sạch dữ liệu để khớp chính xác với định dạng đích sau:

- `currency`: `đ`, `VNĐ`, `VND` → `VND`.
- `duration_days` / `duration_nights`: Số nguyên `int`, trích xuất từ "3 ngày 4 đêm" hoặc `P3D`.
- `price`: Số nguyên `int`, bỏ dấu chấm/phẩy phân cách hàng nghìn.
- `destinations`: `list[str]` chuẩn Title Case (vd: `["Mộc Châu", "Sơn La"]`), không in hoa toàn bộ, không viết tắt, lọc từ taxonomy/breadcrumb của nguồn.
- `route`: `list[str]` các điểm dừng theo thứ tự hành trình, loại bỏ hoàn toàn slogan quảng cáo (vd: `["Hà Nội", "Thung Khe", "Mộc Châu"]`).
- `transport`: Enum chuẩn: `flight` | `bus` | `train` | `cruise` | `mixed`.
- `accommodation`: Chuẩn hóa: `homestay` | `2_star` | `3_star` | `4_star` | `5_star` | `mixed`.
- `itinerary`, `inclusions`, `exclusions`, `cancellation_policy`, `surcharges`, `child_policy`: **Plain text thuần túy**, sạch 100% thẻ HTML (`<p>`, `<br/>`), giải mã toàn bộ escaped entities (`\u003cbr/\u003e`, `&amp;`, `&quot;`, `-\t`), phân tách dòng bằng `\n- ` hoặc `\n`.
- `offers`: Mảng `list[dict]` các lượt khởi hành cụ thể (`departure_date`, `price`, `availability`, cùng các field phụ optional: `tour_code`, `price_by_age`, `single_supplement`, `flights`, `conditions`, `pickup_point`, `hotel_location`), rỗng nếu không có lịch cố định. datetime theo ISO 8601; field phụ nguồn không công bố thì bỏ hẳn khỏi dict (không ghi null thay bằng đoán).

## Định dạng lưu trữ Crawler Pipeline

Định dạng lưu trữ chuẩn của tầng thu thập dữ liệu là **JSON Lines (`.jsonl`)**:
- Mỗi dòng là 1 JSON object hoàn chỉnh của 1 Tour, giữ nguyên native types (`int`, `list[str]`, `list[dict]`).
- Cho phép stream đọc/ghi nối dòng với độ phức tạp bộ nhớ $O(1)$.


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

## Ghi chú field

`tour_code` dùng `url` để xem trực tiếp khi hiển thị, nhưng vẫn giữ trong `Offer` khi nguồn công bố để đối chiếu đặt chỗ. `route` lưu dạng list có thứ tự (không dùng string gộp). `transport` là enum chuẩn. `license_claims` giữ ở `Provider` dạng tự khai báo, không dùng làm bằng chứng xác minh.
