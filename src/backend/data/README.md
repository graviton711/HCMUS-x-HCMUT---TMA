# backend/data — persistence + catalog I/O

## Trách nhiệm

Giữ I/O và persistence hiện có: SQLite guest sessions, owner-scoped requirement/comparison records và history, cùng đọc catalog (fixture mẫu cho dev/test, Supabase cho live). Không rank hoặc gọi LLM. Account/Auth và metadata/archive history vẫn là phần tích hợp tiếp theo.

## Input/output

Vào: requirement/comparison records cần lưu; truy vấn catalog (giới hạn số tour). Ra: records theo id; `TourRow` (rows catalog kèm evidence + `field_meta`). Supabase lỗi thì raise `AppError` `retryable`; không bao giờ fallback fixture lén.

## Workflow

`sessions.py`: token hash + expiry cho guest session; `save_*`/`get_*` buộc resource vào owner session khi có token; `list_history` dùng cursor theo `(created_at, id)` và `get_history_item` trả model đã validate. Migration thêm owner column, giữ nguyên records cũ ở trạng thái unowned. `catalog.py`: `FixtureCatalog.list_tours()` hoặc `SupabaseCatalog.list_tours()` → rows thô. `for_settings()` chọn provider theo `DATA_PROVIDER`; scan/provider limits, trust allowlist và freshness đọc từ `configs/settings.yaml` (`backend.data`), env thắng YAML.

## Interface với module khác

`decide` dùng rows catalog; `api` dùng persistence. `GET /catalog` hiện chỉ công bố destinations, chưa phải catalog DTO đầy đủ cho UI. Đọc bảng Supabase `providers`/`tours`/`offers` (+ `evidence`, `field_meta`) theo `migrations/`. Không import module crawler; không ghi catalog.

## Quyết định kỹ thuật

- SQLite là store cho requirement/comparison records hiện tại.
- Fixture là explicit (`DATA_PROVIDER=fixture`), không phải fallback lén.
- Supabase đọc SQL thô qua `psycopg`, transaction chỉ đọc, `LIMIT` chặn trên.
