# Review tiếp theo — điều khiển và navigation

**Trạng thái:** PLANNING, cập nhật 06/10/2026. Giữ Giấy & Mực; thay hành vi sửa/tìm ở [review trước](frontend-review-2026-10-06.md). Chỉ chỉnh prototype ngoài `src/` và tài liệu; không thay API hiện hành.

## Hành vi đã chốt theo góp ý mới

- Sửa field: nút **Sửa** → diff trước/sau → tự cuộn đến khung xác nhận và focus hành động. Chat sửa và slider ở kết quả dùng chung cơ chế; reduced-motion dùng cuộn tức thì.
- Xác nhận cập nhật yêu cầu, **chưa tự tìm lại**. Nút **Tìm kiếm** ở heading kết quả hoặc chat “tìm kiếm đi” chạy theo yêu cầu đã xác nhận. Câu vừa sửa vừa yêu cầu tìm phải đợi xác nhận rồi mới chạy. Pending edit chặn tìm cho tới xác nhận/giữ nguyên.
- Bỏ nhãn v1/v2/... trên UI. Revision/job/snapshot vẫn giữ nội bộ; UI nói “Yêu cầu đã thay đổi”, “Kết quả theo yêu cầu trước” hoặc “Đang tìm kiếm”. Snapshot cũ còn xem trong lúc chờ/lỗi/hủy.
- Thanh mức độ sở thích 0–5: tiết kiệm chi phí, khách sạn tiện nghi, nhịp đi thư thả, trải nghiệm văn hóa. Có nhãn mức, thao tác bàn phím và mặc định mẫu rõ ràng. Form chỉnh draft; kết quả chỉnh cần xác nhận. Mức sở thích không tự thành hard constraint/điểm AI.
- Chữ nội dung/chats/table khoảng 14–16px, phụ chú ít nhất 12px; tăng spacing tương ứng, giữ bảng cuộn riêng và ba gợi ý desktop.
- Navigation lớn hơn: **Giới thiệu / Tìm tour / Liên hệ chúng tôi / Hỗ trợ người dùng**. Form, processing, kết quả và trao đổi phân tích đều thuộc Tìm tour. Quay lại tab này giữ bề mặt đang dùng; Liên hệ/Hỗ trợ có nội dung thật để review, không link chết hoặc địa chỉ liên hệ bịa.
- Navbar có active marker/hover và heading có reveal nhẹ/decorative ink line; chỉ animation transform/opacity, tôn trọng reduced-motion. Mobile đổi bố cục nav, không làm chữ nhỏ để lấp vừa.

## Ranh giới prototype và contract

- **G14 — Mức sở thích:** prototype giữ 4 mức cùng requirement/result snapshot; FE–BE còn chốt mapping vào preference tree/ranking policy. Không gửi tên field mẫu như DTO, không tự gắn trọng số hoặc xếp hạng thật.
- G11 giữ preview/confirm atomic; confirmation và search là hai action độc lập. G6/G9/G10/G12/G13 vẫn còn; không xóa bảo vệ revision chỉ vì bỏ số trên UI.
- Liên hệ chưa có địa chỉ/form gửi thật; giới thiệu nhóm/vai trò và tình trạng kênh liên hệ. Hỗ trợ hướng dẫn sửa/xác nhận/tìm/evidence, có đường về form hoặc kết quả. Không gửi dữ liệu ra ngoài.

## Kiểm tra

Sửa → auto-scroll/focus → xác nhận/hủy, slider keyboard/diff/draft, tìm bằng nút/chat/câu sửa+kèm tìm, chưa xác nhận không chạy, semantic stale/error/cancel/response muộn, navigation/Back/giữ context, reduced-motion, 1440/1280/768/390/320px. QA trước chỉ đại diện prototype cũ; ghi kết quả và ảnh lượt này riêng.

**Đã kiểm tra:** **57/57** đạt, không console error. 25 kiểm tra bố cục năm bề mặt/năm kích thước, 30 tương tác (auto-scroll/focus, confirm không tự tìm, nút/chat/câu sửa+kèm tìm, pending chặn tìm, snapshot sở thích, nav/background job, chữ lớn), bốn màu slider và reduced-motion. Chạy Chrome với trang/asset local, chưa backend/API/hosting. Ảnh/báo cáo QA chỉ local từ 07/10/2026, bản cũ vẫn có trong lịch sử Git; mở [khung prototype](../prototypes/frontend-design/viewer.html?design=paper) để xem giao diện.
