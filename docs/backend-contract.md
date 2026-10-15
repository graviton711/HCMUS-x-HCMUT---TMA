# Hợp đồng backend

API HTTP cho frontend và các consumer. Schema live ở `/openapi.json`; models trong `src/backend/models.py` là nguồn chuẩn duy nhất. Frontend gọi contract này, không gọi `/v2` legacy và không đọc database trực tiếp. Hội thoại tự do do OpenCode agent điều khiển; backend tools nhận dữ liệu cấu trúc và kiểm tra trước khi đọc catalog.

## Current runtime

- `GET /health` → `{status, version}`.
- `POST /sessions` → guest session Bearer token with expiry. Only a SHA-256 token hash is persisted.
- `GET /catalog` → `{destinations}` from the active read-only catalog provider; this is a basic lookup, not the richer frontend catalog contract.
- `POST /requirements` — body `{conditions, raw_text?, travelers?, ranking?}` để lưu requirement có cấu trúc, hoặc `{form}` cho workspace hiện tại → `{requirement}`. Text tự do không được parse thành điều kiện; field/operator/value sai bị từ chối.
- `GET /requirements/{id}` → requirement đã lưu.
- `POST /comparisons` — body `{requirement_id, candidate_limit?}` → `{comparison}` gồm xếp hạng, hard evaluations, evidence, phân tích và snapshot candidate tự chứa để kết quả đã lưu vẫn render được. Endpoint này dùng `candidate_default` (hiện là 20) và giới hạn `candidate_max` (hiện là 100). Agent MCP quét catalog đến `data.scan_limit` (hiện là 2000 theo `configs/settings.yaml`); số bản ghi quét không khẳng định tổng số tour trong database. `ranked` chỉ chứa offer qua hết điều kiện cứng; `near_miss` chứa offer fail không quá `near_miss_max_fails` điều kiện cứng (mặc định 2), xếp theo pass nhiều → fail ít → giá rẻ để UI render nhóm "Gần đạt" riêng. `unknown` không tính là fail.
- `GET /comparisons/{id}` → comparison đã lưu.
- `GET /history?limit=&cursor=` and `GET /history/{id}` → cursor pagination and owner-scoped requirement/comparison detail for guest sessions.
- `POST /agent/sessions` — Bearer bắt buộc; tạo local agent session và trả `{agent_session_id}`.
- `POST /agent/sessions/{id}/messages` — Bearer bắt buộc; body `{message}`. Có thể trả `{assistant_text, choices?, tool_calls?, requirement?, comparison?, decision_draft?}`. Khi cần gợi ý hoặc xác nhận địa điểm, agent dùng `catalog_facets` để lấy nhãn thực trong scan và `discover_destinations` để lọc theo hard condition đã biết. Tool preflight chỉ trả địa điểm có candidate qua hết điều kiện; ngày cũ/thiếu dữ liệu không tính là đạt. Preflight không tạo comparison, không xác nhận chỗ trống hoặc sức chứa nhóm. Một `decision_draft` chứa requirement đã cấu trúc; việc tạo draft không chạy comparison. Với `Accept: text/event-stream`, trả SSE `progress`, từng lần gọi `tool` có mô tả nghiệp vụ và trạng thái, rồi `result`; lỗi giữa stream dùng event `error`. `tool.status=error` chỉ nói lần gọi đó lỗi; lượt vẫn có thể kết thúc thành công nếu agent gọi lại và trả kết quả hợp lệ. Nếu tool lỗi và agent không có nội dung khác để trả, backend gửi lời nhắc thử lại; phản hồi OpenCode rỗng hoàn toàn vẫn là lỗi `OPENCODE_RESPONSE_EMPTY`.
- `POST /agent/sessions/{id}/decisions` — Bearer bắt buộc; body chứa requirement đã được người dùng review, gồm `conditions`, tổng `travelers`, `traveler_mix` tùy chọn (`adult`, `child`, `small_child`, `infant`) và `weight_percent` cho từng soft condition. Nếu có mix, tổng nhóm tuổi phải bằng `travelers`; thiếu mix thì không suy ra tổng giá theo nhóm. Backend validate lại schema, hard conditions và tổng trọng số đúng 100 trước khi chạy. MCP ghi Comparison hoàn tất vào runtime store theo mã lượt riêng; backend lấy, kiểm tra requirement rồi mới lưu theo owner và trả response/SSE. Kết quả cuối không phụ thuộc model có nhắc lại JSON tool trong câu trả lời hay không. Response trả `metric_profiles`, `decision_options`, `decision_views`, `ranked`, `near_miss`, evidence và `candidates_considered`.

Local agent ID ánh xạ tới OpenCode session theo guest owner; OpenCode ID không lộ ra client. Các lượt tìm kiếm giới hạn số tour hiển thị theo contract, nhưng đánh giá soft bao phủ mọi hard-pass candidate trong phạm vi catalog scan. MCP dùng batch để không gửi toàn bộ evidence cùng lúc vào model context.

Requirements/comparisons created without a Bearer token remain unowned for workspace compatibility. When a guest Bearer token is supplied, reads and history are restricted to that session. Existing unowned records are preserved by the schema migration. `POST /comparisons` runs synchronously. Agent routes require a Bearer session and never accept owner IDs from the client. OpenCode is optional and requires a configured `opencode serve`; ordinary requirement/comparison routes do not depend on it.

## OpenCode event adapter

OpenCode JSON events may expose MCP calls directly or wrap them in Code Mode `execute`. The backend normalizes wrapped tool names and inputs from `state.metadata.toolCalls`, then parses returned JSON from `state.content`. SSE progress and `tool_calls` represent the logical MCP operations; wrapper-level argument errors such as a missing `code` field are not reported as failed catalog operations. A Decision Brief is returned only from a validated `draft_requirement` payload.

## Agent ranking

Metric extraction explicitly reports which source fields were reviewed: itinerary, route, inclusions, exclusions, surcharges, cancellation_policy, or child_policy. Only a non-empty source field named in that report counts as reviewed; an empty fact list never means exclusions contain no extra costs.

Requirement draft mang điều kiện `hard`/`soft`; mỗi soft condition có `weight_percent`. Draft chỉ được chạy khi tổng trọng số bằng 100. Hard conditions quyết định eligibility. Trước khi brief được duyệt, `discover_destinations` lọc catalog theo hard conditions đã biết; đây chỉ là preflight.

Sau khi xác nhận, `query_tours` quét catalog và áp hard filter. Metric enrichment xử lý riêng từng trường mềm trên mọi hard-pass candidate. Structured fact phải có quote khớp nguồn; numeric/categorical values được chuẩn hóa và tính bởi code. Cache enrichment theo content hash và extractor version. MCP lưu comparison cuối qua `decision_run_id`; tool progress không phải kênh bàn giao kết quả.

Mỗi response comparison bổ sung `metric_profiles`, `decision_options` và `recommendation` (optional), đồng thời giữ `ranked`, `near_miss` và snapshots cũ. Metric fact gồm metric key, value/range, unit, state, source field, exact quote, observed time và method version. Exclusion được phân loại bắt buộc/tùy chọn/có điều kiện; chỉ khoản có amount/unit rõ mới cộng vào cost.

Metric/objective views: `cheapest` (exact group total, same currency), `best_fit` (weighted score/range và evidence coverage), `experience_rich`, `fewest_legs`, `cancellation_flexible`, `family_friendly`, `included_value` và `balanced` (Pareto trên các metric có thể so sánh). Metric thiếu dữ liệu thì view đó unavailable hoặc nêu rõ coverage; không tạo overall score ẩn. Mỗi view tối đa 5 candidates. Toàn result phải có ít nhất ba tour thật khác nhau nếu scan có đủ; views có thể dùng chung candidate nhưng không thay tiêu chí distinct tour.

`candidates_considered` là số tour đã quét, không phải tổng catalog. `ranked`/`near_miss` và các tool `ask_choice`, `catalog_facets`, `discover_destinations`, `draft_requirement`, `tour_detail`, `clarify_date` vẫn tương thích. Thay brief/trọng số để chạy what-if tính result mới, không ghi đè comparison cũ. Không tự nới điều kiện; nếu thiếu ba tour, trả số thực có và kịch bản nới điều kiện cần user review.

## Remaining integration target (not yet runtime)

- `/auth/*` → Supabase Auth adapter; backend verify identity với đúng provider project, không tin owner ID từ client.
- `/requirements/{id}/revisions/{revision}`, `/requirements/{id}/proposals`, `/proposals/{id}/*` → revision, draft proposal, confirm/cancel/discard explicit.
- `POST /comparison-jobs`, `GET /jobs/{id}`, `GET /jobs/{id}/events`, `POST /jobs/{id}/cancel` → progress có thứ tự và trạng thái terminal; không đổi kết quả comparison đồng bộ hiện có.
- `/history/*` → rename/pin/archive, transcript, metadata CAS và guest-session linking explicit (basic list/detail are runtime).
- `POST /comparisons/{id}/what-if`, `GET /what-if/{id}`, `POST /what-if/{id}/scenarios/{scenario}/proposals` → phân tích bound với comparison, apply chỉ tạo proposal; cần confirm trước lần tìm kế tiếp.
- `/evidence/*`, `/requirements/{id}/messages/*`, `/contacts` → evidence lookup, conversation follow-up và contact ticket.

Lỗi HTTP dùng `{error: {code, message}}`; SSE dùng event `error` với `{code, message}`; MCP trả cùng envelope JSON trong tool content. `code` ổn định để consumer map ngôn ngữ hiển thị; `message` là tiếng Anh. Lỗi 4xx thông thường không được log. Lỗi 5xx hoặc retryable được log một lần tại ranh giới transport với metadata an toàn; exception không dự kiến trả `INTERNAL_ERROR` chung, không lộ nội dung exception. Agent không có deadline tổng; tiến trình kết thúc khi OpenCode hoàn tất hoặc client ngắt kết nối. Timeout riêng của MCP tool và kết nối dữ liệu vẫn áp dụng.

Thiếu dữ liệu là `unknown`, không tính là đạt. Destination chỉ gồm nơi tham quan đã bỏ origin endpoint khi endpoint trùng sau chuẩn hóa tổng quát; route/raw vẫn được giữ. Snapshot không chứa country alias hay completeness metadata. Agent ánh xạ quốc gia/vùng sang các label thực có trong `catalog_facets`, và hỏi lại nếu không tìm được nhãn phù hợp. Engine chỉ so điều kiện destination tường minh với các label đó. Giá hard dùng basis của từng offer; không fallback âm thầm sang `tours.price_type`. Giá `fixed` được so trực tiếp với ngân sách cùng currency; giá `from` dưới hoặc bằng trần là unknown, lower bound vượt trần có thể fail; giá thiếu hoặc `contact` là unknown. Freshness TTL vẫn áp dụng cho ngày khởi hành. Soft scoring chỉ nhận tour còn offer qua hard filter, quote phải khớp nguyên văn evidence; unknown tạo khoảng điểm hoặc trạng thái chưa so sánh được.

## Pipeline

OpenCode agent điều khiển hội thoại → MCP tools kiểm tra điều kiện có cấu trúc qua `input` → workflow lấy catalog và hard-filter → agent trích structured facts có quote → code xác minh, chuẩn hóa và tính metric profiles → `decide` tạo objective views/options. Không còn free-text keyword/NIM extraction hay slot state machine. Chi tiết: [system-architecture](system-architecture.md), [`src/backend/README.md`](../src/backend/README.md), [`src/backend/agent/README.md`](../src/backend/agent/README.md).

## Chạy tối thiểu

```powershell
uv sync
# Set OPENCODE_SERVER_URL and OPENCODE_SERVER_PASSWORD in .env
# Terminal 1
uv run tour-opencode serve
# Terminal 2
uv run tour-backend serve
```

Mặc định local dùng SQLite và catalog fixture. Khi có `SUPABASE_TOUR_DB_URL`, backend dùng URL đó cho runtime store (đọc/ghi phiên và kết quả) lẫn catalog Supabase (chỉ đọc catalog); không cần `DATABASE_URL` hoặc `DATA_PROVIDER`. Migration `migrations/004_runtime_store.sql` phải được áp dụng trước; session mapping dùng records store.

OpenCode giữ một server local chạy nền; backend gọi `opencode run --server http://127.0.0.1:4098 --format json` theo từng tin nhắn và gắn `--session` khi đã có session ID. Model có một nguồn cấu hình duy nhất: `opencode.model` trong `configs/settings.yaml`; backend luôn truyền giá trị này bằng `--model`. Agent profile và môi trường không đặt model riêng, nên session cũ và mới dùng cùng cấu hình. CLI dùng thư mục làm việc của tiến trình làm project context; backend đặt thư mục này từ `OPENCODE_PROJECT_DIR`, mặc định là root repo. Backend đọc `OPENCODE_SERVER_PASSWORD` từ `.env`/process environment và truyền biến đó cho CLI/API OpenCode. Lệnh `tour-opencode serve` nạp cùng `.env`, dùng loopback và lấy cổng từ `OPENCODE_SERVER_URL`; chỉ địa chỉ bind có thể override bằng `--hostname`, để server và backend không lệch cổng. Lệnh này dành cho server local; server remote được khởi chạy bởi nền tảng deploy. Agent/MCP config nằm trong `opencode.json`, `.opencode/agents/` và `src/backend/agent/`. Backend và OpenCode server cần cùng host/workspace để nạp MCP server. Không cần NIM key cho hội thoại hay soft verdict. Frontend nhận tiến độ tool qua SSE và kết quả cuối cùng qua event `result`; consumer cũ vẫn dùng JSON mặc định. Trang chào: `http://127.0.0.1:8000/`, docs tương tác: `http://127.0.0.1:8000/docs`.

## Operational logging

Operational logs are not part of the HTTP/SSE contract. Each request has a correlation ID returned in `X-Request-ID` and included in backend log records. OpenCode diagnostics record process status and bounded, filtered stderr only on failure; tool logs use logical tool name and status without inputs or outputs. A validated Decision Brief is logged as a boolean lifecycle milestone, not with its contents. Local file logging defaults to `.local/logs/backend.log` and rotates at 10 MiB × 5 backups; hosted Render deployments use the Dashboard log stream and do not rely on container files.
