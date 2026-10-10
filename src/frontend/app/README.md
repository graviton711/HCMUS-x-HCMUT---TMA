# App shell

Shell cung cấp navigation công khai, account UI scaffold, language/theme và sidebar phiên. Route đọc URL, back/forward đồng bộ; `tours?session=<local-id>` chọn phiên đã biết. Local metadata/draft/chat/IDs lưu browser. Account UI chưa nối backend vì `src/backend` chưa có Auth/history routes.

Input: UI preferences và workspace state. Output: navigation không mất draft; metadata/draft local cho guest và workspace actions. Server history/archive/job đang là target, không được coi là connected. [Contract auth/history](AUTH-ADAPTER.md).

Preferences giữ VI/EN + light/dark độc lập dữ liệu source, áp semantic CSS roles và reduced-motion. Asset bản quyền lưu độc lập tại public/assets. Public form contact gửi ticket BE qua anonymous bearer. Auth giả định adapter được tài liệu hóa, không coi bearer auth là compatible v2 nếu BE chưa mapping.

Sidebar desktop mở mặc định 300px; thu gọn còn cột 64px, toàn cột là nút mở bằng click/Enter/Space. Chỉ có một nút thu gọn trong sidebar; nút toolbar dành cho drawer mobile. Kéo cạnh phải hoặc dùng phím trái/phải/Home/End để đổi rộng 240–520px, còn giới hạn theo viewport để giữ chỗ cho nội dung. Lưu rộng/trạng thái riêng trong localStorage; tên phiên có tooltip và có thể xuống dòng. Mobile giữ dialog có focus/Escape; reload trên mobile giữ lựa chọn độ rộng desktop.

Footer gồm Product & Tools, Account & Support, Legal & Security, liên kết đến route/chuyên mục có thật. Các mục dữ liệu, quyền truy cập và phạm vi sử dụng giải thích hành vi hiện tại tại trang Hỗ trợ; không tự công bố điều khoản pháp lý hoặc cam kết bảo mật. Navigation giữ hash để mở đúng chuyên mục.

Draft cũ được bổ sung các field tháng/khoảng ngân sách trước khi validate, giữ lịch chính xác và giá trần đã lưu; không xóa history khi đổi form.
Preferences giữ VI/EN + light/dark độc lập dữ liệu source, áp semantic CSS roles và reduced-motion. Header có hai control riêng: VIE/ENG mở danh sách ngôn ngữ; nút mặt trời/mặt trăng đổi theme trực tiếp. Chọn ngôn ngữ đóng danh sách và trả focus; Escape/click ngoài đóng danh sách. Giữ localStorage key hiện hành và đồng bộ giữa tab. Target nút tối thiểu 44px, dropdown vừa viewport; màn hình <=420px dùng icon account kèm accessible name để header không chen chúc.

Asset bản quyền lưu độc lập tại public/assets. Public contact/account backend flows còn chờ port; không hiển thị như tính năng đã kết nối.

Kiểm chứng control hiển thị thuộc implementation nguồn trên `main`; các test hiện tại kiểm UI fixtures, không chứng minh account/history backend.
