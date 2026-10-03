# Module frontend

**Trạng thái:** PLANNING. Thư mục hiện chỉ chứa tài liệu; stack và cấu trúc source cuối cùng chốt ở P2.
**Tài liệu:** [Planning](../../docs/frontend-plan.md), [flow](../../docs/frontend-flows.md), [checklist FE–BE](../../docs/frontend-backend-checklist.md), [data contract](../../docs/data-contract.md).

## Trách nhiệm

Nhận nhu cầu/URL, thể hiện quá trình xử lý, so sánh tour/offer, trình bày trade-off và evidence. Quản lý draft/thao tác/trạng thái màn hình; không thực hiện crawler hay tự suy dữ kiện thiếu.

## Input / output

- Input người dùng: criteria và URL theo schema sẽ chốt với BE.
- Input API: criteria chuẩn hóa, Tour/Offer/Provider, trade-off, issues, lifecycle theo contract chung.
- Output API: request hợp lệ, câu trả lời làm rõ/thử lại/hủy nếu API hỗ trợ.
- Output người dùng: bảng so sánh, trạng thái dữ liệu, evidence và đường mở nhà cung cấp.

## Workflow

Draft → validate → submit snapshot → làm rõ/xử lý → nhận và validate response → ánh xạ dữ liệu hiển thị → comparison/evidence → sửa hoặc thử lại. Response cũ không được ghi đè snapshot mới.

## Ranh giới dự kiến

| Phần | Interface / trách nhiệm |
|---|---|
| App shell / routes | Điều hướng, back/refresh và context phiên theo policy đã chốt |
| Criteria / URL input | Draft + validation; xuất payload theo contract |
| API boundary | Client, DTO sinh từ schema, runtime validation, lifecycle và error mapping |
| Comparison | Nhận kết quả đã validate; chọn đúng offer/tiêu chí, trình bày trade-off |
| Evidence | Nhận reference chính xác; mở dữ kiện/nguồn của field hoặc nhận định |
| UI foundation | Tokens, component trạng thái, format tiền/ngày, focus và responsive |

Đây là ranh giới trách nhiệm, chưa bắt buộc tạo sáu package hoặc thêm global store. Trước khi viết một phần phải có tài liệu cạnh phần đó.

## Quyết định kỹ thuật

- Đề xuất React + TypeScript + Vite; chưa chốt. API JSON riêng là boundary với BE.
- Contract chuẩn là nguồn DTO; dữ liệu API chưa validate không đi thẳng vào component.
- Tách server result khỏi draft/local UI; chỉ thêm global state khi có nhu cầu chia sẻ thực tế.
- View model được phép gom dữ liệu để render, nhưng phải giữ reference và không tạo dữ kiện mới.
- Mock và API thật dùng cùng schema/client boundary; thư viện, package root, routes và hosting là đầu ra P2.
