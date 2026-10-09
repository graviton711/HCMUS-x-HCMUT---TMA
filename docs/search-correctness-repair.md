# Sửa tìm tour — 09/10/2026

Đã triển khai và kiểm chứng: [báo cáo](search-correctness-verification.md).

Phạm vi đã được user cho phép: FE/BE trên `backend`; catalog Supabase chỉ đọc. Giữ hard → soft → LLM, snapshot lịch sử và các thay đổi chưa commit.

## Quy tắc triển khai

- Điểm xuất phát ở hai đầu danh sách destinations không là điểm đến tham quan khi còn điểm khác. Chuẩn hóa alias trước khi bỏ endpoints, giữ nguyên raw/evidence và route. Danh sách chỉ có origin giữ unknown; điểm origin giữa hành trình không bị bỏ. Mở rộng catalog địa danh có giới hạn; cùng hierarchy được dùng cho cả structured SetValue và EntitySetValue v2. Tên chưa biết vẫn partial, không dùng absence để loại tour.
- Ngày/giá: user chọn cadence dự kiến một ngày. Cấu hình local TTL 86400 giây cho departure_date và price; không đổi observed_at, không nâng dữ liệu cũ thành mới. Tách thiếu policy, dữ liệu stale và timestamp bất thường. Hard mismatch trên lịch mới phải fail; lịch cũ/unknown chưa chứng minh pass/fail hiện tại. Chọn offer unknown được phép xem, không nâng eligibility; stale selection vẫn bị chặn.
- Optional `offers.field_meta.pricing` nhận bảng giá có cấu trúc và assertion đầy đủ, ràng buộc amount với price_by_age, currency/kind với tour, timestamp với offer, provenance nguồn opt-in. Không tạo metadata khi chưa có. Giá from có lower bound và upper=null; không đạt hard cap chỉ vì lower thấp. Không suy phụ thu bằng 0 hoặc tuổi trẻ em. Metadata sai giữ preview unverified và issue riêng.
- UI: nhật ký started là sự kiện đã bắt đầu; hiển thị rõ completed/skipped và tên orchestration. Nêu số tour chưa xác nhận, blockers theo field (đếm tour duy nhất, ưu tiên per-offer diagnostics), giới hạn scan/pool/offers và lý do LLM bỏ qua. Bảng đối chiếu không được gọi toàn bộ là tour phù hợp.
- Lịch sử: refs đọc requirement_id trong payload queued và wrapper result của comparison/what-if hoàn thành. Owner check/CAS không đổi.

## Nghiệm thu

Regression: tour nước ngoài có TP.HCM ở endpoints không pass Việt Nam; structured/semantic hierarchy nhất quán; domestic destination pass; partial unknown và OR giữ đúng; ngày fresh mismatch/fresh match/stale/missing-policy; giá exact/from/metadata thiếu/sai và source untrusted; offer selection unknown; completed history resume; nhật ký terminal và diagnostics VI/EN.

Chạy BE regression và FE tests/lint/typecheck/build. Replay snapshot ca 21:27 bằng adapter mới và thử Supabase read-only với application store tạm nếu khả dụng. Báo riêng dữ liệu thiếu/stale và lỗi implementation; không hứa có recommendation khi catalog chưa đủ giá/ngày. Sau sửa phải tạo lượt tìm mới; comparison đã lưu không đổi.

Browser test bảng đối chiếu dùng bản sao DTO test, thêm scope retrieval bị giới hạn để kiểm panel chẩn đoán tại 1440/1280/390/320px. Dữ liệu test không chứng minh nguồn live. Các field trong panel dùng tên VI/EN, gồm estimated_cost là Chi phí.
