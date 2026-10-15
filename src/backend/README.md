# backend — travel agent + pipeline nghiệp vụ

Luồng hội thoại: user → Codex agent (local mặc định; provider cấu hình được) → MCP tools → validate → catalog/hard filter → structured facts có quote → metric vectors và lựa chọn đa mục tiêu có giải thích. Render giữ OpenCode tới khi điều kiện hosted của OpenAI được xác nhận.

- [`data`](data/README.md): guest sessions, owner-scoped SQLite records/history + đọc catalog.
- [`input`](input/README.md): validate điều kiện có cấu trúc; không parse text tự do.
- [`normalize`](normalize/README.md): ánh xạ rows catalog thành snapshot, giữ basis/giá tuổi từng offer và source fields.
- [`decide`](decide/README.md): hard filter → metric vectors → objective views/Pareto → lựa chọn.
- `workflows.py`: quét index catalog nhẹ, hard-filter trên toàn phạm vi, chỉ tải dữ kiện dài cho hard-pass/near-miss cần dùng, chuẩn hóa snapshot và chạy comparison.
- [`agent`](agent/README.md): owner-scoped provider thread, MCP tools, JSON response và SSE tiến độ tool.
- `opencode_cli.py`: lệnh `tour-opencode serve`, nạp `.env` và khởi chạy OpenCode server local.
- `opencode_binary.py`: phân giải OpenCode CLI dùng chung cho server launcher và agent runner, gồm npm shim trên Windows.
- `codex_gateway.py`: service riêng nhận turn, chạy Codex CLI `0.162.1` với `configs/prompts/backend-agent.yaml`, stream JSONL và khởi tạo device-code login khi cần.
- `api.py`: HTTP orchestration/routes. `models.py`: nguồn chuẩn duy nhất của mọi kiểu. `settings.py`: config env. `errors.py`: `AppError` contract; `error_logging.py`: policy log lỗi backend tại API/SSE/MCP boundaries bằng logger dùng chung.

Frontend React nằm ở sibling module [`src/frontend`](../frontend/README.md). Chat dùng Codex CLI mặc định ở local; `AGENT_PROVIDER=opencode` giữ tương thích môi trường Render hiện tại. ChatGPT account dùng chung quota; không có API-key fallback hay app-level access gate. `SUPABASE_TOUR_DB_URL` là URL duy nhất cho runtime store và catalog Supabase; thiếu URL catalog thì backend báo `CATALOG_NOT_CONFIGURED`. Hợp đồng: [system-architecture](../../docs/system-architecture.md), [data-contract](../../docs/data-contract.md), [backend-contract](../../docs/backend-contract.md).

Unexpected exceptions return `INTERNAL_ERROR` with a generic message. Server and retryable errors are logged once at the transport boundary. Logs include request correlation IDs and traceback frames, but never exception messages or chat/tool payloads. Provider failures include exit status and bounded, secret-filtered diagnostics. Device-code URL/code is logged only by the Codex gateway so the operator can authorize a headless login. Local runs default to `.local/logs/backend.log` with rotation; set `LOG_FILE` to override it or leave it empty to disable. On Render, `RENDER=true` keeps logging on stderr for the Dashboard.
