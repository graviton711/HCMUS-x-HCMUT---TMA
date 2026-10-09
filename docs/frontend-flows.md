# Luồng và trạng thái frontend

Tài liệu mô tả frontend React đang chạy tại [src/frontend](../src/frontend/README.md). Request/response dựa trên API v2; [giới hạn tích hợp](../src/frontend/BACKEND-GAPS.md) phân biệt chức năng hiện có và các service còn thiếu.

## Luồng chính

Giới thiệu → phiên ẩn danh hoặc identity adapter → Tìm tour → nhập nhu cầu/URL/chat → review → xác nhận → tìm kiếm → bảng so sánh/phân tích/evidence.

| Bề mặt             | Input và hành vi                                                          | Output / interface                                            |
| ------------------ | ------------------------------------------------------------------------- | ------------------------------------------------------------- |
| Giới thiệu, hỗ trợ | Nội dung sản phẩm và ảnh điểm đến                                         | Navigation; ảnh không đại diện tour/giá thật                  |
| Auth, tài khoản    | Adapter được cấu hình hoặc tiếp tục ẩn danh                               | Identity adapter tách khỏi bearer phiên API v2                |
| Form               | Structured fields, text, URLs và notes; canonical options từ catalog      | Draft local, requirement hoặc proposal backend                |
| Review             | Các thay đổi trước/sau, clarification, expected revision/proposal version | Confirm atomic, cancel hoặc discard; giữ draft khi conflict   |
| Tìm kiếm           | Requirement đã xác nhận và hành động tìm explicit                         | Comparison/job; kiểm health, provider và worker trước enqueue |
| Kết quả            | Snapshot backend, nhóm gợi ý và URL tham chiếu                            | Cards, bảng dữ kiện, phân tích, chọn offer và evidence        |
| Liên hệ            | Nội dung/loại yêu cầu và context                                          | Ticket backend; không coi ticket là email đã gửi              |

## Draft, proposal và xác nhận

- Form, direct edits, sliders và chat dùng cùng workflow proposal. Draft chưa gửi không ghi đè committed requirement.
- Structured form chỉ được gửi sau review. Text/URL-only tạo proposal; URL-only không ép điểm đến/người lớn/ngân sách/ngày hoặc suy sở thích từ tour.
- Sửa field giữ condition IDs, operators, hard/soft và cây AND/OR. Nhiều predicates cùng field hoặc budget ngoài phạm vi control được giữ; sửa qua chat khi control không biểu diễn đủ.
- Clarification và confirm dùng version backend. `409` giữ draft/proposal và cho tải lại trạng thái; không tự ghi đè dữ liệu server.
- Confirm chỉ commit nhu cầu; tìm kiếm là hành động riêng. Cancel/discard khôi phục theo backend, không dùng PATCH v1 như preview.

## Kết quả và tác vụ

- Backend chọn/rank tối đa ba recommendation; UI giữ các cột tham chiếu, URL chưa đọc được và dữ kiện thiếu. Không tự tính rank/giá hoặc bổ sung tour để đủ ba.
- Hard fail, unknown, unsupported và conflict giữ ý nghĩa từ backend. Giá giữ currency, kind, basis, coverage, nhóm tuổi và điều kiện áp dụng.
- Phân tích dùng claims, phép tính, limitations và semantic assessments backend trả; evidence gắn đúng tour/offer/field/snapshot.
- Chọn offer hoặc yêu cầu nhóm khác tạo comparison mới theo API. Snapshot cũ vẫn xem được khi đang chờ, lỗi hoặc criteria mới chưa được đánh giá.
- Poll jobs/events theo cursor và drain `has_more` sau terminal. Activity dùng events thật; cancel job là hành động riêng. Không phát search khi `/health` báo nguồn synthetic hoặc worker tắt.

## Phiên, navigation và lưu trữ

- Sidebar quản lý chỉ mục/history local: tạo, tìm, ghim, đổi tên, xóa và chuyển phiên. Xóa local không xóa resource backend hoặc tự hủy job.
- Draft/chat/IDs lưu localStorage; bearer và expiry lưu sessionStorage. Resume gọi GET với IDs và quyền truy cập còn hạn; IDs local không thay token.
- Đổi phiên/unmount hủy request frontend; response muộn không ghi đè phiên khác. Đổi route/reload không tự confirm/search hoặc hủy job server.
- VI/EN và sáng/tối lưu độc lập identity/history; dữ liệu nguồn và nội dung người dùng giữ nguyên.
- Auth/profile/history đồng bộ đa thiết bị cần backend contract. Endpoint auth giả định tại [AUTH-ADAPTER.md](../src/frontend/app/AUTH-ADAPTER.md).

Bố cục: [wireframes](wireframes.md). Interfaces: [API boundary](../src/frontend/api/README.md), [workspace](../src/frontend/features/workspace/README.md), [results](../src/frontend/features/workspace/Results.md).
