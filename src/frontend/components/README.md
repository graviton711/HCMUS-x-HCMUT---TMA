# UI components

Icon SVG cùng hệ thống mark, native Dialog và ErrorBoundary dùng chung. Input/output là React props; không API/data state. Dialog giữ focus, Escape và backdrop; boundary hiển thị cách reload khi render lỗi. Ngôn ngữ UI lấy từ PreferencesProvider, không dịch nội dung nguồn.

- `MonthPicker`: danh sách `YYYY-MM` ↔ callback, chọn nhiều tháng theo năm và bỏ từng tháng; tối đa 12, không tự chọn tháng. Năm luôn hiển thị rõ; chặn thêm tháng qua theo Asia/Ho_Chi_Minh, tháng cũ đang chọn vẫn bỏ được.
- `BudgetRange`: hai đầu tiền dạng chuỗi ↔ callback; slider native dùng bàn phím/touch, kèm ô số chính xác. Thang ban đầu 0–100 triệu VND, kéo/phím đổi 500.000; giá trị nhập và vị trí slider giữ chính xác tới 1 VND, không bị giới hạn bởi thang ban đầu.
- `SessionSidebar`: children lịch sử ↔ cột mở/thu gọn và rộng kéo được. Lưu duy nhất preferences bố cục; không quản lý phiên, identity hay API.
