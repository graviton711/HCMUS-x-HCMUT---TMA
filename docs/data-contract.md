# Hợp đồng dữ liệu và API

**Trạng thái:** Contract MVP để frontend, backend và phần crawl/data làm song song.

## Phạm vi MVP

- Người dùng nhập 2–3 URL tour để so sánh trực tiếp. Tìm tour từ mô tả nhu cầu là bước sau.
- Backend bắt đầu bằng các fixture `Tour`/`Offer` chuẩn hóa; thay nguồn fixture bằng adapter khi data thật sẵn sàng.
- Crawler audit hiện tại mô tả website cung cấp được gì; report audit không phải bản ghi tour đầu vào của bộ so sánh.

## Dữ liệu chuẩn hóa

Tách thông tin tương đối ổn định của tour khỏi `Offer` biến động theo ngày khởi hành. Mỗi field dùng cùng wrapper:

```json
{
  "value": "Hà Nội",
  "raw_value": "Ha Noi",
  "status": "found",
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

- `value` là giá trị đã chuẩn hóa để so sánh; `raw_value` giữ giá trị nguồn khi có biến đổi.
- `status` là `found` hoặc `not_observed`; thiếu dữ liệu biểu diễn bằng `value: null`, không tự điền.
- `verification_status` là `provider_claimed` hoặc `independently_verified`; nội dung trên website nhà cung cấp mặc định là tự khai báo, không phải xác minh độc lập.
- `observed_at` ghi thời điểm thu thập, không có nghĩa dữ liệu là thời gian thực. Gắn timestamp riêng cho từng field offer như giá, ngày khởi hành và tình trạng chỗ.

`Provider` là hồ sơ nhà cung cấp; `Tour` tham chiếu nhà cung cấp và giữ các field có ích để đối chiếu; `Offer` tách từng lựa chọn khởi hành và thông tin biến động. Mỗi giá trị trong cả ba entity có evidence riêng.

Khóa chuẩn:

- `Provider.fields`: `display_name`, `legal_name`, `description`, `email`, `phone`, `address`, `website`, `license_claims`.
- `Tour.fields`: `tour_code`, `title`, `description`, `route`, `duration`, `departure_city`, `transport`, `itinerary_by_day`, `included`, `excluded`, `policies`.
- `Offer.fields`: `offer_code`, `departure_date`, `valid_from`, `valid_through`, `price`, `availability`, `supplements`.
- Không coi `valid_from` là `departure_date` nếu nguồn không nói rõ đó là ngày khởi hành.
- Mỗi `Provider` có `id` và `fields`; mỗi `Tour` có `url`, `provider` (một `Provider`), `fields` và danh sách `offers`; mỗi `Offer` có `fields` riêng theo cùng wrapper. Field chưa thấy vẫn có mặt với `value: null`, `status: "not_observed"` và `evidence: []`.

## Giao diện backend–frontend

Backend cung cấp `POST /api/compare` với JSON body:

```json
{ "tour_urls": ["https://example.test/tour/123", "https://example.test/tour/456"] }
```

Response JSON có cấu trúc:

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

`status` là `completed` khi đã xử lý được tất cả URL; `partial` khi một phần URL lỗi nhưng vẫn có tour để so sánh; `error` khi request không hợp lệ hoặc không có tour nào xử lý được. Field tùy chọn bị thiếu không tự làm hỏng request: vẫn trả bản ghi với `not_observed`. Mỗi trade-off phải tham chiếu field/evidence làm căn cứ; không trả thứ hạng bí mật hay kết luận không có nguồn. `issues` chứa lỗi theo URL, như URL không lấy được hoặc nguồn chưa hỗ trợ.

Mỗi phần tử `trade_offs` có dạng:

```json
{
  "criterion": "price",
  "summary": "Tour A rẻ hơn theo mức giá quan sát được; cần kiểm tra phụ thu còn thiếu.",
  "references": [
    {"tour_url": "https://example.test/tour/123", "field": "offers[].price"},
    {"tour_url": "https://example.test/tour/456", "field": "offers[].price"}
  ]
}
```

Ở giai đoạn fixture, request vẫn dùng URL để frontend tích hợp với đúng luồng; backend ánh xạ các URL mẫu sang bản ghi fixture. Chưa khóa framework, database hay cách triển khai crawler runtime.
