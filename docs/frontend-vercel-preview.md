# Deploy preview — một project Vercel, hai services

Frontend React/Vite (`web`) và backend FastAPI (`api`) deploy chung một project
Vercel, một domain, theo [`docs/backend-contract.md`](backend-contract.md).
Cấu hình duy nhất là `vercel.json` ở root.

Trạng thái: API client chỉ gọi contract backend hiện tại (không `/v2`),
contract tests xanh (`src/frontend/tests/backend-contract`). Deploy preview là
để team test chung, chưa phải production hardening.

## Kiến trúc

```text
Browser ──same origin──▶ Vercel routing ──┬── /health, /sessions, /catalog,
                                           │    /requirements*, /comparisons*,
                                           │    /history*, /docs, /openapi.json
                                           │    → service api (FastAPI)
                                           └── còn lại → service web (Vite SPA)
```

- Frontend gọi backend **same-origin**: `VITE_API_BASE_URL` để trống (đã là
  default trong `src/frontend/src/shared/api/client.ts`) nên không set biến này
  trên Vercel. Không có proxy Vite ở production. Nhờ cùng origin, CORS không
  phát sinh trên đường chính (CORS settings vẫn giữ cho truy cập trực tiếp).
- Service `api` là internal mặc định; chỉ 11 path liệt kê trong `vercel.json`
  được public. Không có rewrite nào trỏ vào `api` ngoài danh sách đó.
- Runtime store chạy Postgres (`migrations/004_runtime_store.sql`) nên backend
  stateless, phù hợp serverless. Catalog đọc read-only từ cùng project Supabase.

## Cấu hình trong repo

| File                            | Vai trò                                                                                   |
| ------------------------------- | ----------------------------------------------------------------------------------------- |
| `vercel.json`                   | Hai services + toàn bộ public routing. Không binding (xem dưới).                          |
| `src/backend/vercel_app.py`     | Adapter duy nhất Vercel import (`tool.vercel.entrypoint`); fail-loud nếu `DATABASE_URL` là sqlite trên Vercel. |
| `src/backend/data/sessions.py`  | Reconnect-and-retry 1 lần khi kết nối Postgres chết sau idle (warm instance serverless).  |
| `migrations/004_runtime_store.sql` | Bảng Postgres `runtime_sessions`/`runtime_records` (ingest runner áp dụng).            |
| `configs/settings.yaml`         | `cors_origins` (dev) và `cors_origin_regex` (truy cập trực tiếp, không qua rewrite).      |

## Vì sao không có binding

Cuộc gọi duy nhất giữa hai services là browser → backend, mà binding chỉ inject
vào function lúc runtime (không tồn tại lúc build static, browser cũng không đọc
được). Same-origin rewrite thay thế hoàn toàn: không hostname cố định, preview
nào gọi đúng backend của preview đó, không cần CORS tạm. Backend gọi Supabase và
NIM trực tiếp bằng env, không qua service Vercel nào — thêm binding sẽ là config
chết. Nếu sau này có function server-side gọi service khác, khai báo lúc đó.

## Env trên dashboard (người deploy điền, không commit)

- Service `api`: `DATABASE_URL` (postgres Supabase), `DATA_PROVIDER=supabase`,
  `SUPABASE_TOUR_DB_URL`, `NVIDIA_NIM_API`.
- Service `web`: không cần biến nào (`VITE_API_BASE_URL` cố tình để trống).
- Preview dùng chung data Supabase với prod (ghi vào bảng `runtime_*`); chấp nhận
  được cho team test, tách DB sau nếu cần.

## Bước deploy

1. **Migration (một lần):** `uv run python -c "from ingest.pipeline import migrate_db; migrate_db()"` với `.env` có `SUPABASE_TOUR_DB_URL`.
2. **Vercel:** import repo, preset Services (Root Directory `.`). Kiểm tra preview build log: service `web` build Vite, service `api` bundle Python (không có `node_modules`, `tests`, `artifacts` — xem `excludeFiles`).
3. **Kiểm sau deploy:** `/health` trả `{status: ok}`; `/tours` deep-link mở SPA (không 404); trên URL preview tạo phiên guest → diễn giải → so sánh; network tab không còn request `/v2`, không lỗi CORS; `/docs` mở được.
4. **E2E lên preview:** `E2E_BASE_URL=https://<preview>.vercel.app` rồi chạy `test:e2e` (cần backend thật + Chrome, không dùng production data).

## Ranh giới

- Auth/account chưa runtime → trang account/auth hiện là trang "chưa khả dụng", không kỳ vọng đăng nhập trên preview.
- Bảng runtime nằm cùng project Supabase với catalog (tên `runtime_*`, ingest không chạm đến); nếu team muốn tách biệt tuyệt đối thì chuyển sang schema riêng và cập nhật migration.
- Hobby tối đa 300s/invocation: luồng comparison (extract ≤30s + assess ≤60s) vừa thoải mái; timeout phía backend degrade về soft-unknown thay vì fail.
- `render.yaml` còn lại cho đường deploy Render cũ; xóa khi team chốt chỉ dùng Vercel services để tránh hai đường drift nhau.
- Không tự deploy thêm service cloud khác trước khi smoke test trên backend chuẩn pass.
