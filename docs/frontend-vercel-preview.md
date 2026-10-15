# Deploy preview — Vercel web + Render split boxes (free)

Frontend React/Vite (`web`) chạy trên Vercel; backend FastAPI và OpenCode agent
chạy riêng trên hai service Docker free (512 MB mỗi box) vì single-box OOM
(`Ran out of memory` khi turn chat). Cùng một image (`Dockerfile` +
`start.sh`), env `ROLE` chọn tiến trình. Lý do backend không ở Vercel:
`backend/agent/runner.py` spawn binary `opencode` local (`shutil.which`),
Vercel Python function không có binary này nên mọi route `/agent/*` trả 503 ở
đó. Giữ service `api` trên Vercel chỉ cho các route đồng bộ cũ (xem Ranh giới);
chat demo đi qua backend Render. Cấu hình Vercel duy nhất là `vercel.json` ở
root; cấu hình Render là `render.yaml` + `Dockerfile` + `start.sh` ở root.

Trạng thái: API client chỉ gọi contract backend hiện tại (không `/v2`),
contract tests xanh (`src/frontend/tests/backend-contract`). Deploy preview là
để team test chung, chưa phải production hardening.

## Kiến trúc

```text
Browser ──Vercel preview URL──▶ web (Vite SPA)
   │  VITE_API_BASE_URL=https://mlai-tour-backend[-suffix].onrender.com
   └──▶ Render mlai-tour-backend (ROLE=backend, public /health, /sessions,
        │    /catalog, /requirements*, /comparisons*, /history*,
        │    /agent/sessions, /agent/sessions/*/messages, /docs)
        │    opencode run --server https://mlai-opencode[-suffix].onrender.com
        │    CLI cwd /app = project path on both Render services
        └──▶ Render mlai-opencode (ROLE=opencode, public /global/health,
             serve cwd /app = repo + MCP tour-catalog, catalog đọc Supabase)
```

Thứ tự deploy: opencode trước (copy URL public của nó), rồi điền vào
`OPENCODE_SERVER_URL` của backend và deploy backend. Serve không đặt password
tuần demo (health check cần endpoint public; URL khó đoán); thấy abuse thì đặt
`OPENCODE_SERVER_PASSWORD` giống nhau ở cả hai box (CLI tự đọc env, không cần
sửa code). Cả hai box free đều ngủ khi idle — giữ ấm trước giờ demo bằng cron
ping `/health` backend và `/global/health` opencode.

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
| `Dockerfile` + `start.sh` (repo root) | Image chung: Node 22 + `opencode-ai` + `uv sync` + repo (MCP, agent, prompts). `ROLE=backend` chạy tour-backend public; `ROLE=opencode` chạy serve trên `$PORT`. Chưa build-verify local (Docker engine không chạy được trên máy dev); build Render là điểm verify. |
| `render.yaml`                   | Hai services Docker free 512 MB: `mlai-tour-backend` (giữ URL cũ, Vercel không cần đổi) + `mlai-opencode` mới (URL có suffix, chỉ backend gọi). Nếu turn chat vẫn OOM thì nâng plan hoặc Standard $25. |
| `vercel_backend.py` (repo root) | Adapter Vercel cho service `api` legacy; yêu cầu `SUPABASE_TOUR_DB_URL` là pooler PostgreSQL (serverless không route được IPv6 direct). Module path dạng file ở root vì Vercel không resolve dotted path dưới `src/`. |
| `src/backend/data/sessions.py`  | Kết nối Postgres lazy (import không bao giờ dial DB; DB chết trả 503 JSON thay vì crash function) + reconnect-and-retry 1 lần khi kết nối chết sau idle. |
| `migrations/004_runtime_store.sql` | Bảng Postgres `runtime_sessions`/`runtime_records` (ingest runner áp dụng).            |
| `configs/settings.yaml`         | `cors_origins` (dev) và `cors_origin_regex` (cover `https://[a-z0-9-]+\.vercel\.app`).     |

## Env trên dashboard (người deploy điền, không commit)

- Render `mlai-opencode` (deploy trước): `SUPABASE_TOUR_DB_URL` (MCP đọc
  catalog server-side), không cần thêm gì. Copy URL public của nó.
- Render `mlai-tour-backend`: `SUPABASE_TOUR_DB_URL`, `CORS_ORIGINS`
  (domain web Vercel), `OPENCODE_SERVER_URL` = URL opencode ở trên,
  `OPENCODE_MODEL` + `OPENCODE_AGENT` + `OPENCODE_PROJECT_DIR=/app` đã có
  value trong yaml; CLI dùng đường dẫn này làm working directory khi gửi request.
- Vercel `web`: `VITE_API_BASE_URL` = URL backend (không đổi nếu giữ service
  cũ — vẫn `mlai-tour-backend[-suffix].onrender.com` như trước).
- Vercel `api` (legacy): giữ env cũ nếu còn dùng route đồng bộ ở đó.
- `SUPABASE_TOUR_PUBLISHABLE_KEY` nằm trong `.env.example`, nhưng runtime hiện tại chưa đọc biến này.
- Preview dùng chung data Supabase với prod (ghi vào bảng `runtime_*`); chấp nhận
  được cho team test, tách DB sau nếu cần.

## Bước deploy

1. **Migration (một lần):** `uv run python -c "from ingest.pipeline import migrate_db; migrate_db()"` với `.env` có `SUPABASE_TOUR_DB_URL`.
2. **Render:** blueprint `render.yaml` build image lần đầu (điểm verify Dockerfile);
  `start.sh` warm sẵn MCP một lần lúc boot vì box 0.1 CPU boot lạnh quá 30s
  (`opencode.json` nới `timeout` MCP lên 120s). Kiểm tra `/health`, rồi chat thử 1 turn end-to-end (SSE) trước demo.
3. **Vercel:** import repo, preset Services (Root Directory `.`); set
  `VITE_API_BASE_URL` trên service `web`.
4. **Kiểm sau deploy:** `/health` Render trả `{status: ok}`; SPA mở được;
  network tab không còn request `/v2`, không lỗi CORS; chat ra đủ 5 tour cards;
  BGK query tự do có budget/date cứng mà giá stale/`from` thì `unknown` là đúng
  policy — demo luồng near-miss và review lại brief khi nới điều kiện.
5. **E2E lên preview:** `E2E_BASE_URL=https://<preview>.vercel.app` rồi chạy `test:e2e` (cần backend thật + Chrome, không dùng production data).

## Ranh giới

- Auth/account chưa runtime → trang account/auth hiện là trang "chưa khả dụng", không kỳ vọng đăng nhập trên preview.
- Bảng runtime nằm cùng project Supabase với catalog (tên `runtime_*`, ingest không chạm đến); nếu team muốn tách biệt tuyệt đối thì chuyển sang schema riêng và cập nhật migration.
- Render free ngủ khi idle (cold-start query đầu chậm) + tối đa timeout nền tảng:
  giữ ấm trước giờ demo (cron ping hoặc lên plan trả phí 1 tháng).
- Không tự deploy thêm service cloud khác trước khi smoke test trên backend chuẩn pass.
