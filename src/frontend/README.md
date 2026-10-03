# Module frontend

**Trạng thái:** PLANNING. Thư mục hiện chỉ chứa tài liệu; stack và cấu trúc source cuối cùng chốt ở P2.
**Tài liệu:** [Planning](../../docs/frontend-plan.md), [flow](../../docs/frontend-flows.md), [checklist FE–BE](../../docs/frontend-backend-checklist.md), [tích hợp v1](../../docs/frontend-api-integration.md), [HTTP contract](../../docs/api-contract.md), [domain](../../docs/backend-contracts.md), [schemas](../../contracts/README.md).

**P3 design review:** [Hai hướng visual](../../docs/frontend-design-review.md), [prototype HTML/CSS/JS](../../prototypes/frontend-design/README.md) ngoài `src/`. Prototype có fixture riêng để review bố cục/tương tác, không DTO/client/mock runtime của P4; không chứng minh G9/G10 hoặc chốt stack. Thư mục module này vẫn chỉ có tài liệu.

## Trách nhiệm

Nhận nhu cầu + URL; BE tự tìm/rank/chọn tối đa ba gợi ý và so sánh ngay cùng URL tham chiếu. FE render đề xuất/lý do/bảng/evidence và cho tìm phương án khác/sửa yêu cầu; không màn sàng lọc/chọn tour, không crawler/tự tính ranking.

## Input / output

- Input người dùng: nhu cầu bằng text hoặc form + URL tùy chọn, kể cả một URL trong mục tiêu sản phẩm. V1 hiện URL 2–5/tách mode, cần G9. Form dùng canonical IDs; catalog/mapping control C1/G4 không chặn thiết kế.
- Input API: Session, committed Requirement revision/readiness, parse/comparison Job, Comparison envelope/result, Facts/evaluations và Evidence. Metadata/giá/policies chưa đủ giữ G1–G3/G5.
- Input API mục tiêu: thứ tự/Top 3/lý do/giới hạn/policy và reference chung còn G10; v1 chưa trả ranking, không lấy thứ tự candidates làm rank.
- Output API hiện có: create/patch requirement, typed answers/edits, comparison theo revision, offer selection/reuse URL, GET polling/evidence và cancel; mutation có idempotency key. Cách request review URL/retrieval chung và nhóm so sánh tự động/vòng phương án khác còn G9, chưa đặt DTO/endpoint mới.
- Output người dùng: review nhu cầu/phạm vi, nhóm đề xuất và bảng tự động, trạng thái dữ liệu, evidence và đường mở nhà cung cấp.

## Workflow

Session → draft/validate → hiểu nhu cầu/đọc URL → review → BE retrieval/đánh giá/rank/chọn nhóm/so sánh → render kết quả/evidence ngay → phương án khác/sửa nhu cầu/retry. Nhóm và snapshots do BE chọn, không đợi user chọn tour. G9/G10 còn mở; giữ anti-response-cũ/terminal polling/error v1 làm nền.

## Ranh giới dự kiến

| Phần | Interface / trách nhiệm |
|---|---|
| App shell / routes | Điều hướng, back/refresh, anonymous session token/IDs/expiry theo policy; revision context còn G6 |
| Criteria / URL input + review | Một draft chung, validation/canonical mapping; hard/soft/tree, answers/edits, review phạm vi truy vấn và payload theo contract |
| API boundary | Bearer client; DTO sinh từ public schema, runtime validation, envelope/id mapping, revision/job/cancel/idempotency và lỗi HTTP/job |
| Kết quả / lượt đề xuất | Nhận nhóm tối đa ba gợi ý và tham chiếu/rank/lý do/coverage/bảng từ BE; render ngay, giữ vòng cũ khi tìm phương án khác; không render pool hoặc tự chọn/rank |
| Comparison | Cùng criteria/revision/snapshots cho nhóm BE tạo; offer/giá/ngày/evidence binding chung còn G9; không suy empty từ groups, trade-off có refs |
| Evidence | Nhận reference chính xác; mở dữ kiện/nguồn của field hoặc nhận định |
| UI foundation | Tokens, component trạng thái, format tiền/ngày, focus và responsive |

Đây là ranh giới trách nhiệm, chưa bắt buộc tạo package riêng cho từng hàng hoặc thêm global store. Trước khi viết một phần phải có tài liệu cạnh phần đó.

## Quyết định kỹ thuật

- Đề xuất React + TypeScript + Vite; chưa chốt. API JSON riêng là boundary với BE.
- Contract chuẩn là nguồn DTO; public response schema còn thiếu G8, request schemas chưa đủ full client. Không dùng contract CrawlResult/Extraction nội bộ làm input component.
- Tách draft chung/local lượt kết quả, committed revision, pending jobs và result snapshots; conflict giữ draft, không tự retry ghi đè. Tour URL phân tích lỗi không làm mất phần retrieval và ngược lại; BE xác nhận binding khi retry/chọn offer. Chỉ thêm global state khi cần chia sẻ thực tế.
- View model được phép gom dữ liệu để render, nhưng phải giữ reference và không tạo dữ kiện mới.
- Ranking là trách nhiệm BE: theo criteria/policy, Top 3 tour khác nhau, thiếu ba thì nêu rõ. FE hiển thị lý do/giới hạn và cho yêu cầu phương án khác; không coi hard unknown pass. Đề xuất URL tham chiếu ngoài ba gợi ý và pool 20 nội bộ còn review tại FLOW-3, không expose pool.
- Mock và API thật dùng cùng schema/client boundary; thư viện, package root, routes và hosting là đầu ra P2.
- Giá/cost do BE tính, FE định dạng và giữ evidence; không tạo budget giả để lấy giá, không suy tổng khi có bound/null/thiếu phụ thu. Giữ G1–G8; G9 bổ sung xử lý chung. Phạm vi tìm gợi ý từ URL không tự thành hard constraints.
- Data fixture và source thật dùng cùng API; synthetic phải hiện nhãn. HTTP fixture integration không thay nghiệm thu crawler/data thật P5.2.
- Tourcrawl/scripts đã merge nhưng output CSV/raw JSON chưa phải CrawlResult/public DTO; không gọi crawler trực tiếp từ FE. Ranh giới adapter/registry/price/evidence/profile ở [D1–D5](../../docs/frontend-crawler-integration.md); G1–G8 vẫn giữ.
