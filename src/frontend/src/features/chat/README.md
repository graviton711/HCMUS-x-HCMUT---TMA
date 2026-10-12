# features/chat

Primitive hội thoại không phụ thuộc backend orchestration: types message, UI thread/composer/tool-status và helper format thuần. Không gọi API, không đọc session.

- Input/output: `ChatMsg` union, `Thread`, `Composer`, `ToolStatus`, `QuickReplies` cho lựa chọn của agent, `ResultCards` cho kết quả có evidence. Nội dung assistant hỗ trợ Markdown phổ biến (đậm, danh sách, liên kết, bảng); HTML thô bị bỏ qua.
- Workflow: `pages/chat` orchestrate qua barrel, render message theo `kind`. SSE đẩy mô tả hành động và trạng thái tool ngay khi OpenCode phát event; UI gom các lần gọi có cùng tên tool và mô tả thành một dòng kèm số lần. Kết quả cuối vẫn render theo response chuẩn. ResultCards hiển thị tối đa năm tour duy nhất, không lặp thẻ cho nhiều offer/ngày khởi hành của cùng tour. Interpretation render thành criteria panel, comparison render thành result section (không bọc bubble).
- Interface: barrel `src/features/chat`. Không import `app/pages/features/entities`.
- Quyết định kỹ thuật: message là data bất biến render theo kind; mọi network/state phiên nằm ở page. Kết quả giữ rõ hai nhóm ranked/near-miss, trạng thái unknown và disclosure cho lý do/evidence; style ở `ui/chat.module.css` dùng token chung, surface gọn và motion tôn trọng reduced-motion. Trang đầu có entrance animation nhẹ để trạng thái tĩnh vẫn có nhịp thị giác.
- Trình bày: vùng nhập giữ caret khi được focus, kể cả khi còn placeholder; textarea có leading/padding trên đủ để caret không bị cắt ở đầu dòng. Dòng gợi ý bên dưới dùng con trỏ mặc định để I-beam chỉ xuất hiện trên vùng có thể nhập.
- Bố cục chat: thread chiếm vùng cuộn riêng; composer đặt ở cuối canvas, có bề rộng đồng bộ với nội dung hội thoại. Viền tập trung là một vòng nhấn mảnh, không tạo cảm giác hai khung chồng nhau; trạng thái gửi tắt vẫn có độ tương phản đủ để nhận diện nút.
- Hành động sau kết quả như nới một tiêu chí là nút phụ nền sáng, viền nhẹ; không dùng primary đen để tránh lấn át thẻ tour và dữ kiện.
