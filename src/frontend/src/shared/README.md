# shared

Các primitive không phụ thuộc domain. Không được import `app`, `pages`, `features` hay `entities`.

- `api/`: HTTP client cho backend, tách theo concern — `types.ts` (DTO), `client.ts` (`CurrentBackendClient`), `errors.ts` (`CurrentApiError`). Là HTTP client duy nhất ở runtime; không fallback `/v2`.
- `ui/`: mỗi primitive một folder (`Icon/`, `Dialog/`). `Icon` nhận `IconName` type-safe, chỉ giữ shape đang dùng. `Dialog` nhận close label và `variant` (`default`/`sidebar`) qua props, không tự đọc preferences hay class của feature.
- `styles/`: `tokens.css` (font, biến CSS, theme Calm Density) nạp trước, sau đó `global.css` (reset + primitive dùng chung: button, field, notice, empty-state). Mọi màu/radius/shadow/motion phải resolve về token; vùng dữ liệu không dùng blur/shadow.
- `lib/`: helper thuần (`safeUrl`, `displaySessionTitle` — chuẩn hóa title chỉ ở phần hiển thị, không sửa storage; `sessionTitle` — đặt tên phiên từ destination đã diễn giải).
- `preferences/`: cơ chế locale/theme toàn app (`PreferencesProvider`, `usePreferences`, code ở `model.tsx`). Control nằm ở `features/preferences`.
