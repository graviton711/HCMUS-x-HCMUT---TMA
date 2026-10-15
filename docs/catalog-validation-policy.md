# Policy kiểm tra catalog trên backend hiện tại

Backend chỉ đọc catalog Supabase. Nguồn do người dùng khai báo là nguồn được duyệt; dữ liệu trong catalog là đầu vào có thẩm quyền cho quyết định. Snapshot normalization ánh xạ các trường DB, không xác minh lại domain hay metadata giá.

## Nguyên tắc

- Nguồn được duyệt khi được khai báo trong danh sách nguồn; runtime không áp dụng allowlist domain thứ hai.
- Backend dùng `offers.price`, `offers.price_type` và currency trong catalog để đánh giá ngân sách. `tours.price_type` chỉ là tham chiếu cấp tour, không được kế thừa cho offer. Metadata quote không thay thế các trường chuẩn.
- `observed_at` được giữ làm bằng chứng thời điểm ghi nhận; tuổi giá không chặn pass/fail ngân sách.
- Fixture là explicit cho dev/test; lỗi Supabase không fallback fixture.

## Freshness và giá

- Freshness TTL chỉ áp dụng cho ngày khởi hành; không áp dụng TTL giá trong quyết định ngân sách.
- `offers.price_type=fixed` được so trực tiếp với ngân sách. `from` luôn là lower bound: vượt trần thì fail, không vượt trần thì unknown. Giá `contact`, `unknown` hoặc thiếu basis là unknown.
- Metadata `offers.field_meta.pricing` là tùy chọn và chỉ bổ sung thông tin; không cần khớp raw columns để backend dùng giá catalog. Không suy giá cuối cùng từ giá `from`.
- Ngày khởi hành stale vẫn là unknown cho điều kiện ngày; thiếu giá vẫn là unknown cho điều kiện ngân sách.

## Module ownership

`backend.data.catalog` đọc rows; `backend.normalize.snapshots` ánh xạ chúng thành snapshot; `backend.decide.engine` áp eligibility; `backend.api` serialize kết quả. Không thêm schema/API tree song song dưới `src/api`, `contracts/` hoặc `examples/`.
