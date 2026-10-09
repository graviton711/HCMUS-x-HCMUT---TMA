# backend — 4 module + api mỏng

Luồng: input người dùng → lọc cứng thu pool → LLM chấm mềm → phân tích quyết định.

- [`data`](data/README.md): phiên + đọc catalog.
- [`input`](input/README.md): text/form thành điều kiện.
- [`normalize`](normalize/README.md): rows catalog thành snapshot.
- [`decide`](decide/README.md): lọc → chấm → rank → phân tích.
- `api.py`: routes mỏng trên pipeline. `models.py`: nguồn chuẩn duy nhất của mọi kiểu. `settings.py`: config env. `errors.py`: `AppError`.

Hợp đồng: [system-architecture](../../docs/system-architecture.md), [data-contract](../../docs/data-contract.md), [backend-contract](../../docs/backend-contract.md).
