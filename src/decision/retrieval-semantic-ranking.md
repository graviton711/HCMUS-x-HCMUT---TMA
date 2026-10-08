# Structured retrieval và đánh giá ngữ nghĩa v2

User duyệt triển khai 08/10/2026. Hai trục độc lập: kiểu xử lý structured/semantic và strength hard/soft/unresolved. Không đổi field có cấu trúc thành hard nếu user chỉ ưu tiên; party là input pricing/applicability.

## Workflow và interfaces

1. Extraction/normalization/confirm giữ nguyên; guard phát hiện party đã biểu diễn lại thành unsupported condition để NIM repair, không tự bỏ ý khác.
2. Supabase đọc bounded scan trong repeatable-read, normalize và kiểm bằng chứng. Đánh giá hard tree trước giới hạn pool; static fail được loại trước truy vấn offers bằng SQL IDs. Chỉ loại khi fail được chứng minh, unknown được giữ. Không dùng raw price/date hoặc metadata `verified` để loại.
3. Đánh giá toàn bộ hard tree trên **từng offer** rồi lấy tồn tại một offer đạt; không ghép ngày offer A và giá offer B. Cắt pool sau đánh giá, ưu tiên pass rồi unknown rồi relevance. URL tham khảo luôn giữ. Offer coverage/truncation public; thiếu offer không chứng minh fail.
4. Pool đủ hard (hoặc URL-only không hard) đi qua semantic assessment bất đồng bộ. LLM đọc các đoạn snapshot có giới hạn, trả criterion/status/citations, không sinh điểm tổng, giá/ngày hoặc sửa requirement. Reputation/service quality/value for money chưa có nguồn đánh giá độc lập giữ unsupported.
5. Backend kiểm exact quote, snapshot/source/condition binding, completeness khi phủ định. Assessment là model interpretation, không nâng source thành verified; dữ liệu unverified không tham gia utility. Có timeout/deadline, một bounded repair, failure giữ structured comparison và báo partial assessment.
6. Ranking pure dùng utility có bằng chứng; score trên phần biết vẫn public, thêm lower/upper trên tổng trọng số và coverage. Sort lower rồi upper rồi coverage; đây là thứ tự bảo thủ theo policy, không xác suất và không chứng minh ưu thế khi khoảng chồng nhau. Numeric utility dùng anchor cố định theo requirement thay vì min-max pool. Ties/no-score được công bố.
7. Sau khi chờ NIM, kiểm tra lại freshness trên đúng pool đã chuẩn bị; không thay tour trong pool giữa chừng khiến assessment mất binding. Publication giữ revision/cancellation/source gates. Lưu assessment theo comparison snapshot; offer_change cùng revision/snapshot/model dùng lại assessment đã kiểm, không gọi LLM lại.

## Contract

- `CrawlResultV2.retrieval`: policy/counts/scan + pool truncation; `offer_coverage`: complete theo tour snapshot, không trộn với pool truncation.
- Column: offer assessments và eligible offer IDs; top-level evaluations có offer binding khi là per-offer.
- `analysis.semantic_assessment`: state, policy/model, typed assessments, limitations/error code; không lưu credentials hoặc raw model reasoning.
- `analysis.metric_availability`: trạng thái các phép tính hiện có và prerequisites; không ép giá from thành exact.
- Supabase SQL pushdown chỉ thu hẹp IDs sau static evidence evaluation; predicate phức tạp vẫn xử lý bằng normalized evaluator. Chưa thêm database migration/index hoặc cho phép đọc raw field không bằng chứng như trusted filter. Bounded scan vẫn có giới hạn và được báo rõ.

## Kiểm chứng

Hard/soft độc lập kiểu dữ liệu; AND/OR; static fail trước pool; unknown giữ; cross-offer false pass; nhiều offers đạt; offer coverage thiếu; URL fail vẫn xem; citation giả/trộn snapshots; incomplete negative; NIM timeout/invalid và cancel/source pause; missing soft, ties, pool-independent utility; party duplicate repair; hai smoke Nhật/Tết không tự invent dữ liệu.
