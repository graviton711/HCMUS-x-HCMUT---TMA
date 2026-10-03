# Prototype review frontend — P3

**Trạng thái:** PLANNING. Bản mẫu HTML/CSS/JavaScript để review hai hướng visual; không phải frontend production, không kết nối API và không chốt framework.

## Trách nhiệm / input / output

- Input: flow, wireframe và nguyên tắc dữ liệu trong `docs/`; cùng một bộ tour/giá/nguồn **minh họa** cho cả hai hướng.
- Output: trang review reference + hướng A Giấy & mực và hướng B Hành trình xanh; desktop/mobile, bảng so sánh và panel nguồn theo field.
- Phạm vi lượt này: P3.1–P3.2. Token, ba màn đầy đủ và toàn bộ state sẽ tiếp tục sau review; không đánh dấu P3 hoàn thành.

## Workflow và interface

1. Mở `index.html`, chọn A/B; nhận ngay ba gợi ý và bảng so sánh.
2. Mở lý do/nguồn từng dữ kiện; đổi nhóm minh họa bằng Tìm phương án khác.
3. Thử có URL tham chiếu, ít hơn ba gợi ý, thiếu dữ liệu và mobile.
4. Ghi nhận lựa chọn visual tại [design review](../../docs/frontend-design-review.md).

Có thể đổi Desktop 1280px / Mobile 390px trực tiếp trong `viewer.html`; iframe tạo viewport của prototype. Trang review có bốn reference và credits ảnh/font. Nguồn chi tiết tại [assets/SOURCES.md](assets/SOURCES.md).

JS chỉ điều khiển UI và fixture minh họa: không parse nhu cầu, không retrieval, không tính rank, không ghép hai API v1. URL giả dùng `.example`; không mở thành nguồn thật. Nhóm tiếp theo cố định để kiểm chứng UX, không phải thuật toán ranking. Không lưu token hoặc nhu cầu cá nhân.

## Quyết định kỹ thuật

- Vanilla HTML/CSS/JS độc lập, không package.json/framework/build; chỉ phục vụ thử bố cục và thao tác trong PLANNING.
- Một bộ dữ liệu/hành vi chung; hai hướng thay đổi typography, màu, bố cục và mức dùng ảnh. Hai trang riêng để review đồng thời.
- Ba gợi ý mới + URL tham chiếu là **giả định thiết kế chờ FLOW-3**, không phải contract đã duyệt. Mẫu có nút bật tham chiếu để kiểm tra cả trường hợp bốn cột.
- Bảng cùng hàng tiêu chí, vùng cuộn riêng trên mobile; tên tour và cột tiêu chí được giữ khi cuộn. Keyboard/focus, dialog có đóng/Escape và trả focus, reduced-motion.
- Mọi tên nhà cung cấp, giá, ngày, lý do và trích đoạn trong mẫu đều giả lập. Ảnh chỉ minh họa điểm đến, không chứng minh dịch vụ. License/nguồn ảnh, font và icon được ghi tại design review.

## Mở bản mẫu

Dùng HTTP server tĩnh phục vụ riêng thư mục này. Ví dụ nếu máy có Python: `python -m http.server 4173 --bind 127.0.0.1 --directory prototypes/frontend-design`, rồi mở `http://127.0.0.1:4173/`.

Không cần extension VS Code. Kiểm tra desktop 1440px, tablet 768px, mobile 390px và 320px bằng browser DevTools. Khi bản mẫu hoàn tất, bằng chứng kiểm tra được ghi trong design review.

**Đã kiểm tra:** 56/56 browser checks đạt; ảnh A/B desktop/mobile và JSON kết quả trong `review/`. Chỉ kiểm chứng fixture/prototype, không API hoặc production E2E. P3.2 chờ chọn hướng; token và ba màn đầy đủ chưa duyệt.

## Chia sẻ preview online

User đã đồng ý dùng GitHub Pages để nhóm mở bằng link, không cần pull/chạy local. [Quy trình publish](../../docs/frontend-preview-publishing.md) ghi phạm vi, điều kiện Pages và trạng thái triển khai. Workflow chỉ lấy thư mục này từ `feature/minh-phu`; link public sẽ được ghi sau khi deploy và kiểm tra thành công. Mọi đường dẫn asset trong trang là tương đối để chạy dưới project path.
