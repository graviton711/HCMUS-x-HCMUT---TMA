# Policy kiểm tra catalog trên backend hiện tại

Backend chỉ đọc catalog Supabase. Nguồn do người dùng khai báo là nguồn được duyệt; dữ liệu trong catalog là đầu vào có thẩm quyền cho quyết định. Snapshot normalization ánh xạ các trường DB, không xác minh lại domain hay metadata giá.

## Nguyên tắc

- Nguồn được duyệt khi được khai báo trong danh sách nguồn; runtime không áp dụng allowlist domain thứ hai.
- Backend dùng `offers.price` và currency để đánh giá ngân sách. `price_type` được giữ như metadata nguồn, không quyết định offer có đạt ngân sách hay được xếp giá. `tours.price_type` chỉ là tham chiếu cấp tour; metadata quote không thay thế các trường giá chuẩn.
- `observed_at` được giữ làm bằng chứng thời điểm ghi nhận; tuổi crawl không chặn so khớp ngày khởi hành với khoảng ngày người dùng yêu cầu.
- Lỗi Supabase được báo thẳng (`CATALOG_UNAVAILABLE`), không có fallback offline.

## Freshness và giá

- Freshness là thông tin nguồn riêng, không phải điều kiện để so khớp ngày: ngày khởi hành có trong offer được so trực tiếp với `date_from`/`date_to`, bất kể thời điểm crawl. Ngày thiếu hoặc sai định dạng là unknown. Pass ngày không xác nhận tour còn chỗ hay nhà cung cấp vẫn mở bán.
- Mọi `offers.price` dạng số có currency đều được dùng như giá công bố của offer, không phụ thuộc metadata `fixed`, `from`, `contact` hay `unknown`; thấp hơn hoặc bằng ngân sách thì đạt, cao hơn thì không đạt. Giá không có số hoặc currency là unknown.
- Giá công bố dùng để lọc và so sánh, không phải cam kết tổng tiền cuối cùng. Phụ phí và khoản loại trừ được phân tích riêng từ exclusions, surcharges và các field dịch vụ; chỉ khoản có số tiền, đơn vị và điều kiện áp dụng rõ mới được tính vào tổng đã biết.
- Metadata `offers.field_meta.pricing` là tùy chọn và chỉ bổ sung thông tin; không cần khớp raw columns để backend dùng giá catalog.
- TTL ngày khởi hành chỉ điều khiển nhãn freshness hiển thị, không làm thay đổi kết quả điều kiện ngày. Thiếu giá vẫn là unknown cho điều kiện ngân sách.

## Module ownership

`backend.data.catalog` đọc rows; `backend.normalize.snapshots` ánh xạ chúng thành snapshot; `backend.decide.engine` áp eligibility; `backend.api` serialize kết quả. Không thêm schema/API tree song song dưới `src/api`, `contracts/` hoặc `examples/`.
