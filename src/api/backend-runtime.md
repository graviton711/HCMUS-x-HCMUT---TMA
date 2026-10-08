# Backend v1: chạy và tích hợp

Backend v2 được bổ sung ngày 07/10/2026, giữ các routes v1 bên dưới. SQLite hiện schema 2 và tự migrate từ 1. Luồng proposal/admin/events và giới hạn nghiệm thu mới tại [backend-v2-runtime](backend-v2-runtime.md); request examples tại [backend-v2](../../examples/backend-v2.md).

**Trạng thái 02/10/2026:** Có implementation, 85 tests offline đạt và hai luồng chạy qua ASGI API với worker thật. NIM live smoke đạt 8/8 ca đã chọn, gồm 2 lượt sửa hội thoại. Crawler thật chưa có dữ liệu để kiểm chứng.

## Chạy local

Từ root repo, Python >=3.12:

```powershell
uv sync
uv run tour-backend serve
```

Mở `http://127.0.0.1:8000/` để thấy trang chào và liên kết vào Swagger `/docs`, health `/health`. Đây là backend API; giao diện sản phẩm do frontend phụ trách. CLI mặc định bind loopback. Dùng `--port 8001` nếu port đang bận.

`Application startup complete` nghĩa là server đã chạy. CLI không tự reload khi sửa code: nhấn Ctrl+C rồi chạy lại `uv run tour-backend serve` để nạp bản mới.

`.env` hiện có được giữ nguyên: `NVIDIA_NIM_API`, `NVIDIA_NIM_MODEL=nvidia/nemotron-3-super-120b-a12b`. Environment variables ưu tiên hơn file. Không có credential trong schema, response, source control hay log mặc định.

## Luồng frontend

1. `POST /v1/sessions` lấy token; gửi `Authorization: Bearer <token>` cho `/v1/*` còn lại.
2. `POST /v1/requirements`: text trả 202 + parse job; form hoặc URL-only trả 201 + revision 1.
3. Poll `/v1/jobs/{id}`; khi parse succeeded, GET requirement để lấy conditions, defaults, clarifications/readiness.
4. PATCH bằng `expected_revision` và đúng một nhóm text/answers/edits; response 409 nghĩa phải tải state mới.
5. POST comparison với requirement id/revision; poll job rồi GET comparison/evidence.

Xem [payload chạy được](../../examples/README.md), [HTTP contract](api-contract.md) và [schemas](../../contracts/README.md). Session demo có hạn 24 giờ; chưa có tài khoản/password. Lỗi NIM không commit revision mới. Idempotency keys có phạm vi session và body/path; hết hạn sau 24 giờ.

Trong Swagger: tạo session → **Authorize** bằng riêng token → tạo requirement → so sánh bằng ID/revision thật. Chọn example **So sánh URL mô phỏng** để thử persistence không cần NIM/crawler. Session, requirement và comparison/job được lưu ngay khi từng request hợp lệ; refresh SQLite viewer để thấy dữ liệu. Request 401/404 không tạo comparison/job. Hướng dẫn xử lý ở [examples](../../examples/README.md#checking-database-writes).

Budget coverage thiếu → `tour_price` + provenance `system_default`, theo quyết định user. Giá trị explicit `trip_total` vẫn được giữ. Currency/basis không được suy đoán. Thiếu tuổi chỉ chặn phép đánh giá chi phí cần tuổi, không chặn đối chiếu tour tĩnh.

## Dữ liệu và crawler

Mặc định `DATA_PROVIDER=fixture`: ba tour giả tại `https://tour-demo.invalid/tour-a`, `tour-b`, `tour-c`; không fetch các URL này. Kết quả mang `origin=synthetic`. Ví dụ discover với 2 người lớn + bé 8 tuổi và trần giá tour 30 triệu có một tour đạt, một tour thiếu giá trẻ, một tour vượt trần.

Kết nối crawler: cấu hình `DATA_PROVIDER=http`, `CRAWLER_URL`, `CRAWLER_REGISTRY_PATH`, tùy chọn `CRAWLER_API_KEY`. [Registry mẫu](../../examples/source-registry.json) chưa duyệt nguồn nào. Crawler nhận POST CrawlRequest và trả CrawlResult; URL fetch/redirect/DNS checks thuộc crawler. Backend chỉ gọi endpoint server cấu hình, không fetch URL người dùng.

Backend kiểm tra correlation, whitelist nguồn, snapshot/evidence bindings, types và thời điểm. Field tĩnh sai được cách ly với issue; envelope/provenance/giá không hợp lệ bị từ chối. Với nguồn thật, TTL cho `price`, `departure_date`, `return_date`, `availability` do registry cấu hình; thiếu TTL thì freshness unknown, không chứng minh điều kiện biến động. `pricing_complete` là sourced boolean chứng minh mọi phụ thu/giảm giá bắt buộc đã được phản ánh; thiếu thì không xác nhận tổng tiền.

URL comparison giữ mọi target và thứ tự. Có nhiều offers thì yêu cầu chọn bằng snapshot id từ comparison cũ; không lấy giá rẻ nhất tự động. Reuse cùng requirement/targets/nguồn được duyệt và đánh giá freshness lại. Discovery đổi revision phải thu thập lại để không dùng nhầm phạm vi search cũ. Chưa có cache tìm kiếm dùng chung giữa các requirement.

## Runtime và giới hạn

- FastAPI/Pydantic, SQLAlchemy + SQLite tại `data/backend.db`; OS lock chỉ cho một process/worker dùng database. Schema v1 được tạo tự động, không tự migration phá dữ liệu. PostgreSQL/multi-host chưa triển khai.
- Jobs lưu bền, deadline mặc định 180 giây. Running khi restart → failed `JOB_INTERRUPTED`; queued còn hạn tiếp tục. Cancellation terminal được commit ngay; upstream có thể tiếp tục đến deadline nhưng kết quả đến muộn không ghi đè.
- NIM timeout 90 giây, tối đa một repair schema/grounding trong tổng deadline, không đổi model âm thầm. `NIM_REASONING=none` là baseline vận hành hiện tại, chưa phải kết luận tốt nhất từ full gold.
- Input tối đa 64 KB, text 8.000 ký tự, 50 conditions, URL 2–5, giới hạn session/job/request. CORS có danh sách origins cụ thể. Session/auth này dành cho demo local; chưa phải auth người dùng cho deployment public.
- Lưu revisions và validated crawl envelopes bất biến theo comparison để replay. Purge lúc startup hoặc `uv run tour-backend purge` khi server đã dừng; mặc định giữ 7 ngày, bảo vệ dependencies của jobs đang chờ.
- Catalog alias hiện gồm một số điểm đến phổ biến; địa danh/chỉ tiêu ngoài catalog giữ unresolved/unsupported. Không bảo đảm hiểu mọi cách nói tiếng Việt. Số viết bằng chữ, yêu cầu vận động/uy tín chưa có metric cần user làm rõ hoặc sửa form.
- JSON Schema/OpenAPI mô tả request/domain; còn invariants nghiệp vụ ở Python. Chưa có streaming progress theo từng nguồn hay tự tổng hợp điểm xếp hạng.

Settings đầy đủ ở [settings.py](settings.py), mẫu env không chứa key thật ở [backend.env.example](../../examples/backend.env.example).

## Kiểm tra

```powershell
uv run pytest -q
uv run ruff check src tests
uv run ruff format --check src tests
uv run tour-backend export-schemas
```

85 tests kiểm tra normalization/defaults/patches, AND/OR, giá nhóm/bounds/completeness, ownership, revisions/idempotency, cancellation/restart/deadline và hai luồng API. Bao gồm OpenAPI bearer auth, request bị từ chối không ghi resource/job, và Swagger URL example ghi SQLite qua kết nối đọc độc lập. Có một deprecation warning của Starlette TestClient/httpx; suite vẫn đạt trên dependencies đã khóa.

Live riêng: `uv run tour-backend probe-nim`, hoặc `uv run tour-backend evaluate-nim --output data/evaluation.local.json`. Đây là các lượt gọi provider thật với câu giả lập; không chạy trong pytest mặc định. Smoke cuối đạt 8/8 ca + kiểm tra 2 patch; 10 responses hợp lệ có latency 1,453–13,422 giây và một ca cần repair. Đây không phải latency end-to-end benchmark. **Chưa chạy full gold 50 câu/15 chuỗi hoặc held-out set**, nên không suy ra accuracy ngoài bộ này.

Luồng kiểm tra ASGI dùng NIM thật đã nhận đủ destination/origin/duration/budget/hotel, readiness ready; discovery trả một eligible, một ineligible, một needs_verification; URL-only giữ đủ ba targets và `filter_applied=false`. Tour data trong kiểm tra vẫn là synthetic.
