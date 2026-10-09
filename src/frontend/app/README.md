# App shell

Shell cung cấp navigation công khai, auth/account adapter, language/theme và sidebar phiên. Route đọc URL, back/forward đồng bộ; `tours?session=<local-id>` chọn phiên đã biết. Local metadata/draft/chat/IDs lưu browser; session bearer/expiry ở sessionStorage; không giả tài khoản.

Input: UI preferences và workspace state. Output: navigation không mất draft; tạo/ghim/đổi tên/xóa chỉ mục local; gọi job/resource BE qua workspace. Delete chỉ xóa lịch sử trên trình duyệt, không hủy job/delete BE vì chưa có lifecycle endpoint.

Preferences giữ VI/EN + light/dark độc lập dữ liệu source, áp semantic CSS roles và reduced-motion. Asset bản quyền lưu độc lập tại public/assets. Public form contact gửi ticket BE qua anonymous bearer. Auth giả định adapter được tài liệu hóa, không coi bearer auth là compatible v2 nếu BE chưa mapping.

Sidebar desktop mở mặc định 300px; thu gọn còn cột 64px, toàn cột là nút mở bằng click/Enter/Space. Chỉ có một nút thu gọn trong sidebar; nút toolbar dành cho drawer mobile. Kéo cạnh phải hoặc dùng phím trái/phải/Home/End để đổi rộng 240–520px, còn giới hạn theo viewport để giữ chỗ cho nội dung. Lưu rộng/trạng thái riêng trong localStorage; tên phiên có tooltip và có thể xuống dòng. Mobile giữ dialog có focus/Escape; reload trên mobile giữ lựa chọn độ rộng desktop.

Footer gồm Product & Tools, Account & Support, Legal & Security, liên kết đến route/chuyên mục có thật. Các mục dữ liệu, quyền truy cập và phạm vi sử dụng giải thích hành vi hiện tại tại trang Hỗ trợ; không tự công bố điều khoản pháp lý hoặc cam kết bảo mật. Navigation giữ hash để mở đúng chuyên mục.

Draft cũ được bổ sung các field tháng/khoảng ngân sách trước khi validate, giữ lịch chính xác và giá trần đã lưu; không xóa history khi đổi form.
