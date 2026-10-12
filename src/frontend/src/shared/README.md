# shared

Các primitive không phụ thuộc domain. Không được import `app`, `pages`, `features` hay `entities`.

- `api/`: HTTP client cho backend, tách theo concern — `types.ts` (DTO), `client.ts` (`CurrentBackendClient`), `errors.ts` (`CurrentApiError`). Là HTTP client duy nhất ở runtime; không fallback `/v2`.
- `ui/`: mỗi primitive một folder (`Icon/`, `Dialog/`). `Icon` nhận `IconName` type-safe, chỉ giữ shape đang dùng. `Dialog` nhận close label, `variant` (`default`/`sidebar`) và footer tùy chọn qua props; không tự đọc preferences hay class của feature. Vì Tailwind Preflight reset margin mặc định, dialog phải tự khai báo vị trí căn giữa; biến thể sidebar khai báo vị trí neo trái.
- Drawer dialog dùng cùng lề ngang 20px và padding trên 24px với sidebar desktop. Footer được đặt ngoài vùng nội dung cuộn; vào/ra bằng chuyển động ngắn, tắt khi hệ điều hành yêu cầu reduced motion.
- `styles/`: `tokens.css` (font Manrope có subset tiếng Việt/Latin, Space Grotesk cho wordmark/số liệu, palette và scale) nạp trước, sau đó `global.css` (reset + primitive dùng chung: button, field, notice, empty-state). Mọi màu/radius/shadow/motion phải resolve về token; vùng dữ liệu không dùng blur/shadow. Reduced motion xóa cả thời lượng lẫn độ trễ animation.
- `lib/`: helper thuần (`safeUrl`, `displaySessionTitle` — chuẩn hóa title chỉ ở phần hiển thị, không sửa storage; `sessionTitle` — đặt tên phiên từ destination đã diễn giải).
- `preferences/`: cơ chế locale/theme toàn app (`PreferencesProvider`, `usePreferences`, code ở `model.tsx`). Control nằm ở `features/preferences`.
