# shared

Các primitive không phụ thuộc domain. Không được import `app`, `pages`, `features` hay `entities`.

- `api/`: HTTP client cho backend, tách theo concern — `types.ts` (DTO), `client.ts` (`CurrentBackendClient`), `errors.ts` (`CurrentApiError`). Là HTTP client duy nhất ở runtime; không fallback `/v2`.
- `ui/`: mỗi primitive một folder (`Icon/`, `Dialog/`). `Icon` nhận `IconName` type-safe, chỉ giữ shape đang dùng. `Dialog` nhận close label và `variant` (`default`/`sidebar`) qua props, không tự đọc preferences hay class của feature.
- `styles/`: `tokens.css` (font, biến CSS, theme) nạp trước, sau đó `global.css` (reset + primitive dùng chung: button, field, notice, empty-state).
- `lib/`: helper thuần (`safeUrl`).
- `preferences/`: cơ chế locale/theme toàn app (`PreferencesProvider`, `usePreferences`, code ở `model.tsx`). Control nằm ở `features/preferences`.
