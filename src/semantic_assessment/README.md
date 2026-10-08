# Semantic assessment

`what_if.py` là lớp diễn giải cuối theo [policy](../../docs/what-if-analysis.md): NIM chỉ chọn insight IDs do backend tính và render; không tự sinh số hoặc yêu cầu mới. Dùng fallback khi model lỗi/timeout/không cấu hình. Analysis đánh giá soft trên union hard-pass có giới hạn một lần, giữ binding/verification và refresh trước publish.

Trách nhiệm: đọc pool và snapshot văn bản, đánh giá mức hỗ trợ của nội dung với soft condition; không quyết định eligibility hoặc tính giá. Input confirmed requirement, prepared candidates và immutable CrawlResultV2. Output assessment có criterion/candidate/snapshot/citation binding, model/policy và trạng thái partial/skipped.

Workflow: chuẩn bị excerpts bounded → NIM JSON schema → schema/exact quote/binding/completeness validation → một repair nếu cần → lưu assessment trong comparison. Không nâng verification của crawler facts. Source unverified chỉ được hiển thị diễn giải, không cộng utility. Chưa chấm uy tín/dịch vụ tốt/đáng tiền từ quảng cáo. Timeout/error không phá structured result; job/source publication guards vẫn do API quản lý.

Giới hạn input tính trên JSON pairs + excerpts đã serialize. Nếu quá budget, thu ngắn excerpts và đánh dấu incomplete; khi không còn chỗ mới bỏ pair cuối. `limited` công khai phạm vi thiếu. Raw quotes của nguồn chỉ giữ nội bộ để kiểm citation, không gửi lặp vào NIM.

`decision/candidates.py` chuẩn bị pool; `service.py` điều phối; `gateway.py` gọi NIM; `models.py` định nghĩa JSON contract. Chi tiết: [retrieval-semantic-ranking](../../docs/retrieval-semantic-ranking.md).
# Catalog excerpts

[Policy](../../docs/catalog-validation-policy.md): nội dung nguyên văn đã làm sạch trong catalog_validated có thể hỗ trợ matched bằng quote đúng snapshot sau hard filter. Receipt giữ nguồn/binding; text completeness unknown không dùng absence làm not_matched. Không sinh đánh giá uy tín/chất lượng từ lời quảng cáo.
