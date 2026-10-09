# backend/data — lưu phiên + đọc catalog

## Trách nhiệm

Giữ mọi I/O: phiên SQLite (requirements, comparisons) và đọc catalog (fixture mẫu cho dev/test, Supabase cho live). Không rank, không LLM, không HTTP.

## Input/output

Vào: records requirement/comparison cần lưu; truy vấn catalog (giới hạn số tour). Ra: records theo id; `TourRow` (rows catalog kèm evidence + `field_meta`). Supabase lỗi thì raise `AppError` `retryable`; không bao giờ fallback fixture lén.

## Workflow

`sessions.py`: `create_requirement` → `get_requirement`; `create_comparison` → `get_comparison` (SQLite, WAL). `catalog.py`: `FixtureCatalog.list_tours()` hoặc `SupabaseCatalog.list_tours()` → rows thô. `for_settings()` chọn provider theo `DATA_PROVIDER`.

## Interface với module khác

`decide` dùng rows catalog; `api` dùng sessions. Đọc bảng Supabase `providers`/`tours`/`offers` (+ `evidence`, `field_meta`) theo `migrations/`. Không import module crawler; không ghi catalog.

## Quyết định kỹ thuật

- SQLite cho phiên: một file, không ops, đủ cho MVP.
- Fixture là explicit (`DATA_PROVIDER=fixture`), không phải fallback lén.
- Supabase đọc SQL thô qua `psycopg`, transaction chỉ đọc, `LIMIT` chặn trên.
