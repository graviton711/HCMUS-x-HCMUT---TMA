# Deploy preview — Vercel web + Render backend single-box

Frontend React/Vite (`web`) chạy trên Vercel; backend FastAPI + OpenCode agent
chạy chung một container Docker trên Render (single-box, y hệt local dev:
`opencode serve 127.0.0.1:4098` nội bộ + `tour-backend serve 0.0.0.0:$PORT`
public). Lý do backend không ở Vercel: `backend/agent/runner.py` spawn binary
`opencode` local (`shutil.which`), Vercel Python function không có binary này
nên mọi route `/agent/*` trả 503 ở đó. Giữ service `api` trên Vercel chỉ cho
các route đồng bộ cũ (xem Ranh giới); chat demo đi qua backend Render.
Cấu hình Vercel duy nhất là `vercel.json` ở root; cấu hình Render là
`render.yaml` + `Dockerfile` ở root.

Trạng thái: API client chỉ gọi contract backend hiện tại (không `/v2`),
contract tests xanh (`src/frontend/tests/backend-contract`). Deploy preview là
để team test chung, chưa phải production hardening.

## Kiến trúc

```text
Browser ──Vercel preview URL──▶ web (Vite SPA)
   │  VITE_API_BASE_URL=https://mlai-tour-backend.onrender.com
   └──▶ Render mlai-tour-backend (Docker single-box)
          ├── tour-backend 0.0.0.0:$PORT (public: /health, /sessions,
          │    /catalog, /requirements*, /comparisons*, /history*,
          │    /agent/sessions, /agent/sessions/*/messages, /docs)
          └── opencode serve 127.0.0.1:4098 (container-local only,
               repo + MCP tour-catalog trong image, không public)
```

- Frontend gọi backend Render **cross-origin**: set `VITE_API_BASE_URL` trên
  service `web` lúc build (client đọc `import.meta.env`, default rỗng =
  same-origin). Backend cho phép origin qua `CORS_ORIGINS` (env Render) và
  `cors_origin_regex` có sẵn (`https://[a-z0-9-]+\.vercel\.app`).
- Service `api` trên Vercel còn lại phục vụ route đồng bộ cũ
  (`/health`, `/sessions`, `/catalog`, `/requirements*`, `/comparisons*`,
  `/history*`, `/docs`, `/openapi.json` + `/agent/*` rewrite nhưng agent 503
  ở đó vì thiếu binary opencode). Sau demo xem xét gỡ để khỏi nuôi hai backend.

## Cấu hình trong repo

| File                            | Vai trò                                                                                   |
| ------------------------------- | ----------------------------------------------------------------------------------------- |
| `vercel.json`                   | Hai services + toàn bộ public routing Vercel.                                             |
| `Dockerfile` (repo root)        | Image single-box Render: Node 22 + `opencode-ai` + `uv sync` + repo (MCP, agent, prompts). Chưa build-verify local (Docker engine không chạy được trên máy dev); lần build đầu trên Render là điểm verify. |
| `render.yaml`                   | Service Docker `mlai-tour-backend` (free 0.1 CPU/512 MB — chật cho uvicorn+opencode+MCP; OOM thì nâng plan). |
| `vercel_backend.py` (repo root) | Adapter Vercel cho service `api` legacy; yêu cầu `SUPABASE_TOUR_DB_URL` là pooler PostgreSQL (serverless không route được IPv6 direct). Module path dạng file ở root vì Vercel không resolve dotted path dưới `src/`. |
| `src/backend/data/sessions.py`  | Kết nối Postgres lazy (import không bao giờ dial DB; DB chết trả 503 JSON thay vì crash function) + reconnect-and-retry 1 lần khi kết nối chết sau idle. |
| `migrations/004_runtime_store.sql` | Bảng Postgres `runtime_sessions`/`runtime_records` (ingest runner áp dụng).            |
| `configs/settings.yaml`         | `cors_origins` (dev) và `cors_origin_regex` (cover `https://[a-z0-9-]+\.vercel\.app`).     |

## Env trên dashboard (người deploy điền, không commit)

- Render `mlai-tour-backend`: `SUPABASE_TOUR_DB_URL` (direct `db.*` dùng được —
  container có full networking, không bắt buộc pooler), `CORS_ORIGINS`
  (domain web Vercel), `OPENCODE_SERVER_URL=http://127.0.0.1:4098`,
  `OPENCODE_MODEL` + `OPENCODE_AGENT` như `.env.example`. Không cần password
  vì serve chỉ bind container-localhost, không public.
- Vercel `web`: `VITE_API_BASE_URL=https://mlai-tour-backend.onrender.com`
  (set lúc build — client embed tại build time).
- Vercel `api` (legacy): giữ env cũ nếu còn dùng route đồng bộ ở đó.
- `SUPABASE_TOUR_PUBLISHABLE_KEY` nằm trong `.env.example`, nhưng runtime hiện tại chưa đọc biến này.
- Preview dùng chung data Supabase với prod (ghi vào bảng `runtime_*`); chấp nhận
  được cho team test, tách DB sau nếu cần.

## Bước deploy

1. **Migration (một lần):** `uv run python -c "from ingest.pipeline import migrate_db; migrate_db()"` với `.env` có `SUPABASE_TOUR_DB_URL`.
2. **Render:** blueprint `render.yaml` build image lần đầu (điểm verify Dockerfile);
  kiểm tra `/health`, rồi chat thử 1 turn end-to-end (SSE) trước demo.
3. **Vercel:** import repo, preset Services (Root Directory `.`); set
  `VITE_API_BASE_URL` trên service `web`.
4. **Kiểm sau deploy:** `/health` Render trả `{status: ok}`; SPA mở được;
  network tab không còn request `/v2`, không lỗi CORS; chat ra đủ 5 tour cards;
  BGK query tự do có budget/date cứng mà giá stale/`from` thì `unknown` là đúng
  policy — demo luồng near-miss/`relax_criterion` trong trường hợp này.
5. **E2E lên preview:** `E2E_BASE_URL=https://<preview>.vercel.app` rồi chạy `test:e2e` (cần backend thật + Chrome, không dùng production data).

## Ranh giới

- Auth/account chưa runtime → trang account/auth hiện là trang "chưa khả dụng", không kỳ vọng đăng nhập trên preview.
- Bảng runtime nằm cùng project Supabase với catalog (tên `runtime_*`, ingest không chạm đến); nếu team muốn tách biệt tuyệt đối thì chuyển sang schema riêng và cập nhật migration.
- Render free ngủ khi idle (cold-start query đầu chậm) + tối đa timeout nền tảng:
  giữ ấm trước giờ demo (cron ping hoặc lên plan trả phí 1 tháng).
- Không tự deploy thêm service cloud khác trước khi smoke test trên backend chuẩn pass.
