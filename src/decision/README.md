# Decision

Phân tích what-if theo [policy](../../docs/what-if-analysis.md): evaluate universe trước pool, hard/soft group ablation, mức nới có bằng chứng và cặp blockers; cùng snapshot/time/party. `what_if.py` tính metrics/witnesses, `v2.py` dùng chung rank; không gọi model hoặc tự sửa requirement. DTO ở `domain/what_if.py`.

What-if công khai condition diagnostics (counts/reason codes trên candidate summaries) để tìm thiếu dữ liệu, giữ phân biệt với eligibility toàn cây và contribution/causal metrics.

V2 structured retrieval/per-offer và semantic assessment theo [policy triển khai](../../docs/retrieval-semantic-ranking.md). Candidate evaluator là pure; NIM nằm trong module `semantic_assessment`. Không ghép predicates qua nhiều offers; ranking công bố khoảng điểm và coverage.

`prepare_candidates` chọn pool trước assessment; `refresh_candidates` đánh giá lại cùng pool sau upstream wait, giữ IDs và truncation. Không thêm tour khác vì eligibility thay đổi theo thời gian.

Catalog v2 preview giữ published_price/itinerary và trạng thái/giá chưa phân loại của offer. Dữ liệu unverified vẫn hiển thị và giữ reason, không tham gia hard pass hoặc price metrics; nhiều offers chưa chọn không tự lấy offer rẻ nhất. [Contract import](../data_access/supabase/README.md).

V2 (`v2.py`) bổ sung matrix DTO, giá không phụ thuộc Budget, rank policy có contributions/coverage, next-group exclusions và metrics có operands/evidence. V1 giữ nhóm eligibility hiện có. Pace/culture chưa có metric được công bố unsupported. Xem [backend-v2-runtime](../../docs/backend-v2-runtime.md).

**Trạng thái:** Đã có implementation v1 và v2; phần v1 ở [backend-runtime.md](../../docs/backend-runtime.md), v2 ở tài liệu trên.

## Trách nhiệm / input-output

Input: requirement revision/QuerySpec, tour/offer snapshots, source issues, offer selections và versioned policy. Output: candidate evaluations, cost estimates, URL matrix/discovery groups, comparable trade-offs và evidence-linked claims. Không gọi model, crawl hoặc quyết định thay user.

## Workflow và interfaces

1. Tạo candidate ở mức tour_only hoặc một offer cụ thể; giữ target map cho URL flow.
2. Kiểm tra applicability của pricing/party/room/service, tính cost bounds nếu có chứng cứ; thiếu coverage/quote thì giữ unknown.
3. Evaluate từng predicate pass/fail/unknown theo evidence, verification/freshness policy; fold ALL/ANY theo logic ba trạng thái.
4. Giữ decision blockers và empty hard tree rõ ràng; không tạo eligible khi nghĩa condition chưa resolve.
5. So sánh soft criteria trên dữ liệu comparable; dựng claims/trade-offs bằng template và evidence refs. API render dữ liệu có cấu trúc, không phụ thuộc prose thành công.

## Quyết định kỹ thuật

- Pure logic: cùng revision/snapshot/policy/evaluated_at cho cùng output; dễ replay/debug và không dùng confidence tự khai từ LLM.
- Lower/upper cost bound chỉ hợp lệ khi applicability/discount/fees/coverage cho phép chứng minh. Subtotal người lớn không mặc định là lower bound tổng nếu điều kiện giá/discount còn chưa rõ.
- Không tự đổi currency, tính trung bình nhóm để chứng minh giá từng người, nhân giá người lớn cho trẻ hoặc coi missing surcharge bằng 0.
- Source thiếu lịch/giá/chỗ không chứng minh fail/pass; unsupported mandatory user requirement cũng không bị drop.
- Với sets/itinerary chưa complete: đã thấy item có thể chứng minh contains; chưa thấy item không đủ chứng minh excludes hoặc contains fail. Các đại lượng “tất cả/minimum/maximum” cũng cần coverage đúng scope, không dùng một hotel/leg đại diện toàn tour.
- Tour-only và multiple offers chưa chọn vẫn có static comparison; không ghép volatile cells thành offer giả.
- V1 giữ eligibility/trade-offs, không xếp hạng tổng mặc định. V2 dùng `rank-v2.3-bounds`: score trên phần biết đi kèm coverage và khoảng điểm trên toàn bộ trọng số; sort lower/upper/coverage theo policy bảo thủ. Thiếu dữ liệu không làm tăng điểm tổng, khoảng điểm không là xác suất. Numeric utility dùng anchor cố định, không phụ thuộc pool. Sliders chỉ reweight metric đã hỗ trợ.
- Metric availability chỉ là computed khi có phép tính comparable; nêu lý do khi thiếu party, offer, exact price hoặc cùng currency/basis/coverage. Retrieval đã loại hết tour phải giữ lý do ALL_INELIGIBLE trong phạm vi đã quét, kèm truncation để tránh hiểu là toàn thị trường không có tour.

Acceptance: bảng truth table ALL/ANY đúng; budget bounds không tạo false pass/fail; OR không bị biến AND; mandatory fail giữ visible ở URL flow; mỗi claim truy ra evaluation và evidence đúng snapshot.
## Semantic v2 evaluation

`semantic.py` đánh giá entity alternatives/temporal/scoped transport/tour type/route/nature và delegate fields cũ. Unsupported qualitative metric trả unknown với reason; ranking công khai coverage và giữ null utility khi thiếu. [Contract](../../docs/requirements-semantics.md).
# Catalog validation

[Policy](../../docs/catalog-validation-policy.md): evaluator nhận `catalog_validated` chỉ khi source hiện hành approved và capability cho phép. Freshness/scope/completeness/price qualifiers vẫn độc lập; áp dụng cùng logic cho retrieval, comparison và what-if. Website proof vẫn được dùng; không coi receipt là independent verification.
