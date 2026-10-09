# App shell

Shell cung cấp navigation công khai, auth/account adapter, language/theme và sidebar phiên. Route đọc URL, back/forward đồng bộ; `tours?session=<local-id>` chọn phiên đã biết. Local metadata/draft/chat/IDs lưu browser; session bearer/expiry ở sessionStorage; không giả tài khoản.

Input: UI preferences và workspace state. Output: navigation không mất draft; metadata/draft local cho guest, history server theo account; gọi job/resource BE qua workspace. Archive account ẩn history; không hủy job hoặc xóa evidence. [Contract auth/history](AUTH-ADAPTER.md).

Preferences giữ VI/EN + light/dark độc lập dữ liệu source, áp semantic CSS roles và reduced-motion. Header có hai control riêng: VIE/ENG mở danh sách ngôn ngữ; nút mặt trời/mặt trăng đổi theme trực tiếp. Chọn ngôn ngữ đóng danh sách và trả focus; Escape/click ngoài đóng danh sách. Giữ localStorage key hiện hành và đồng bộ giữa tab. Target nút tối thiểu 44px, dropdown vừa viewport; màn hình <=420px dùng icon account kèm accessible name để header không chen chúc.

Asset bản quyền lưu độc lập tại public/assets. Public form contact gửi ticket BE qua anonymous bearer. Account bearer qua Supabase Auth adapter đã được BE verify và map owner v2.

Kiểm chứng control hiển thị 09/10: browser responsive ở 1440/1280/390/320px qua cả VI/EN, sáng/tối, đóng menu/focus và reload; lint/TypeScript/production build passed. Ảnh `artifacts/frontend/header-controls-*` và `language-menu-*` dùng phiên test ẩn danh, không chứa tài khoản thật.
