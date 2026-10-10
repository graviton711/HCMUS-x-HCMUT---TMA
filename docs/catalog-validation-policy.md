# Policy kiểm tra catalog trên backend hiện tại

Backend chỉ đọc catalog Supabase. Các trạng thái dưới đây được quyết định trong `src/backend/normalize`; frontend không tự nâng độ tin cậy. Snapshot normalization hiện áp dụng freshness TTL và kiểm tra metadata giá theo policy này.

## Nguyên tắc

- Crawler giữ raw value, record key, source URL, evidence và `observed_at`; backend kiểm tra binding/shape trước khi dùng cho hard evaluation.
- Chỉ domain nguồn được cấu hình chính xác mới có thể coi metadata giá là trusted; không wildcard/subdomain ngầm, không tin chỉ vì provider đang bật.
- Dữ liệu sai shape, timestamp tương lai, timestamp không khớp offer hoặc metadata mâu thuẫn chỉ được giữ để preview, không dùng để chứng minh pass/fail.
- Trusted price metadata không đồng nghĩa kiểm chứng độc lập về chất lượng tour. Evidence website và catalog validation là hai nguồn khác nhau.
- Fixture là explicit cho dev/test; lỗi Supabase không fallback fixture.

## Freshness và giá

- Policy TTL phải cấu hình rõ theo field; cadence local được chốt là 24 giờ cho `departure_date` và `price`. Không sửa timestamp để làm dữ liệu trông mới.
- `price_type=from` không bao giờ thành exact. Giá chỉ so khi amount, currency, basis và coverage phù hợp.
- Metadata `offers.field_meta.pricing` là optional; quote phải khớp raw amount/type/currency/time và đúng offer. Không suy `complete`, phụ thu, trẻ em hay coverage từ trường rỗng.
- Stale/missing/invalid data vẫn có thể hiển thị raw evidence nhưng eligibility là unknown.

## Module ownership

`backend.data.catalog` đọc rows; `backend.normalize.snapshots` kiểm tra và tạo snapshot; `backend.decide.engine` áp eligibility; `backend.api` serialize kết quả. Không thêm schema/API tree song song dưới `src/api`, `contracts/` hoặc `examples/`.
