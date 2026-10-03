# Module frontend

**Trạng thái:** PLANNING. Thư mục hiện chỉ chứa tài liệu; stack và cấu trúc source cuối cùng chốt ở P2.
**Tài liệu:** [Planning](../../docs/frontend-plan.md), [flow](../../docs/frontend-flows.md), [checklist FE–BE](../../docs/frontend-backend-checklist.md), [tích hợp v1](../../docs/frontend-api-integration.md), [HTTP contract](../../docs/api-contract.md), [domain](../../docs/backend-contracts.md), [schemas](../../contracts/README.md).

## Trách nhiệm

Nhận nhu cầu/URL, thể hiện quá trình xử lý, so sánh tour/offer, trình bày trade-off và evidence. Quản lý draft/thao tác/trạng thái màn hình; không thực hiện crawler hay tự suy dữ kiện thiếu.

## Input / output

- Input người dùng: text hoặc form conditions/party/trees; URL 2–5 với criteria tùy chọn. Form dùng canonical IDs; catalog và mapping control chốt C1/G4.
- Input API: Session, committed Requirement revision/readiness, parse/comparison Job, Comparison envelope/result, Facts/evaluations và Evidence. Metadata/giá/policies chưa đủ giữ G1–G3/G5.
- Output API: create/patch requirement, typed answers/edits, comparison theo revision, offer selection/reuse URL, GET polling/evidence và cancel; mutation có idempotency key theo action.
- Output người dùng: bảng so sánh, trạng thái dữ liệu, evidence và đường mở nhà cung cấp.

## Workflow

Bootstrap session → draft/validate → create requirement → text thì poll parse → review committed revision/làm rõ → khi can_collect_data tạo comparison → poll job/GET result → validate/ánh xạ → bảng/evidence → sửa hoặc thử lại. Response cũ không ghi đè snapshot mới; filter_applied=false vẫn có bảng dữ kiện. Mọi terminal status dừng polling; async error đọc job.error.

## Ranh giới dự kiến

| Phần | Interface / trách nhiệm |
|---|---|
| App shell / routes | Điều hướng, back/refresh, anonymous session token/IDs/expiry theo policy; revision context còn G6 |
| Criteria / URL input | Draft + validation/canonical mapping; hard/soft/tree, answers/edits và payload theo contract |
| API boundary | Bearer client; DTO sinh từ public schema, runtime validation, envelope/id mapping, revision/job/cancel/idempotency và lỗi HTTP/job |
| Comparison | Kết quả gắn revision/snapshots; targets/candidates/evaluations, không suy empty từ groups; chọn offer URL qua reuse, trade-off có refs |
| Evidence | Nhận reference chính xác; mở dữ kiện/nguồn của field hoặc nhận định |
| UI foundation | Tokens, component trạng thái, format tiền/ngày, focus và responsive |

Đây là ranh giới trách nhiệm, chưa bắt buộc tạo sáu package hoặc thêm global store. Trước khi viết một phần phải có tài liệu cạnh phần đó.

## Quyết định kỹ thuật

- Đề xuất React + TypeScript + Vite; chưa chốt. API JSON riêng là boundary với BE.
- Contract chuẩn là nguồn DTO; public response schema còn thiếu G8, request schemas chưa đủ full client. Không dùng contract CrawlResult/Extraction nội bộ làm input component.
- Tách draft/local UI, committed revision, pending parse/comparison jobs và result snapshots; conflict giữ draft, không tự retry ghi đè. Chỉ thêm global state khi có nhu cầu chia sẻ thực tế.
- View model được phép gom dữ liệu để render, nhưng phải giữ reference và không tạo dữ kiện mới.
- Mock và API thật dùng cùng schema/client boundary; thư viện, package root, routes và hosting là đầu ra P2.
- Giá/cost do BE tính, FE định dạng và giữ evidence; không tạo budget giả để lấy giá, không suy số tổng khi có bound/null hoặc thiếu phụ thu. G1–G8 còn giữ để hoàn thiện interface.
- Data fixture và source thật dùng cùng API; synthetic phải hiện nhãn. HTTP fixture integration không thay nghiệm thu crawler/data thật P5.2.
- Tourcrawl/scripts đã merge nhưng output CSV/raw JSON chưa phải CrawlResult/public DTO; không gọi crawler trực tiếp từ FE. Ranh giới adapter/registry/price/evidence/profile ở [D1–D5](../../docs/frontend-crawler-integration.md); G1–G8 vẫn giữ.
