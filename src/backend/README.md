# backend — 4 module + api mỏng

Luồng: input người dùng → lọc cứng thu pool → LLM chấm mềm → phân tích quyết định.

- [`data`](data/README.md): phiên, owner-scoped history/jobs/proposals + đọc catalog.
- [`input`](input/README.md): text/form/revision thành điều kiện chuẩn.
- [`normalize`](normalize/README.md): rows catalog thành snapshot có pricing/freshness.
- [`decide`](decide/README.md): lọc → chấm → rank → phân tích và what-if.
- `api.py`: HTTP orchestration/routes; `auth.py`: xác thực identity ở provider boundary. `models.py`: nguồn chuẩn duy nhất của mọi kiểu. `settings.py`: config env. `errors.py`: `AppError`.

Frontend React nằm ở sibling module [`src/frontend`](../frontend/README.md), gọi API này và không mang backend v2 riêng. Hợp đồng: [system-architecture](../../docs/system-architecture.md), [data-contract](../../docs/data-contract.md), [backend-contract](../../docs/backend-contract.md).
