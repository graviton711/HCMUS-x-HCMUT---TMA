# API và điều phối

**Trạng thái:** Đang triển khai theo contracts; tình trạng kiểm tra cuối cùng ở [backend-runtime.md](../../docs/backend-runtime.md).

## Trách nhiệm / input-output

Nhận DTO HTTP, kiểm tra session/ownership, tạo requirement revision và durable jobs, điều phối modules rồi trả progress/results/errors. Input: user text/form/URLs/edits; output: resources versioned và evidence có quyền truy cập. Route không chứa logic extraction/filter/pricing.

## Workflow và interfaces

1. Validate request/idempotency; lưu resource/job và reference timestamp.
2. Worker claim job bằng lease, chạy requirements hoặc data_access → decision với deadline; persist phase/source progress.
3. Requirement patch commit bằng expected revision; comparison khóa revision/snapshots/policy được chọn.
4. Publish terminal status/result refs trong transaction; frontend poll jobs/resources. Evidence endpoint kiểm tra binding/ownership.

## Quyết định kỹ thuật

- Đề xuất FastAPI/Pydantic, cùng một backend với worker nhỏ có durable state; không cần microservices/queue ngoài ngay từ đầu.
- Parse text async do NIM latency biến động; form/answer đã có kiểu có thể validate và trả ngay.
- Worker restart dùng lease/recovery; chỉ retry khi idempotent và còn deadline. Job đã terminal không overwrite bằng late upstream response.
- Không commit revision mới khi model technical error. Khi revision thay trong lúc parse patch chạy, trả conflict thay vì ghi đè.
- Succeeded empty result khác failed upstream. Partial chỉ khi có lỗi acquisition nhưng vẫn có dữ liệu dùng được; field unknown không mặc định làm job lỗi.
- Giữ stable error codes/trace ids, log secret-free; raw text theo retention riêng. Auth/session, CORS, input/rate/concurrency limits phải phù hợp hosting public.

Acceptance: text/form paths cùng domain semantics; owner không xem resource user khác; idempotency không tạo job lặp; revision races không mất update; timeout/restart luôn đến trạng thái terminal.

## Persistence đề xuất

Dev local dùng SQLite qua SQLAlchemy/repository, một backend + worker; mặc định journal của runtime, không tự bật WAL chưa kiểm tra version/config. Public deployment nhiều process/host đề xuất PostgreSQL. Chưa có dependency/database/migrations được tạo.

| Records | Khóa/điều kiện chính |
|---|---|
| requirements / requirement_revisions | Owner, current_revision; revision immutable, unique (requirement_id, revision) |
| jobs | Owner/kind/status, immutable input ref, deadline, attempt, lease_owner/lease_until, cancel_requested |
| comparisons | Owner + requirement revision, selected snapshot/policy refs, result/status |
| idempotency | Unique (owner, key), body hash, resource ref, expiry |
| supplier/tour/offer snapshots + evidence | Do data_access repository quản lý, refs/transaction không mồ côi |

Không giữ transaction trong lúc gọi NIM/crawler. Claim/commit bằng conditional update có status/lease/revision predicate và kiểm tra row count=1; ORM version counter không thay tất cả CAS này. Commit result + terminal job state atomically; cancellation/late response kiểm tra lại trước commit.
