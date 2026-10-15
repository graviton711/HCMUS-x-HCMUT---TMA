# backend/data — persistence + catalog I/O

## Trách nhiệm

Giữ I/O và persistence: guest sessions, owner-scoped agent-session/requirement/comparison records, history, cache metric đã trích xuất theo hash nội dung/phiên bản, cùng đọc catalog Supabase chỉ-đọc. Không rank hoặc gọi LLM. Account/Auth và metadata/archive history vẫn là phần tích hợp tiếp theo.

## Input/output

Vào: requirement/comparison records cần lưu; truy vấn catalog (giới hạn số tour). Ra: records theo id; `TourRow` (rows catalog kèm evidence + `field_meta`). Supabase lỗi thì raise `AppError` `retryable`; không có fallback offline.

## Workflow

`sessions.py`: token hash + expiry cho guest session; `save_*`/`get_*` buộc resource vào owner session khi có token; `list_history` dùng cursor theo `(created_at, id)` và trả page cùng `has_more`; `get_history_item` trả model đã validate. Mapping `agent_session` trong records lưu local chat ID ↔ OpenCode session ID theo owner; OpenCode ID không xuất hiện trong history/API. MCP và API dùng chung runtime store để bàn giao Comparison theo mã `decision_run_id` ngẫu nhiên; API lấy một lần, xác thực requirement rồi lưu comparison dưới owner thật. Scan snapshot lưu riêng theo comparison ID dưới owner thật, phục vụ trace pagination và what-if; response comparison có thể rút gọn độc lập. Dùng record kind trong runtime store hiện có, không cần migration schema. Cache metric chỉ hợp lệ khi content hash và extractor version khớp; cache không thay snapshot/evidence nguồn. Bản ghi tạm của lượt quyết định được dọn khi lượt kết thúc, cache metric tồn tại để tránh trích lại tour không đổi. Migration thêm owner column, giữ nguyên records cũ ở trạng thái unowned. `catalog.py`: `SupabaseCatalog.list_tour_index()` đọc trước các cột nhẹ cần cho hard filter và trace; workflow chỉ gọi `list_tour_details()` cho tour hard-pass và nhóm near-miss cần hiển thị. Snapshot vẫn giữ index của toàn bộ phạm vi quét để đếm funnel và chạy scenario; detail của tour mới đạt trong scenario được nạp theo khóa nguồn ổn định và chỉ chấp nhận nếu timestamp quan sát khớp snapshot. `for_settings()` luôn dùng Supabase qua `SUPABASE_TOUR_DB_URL` (thiếu URL thì báo `CATALOG_NOT_CONFIGURED`); scan/provider limits và freshness ngày khởi hành đọc từ `configs/settings.yaml` (`backend.data`), env thắng YAML. Catalog là đầu vào có thẩm quyền; backend không áp allowlist trust domain.

## Interface với module khác

`decide` dùng snapshots đã normalize; `workflows` điều phối index scan và tải detail có chọn lọc; `api` dùng persistence. MCP dùng runtime store để chuyển kết quả quyết định hoàn tất sang API, không dùng output của model làm kênh bàn giao. `GET /catalog` hiện chỉ công bố destinations, chưa phải catalog DTO đầy đủ cho UI. Đọc bảng Supabase `providers`/`tours`/`offers` (+ `evidence`, `field_meta`) theo `migrations/`. Không import module crawler; không ghi catalog.

## Quyết định kỹ thuật

- Runtime store (sessions/requirements/comparisons) dùng `SUPABASE_TOUR_DB_URL` nếu có; nếu không, config local giữ SQLite. Một URL Supabase cấp cho cả runtime store và catalog.
- Bảng runtime ở Postgres được tạo bởi `migrations/004_runtime_store.sql`; agent session mapping, decision handoff và metric cache dùng record kinds trong `runtime_records`, không cần bảng riêng. Ingest áp migrations cho Supabase; backend không tự chạy DDL.
- Catalog mặc định là Supabase chỉ-đọc; thiếu `SUPABASE_TOUR_DB_URL` thì báo `CATALOG_NOT_CONFIGURED`, không có fallback offline.
- Supabase đọc SQL thô qua `psycopg`, transaction chỉ đọc, `LIMIT` chặn trên. Quét đầu tiên chỉ lấy cột nhẹ; các trường văn bản lớn như itinerary, exclusions và policies chỉ tải cho ứng viên cần đánh giá/hiển thị. Log lỗi catalog chỉ ghi operation, thời lượng, loại exception và SQLSTATE nếu có; không ghi DSN, exception text hoặc dữ liệu tour.
