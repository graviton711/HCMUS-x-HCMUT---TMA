# Module frontend

**Trạng thái:** PLANNING. Thư mục hiện chỉ chứa tài liệu; stack và cấu trúc source cuối cùng chốt ở P2.
**Tài liệu:** [flow](../../docs/frontend-flows.md), [tích hợp v1](../../docs/frontend-api-integration.md), [HTTP contract](../../docs/api-contract.md), [domain](../../docs/backend-contracts.md), [schemas](../../contracts/README.md).

## Trách nhiệm

Giới thiệu → form nhu cầu + URL và xác nhận → kết quả. BE tự tìm/rank/chọn tối đa ba gợi ý/so sánh cùng URL tham chiếu. FE render criteria đầy đủ, sửa trực tiếp/chat/diff/xác nhận, bảng kiểm chứng/Phân tích AI/evidence và activity thật; nhóm khác qua chat, Retry lỗi riêng. Không màn sàng lọc/chọn tour, không crawler/tự tính ranking.

## Input / output

- Input người dùng: form bắt buộc/tùy chọn/default + chat ghi chú, URL tùy chọn; criteria sửa trực tiếp/chat ở màn kết quả. Field mẫu cá nhân hóa chưa thay C1/G4; URL-only không ép party/budget/ngày. V1 URL 2–5/tách mode cần G9; form dùng canonical IDs.
- Input API: Session, committed Requirement revision/readiness, parse/comparison Job, Comparison envelope/result, Facts/evaluations và Evidence. Metadata/giá/policies chưa đủ giữ G1–G3/G5.
- Input API mục tiêu: thứ tự/Top 3/lý do/giới hạn/policy và reference chung còn G10; v1 chưa trả ranking, không lấy thứ tự candidates làm rank.
- Input API mục tiêu thêm: chat context/proposal preview/diff/confirm atomic (G11), analysis/operands/basis/coverage/offer/evidence/unknown (G12), activity có thứ tự/thời điểm/phase/source/terminal (G13). Chưa endpoint/DTO; mock không chứng minh runtime.
- Output API hiện có: create/patch requirement, typed answers/edits, comparison theo revision, offer selection/reuse URL, GET polling/evidence và cancel; mutation có idempotency key. Cách request review URL/retrieval chung và nhóm so sánh tự động/vòng phương án khác còn G9, chưa đặt DTO/endpoint mới.
- Output người dùng: giới thiệu/widget/demo minh họa, form review/xác nhận tại chỗ, nhóm đề xuất/bảng/analysis, criteria/chat/diff, nhật ký xử lý/trạng thái/evidence và đường mở nhà cung cấp. Bỏ stepper/nút Sửa yêu cầu/Lưu bản nháp/Tìm lại.

## Workflow

Theo review điều khiển: sửa field/slider/chat tự cuộn tới diff/xác nhận. Confirm cập nhật criteria; Tìm kiếm hoặc lệnh chat chạy theo criteria đã xác nhận. UI không hiện revision; snapshot/bảo vệ revision giữ nội bộ. Form/kết quả/processing đều thuộc nav Tìm tour; Liên hệ/Hỗ trợ là bề mặt phụ. Mức sở thích còn G14, chưa mapping vào API/ranking policy.

Giới thiệu → form/session/draft/validate + chat ghi chú → review và xác nhận ngay form → màn 3 skeleton/activity → BE retrieval/đánh giá/rank/chọn nhóm/so sánh/analysis → render bảng/analysis/evidence. Sửa trực tiếp/chat tạo diff → confirm atomic revision → Tìm kiếm bằng nút/chat theo yêu cầu đã xác nhận; nhóm khác qua chat, Retry lỗi riêng. Nhóm/snapshots do BE chọn; G9–G14 mở, polling/terminal/error v1 làm nền.

## Ranh giới dự kiến

| Phần | Interface / trách nhiệm |
|---|---|
| App shell / routes | Ba màn Giới thiệu / form + xác nhận / Kết quả, back/refresh/session token/IDs/expiry; revision context còn G6, widget provider/quyền/fallback chưa chốt |
| Criteria / URL input + review | Một draft chung, field/default có nhãn, validation/canonical mapping; hard/soft/tree, review phạm vi ngay form, criteria màn 3 rộng và sửa trực tiếp |
| Chat / proposal | Câu hỏi dùng snapshot, thay đổi tạo diff/hủy/xác nhận theo revision, nhóm khác/exclusion; preview không commit/atomic commit còn G11 |
| API boundary | Bearer client; DTO sinh từ public schema, runtime validation, envelope/id mapping, revision/job/cancel/idempotency và lỗi HTTP/job |
| Kết quả / lượt đề xuất | Nhận nhóm tối đa ba gợi ý và tham chiếu/rank/lý do/coverage/bảng từ BE; render ngay, giữ vòng cũ khi tìm phương án khác; không render pool hoặc tự chọn/rank |
| Comparison / Phân tích AI | Bảng kiểm chứng và tab giải thích/phép tính/đánh đổi/unknown cùng criteria/revision/offer/evidence; G9/G12 còn chốt, không suy empty từ groups |
| Activity / trạng thái | Skeleton/chậm/partial/empty/error/cancel, log đúng activity của job và terminal; G13 chưa public DTO/stream, prototype log mock có nhãn |
| Evidence | Nhận reference chính xác; mở dữ kiện/nguồn của field hoặc nhận định |
| UI foundation | Tokens, component trạng thái, format tiền/ngày, focus và responsive |

Đây là ranh giới trách nhiệm, chưa bắt buộc tạo package riêng cho từng hàng hoặc thêm global store. Trước khi viết một phần phải có tài liệu cạnh phần đó.

## Quyết định kỹ thuật

- Đề xuất React + TypeScript + Vite; chưa chốt. API JSON riêng là boundary với BE.
- Contract chuẩn là nguồn DTO; public response schema còn thiếu G8, request schemas chưa đủ full client. Không dùng contract CrawlResult/Extraction nội bộ làm input component.
- Tách draft/pending proposal/diff, committed revision, jobs và snapshots; stale proposal/context đổi không commit, conflict giữ draft. Criteria chỉ đổi sau confirm; kết quả cũ ghi revision đã dùng khi chờ/lỗi/hủy, response muộn không ghi đè. Tour URL lỗi không làm mất retrieval và ngược lại; BE giữ binding khi retry/offer.
- View model được phép gom dữ liệu để render, nhưng phải giữ reference và không tạo dữ kiện mới.
- Ranking là trách nhiệm BE: theo criteria/policy, Top 3 tour khác nhau, thiếu ba thì nêu rõ. FE hiển thị lý do/giới hạn và cho yêu cầu phương án khác; không coi hard unknown pass. Đề xuất URL tham chiếu ngoài ba gợi ý và pool 20 nội bộ còn review tại FLOW-3, không expose pool.
- Mock và API thật dùng cùng schema/client boundary; thư viện, package root, routes và hosting là đầu ra P2.
- Giá/cost do BE tính, FE định dạng và giữ evidence; không tạo budget giả để lấy giá, không suy tổng khi có bound/null/thiếu phụ thu. Giữ G1–G8; G9 bổ sung xử lý chung. Phạm vi tìm gợi ý từ URL không tự thành hard constraints.
- Chat preview không dùng PATCH text v1 vì parse thành công sẽ commit. G11 cần protocol riêng được chốt trước runtime; Phân tích AI G12 giữ operands/basis/coverage/offer/evidence, không sinh điểm hoặc suy nghĩ nội bộ; G13 chỉ progress thật, không % giả.
- Giấy ấm/Newsreader/Be Vietnam Pro đã chốt; accent xanh sâu/đất nung, ảnh/motion nhẹ/reduced-motion còn review token. Cột criteria 340–380px/~30% desktop, mobile xếp dọc/bảng cuộn riêng. Widget/weather/location/demo prototype có nhãn mock, không API ngoài/geolocation thật.
- Data fixture và source thật dùng cùng API; synthetic phải hiện nhãn. HTTP fixture integration không thay nghiệm thu crawler/data thật P5.2.
- Tourcrawl/scripts đã merge nhưng output CSV/raw JSON chưa phải CrawlResult/public DTO; không gọi crawler trực tiếp từ FE. Ranh giới adapter/registry/price/evidence/profile ở [D1–D5](../../docs/frontend-crawler-integration.md); G1–G8 vẫn giữ.
