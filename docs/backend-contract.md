# Hợp đồng backend

API HTTP cho frontend và các consumer. Schema live ở `/openapi.json`; models trong `src/backend/models.py` là nguồn chuẩn duy nhất. Frontend gọi contract này, không gọi `/v2` legacy và không đọc database trực tiếp. Hội thoại tự do do OpenCode agent điều khiển; backend tools nhận dữ liệu cấu trúc và kiểm tra trước khi đọc catalog.

## Current runtime

- `GET /health` → `{status, version}`.
- `POST /sessions` → guest session Bearer token with expiry. Only a SHA-256 token hash is persisted.
- `GET /catalog` → `{destinations}` from the active read-only catalog provider; this is a basic lookup, not the richer frontend catalog contract.
- `POST /requirements` — body `{conditions, raw_text?, travelers?}` để lưu requirement có cấu trúc, hoặc `{form}` cho workspace hiện tại → `{requirement}`. Text tự do không được parse thành điều kiện; field/operator/value sai bị từ chối.
- `GET /requirements/{id}` → requirement đã lưu.
- `POST /comparisons` — body `{requirement_id, candidate_limit?}` → `{comparison}` gồm xếp hạng, hard evaluations, evidence, phân tích và snapshot candidate tự chứa để kết quả đã lưu vẫn render được. Endpoint này dùng `candidate_default` (hiện là 20) và giới hạn `candidate_max` (hiện là 100). Agent MCP tìm trên catalog đến `data.scan_limit` (hiện là 1000); số bản ghi quét không khẳng định tổng số tour trong database. `ranked` chỉ chứa offer qua hết điều kiện cứng; `near_miss` chứa offer fail không quá `near_miss_max_fails` điều kiện cứng (mặc định 2), xếp theo pass nhiều → fail ít → giá rẻ để UI render nhóm "Gần đạt" riêng. `unknown` không tính là fail.
- `GET /comparisons/{id}` → comparison đã lưu.
- `GET /history?limit=&cursor=` and `GET /history/{id}` → cursor pagination and owner-scoped requirement/comparison detail for guest sessions.
- `POST /agent/sessions` — Bearer bắt buộc; tạo local agent session và trả `{agent_session_id}`.
- `POST /agent/sessions/{id}/messages` — Bearer bắt buộc; body `{message}`. Mặc định trả JSON `{assistant_text, choices?, tool_calls?, requirement?, comparison?}`. Với `Accept: text/event-stream`, trả SSE: event `progress` khi bắt đầu, event `tool` cho từng tool call và trạng thái `running`/`completed`/`error`, sau đó event `result` chứa cùng response JSON; lỗi giữa stream dùng event `error` với `{code, message}`. Local ID ánh xạ tới OpenCode session theo guest owner trong runtime store. OpenCode ID không lộ ra client. Một response có tối đa 5 tour.

Requirements/comparisons created without a Bearer token remain unowned for workspace compatibility. When a guest Bearer token is supplied, reads and history are restricted to that session. Existing unowned records are preserved by the schema migration. `POST /comparisons` runs synchronously. Agent routes require a Bearer session and never accept owner IDs from the client. OpenCode is optional and requires a configured `opencode serve`; ordinary requirement/comparison routes do not depend on it.

Agent có thể hỏi lựa chọn qua `ask_choice`, lấy catalog facets, lọc tour bằng hard rules, đọc chi tiết/evidence, đánh giá sở thích mềm bằng verdict 3 mức, nới một hard criterion, và đổi lunar date qua `clarify_date`. Unknown không được coi là pass.

## Remaining integration target (not yet runtime)

- `/auth/*` → Supabase Auth adapter; backend verify identity với đúng provider project, không tin owner ID từ client.
- `/requirements/{id}/revisions/{revision}`, `/requirements/{id}/proposals`, `/proposals/{id}/*` → revision, draft proposal, confirm/cancel/discard explicit.
- `POST /comparison-jobs`, `GET /jobs/{id}`, `GET /jobs/{id}/events`, `POST /jobs/{id}/cancel` → progress có thứ tự và trạng thái terminal; không đổi kết quả comparison đồng bộ hiện có.
- `/history/*` → rename/pin/archive, transcript, metadata CAS và guest-session linking explicit (basic list/detail are runtime).
- `POST /comparisons/{id}/what-if`, `GET /what-if/{id}`, `POST /what-if/{id}/scenarios/{scenario}/proposals` → phân tích bound với comparison, apply chỉ tạo proposal; cần confirm trước lần tìm kế tiếp.
- `/evidence/*`, `/requirements/{id}/messages/*`, `/contacts` → evidence lookup, conversation follow-up và contact ticket.

Lỗi dùng `{error: {code, message}}`. `code` ổn định để consumer map ngôn ngữ hiển thị; `message` là tiếng Anh. Thiếu là `unknown`, không tính là đạt. Destination chỉ gồm nơi tham quan đã bỏ origin endpoint; route/raw vẫn được giữ. Giá hard chỉ so khi fresh, trusted, exact, cùng currency/basis; giá `from` dưới trần là unknown, lower bound đã vượt trần có thể fail. Soft scoring chỉ nhận tour còn offer qua hard filter và chỉ chấp nhận quote nguyên văn trong evidence; verdict chưa rõ không được biến thành đạt.

## Pipeline

OpenCode agent điều khiển hội thoại → MCP tools kiểm tra điều kiện có cấu trúc qua `input` → `decide` lấy snapshot từ `data`, hard-filter, áp dụng soft verdict có quote được xác minh, xếp hạng và phân tích. Không còn free-text keyword/NIM extraction hay slot state machine. Chi tiết: [system-architecture](system-architecture.md), [`src/backend/README.md`](../src/backend/README.md), [`src/backend/agent/README.md`](../src/backend/agent/README.md).

## Chạy tối thiểu

```powershell
uv sync
opencode serve --hostname 127.0.0.1 --port 4098
# Set OPENCODE_SERVER_URL=http://127.0.0.1:4098 in .env
uv run tour-backend serve
```

Mặc định local dùng SQLite và catalog fixture. Khi có `SUPABASE_TOUR_DB_URL`, backend dùng URL đó cho runtime store (đọc/ghi phiên và kết quả) lẫn catalog Supabase (chỉ đọc catalog); không cần `DATABASE_URL` hoặc `DATA_PROVIDER`. Migration `migrations/004_runtime_store.sql` phải được áp dụng trước; session mapping dùng records store.

OpenCode giữ một server local chạy nền; backend gọi `opencode run --attach http://127.0.0.1:4098 --format json` theo từng tin nhắn và gắn `--session` khi đã có session ID. Agent/MCP config nằm trong `opencode.json`, `.opencode/agents/` và `src/backend/agent/`. Backend và OpenCode server cần cùng host/workspace để nạp MCP server. Không cần NIM key cho hội thoại hay soft verdict. Frontend nhận tiến độ tool qua SSE và kết quả cuối cùng qua event `result`; consumer cũ vẫn dùng JSON mặc định. Trang chào: `http://127.0.0.1:8000/`, docs tương tác: `http://127.0.0.1:8000/docs`.
