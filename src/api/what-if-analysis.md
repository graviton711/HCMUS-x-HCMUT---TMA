# Phân tích thay đổi điều kiện — v2

User yêu cầu implementation trên `backend` ngày 08/10/2026. Policy `what-if-v1`; đây là phân tích có điều kiện, không tự đổi requirement hoặc đề xuất tour vi phạm yêu cầu gốc.

## Trách nhiệm và interfaces

- `decision/what_if.py`: pure analysis trên một CrawlResultV2, requirement revision và evaluated_at cố định. Output baseline, nhóm điều kiện, scenarios, witness offers/evaluations/evidence, biến động thứ hạng, tỷ lệ có mẫu số và giới hạn.
- `domain/what_if.py`: public DTO; API tạo job qua `POST /v2/comparisons/{cid}/what-if`, đọc `GET /v2/what-if/{id}`. Comparison phải hoàn tất, đúng owner/current confirmed revision, không proposal chưa duyệt.
- `GatewayV2.collect_analysis`: một lần acquisition rộng, không hard filter/pool20. Supabase dùng một repeatable-read transaction, bounded tối đa500 tours và existing offer/scan limits; date anchor không thiên về ngày gốc. URL-only giữ scope URL; HTTP là bounded upstream scope, không hứa toàn catalog.
- Hybrid analysis dùng discovery snapshot rộng, không merge lần đọc URL riêng. Reference URL ngoài universe bounded có thể vắng; scope không hứa giữ mọi reference hoặc mở URL chưa có trong catalog.
- Baseline được **tính lại trên snapshot phân tích mới**, không lấy số lượng/thứ hạng của comparison cũ để tính delta. Công khai parent comparison, snapshot fingerprint, evaluated_at, source/scan/pool/offer coverage và exclusions.
- `scope.condition_diagnostics` đếm pass/fail/unknown và reason codes cho mỗi condition trên các candidate summaries gốc, kèm `offer_counts`/`offer_unknown_reason_counts` trên từng offer. Phân biệt `MULTIPLE_OFFERS_UNSELECTED` của summary với lỗi proof/giá thật trên offers. Đây là chẩn đoán dữ liệu trong snapshot, không là mức đóng góp hoặc thay cho đánh giá toàn cây trên từng offer.
- `semantic_assessment/what_if.py`: LLM cuối chỉ chọn tối đa3 insight IDs đã tính; backend render câu từ metrics/templates. Model không sinh số/% hoặc sửa điều kiện. Timeout/schema/ID lỗi dùng deterministic fallback; `WHAT_IF_EXPLANATION_ENABLED=false` tắt riêng bước này, default timeout15seconds. Soft semantic assessment thực hiện một lần trên union những candidates đủ hard ở baseline hoặc scenario, giới hạn hiện có; dữ liệu thiếu giữ null/bounds. Source capability đổi trong lúc xử lý chặn publication; snapshot scope lưu capabilities đã dùng.

## Workflow và quyết định

1. Đọc rộng, evaluate tất cả candidates trước giới hạn hiển thị. Hard tree xét từng offer, tồn tại offer đạt; giữ pass/fail/unknown và offer coverage. Không ghép ngày offer A với giá offer B.
2. Gom nhóm điều kiện cùng field và các bounds thời gian; toàn bộ nhánh ANY là đơn vị không tách. Những nhóm giao nhau được hợp nhất, tránh thay nghĩa AND/OR. Party không được ablate.
3. Hard leave-one-group-out và soft leave-one-group-out; giữ party, exclusions, các điều kiện khác và snapshot. Hard empty trong scenario là giả định không ràng buộc, không biến thành personalized confirmation.
4. Thử nới trần budget và cửa sổ ngày theo giá/ngày **có bằng chứng** trên snapshot: tối đa3 giá trị/nhóm, default increase25% và shift7days chỉ là giới hạn tìm kịch bản, không là sự đồng ý của user. Giữ currency/basis/coverage; chưa tạo actionable edits cho temporal/lunar hoặc operators chưa hỗ trợ.
5. Thử các cặp hard groups trong scenario budget. Chỉ ghi kết quả mở thêm lựa chọn vượt các thay đổi riêng; gọi là minimal trong các subset đã kiểm, không tuyên bố optimum toàn cục. Công khai groups/scenarios/pairs bị cắt.
6. Hard delta phân biệt fail→pass (đã chứng minh bị chặn), unknown→pass (yêu cầu gốc chưa xác minh), và candidates vẫn unknown. Tỷ lệ `proven_blocked / scenario_eligible` chỉ có khi mẫu số>0 và không có unknown→pass trong cohort; áp dụng cho snapshot đã đọc, không cộng thành100%, không là importance/cause probability.
7. Soft delta dùng cùng ranking `rank-v2.3-bounds`; công bố top/rank changes, coverage/ties/intervals. Không coi trọng số là contribution%, không khẳng định ưu thế từ tie/overlapping intervals. Unsupported soft giữ unknown; thiếu dữ liệu có reason.
8. `POST /v2/what-if/{id}/scenarios/{sid}/proposals` tạo typed proposal có CAS; user review rồi confirm/search bằng flow sẵn có. Bỏ core tạo draft thiếu thông tin theo core policy; mức nới giữ core có thể confirm. Chưa tự confirm/tìm lại. Apply guard current revision, owner và nguồn đang được duyệt; kết quả search sau này đọc dữ liệu mới.

## Bounded execution và kiểm chứng

Default32 **scenario attempts** (max64, bao gồm cặp bị bỏ vì dư thừa), candidate100 (max500), reported rank changes tối đa10 và witnesses tối đa3/scenario. Cặp có `joint_only_candidate_ids` xác định đúng tour chỉ mở khi thay cả hai nhóm. Pure evaluation cache chỉ dùng trong snapshot/time/party bất biến; deadline/cancel/source checks trước publication và recheck freshness sau chờ LLM. Scenarios tham chiếu evidence/snapshots được persisted cùng resource; không sửa Supabase/schema catalog hoặc frontend.

Acceptance: mở tour ngoài pool gốc; same-snapshot baseline; OR/temporal grouping; joint blockers; same-offer; unknown không thành proven expansion/%0; denominator0; budget basis/coverage và exact/from bounds; dates không tự suy lunar; soft rank/ties/unsupported; cap/truncation/exclusions; owner/idempotency/stale revision/atomic apply; NIM citation/source/freshness/cancel; schemas + fixture API smoke + catalog live read-only nếu cấu hình khả dụng.
# Catalog validation

[catalog-validation-v1](../data_access/supabase/catalog-validation-policy.md) cho phép dữ liệu crawler qua kiểm tra tham gia cùng evaluator. “Proven” trong thống kê là đã xác định theo data/policy công bố, không là kiểm chứng độc lập website. Receipt/policy đi cùng snapshot; không tính unknown là fail hoặc đổi kết quả cũ khi trust thay đổi.
