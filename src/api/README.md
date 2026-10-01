# API và điều phối

**Trạng thái:** Đã có implementation v1; phạm vi kiểm tra và giới hạn ở [backend-runtime.md](../../docs/backend-runtime.md).

## Trách nhiệm / input-output

Nhận DTO HTTP, kiểm tra session/ownership, tạo requirement revision và durable jobs, điều phối modules rồi trả progress/results/errors. Input: user text/form/URLs/edits; output: resources versioned và evidence có quyền truy cập. Route không chứa logic extraction/filter/pricing.

`GET /` trả trang chào HTML công khai, dẫn tới `/docs` và `/health`; không tạo session hoặc gọi NIM/crawler. Trang này giúp mở địa chỉ server trực tiếp mà không gặp 404; giao diện sản phẩm do frontend phụ trách.

## Workflow và interfaces

1. Validate request/idempotency; lưu resource/job và reference timestamp.
2. Worker claim job bằng lease, chạy requirements hoặc data_access → decision với deadline; persist phase và source results. Chưa có progress streaming theo từng nguồn trong khi HTTP crawler đang chạy.
3. Requirement patch commit bằng expected revision; comparison khóa revision/snapshots/policy được chọn.
4. Publish terminal status/result refs trong transaction; frontend poll jobs/resources. Evidence endpoint kiểm tra binding/ownership.

## Quyết định kỹ thuật

- FastAPI/Pydantic, cùng một backend với worker nhỏ có durable state; không cần microservices/queue ngoài ngay từ đầu.
- Parse text async do NIM latency biến động; form/answer đã có kiểu có thể validate và trả ngay.
- OS lock giới hạn một process cho mỗi SQLite database. Restart chuyển running thành failed JOB_INTERRUPTED; queued còn deadline tiếp tục, không tự gọi lại upstream cũ. Job đã terminal không overwrite bằng late upstream response.
- Không commit revision mới khi model technical error. Khi revision thay trong lúc parse patch chạy, trả conflict thay vì ghi đè.
- Succeeded empty result khác failed upstream. Partial chỉ khi có lỗi acquisition nhưng vẫn có dữ liệu dùng được; field unknown không mặc định làm job lỗi.
- Giữ stable error codes/trace ids, log secret-free; raw text theo retention riêng. Auth/session, CORS, input/rate/concurrency limits phải phù hợp hosting public.

Acceptance: text/form paths cùng domain semantics; owner không xem resource user khác; idempotency không tạo job lặp; revision races không mất update; timeout/restart luôn đến trạng thái terminal.

## Persistence hiện tại

Dev local dùng SQLite qua SQLAlchemy/repository, một backend + worker; mặc định journal của runtime, không tự bật WAL chưa kiểm tra version/config. Public deployment nhiều process/host đề xuất PostgreSQL. Dependencies khóa trong uv.lock, schema SQLite v1 khởi tạo bởi Store; chưa có migration lên phiên bản khác.

| Table | Vai trò |
|---|---|
| sessions | Hash token, expiry, owner ID |
| resources | Owner/kind/status/current revision; requirement metadata hoặc comparison payload |
| requirement_revisions | Immutable JSON, unique (resource_id, revision) |
| jobs | Input JSON, status/phase, deadline, lease, error/metrics; terminal cancellation |
| idempotency | Unique (owner, key), body/path hash, response, expiry |
| schema_info | Database schema version |

Validated supplier/tour/offer/evidence envelopes lưu trong comparison payload, không có bảng snapshot riêng ở v1.

Không giữ transaction trong lúc gọi NIM/crawler. Claim/commit bằng conditional update có status/lease/revision predicate và kiểm tra row count=1; ORM version counter không thay tất cả CAS này. Commit result + terminal job state atomically; cancellation/late response kiểm tra lại trước commit.
