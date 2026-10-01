# Decision

**Trạng thái:** Đang triển khai theo contracts; tình trạng kiểm tra cuối cùng ở [backend-runtime.md](../../docs/backend-runtime.md).

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
- Không xếp hạng tổng mặc định. User sort có tiêu chí công khai, unknown/incomparable giữ nhãn; Pareto/trọng số là phần sau khi đã có metric đáng tin.

Acceptance: bảng truth table ALL/ANY đúng; budget bounds không tạo false pass/fail; OR không bị biến AND; mandatory fail giữ visible ở URL flow; mỗi claim truy ra evaluation và evidence đúng snapshot.
