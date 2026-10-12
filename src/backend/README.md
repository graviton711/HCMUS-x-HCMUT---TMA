# backend — travel agent + pipeline nghiệp vụ

Luồng hội thoại: user → OpenCode agent → MCP tools → validate → catalog/hard filter → soft verdict → kết quả có evidence.

- [`data`](data/README.md): guest sessions, owner-scoped SQLite records/history + đọc catalog.
- [`input`](input/README.md): validate điều kiện có cấu trúc; không parse text tự do.
- [`normalize`](normalize/README.md): rows catalog thành snapshot có pricing/freshness.
- [`decide`](decide/README.md): lọc → chấm → rank → phân tích.
- `workflows.py`: đọc catalog, chuẩn hóa snapshot và chạy hard-filter/comparison.
- [`agent`](agent/README.md): owner-scoped OpenCode session, MCP tools, JSON response và SSE tiến độ tool.
- `api.py`: HTTP orchestration/routes. `models.py`: nguồn chuẩn duy nhất của mọi kiểu. `settings.py`: config env. `errors.py`: `AppError`.

Frontend React nằm ở sibling module [`src/frontend`](../frontend/README.md). Chat dùng OpenCode agent; không có NIM extraction hay keyword fallback. `SUPABASE_TOUR_DB_URL` là URL duy nhất cho runtime store và catalog Supabase; nếu vắng mặt, local dùng SQLite và fixture theo YAML. Hợp đồng: [system-architecture](../../docs/system-architecture.md), [data-contract](../../docs/data-contract.md), [backend-contract](../../docs/backend-contract.md).
