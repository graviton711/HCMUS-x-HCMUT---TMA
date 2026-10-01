# Data access

**Trạng thái:** Đang triển khai theo contracts; tình trạng kiểm tra cuối cùng ở [backend-runtime.md](../../docs/backend-runtime.md).

## Trách nhiệm / input-output

Input: QuerySpec hoặc URL targets, source registry, deadline và snapshot selections nếu có. Output: validated immutable snapshots, evidence, source coverage và issues. Sở hữu gateway/repository/cache policy phía backend; adapters/access discovery do người crawl làm.

## Workflow và interfaces

1. Chọn approved sources theo capability; lập pushdown plan không mất hard predicates.
2. Gọi crawler gateway với concurrency/deadline; URL fetch layer kiểm tra domain, redirects và đích mạng, không chỉ kiểm tra URL một lần ở API.
3. Validate envelope/field/evidence bindings qua domain; giữ raw snapshot phục vụ debug theo retention, loại invalid field khỏi decision input.
4. Dedup trong nguồn theo entity ID/canonical URL; lưu snapshots/evidence trong một transaction phù hợp, không merge giá giữa offers/nguồn.
5. Trả source result kể cả blocked/unsupported/timeout. API/job coordinator nhận progress; decision nhận snapshots có chất lượng và policy rõ.

## Quyết định kỹ thuật

- Gateway có fixture implementation cho demo phát triển; `origin=synthetic` đi xuyên API/UI. Không cần thay decision engine khi nối crawler thật.
- Freshness theo source/field/policy version. Policy chưa cấu hình thì unknown; dữ kiện volatile dùng strict policy trước khi chứng minh hard price/date/availability.
- TTL cache không thay observed_at hoặc chứng minh giá còn hiệu lực. Refresh tạo snapshot mới; snapshot đã khóa vào comparison không đổi.
- Offer selection phải thuộc target + snapshot user sở hữu; stale selection không tự chuyển sang offer rẻ/mới khác.
- Retry lỗi transient có giới hạn trong deadline, không retry access-blocked/unsupported. Coverage/truncation công khai.
- Repository lưu requirement revisions/jobs ở lớp điều phối cùng database; data_access quản lý supplier/tour/offer/evidence. Dev đề xuất SQLite qua SQLAlchemy, deployment nhiều host đề xuất PostgreSQL theo hosting; business logic không phụ thuộc engine.

Acceptance: field sai không thành fact; lỗi một source không mất source khác; rollback không tạo evidence refs mồ côi; cache/crawler/fixture cho cùng schema; dữ liệu mô phỏng không mang nhãn thật.
