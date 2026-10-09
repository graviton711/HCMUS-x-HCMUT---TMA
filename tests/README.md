# Tests

Chạy deterministic, offline: records mẫu, services mock, SQLite tạm. Không cần `.env`, credentials, ghi catalog hay gọi NIM/crawler live.

- `test_backend_*`: backend mới (input, normalize, decide, sessions, API).
- `test_ingest_*`: pipeline crawler.
- `test_shared_runtime`: helpers dùng chung.

```powershell
uv run pytest -q
uv run ruff check src tests
```
