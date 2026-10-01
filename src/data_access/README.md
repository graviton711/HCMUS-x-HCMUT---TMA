# Data access

**Trạng thái:** Đã có implementation v1; phạm vi kiểm tra và giới hạn ở [backend-runtime.md](../../docs/backend-runtime.md).

## Trách nhiệm / input-output

Input: QuerySpec hoặc URL targets, source registry, deadline và snapshot selections nếu có. Output: validated immutable snapshots, evidence, source coverage và issues. Sở hữu gateway/validation phía backend; snapshot persistence ở API Store; adapters/access discovery do người crawl làm.

## Workflow và interfaces

1. Chọn approved sources theo mode/capability; gửi QuerySpec đã chuẩn hóa. Crawler quyết định pushdown theo capability, backend luôn đánh giá lại conditions.
2. Gọi HTTP crawler bằng một request có deadline (crawler quản lý concurrency từng nguồn); URL fetch layer kiểm tra domain, redirects và đích mạng, không chỉ kiểm tra URL một lần ở API.
3. Validate envelope/field/evidence bindings qua domain; lưu validated envelope theo retention; cách ly field tĩnh sai, từ chối envelope/giá/provenance không hợp lệ.
4. Reject duplicate snapshot/evidence IDs. Không merge giá giữa offers/nguồn; Store commit envelope và comparison atomically. Dedup tour catalog xuyên nhiều request chưa có.
5. Trả source result kể cả blocked/unsupported/timeout. API/job coordinator nhận progress; decision nhận snapshots có chất lượng và policy rõ.

## Quyết định kỹ thuật

- Gateway có fixture implementation cho demo phát triển; `origin=synthetic` đi xuyên API/UI. Không cần thay decision engine khi nối crawler thật.
- Freshness theo source/field/policy version. Policy chưa cấu hình thì unknown; dữ kiện volatile dùng strict policy trước khi chứng minh hard price/date/availability.
- TTL cache không thay observed_at hoặc chứng minh giá còn hiệu lực. Refresh tạo snapshot mới; snapshot đã khóa vào comparison không đổi.
- Offer selection phải thuộc target + snapshot user sở hữu; stale selection không tự chuyển sang offer rẻ/mới khác.
- HTTP crawler hiện một attempt; lỗi transient trả retryable để caller chạy lại, không retry access-blocked/unsupported. Coverage/truncation công khai.
- Repository lưu requirement revisions/jobs ở lớp điều phối cùng database; validated crawl envelope được Store lưu cùng comparison. Dev đề xuất SQLite qua SQLAlchemy, deployment nhiều host đề xuất PostgreSQL theo hosting; business logic không phụ thuộc engine.

Acceptance: field sai không thành fact; lỗi một source không mất source khác; rollback không tạo evidence refs mồ côi; reused snapshots/crawler/fixture cho cùng schema; dữ liệu mô phỏng không mang nhãn thật.
