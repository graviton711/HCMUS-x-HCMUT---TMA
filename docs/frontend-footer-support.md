# Footer và trợ giúp công khai

## Phạm vi

Giữ phong cách, tokens và route hiện hành. Footer giúp điều hướng, hiểu giới hạn nguồn/giá/AI và báo sai dữ liệu. Nội dung VI/EN tương đương; không công bố email, hotline, lịch cập nhật, chứng nhận hoặc thông tin nhóm chưa được xác nhận.

## Trách nhiệm và interface

- `app/Footer.tsx`: nhận handler link từ App, render brand + ba nhóm Khám phá / Tài khoản & Hỗ trợ / Thông tin & Quyền riêng tư. Giữ href thật để mở tab mới và back/forward. Dòng cuối giải thích phạm vi hỗ trợ so sánh; chưa bổ sung credit chưa xác nhận.
- `SupportPage`: hướng dẫn có anchor `compare`, FAQ `faq`, thông tin `sources`, `privacy`, `security`, `scope`. Native details cho FAQ; liên kết nội trang đi qua router để URL, cuộn và focus cùng đúng mục. Nội dung mô tả hành vi, không thay chính sách pháp lý chính thức.
- `ContactPage`: nhận category từ query đã allowlist `feedback|data_issue|support`. Link báo dữ liệu sai là `/contact?category=data_issue`; mặc định feedback nếu query thiếu/sai. Đổi category không xóa nội dung/email đã nhập. Submit giữ API/session/idempotency hiện hành.
- App theo dõi query/hash, điều hướng đến heading/section có thể focus, giữ modified-click/native href. Footer không gọi API riêng.

## Nội dung phải đúng

- Guest: metadata/draft/bản trao đổi lưu browser; token truy cập có thời hạn. Nội dung đã gửi cũng có record ở backend, xóa bản local không xóa record server.
- Account: nhu cầu và lịch sử đã lưu tải lại theo tài khoản trên thiết bị khác trong retention server; draft chưa gửi vẫn local. Nhập guest cần explicit action và quyền truy cập còn hạn. Archive ẩn khỏi history, không xóa toàn bộ job/evidence hoặc ngầm hủy job.
- FAQ giải thích không đạt hard khác với thiếu dữ kiện/quá cũ, ngân sách giá niêm yết và nhãn Từ/phụ thu/thực trả, hard/soft, OR tháng rời nhau, what-if chỉ phân tích phạm vi đã đọc và thay đổi cần xác nhận.
- Nguồn và AI: lấy nguồn được cấu hình/URL được phép, không hứa bao phủ mọi tour. Ngày và giá phải cùng lịch; xem nguồn/thời điểm/giới hạn tại từng dữ kiện. AI đọc nhu cầu và hỗ trợ phân tích sau lọc hard, không chứng nhận giá/chỗ còn hay uy tín thiếu nguồn. Chưa có lịch cập nhật định kỳ để công bố.
- Contacts chỉ tạo mã tiếp nhận; không hứa email tự động hoặc thời gian phản hồi. Phạm vi sản phẩm chưa booking/payment/seat confirmation.

## UI và kiểm chứng

- Căn footer theo content width; link khoảng 14px, vùng bấm ít nhất 44px cao; desktop bốn cột, mobile hai cột, không overflow ở 320px. Dùng semantic footer/nav với tên nhóm riêng, focus rõ, màu tokens cho hai theme.
- Kiểm link đúng anchor cả direct URL/reload/back/forward và bàn phím; FAQ Enter/Space mở đóng, focus không bị header che. VI/EN, light/dark ở desktop/mobile.
- Đổi ngôn ngữ giữ FAQ đang mở. Mobile nhóm thông tin chiếm hàng riêng, link chia hai cột để tránh cột cuối quá dài và khoảng trống lớn.
- Unit test cần thiết cho allowlist/query thay đổi giữ draft và contact gửi đúng category với idempotency; browser kiểm route/focus/FAQ/layout. Không tạo ticket/tài khoản thật hoặc gọi AI trong kiểm chứng công khai.
- Kết quả kiểm chứng ghi sau khi thực hiện, không coi unit pass là bằng chứng live nguồn tour.

## Kiểm chứng 10/10/2026

- Đã triển khai tại worktree `HCMUS-x-HCMUT---TMA-frontend-recovery`, branch `feature/minh-phu`; không đổi checkout/backend đang chạy của user.
- 84 unit/integration tests passed, gồm 3 test contact mới: category ngoài allowlist, đổi query giữ draft, gửi report và retry cùng key sau lỗi. Backend runtime integration dùng fixture cách ly.
- TypeScript/production build, lint và Prettier các file code thay đổi passed; `git diff --check` passed.
- Hai browser tests passed: các anchor đúng mục/focus, lặp cùng link, direct URL/reload/back/forward; FAQ Enter/Space và đổi ngôn ngữ giữ trạng thái; category contact qua query/back, email/message giữ nguyên.
- Layout kiểm ở 1440/1280/390/320px, VI/EN và light/dark: không overflow toàn trang, footer link >=44px cao. Đã xem ảnh desktop/mobile thực tế; nhóm cuối mobile chia hai cột.
- Ảnh ở `artifacts/frontend/footer-help-*` và `support-faq-*` (Git ignored). Browser public checks chặn transport auth/v2, không tạo ticket/tài khoản thật và không gọi AI/Supabase; không chứng minh luồng nguồn tour live.

## Bàn giao gộp

Theo yêu cầu user ngày 10/10, 23 file FE recovery/footer/support đã chuyển từ worktree nguồn sang checkout chính `HCMUS-x-HCMUT---TMA`, nhánh `backend`, để commit/push cùng BE một lần. Baseline hai checkout giống nhau; các file đích được kiểm chưa có sửa riêng trước khi chép. Không push nhánh `feature/minh-phu` trong lần bàn giao này.

Kiểm lại trên checkout chính: 84 frontend tests, build/TypeScript và lint passed; hai browser footer/help tests trên FE 5173 passed, gồm layout VI/EN/light/dark ở 1440/1280/390/320px. Backend 510 tests và Ruff passed. Các kiểm browser tiếp tục chặn auth/v2; không tạo dữ liệu thật.

Theo yêu cầu tiếp theo, worktree phụ đã gỡ khỏi Git và Desktop; bản sao code/tài liệu/artifacts cần giữ cùng phần folder còn lại được lưu local dưới `artifacts/worktree-backups/` (Git ignored). Từ nay FE và BE cùng làm trên `backend`. FE dev ở 5173 đã chuyển sang checkout chính; hai browser footer/help tests chạy lại tại đây passed.
