# backend — 4 module + api mỏng

Luồng: input người dùng → lọc cứng thu pool → LLM chấm mềm → phân tích quyết định.

- [`data`](data/README.md): guest sessions, owner-scoped SQLite records/history + đọc catalog.
- [`input`](input/README.md): text/form thành điều kiện chuẩn.
- [`normalize`](normalize/README.md): rows catalog thành snapshot có pricing/freshness.
- [`decide`](decide/README.md): lọc → chấm → rank → phân tích.
- `api.py`: HTTP orchestration/routes. `models.py`: nguồn chuẩn duy nhất của mọi kiểu. `settings.py`: config env. `errors.py`: `AppError`.

Frontend React nằm ở sibling module [`src/frontend`](../frontend/README.md). Guest search đã nối end-to-end với API hiện tại; account, proposals, jobs, evidence/messages và what-if vẫn chờ port. Hợp đồng và kế hoạch: [system-architecture](../../docs/system-architecture.md), [data-contract](../../docs/data-contract.md), [backend-contract](../../docs/backend-contract.md).
