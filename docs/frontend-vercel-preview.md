# Deploy preview — frontend Vercel, backend Render

Frontend React/Vite ở `src/frontend`; backend FastAPI ở `src/backend`. Cả hai tách biệt, chỉ gặp nhau qua HTTP contract trong [`docs/backend-contract.md`](backend-contract.md).

Trạng thái: điều kiện chặn cũ đã đạt — API client chỉ gọi contract backend hiện tại (không `/v2`), contract tests xanh (`src/frontend/tests/backend-contract`). Deploy preview là để team test chung, chưa phải production hardening.

## Kiến trúc

```text
Vercel (static)                Render (web service, stateless)
src/frontend/vercel.json  →    render.yaml
  build: pnpm build             uv run tour-backend serve --port $PORT
  output: dist                  runtime data → Supabase Postgres (migrations/004)
  SPA rewrite → index.html      catalog đọc read-only từ cùng project
```

- Frontend gọi backend qua biến môi trường `VITE_API_BASE_URL` (build-time). Không có proxy Vite ở production.
- Runtime store (sessions/requirements/comparisons) chọn driver theo scheme của `DATABASE_URL`: SQLite cho local, **Postgres cho preview** → backend stateless, Render free plan chạy được (sleep khi idle, cold start vài giây).
- Backend chỉ nhận cross-origin từ allowlist CORS (settings `cors_origins` + `cors_origin_regex` cho preview deploy của Vercel).
- Secret (NVIDIA_NIM_API, SUPABASE_TOUR_DB_URL) chỉ đặt ở backend env, không bao giờ vào bundle frontend.

## Cấu hình trong repo

| File                            | Vai trò                                                                                   |
| ------------------------------- | ----------------------------------------------------------------------------------------- |
| `src/frontend/vercel.json`      | Framework Vite, output `dist`, SPA rewrite mọi route về `index.html`.                     |
| `render.yaml`                   | Blueprint backend: Python service, build `uv sync`, start `tour-backend serve`.           |
| `migrations/004_runtime_store.sql` | Bảng Postgres `runtime_sessions`/`runtime_records` (ingest runner áp dụng).            |
| `configs/settings.yaml`         | `cors_origins` (dev) và `cors_origin_regex` (`*.vercel.app` preview).                     |
| `src/backend/api.py`            | `CORSMiddleware` đọc hai giá trị trên.                                                    |

## Bước deploy

1. **Migration (một lần):** `uv run python -c "from ingest.pipeline import migrate_db; migrate_db()"` với `.env` có `SUPABASE_TOUR_DB_URL` — tạo bảng runtime trên Postgres.
2. **Backend (Render):** tạo service từ repo, dùng blueprint `render.yaml` (hoặc thủ công: build `pip install uv && uv sync --frozen`, start `uv run tour-backend serve --host 0.0.0.0 --port $PORT`). Env: `DATABASE_URL=postgres://...cùng project Supabase`, `DATA_PROVIDER=supabase`, `SUPABASE_TOUR_DB_URL`, `NVIDIA_NIM_API`. Không cần persistent disk.
3. **Frontend (Vercel):** import repo, Root Directory `src/frontend`. Framework tự nhận Vite qua `package.json` (không dùng script `dev`). Build `pnpm build`, output `dist`. Env: `VITE_API_BASE_URL=https://<backend>.onrender.com`.
4. **CORS:** domain Vercel production/preview nằm trong `cors_origin_regex` mặc định (`https://[a-z0-9-]+.vercel.app`); nếu đặt domain riêng thì thêm vào `CORS_ORIGINS`.
5. **Kiểm sau deploy:** `/health` trả `{status: ok}`; trên URL Vercel tạo phiên guest → diễn giải → so sánh; network tab không còn request `/v2` và không có lỗi CORS.

## Ranh giới

- Auth/account chưa runtime → trang account/auth hiện là trang "chưa khả dụng", không kỳ vọng đăng nhập trên preview.
- Bảng runtime nằm cùng project Supabase với catalog (tên `runtime_*`, ingest không chạm đến); nếu team muốn tách biệt tuyệt đối thì chuyển sang schema riêng và cập nhật migration.
- Render free instance sleep sau idle; lần gọi đầu sẽ cold start vài giây. Backend stateless nên sleep không mất dữ liệu.
- Không tự deploy thêm service cloud khác trước khi smoke test trên backend chuẩn pass.
