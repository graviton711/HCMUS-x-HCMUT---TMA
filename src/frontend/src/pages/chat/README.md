# pages/chat

Màn hình search-first (`/`): nhập yêu cầu, làm rõ điều kiện, trình bày kết quả so sánh trên API backend hiện tại.

- Input: `LocalSession` (hoặc null trước lần gửi đầu), callback session từ `app`.
- Output: entry search; composer; quick-reply từng slot thiếu; ranked/near-miss comparison; nới 1 điều kiện qua `drop_fields`; hoàn tác bản trước; recovery khi backend session hết hạn.
- Workflow: `ChatPage` → `useChat` (access → interpret → compare, state machine `idle/thinking/working` + `failedStep`) → render `features/chat` UI. Reload rebuild message cuối từ requirement/comparison đã lưu.
- Interface: export `ChatPage`. `model/` nội bộ (relax/undo, title từ destination); `lib/slots.ts` nội bộ (câu hỏi từng slot). Bearer access (`accessFor`, `SessionExpiredError`), format helpers và `sessionTitle` dùng chung từ `features/session-history`, `features/chat`, `shared/lib` — không copy per-page.
- Quyết định kỹ thuật:
  - Search-first: kết quả là vùng nội dung chính, không bọc như tin nhắn chat nhỏ. Canvas rộng (`workspace-wide`) khi có comparison.
  - Composer khóa khi backend client chưa sẵn sàng để không kẹt `busy`; slot hỏi-nhanh giữ hiển thị ở dạng disabled khi đang xử lý; auto-scroll chỉ khi user đã ở gần đáy.
  - Title lưu trong session ưu tiên destination đã diễn giải; hiển thị luôn qua `displaySessionTitle` (grapheme-safe, không slice code unit).
  - Lỗi hết hạn phiên mang cờ `expired` typed (`SessionExpiredError`), UI hiện primary `Tạo phiên mới và tiếp tục` + `Thử lại`; `failedStep` phân biệt interpret/compare để retry đúng bước; undo khôi phục cả `requirementId`.
  - Session bar và sidebar toggle do `app` sở hữu; page không render header riêng.
  - Không thay đổi session/API contract.
