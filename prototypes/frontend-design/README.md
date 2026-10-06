# Prototype review frontend — P3

**Trạng thái:** PLANNING. Ngày 06/10/2026 user chốt Giấy & Mực. Mở rộng prototype A thành Giới thiệu → Form/xác nhận → Kết quả có chat và Phân tích AI theo [review nhóm](../../docs/frontend-review-2026-10-06.md); B giữ làm tham khảo lịch sử. Không frontend production, kết nối API hoặc chốt framework.

**Review bổ sung:** [Điều khiển/navigation](../../docs/frontend-review-controls.md). Sửa → tự cuộn đến xác nhận; confirm cập nhật tiêu chí, Tìm kiếm/nội dung chat mới chạy. Bỏ revision khỏi UI, thêm bốn slider sở thích, tăng cỡ chữ và nav Giới thiệu/Tìm tour/Liên hệ/Hỗ trợ. Các mức sở thích là mẫu, chưa công thức ranking hoặc DTO backend (G14).

## Trách nhiệm / input / output

- Input: flow, wireframe và nguyên tắc dữ liệu trong `docs/`; cùng một bộ tour/giá/nguồn **minh họa** cho cả hai hướng.
- Output: trang review reference + hướng A Giấy & mực và hướng B Hành trình xanh; desktop/mobile, bảng so sánh và panel nguồn theo field.
- Phạm vi lượt mới: mở rộng ba màn, cột yêu cầu rộng hơn/sửa trực tiếp, chat đề xuất–xác nhận–hủy, bảng dữ kiện + tab phân tích, trạng thái xử lý giả lập. Không đánh dấu P3 hoàn thành trước review.

## Workflow và interface

1. Mở `paper.html`: giới thiệu → Tìm tour → form với các trường bắt buộc/tùy chọn → Xác nhận.
2. Theo dõi log/skeleton giả lập; xem bảng dữ kiện, Phân tích AI, nguồn và đổi offer.
3. Sửa field hoặc gửi chat (ví dụ “đổi ngân sách thành 32 triệu”, “tìm nhóm khác”), xem diff và xác nhận/hủy. Thử chậm/lỗi/partial/empty/cancel, mobile và URL tham chiếu.
4. Ghi nhận lựa chọn visual tại [design review](../../docs/frontend-design-review.md).

Có thể đổi Desktop 1280px / Mobile 390px trực tiếp trong `viewer.html`; iframe tạo viewport của prototype. Trang review có bốn reference và credits ảnh/font. Nguồn chi tiết tại [assets/SOURCES.md](assets/SOURCES.md).

JS chỉ điều khiển UI và fixture minh họa: chat nhận một số câu mẫu, phép tính từ giá fixture, không LLM/retrieval/rank hoặc ghép hai API v1. Widget vị trí/thời tiết và walkthrough demo đều mô phỏng, không gọi API ngoài. URL giả dùng `.example`; không mở thành nguồn thật. Hai nhóm cố định; sửa criteria ngoài fixture phải nêu giới hạn. Không lưu token hoặc nhu cầu cá nhân qua refresh.

## Quyết định kỹ thuật

- Vanilla HTML/CSS/JS độc lập, không package.json/framework/build; chỉ phục vụ thử bố cục và thao tác trong PLANNING.
- Một bộ dữ liệu/hành vi chung; hai hướng thay đổi typography, màu, bố cục và mức dùng ảnh. Hai trang riêng để review đồng thời.
- Ba gợi ý mới + URL tham chiếu là **giả định thiết kế chờ FLOW-3**, không phải contract đã duyệt. Mẫu có nút bật tham chiếu để kiểm tra cả trường hợp bốn cột.
- Bảng cùng hàng tiêu chí, vùng cuộn riêng trên mobile; tên tour và cột tiêu chí được giữ khi cuộn. Keyboard/focus, dialog có đóng/Escape và trả focus, reduced-motion.
- Mọi tên nhà cung cấp, giá, ngày, lý do và trích đoạn trong mẫu đều giả lập. Ảnh chỉ minh họa điểm đến, không chứng minh dịch vụ. License/nguồn ảnh, font và icon được ghi tại design review.

## Mở bản mẫu

Có thể mở trực tiếp `paper.html` bằng Chrome/Edge để thử offline; font, ảnh và scripts đều nằm cạnh file. Nhấn “Thử nhu cầu mẫu” ở trang giới thiệu để đi nhanh qua luồng. Thêm `?demo=results` vào URL file nếu muốn mở ngay fixture kết quả.

Dùng HTTP server tĩnh phục vụ riêng thư mục này. Ví dụ nếu máy có Python: `python -m http.server 4173 --bind 127.0.0.1 --directory prototypes/frontend-design`, rồi mở `http://127.0.0.1:4173/`.

Không cần extension VS Code. Kiểm tra desktop 1440px, tablet 768px, mobile 390px và 320px bằng browser DevTools. Khi bản mẫu hoàn tất, bằng chứng kiểm tra được ghi trong design review.

**Kiểm tra lượt điều khiển mới:** [57/57](review/controls/qa-summary.json) đạt, console sạch; năm bề mặt không tràn ngang ở 1440/1280/768/390/320px. Đã kiểm tra sửa → cuộn/focus xác nhận, confirm chưa tự tìm, Tìm kiếm qua nút/chat, slider/draft/snapshot, nav giữ context/background job, chữ 14px trở lên ở chat/table, bốn màu slider và reduced-motion. Ảnh mới trong `review/controls/`; chạy Chrome bằng file local, chưa backend/API/hosting.

**Kiểm tra lượt trước 06/10:** 61/61 browser checks đạt, console sạch; Home/Form/Kết quả không tràn ngang ở 1440/1280/768/390/320px. Chat diff/xác nhận/hủy, sửa trực tiếp, evidence/offer/phép tính, slow/error/retry/cancel và revision/response muộn đã kiểm tra. [JSON tổng hợp](review/v2/qa-summary.json) và ảnh trong `review/v2/` là lịch sử trước lần đổi điều khiển. QA chạy trang và asset local bằng `file://`; chưa HTTP preview/hosting/API.

**Kiểm tra cũ:** 56/56 browser checks cho A/B ngày 03/10 và ảnh tại `review/` là lịch sử.

## Chia sẻ preview online

Prototype/workflow đã push lên `feature/minh-phu`. [Quy trình publish](../../docs/frontend-preview-publishing.md) ghi phạm vi, điều kiện Pages và run đang chờ chủ repo bật hosting. Workflow chỉ lấy thư mục này; link public sẽ được ghi sau khi deploy và kiểm tra thành công. Mọi đường dẫn asset trong trang là tương đối để chạy dưới project path.
