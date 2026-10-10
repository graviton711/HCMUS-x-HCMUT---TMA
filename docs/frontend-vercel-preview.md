# Deploy preview — frontend Vercel, backend Render

Frontend React/Vite ở `src/frontend`; backend FastAPI ở `src/backend`. Cả hai tách biệt, chỉ gặp nhau qua HTTP contract trong [`docs/backend-contract.md`](backend-contract.md).

Trạng thái: điều kiện chặn cũ đã đạt — API client chỉ gọi contract backend hiện tại (không `/v2`), contract tests xanh (`src/frontend/tests/backend-contract`). Deploy preview là để team test chung, chưa phải production hardening.

## Kiến trúc

```text
Vercel (static)                Render (web service)
src/frontend/vercel.json  →    render.yaml
  build: pnpm build             uv run tour-backend serve --port $PORT
  output: dist                  SQLite trên persistent disk (sessions)
  SPA rewrite → index.html      DATA_PROVIDER=supabase, đọc catalog read-only
```

- Frontend gọi backend qua biến môi trường `VITE_API_BASE_URL` (build-time). Không có proxy Vite ở production.
- Backend chỉ nhận cross-origin từ allowlist CORS (settings `cors_origins` + `cors_origin_regex` cho preview deploy của Vercel).
- Secret (NVIDIA_NIM_API, SUPABASE_TOUR_DB_URL) chỉ đặt ở backend env, không bao giờ vào bundle frontend.

## Cấu hình trong repo

| File                            | Vai trò                                                                                   |
| ------------------------------- | ----------------------------------------------------------------------------------------- |
| `src/frontend/vercel.json`      | Framework Vite, output `dist`, SPA rewrite mọi route về `index.html`.                     |
| `render.yaml`                   | Blueprint backend: Python service, build `uv sync`, start `tour-backend serve`, disk data. |
| `configs/settings.yaml`         | `cors_origins` (dev) và `cors_origin_regex` (`*.vercel.app` preview).                     |
| `src/backend/api.py`            | `CORSMiddleware` đọc hai giá trị trên.                                                    |

## Bước deploy

1. **Backend (Render):** tạo service từ repo, dùng blueprint `render.yaml` (hoặc thủ công: build `uv sync`, start `uv run tour-backend serve --host 0.0.0.0 --port $PORT`, mount disk 1GB tại `/opt/render/project/src/data` cho `DATABASE_URL=sqlite:////opt/render/project/src/data/backend.db`). Env: `DATA_PROVIDER=supabase`, `SUPABASE_TOUR_DB_URL`, `NVIDIA_NIM_API`.
2. **Frontend (Vercel):** import repo, Root Directory `src/frontend`. Framework tự nhận Vite qua `package.json` (không dùng script `dev`). Build `pnpm build`, output `dist`. Env: `VITE_API_BASE_URL=https://<backend>.onrender.com`.
3. **CORS:** domain Vercel production/preview nằm trong `cors_origin_regex` mặc định (`https://[a-z0-9-]+.vercel.app`); nếu đặt domain riêng thì thêm vào `CORS_ORIGINS`.
4. **Kiểm sau deploy:** `/health` trả `{status: ok}`; trên URL Vercel tạo phiên guest → diễn giải → so sánh; network tab không còn request `/v2` và không có lỗi CORS.

## Ranh giới

- Auth/account chưa runtime → trang account/auth hiện là trang "chưa khả dụng", không kỳ vọng đăng nhập trên preview.
- SQLite on disk là persistence cho sessions đã lưu; Render free instance sleep sau idle, lần gọi đầu sẽ cold start vài giây.
- Không tự deploy thêm service cloud khác trước khi smoke test trên backend chuẩn pass.
