# Policy kiểm tra catalog trên backend hiện tại

Backend chỉ đọc catalog Supabase. Nguồn do người dùng khai báo là nguồn được duyệt; dữ liệu trong catalog là đầu vào có thẩm quyền cho quyết định. Snapshot normalization ánh xạ các trường DB, không xác minh lại domain hay metadata giá.

## Nguyên tắc

- Nguồn được duyệt khi được khai báo trong danh sách nguồn; runtime không áp dụng allowlist domain thứ hai.
- Backend dùng `offers.price`, `offers.price_type` và currency trong catalog để đánh giá ngân sách. `tours.price_type` chỉ là tham chiếu cấp tour, không được kế thừa cho offer. Metadata quote không thay thế các trường chuẩn.
- `observed_at` được giữ làm bằng chứng thời điểm ghi nhận; tuổi crawl không chặn so khớp ngày khởi hành với khoảng ngày người dùng yêu cầu.
- Fixture là explicit cho dev/test; lỗi Supabase không fallback fixture.

## Freshness và giá

- Freshness là thông tin nguồn riêng, không phải điều kiện để so khớp ngày: ngày khởi hành có trong offer được so trực tiếp với `date_from`/`date_to`, bất kể thời điểm crawl. Ngày thiếu hoặc sai định dạng là unknown. Pass ngày không xác nhận tour còn chỗ hay nhà cung cấp vẫn mở bán.
- `offers.price_type=fixed` được so trực tiếp với ngân sách. `from` luôn là lower bound: vượt trần thì fail, không vượt trần thì unknown. Giá `contact`, `unknown` hoặc thiếu basis là unknown.
- Metadata `offers.field_meta.pricing` là tùy chọn và chỉ bổ sung thông tin; không cần khớp raw columns để backend dùng giá catalog. Không suy giá cuối cùng từ giá `from`.
- TTL ngày khởi hành chỉ điều khiển nhãn freshness hiển thị, không làm thay đổi kết quả điều kiện ngày. Thiếu giá vẫn là unknown cho điều kiện ngân sách.

## Module ownership

`backend.data.catalog` đọc rows; `backend.normalize.snapshots` ánh xạ chúng thành snapshot; `backend.decide.engine` áp eligibility; `backend.api` serialize kết quả. Không thêm schema/API tree song song dưới `src/api`, `contracts/` hoặc `examples/`.
