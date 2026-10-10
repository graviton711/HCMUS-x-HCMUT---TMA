# App shell

`/account` includes the personal Profile Hub. Supabase data is separate from SQLite search history; explicit reuse creates a new draft. Contract and setup: [Profile Hub](../../../docs/profile-hub.md).

Account navigation is one responsive six-view workspace; personal fields/avatar live in Profile and account/data/display actions in Settings. Signed-in header shows only an accessible round avatar. Layout and data contract: [account layout](../../../docs/profile-hub-layout.md). Avatar metadata/profile fields remain in the tab's Auth session; no extra persistent local cache or implicit search preference is created.

Shell cung cấp navigation công khai, auth/account adapter, language/theme và sidebar phiên. Route đọc URL, back/forward đồng bộ; `tours?session=<local-id>` chọn phiên đã biết. Local metadata/draft/chat/IDs lưu browser; session bearer/expiry ở sessionStorage; không giả tài khoản.

Input: UI preferences và workspace state. Output: navigation không mất draft; metadata/draft local cho guest, history server theo account; gọi job/resource BE qua workspace. Archive account ẩn history; không hủy job hoặc xóa evidence. [Contract auth/history](AUTH-ADAPTER.md).

Preferences giữ VI/EN + light/dark độc lập dữ liệu source, áp semantic CSS roles và reduced-motion. Asset bản quyền lưu độc lập tại public/assets. Public form contact gửi ticket BE qua anonymous bearer. Auth giả định adapter được tài liệu hóa, không coi bearer auth là compatible v2 nếu BE chưa mapping.

Sidebar desktop mở mặc định 300px; thu gọn còn cột 64px, toàn cột là nút mở bằng click/Enter/Space. Chỉ có một nút thu gọn trong sidebar; nút toolbar dành cho drawer mobile. Kéo cạnh phải hoặc dùng phím trái/phải/Home/End để đổi rộng 240–520px, còn giới hạn theo viewport để giữ chỗ cho nội dung. Lưu rộng/trạng thái riêng trong localStorage; tên phiên có tooltip và có thể xuống dòng. Mobile giữ dialog có focus/Escape; reload trên mobile giữ lựa chọn độ rộng desktop.

Footer gồm Khám phá, Tài khoản & Hỗ trợ, Thông tin & Quyền riêng tư; link đến hướng dẫn/FAQ/nguồn và AI/privacy/scope có anchor thật. Nội dung phân biệt guest/account, retention và archive; không tự công bố điều khoản pháp lý hoặc cam kết bảo mật. Navigation giữ query/hash và focus đúng mục. Contact allowlist category từ query để báo dữ liệu sai; không xóa message/email khi đổi category. [Contract footer/support](../../../docs/frontend-footer-support.md).

Draft cũ được bổ sung các field tháng/khoảng ngân sách trước khi validate, giữ lịch chính xác và giá trần đã lưu; không xóa history khi đổi form.
Preferences giữ VI/EN + light/dark độc lập dữ liệu source, áp semantic CSS roles và reduced-motion. Header có hai control riêng: VIE/ENG mở danh sách ngôn ngữ; nút mặt trời/mặt trăng đổi theme trực tiếp. Chọn ngôn ngữ đóng danh sách và trả focus; Escape/click ngoài đóng danh sách. Giữ localStorage key hiện hành và đồng bộ giữa tab. Target nút tối thiểu 44px, dropdown vừa viewport; màn hình <=420px dùng icon account kèm accessible name để header không chen chúc.

Asset bản quyền lưu độc lập tại public/assets. Public form contact gửi ticket BE qua anonymous bearer. Account bearer qua Supabase Auth adapter đã được BE verify và map owner v2.

Kiểm chứng control hiển thị 09/10: browser responsive ở 1440/1280/390/320px qua cả VI/EN, sáng/tối, đóng menu/focus và reload; lint/TypeScript/production build passed. Ảnh `artifacts/frontend/header-controls-*` và `language-menu-*` dùng phiên test ẩn danh, không chứa tài khoản thật.
