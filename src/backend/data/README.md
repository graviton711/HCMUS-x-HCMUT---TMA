# backend/data — lưu phiên + đọc catalog

## Trách nhiệm

Giữ I/O và persistence: phiên SQLite (requirements, revisions, comparisons, proposals, jobs, history, ownership) và đọc catalog (fixture mẫu cho dev/test, Supabase cho live). Auth provider call được điều phối ở API boundary; không rank hoặc gọi LLM.

## Input/output

Vào: records có owner/session cần lưu; truy vấn catalog (giới hạn số tour). Ra: records trong đúng owner scope; `TourRow` (rows catalog kèm evidence + `field_meta`). Supabase lỗi thì raise `AppError` `retryable`; không bao giờ fallback fixture lén.

## Workflow

`sessions.py`: lưu/đọc session, requirement revisions, comparison, proposal, job event và history metadata trong SQLite/WAL; mọi account read/write có owner check, guest import chỉ qua thao tác explicit. `catalog.py`: `FixtureCatalog.list_tours()` hoặc `SupabaseCatalog.list_tours()` → rows thô. `for_settings()` chọn provider theo `DATA_PROVIDER`; scan/providers limits và timeout đọc từ `configs/settings.yaml` (`backend.data`), env thắng YAML.

## Interface với module khác

`decide` dùng rows catalog; `api` dùng persistence. Đọc bảng Supabase `providers`/`tours`/`offers` (+ `evidence`, `field_meta`) theo `migrations/`. Không import module crawler; không ghi catalog.

## Quyết định kỹ thuật

- SQLite cho application records; schema upgrade phải giữ nguyên guest records hiện có.
- Owner identity chỉ lấy từ token đã verify với Supabase Auth; không nhận owner ID do client tự khai.
- Không lưu password, access/refresh token hoặc response credential của provider trong SQLite/log.
- Fixture là explicit (`DATA_PROVIDER=fixture`), không phải fallback lén.
- Supabase đọc SQL thô qua `psycopg`, transaction chỉ đọc, `LIMIT` chặn trên.
