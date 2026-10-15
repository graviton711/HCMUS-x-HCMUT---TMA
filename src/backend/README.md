# backend — travel agent + pipeline nghiệp vụ

Luồng hội thoại: user → OpenCode agent → MCP tools → validate → catalog/hard filter → soft verdict → kết quả có evidence.

- [`data`](data/README.md): guest sessions, owner-scoped SQLite records/history + đọc catalog.
- [`input`](input/README.md): validate điều kiện có cấu trúc; không parse text tự do.
- [`normalize`](normalize/README.md): ánh xạ rows catalog thành snapshot; freshness chỉ dùng cho ngày khởi hành.
- [`decide`](decide/README.md): lọc → chấm → rank → phân tích.
- `workflows.py`: đọc catalog, chuẩn hóa snapshot và chạy hard-filter/comparison.
- [`agent`](agent/README.md): owner-scoped OpenCode session, MCP tools, JSON response và SSE tiến độ tool.
- `opencode_cli.py`: lệnh `tour-opencode serve`, nạp `.env` và khởi chạy OpenCode server local.
- `opencode_binary.py`: phân giải OpenCode CLI dùng chung cho server launcher và agent runner, gồm npm shim trên Windows.
- `api.py`: HTTP orchestration/routes. `models.py`: nguồn chuẩn duy nhất của mọi kiểu. `settings.py`: config env. `errors.py`: `AppError` contract; `error_logging.py`: policy log lỗi backend tại API/SSE/MCP boundaries bằng logger dùng chung.

Frontend React nằm ở sibling module [`src/frontend`](../frontend/README.md). Chat dùng OpenCode agent; không có NIM extraction hay keyword fallback. `SUPABASE_TOUR_DB_URL` là URL duy nhất cho runtime store và catalog Supabase; nếu vắng mặt, local dùng SQLite và fixture theo YAML. Hợp đồng: [system-architecture](../../docs/system-architecture.md), [data-contract](../../docs/data-contract.md), [backend-contract](../../docs/backend-contract.md).

Unexpected exceptions return `INTERNAL_ERROR` with a generic message. Server and retryable errors are logged once at the transport boundary. Logs include request correlation IDs and traceback frames, but never exception messages or chat/tool payloads. OpenCode process failures include exit status and a bounded, secret-filtered stderr tail. Local runs default to `.local/logs/backend.log` with rotation; set `LOG_FILE` to override it or leave it empty to disable. On Render, `RENDER=true` keeps logging on stderr for the Dashboard.
