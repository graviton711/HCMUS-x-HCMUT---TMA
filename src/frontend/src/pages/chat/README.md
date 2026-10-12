# pages/chat

Màn hình chat (`/`): hội thoại nhiều lượt với OpenCode travel agent, lựa chọn hỏi thêm và kết quả so sánh có evidence.

- Input: `LocalSession` (hoặc null trước lần gửi đầu), callback session từ `app`.
- Output: chat text; QuickReplies từ `ask_choice`; tối đa 5 tour cards; retry khi session hết hạn/lỗi.
- Workflow: `ChatPage` → `useChat` (guest access → local agent session → từng tin nhắn gửi `POST /agent/sessions/{id}/messages`) → render assistant text, choices và comparison từ agent tools. Transcript đã hoàn tất được lưu trong lịch sử local và khôi phục khi reload; lượt đang chạy không tự gửi lại. Comparison cũ vẫn được lưu theo ID trong backend. `draft.text` chỉ giữ prompt gốc để khôi phục, không tích lũy các lượt hội thoại. Canvas giữ độ rộng đọc thoải mái, thread cuộn độc lập và composer ghim ở đáy workspace. Dù vùng kết quả mở rộng, composer vẫn căn theo cùng cột đọc tối đa 900px như nội dung hội thoại.
- Interface: export `ChatPage`. `model/` nội bộ. Bearer access (`accessFor`, `SessionExpiredError`), format helpers và `sessionTitle` dùng chung từ `features/session-history`, `features/chat`, `shared/lib` — không copy per-page.
- Trình bày: composer đầu trang dùng vùng nhập hai dòng; hero, composer và ví dụ xuất hiện theo nhịp ngắn. Hội thoại giữ cùng nhịp khoảng cách, viền đơn và nút gửi rõ trạng thái sẵn sàng.
- Quyết định kỹ thuật:
  - Tin nhắn agent dùng SSE trên endpoint hiện tại: UI hiện trạng thái tổng quát khi agent đang chuẩn bị, cập nhật mô tả hành động của từng tool khi bắt đầu/kết thúc, rồi render response cuối gồm text, choices và comparison. Backend dựng mô tả từ tên tool cùng input cấu trúc an toàn; UI gộp các thao tác giống hệt và hiện số lần, không hiển thị private reasoning. Backend vẫn giữ JSON mặc định cho consumer khác. Backend và OpenCode/MCP cần khởi động lại sau khi đổi code; Vite HMR không reload các tiến trình đó.
  - Auto-send được quyết định từ trạng thái trước khi tạo local agent session; ID agent đã lưu là dấu hiệu phiên đang tiếp tục, không phải yêu cầu chạy lại prompt. Transcript hiển thị lấy từ bản local đã lưu; tool activity đang chạy không được phục hồi sau reload.
  - Composer khóa khi backend client chưa sẵn sàng; auto-scroll chỉ khi user đã ở gần đáy. Composer lớn hơn ở trạng thái hội thoại trống và dùng một hàng điều khiển gọn khi chat đã bắt đầu.
  - Title lấy từ yêu cầu/comparison hoặc tin nhắn đầu tiên; hiển thị luôn qua `displaySessionTitle` (grapheme-safe, không slice code unit).
  - Guest access hết hạn cho phép tạo session mới và gửi lại bản nháp.
  - Session bar và sidebar toggle do `app` sở hữu; page không render header riêng.
  - OpenCode agent là luồng hội thoại duy nhất; client giữ local agent session ID nhưng không thấy OpenCode session ID.
