# App shell

Shell cung cấp navigation công khai, auth/account adapter, language/theme và sidebar phiên. Route đọc URL, back/forward đồng bộ; `tours?session=<local-id>` chọn phiên đã biết. Local metadata/draft/chat/IDs lưu browser; session bearer/expiry ở sessionStorage; không giả tài khoản.

Input: UI preferences và workspace state. Output: navigation không mất draft; tạo/ghim/đổi tên/xóa chỉ mục local; gọi job/resource BE qua workspace. Delete chỉ xóa lịch sử trên trình duyệt, không hủy job/delete BE vì chưa có lifecycle endpoint.

Preferences giữ VI/EN + light/dark độc lập dữ liệu source, áp semantic CSS roles và reduced-motion. Asset bản quyền lưu độc lập tại public/assets. Public form contact gửi ticket BE qua anonymous bearer. Auth giả định adapter được tài liệu hóa, không coi bearer auth là compatible v2 nếu BE chưa mapping.
