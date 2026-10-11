# features/chat

Primitive hội thoại không phụ thuộc backend orchestration: types message, UI thread/composer/tool-status và helper format thuần. Không gọi API, không đọc session.

- Input/output: `ChatMsg` union, `Thread`, `Composer`, `ToolStatus`, `QuickReplies`, `failedDetailsForOffer/display`.
- Workflow: `pages/chat` orchestrate qua barrel, render message theo `kind`. Interpretation render thành criteria panel; comparison render thành result section (không bọc bubble).
- Interface: barrel `src/features/chat`. Không import `app/pages/features/entities`.
- Quyết định kỹ thuật: message là data bất biến render theo kind; mọi network/state phiên nằm ở page. Style ở `ui/chat.module.css` theo token Calm Density: surface đặc, disclosure mở khi cần, motion 120–240ms.
