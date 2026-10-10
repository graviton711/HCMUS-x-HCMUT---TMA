# Preview frontend — hướng triển khai, chưa sẵn sàng

Frontend source nằm ở `src/frontend` (React/Vite). Vercel chỉ là đích chia sẻ UI sau khi client/DTO được port sang `src/backend` và contract tests xác nhận end-to-end; hiện chưa deploy và không có link preview.

## Đích cấu hình

- Root Directory: `src/frontend`; build `pnpm build`, output `dist`; install `pnpm install --frozen-lockfile`.
- Backend chạy riêng trên HTTPS với SQLite persistent và catalog Supabase chỉ đọc. Secret/NIM/Auth config chỉ ở backend.
- Production cần `VITE_API_BASE_URL` trỏ đến origin backend và CORS allowlist khớp frontend. SPA routes cần fallback về `index.html`, không rewrite API thành HTML.

Không cấu hình deploy hoặc tạo service cloud trước khi API client hiện tại không còn gọi `/v2` và smoke test dùng backend chuẩn pass.
