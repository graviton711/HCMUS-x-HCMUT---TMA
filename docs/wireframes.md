# Bố cục frontend

Các bề mặt dưới đây mô tả frontend React; [flow](frontend-flows.md) xác định lifecycle và [giới hạn backend](../src/frontend/BACKEND-GAPS.md) xác định tính năng cần service bổ sung. Prototype HTML là tài liệu tham khảo riêng tại [prototypes/frontend-design](../prototypes/frontend-design/README.md).

## Trang công khai

```text
Navigation: Giới thiệu | Tìm tour | Liên hệ | Hỗ trợ | Auth/account
Toolbar: ngôn ngữ và sáng/tối
Nội dung trang
Footer
```

Giới thiệu dùng ảnh điểm đến và nội dung sản phẩm. Liên hệ có form gửi ticket. Hỗ trợ có hướng dẫn sử dụng; không hiển thị tour/giá/thời tiết mô phỏng như dữ liệu thật.

## Auth và tài khoản

```text
Desktop: ảnh điểm đến | form đăng nhập/đăng ký
Mobile: form và nội dung xếp dọc
Hành động: đăng nhập/đăng ký | Google | tiếp tục phiên ẩn danh
Tài khoản: hồ sơ và trạng thái identity adapter
```

Login/Google chỉ bật khi adapter tương ứng được cấu hình. Thông báo thiếu service hiển thị tại form; tiếp tục ẩn danh sử dụng session backend thật.

## Workspace Tìm tour

```text
Sidebar phiên | Header phiên / lượt tìm
              | Form nhu cầu + URLs + notes/chat
              | Review thay đổi / clarification
              | Xác nhận hoặc hủy
              | Tìm kiếm
              | Criteria | Cards / Bảng dữ kiện / Phân tích AI
              | Composer chat và nhật ký job
```

- Sidebar desktop có thể thu gọn; mobile dùng drawer. Chuyển phiên giữ draft và snapshot của từng phiên.
- Form có nhóm bắt buộc/tùy chọn theo loại input; URL-only không bắt nhập toàn bộ structured fields.
- Review nằm trong workspace, thể hiện diff trước/sau và version conflict. Confirm và tìm kiếm là hai thao tác riêng.
- Criteria có controls dựa catalog; sửa trực tiếp/chat/slider tạo proposal trước khi thay committed requirement.
- Cards render tối đa ba recommendation backend chọn. Bảng giữ toàn bộ columns, kể cả URL tham chiếu chưa đủ dữ kiện, và cuộn ngang trong vùng riêng.
- Facts/Phân tích AI dùng cùng snapshot; đổi offer chờ comparison mới, không đổi giá/evidence cũ ngầm.

## Evidence và trạng thái

Evidence mở trong dialog: tour/offer/field, trích dẫn hoặc provenance, source link, thời điểm và giới hạn dữ liệu. Đóng dialog trả focus; bàn phím hỗ trợ tab/navigation và reduced-motion.

Loading, pending changes, kết quả cũ, empty/partial/error/cancel có nhãn riêng. Hard status, độ đầy đủ, verification và freshness giữ metadata backend; timestamp không tự chứng minh dữ liệu mới/xác minh.

## Giao diện responsive

Semantic CSS tokens cho nền giấy ấm, xanh sâu/đất nung, Newsreader và Be Vietnam Pro; VI/EN và sáng/tối. Mobile xếp nội dung dọc, bảng cuộn riêng và dialog trong viewport. Motion opacity/transform tôn trọng reduced-motion. Kiểm tra layout và workflow tại [tests](../src/frontend/tests/README.md).
