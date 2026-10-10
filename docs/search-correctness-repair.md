# Nâng độ đúng của tìm kiếm trên backend hiện tại

Các thay đổi dưới đây được port từ điều tra trên `main` vào modules hiện có; ghi chú nguồn trong [`search-correctness-verification.md`](search-correctness-verification.md) chỉ là bằng chứng lịch sử, không thay regression trên backend hiện tại.

## Destination và route

- `destinations` là nơi tham quan; `route` giữ nguyên tuyến nguồn để giải thích. Bỏ origin trùng ở đầu/cuối khỏi destination đã chuẩn hóa, nhưng giữ nguyên raw/evidence/route.
- Nếu chỉ còn origin thì destination là unknown; origin nằm giữa tuyến không bị bỏ.
- Alias/taxonomy dùng chung cho structured và text extraction. Tên chưa map là partial/unknown, không dùng absence để loại tour.
- Country match cần evidence từ destination places, không suy tour trong nước từ điểm khởi hành.

## Freshness và giá

- Freshness policy local mặc định 24 giờ cho `departure_date` và `price`; không sửa `observed_at`. Thiếu timestamp, stale hoặc timestamp tương lai không chứng minh hard pass/fail.
- `offers.field_meta.pricing` là optional. Chỉ xác thực giá có cấu trúc nếu quote gắn đúng offer, amount/currency/kind/basis/observation time khớp raw fields và nguồn nằm trong allowlist cấu hình.
- `from` là lower bound, không phải giá exact. Không suy tổng chuyến, phụ thu bằng 0, applicability hay tuổi trẻ em. Metadata thiếu/sai giữ preview nhưng evaluation `unknown` và verification `unverified`.
- Giá chỉ được so với hard budget khi currency, basis và coverage tương thích; lựa chọn offer unknown không nâng eligibility.

## Frontend

- Nhật ký phân biệt event bắt đầu, hoàn tất, bỏ qua và lỗi; không diễn đạt trạng thái bắt đầu như đang chạy vô thời hạn.
- Kết quả nêu riêng số tour đủ dữ liệu, chưa xác nhận, bị loại và phạm vi scan/pool/offer. Đếm tour duy nhất theo blocker, giữ diagnostics từng offer.
- Bảng so sánh không gọi mọi cột là “tour phù hợp”; unknown/blocker được render từ DTO backend.

## History/what-if

Khôi phục resource từ persisted requirement/comparison/what-if references sau terminal state; owner checks và CAS không đổi. What-if chỉ phân tích snapshot bị ràng buộc và tạo proposal để user review/confirm.

## Nghiệm thu

Regression cần bao gồm: endpoint origin không gây match nhầm quốc gia; route vẫn giữ raw; alias structured/text thống nhất; unknown/OR không bị biến thành fail; ngày fresh mismatch/fresh match/stale/missing policy; exact/from/metadata thiếu, sai và untrusted; completed history reference; UI VI/EN cho blockers và giới hạn retrieval. Chạy toàn bộ offline tests; Supabase nếu có chỉ đọc.
