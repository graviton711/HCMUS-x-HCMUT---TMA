# Backend runtime

**Trạng thái:** Đang triển khai; các mục dưới là phạm vi cần kiểm tra trước khi bàn giao.

## Phạm vi

- Python/FastAPI/Pydantic, SQLAlchemy + SQLite local; modules ở `src/domain`, `src/requirements`, `src/data_access`, `src/decision`, `src/api`.
- Text extraction dùng NVIDIA NIM từ `.env` ở root, không log/expose key. Structured form/answers/edits đi qua cùng semantic validators nhưng không cần model.
- Durable parse/comparison jobs chạy trong worker của cùng app, có deadline, cancellation và conditional revision/lease commits.
- Session bearer token ngẫu nhiên do backend cấp; chỉ lưu hash, resources bị giới hạn theo owner. Đây là session demo, chưa có account/password/login.
- Data provider mặc định fixture, output luôn `origin=synthetic`. HTTP crawler provider gọi một endpoint do server cấu hình và registry đã duyệt; không crawl website trong backend.

## Settings và policy

`.env` hiện tại giữ nguyên `NVIDIA_NIM_API`, `NVIDIA_NIM_MODEL`. Settings khác có default/configuration riêng: database local, data provider, crawler URL/registry path, CORS origins, NIM reasoning/timeout, worker concurrency và job deadlines. Env ưu tiên trên file; thiếu key không ngăn structured flow nhưng text job trả lỗi cấu hình rõ.

Cấu hình reasoning cần chọn qua đánh giá từng case độc lập, so sánh chất lượng và độ trễ; probe hiện tại chưa đủ để chọn profile mặc định. Native schema output vẫn được validate/ground từng quote. Không batch context khác nhau trong một request.

Freshness cho fixtures là policy mô phỏng công khai. Với nguồn thật, TTL volatile phải cấu hình theo source; chưa có policy thì unknown và không chứng minh hard price/date/availability. Supplier-published facts không mang nhãn independently verified.

## HTTP bổ sung cho bootstrap/tích hợp

- `POST /v1/sessions`: tạo session và trả bearer token một lần.
- `GET /health`: readiness cơ bản + data origin, không có secrets.
- `GET /v1/sources`: registry/capabilities công khai cho session.
- Schema JSON crawler/requirements được xuất từ models thật để crawler/frontend dùng; CLI có lệnh export contracts.

Các endpoints requirement/comparison/job/evidence và semantics theo [api-contract.md](api-contract.md). DTO formal trong OpenAPI/models là nguồn chính sau khi implement; ví dụ draft sẽ được cập nhật để khớp.

## Kiểm tra bắt buộc

Meaningful unit/integration tests cho semantic validation, grounding, patch preservation, three-valued filtering, price bounds/coverage/party, partial data/evidence binding, session isolation, revision conflict, idempotency, jobs/cancellation/recovery và hai luồng API. NIM transport dùng mock trong tests; kiểm tra live riêng có giới hạn, không gọi model trong mỗi test mặc định.

Không tuyên bố gold accuracy chỉ vì test suite chạy. 50 câu + 15 chuỗi là bộ specification; đánh giá model trên toàn bộ bộ đó được báo riêng nếu thực sự chạy.

## Quyết định triển khai v1

- Budget coverage mặc định `tour_price` (user chốt); provenance `system_default` khác với giá trị được nói rõ. Currency/basis vẫn không suy đoán.
- DTO Pydantic strict, field catalog và tree kiểm tra ở domain. NIM trả raw values/quotes/operations; backend tự chuẩn hóa tiền, địa danh, ngày. Unsupported giữ blocker.
- HTTP dùng bearer session demo; worker lưu job trong SQLite, một tiến trình/worker cho local. Restart đánh dấu job running bị gián đoạn thành failed; queued tiếp tục nếu còn deadline. Đây là recovery xác định, không hứa chạy lại request upstream đã gửi.
- Snapshot/evidence lưu nguyên envelope đã validate trong comparison, requirement revisions bất biến trong bảng riêng. Ownership truy theo comparison. Reuse snapshot chỉ trong cùng requirement và registry hiện được duyệt; freshness vẫn đánh giá lại.
- Schema khởi tạo v1 bằng SQLAlchemy; khi đổi version database phải migration rõ, không tự phá database cũ. Chưa có triển khai PostgreSQL/public multi-worker.
- Crawler HTTP URL do server cấu hình, không lấy từ user; nguồn thật phải có registry và TTL do team cấu hình. Gateway không tự fetch URL tour. Payload quá lớn, correlation sai, source/evidence binding sai bị từ chối; invalid field được cách ly với issue nếu envelope vẫn có thể dùng.
- `GET /health`, `POST /v1/sessions`, `GET /v1/sources`, CLI export schema; CLI kiểm tra NIM dùng câu giả lập, không log credential/raw upstream error.
- API có giới hạn input/job/session và CORS explicit. Session demo có expiry; dữ liệu local cần lệnh purge theo retention, không phải auth account production.
