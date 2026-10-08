# Kiểm tra đủ nhu cầu cá nhân hóa — v2

User duyệt implementation 08/10/2026 trên `backend`. Policy `personalized-core-v1`; không sửa frontend hoặc ghi Supabase. Budget form/người lớn là trần bắt buộc, không là ưu tiên.

## Trách nhiệm và contract

`requirements/completeness.py` kiểm tra thông tin sau semantic normalization, độc lập chất lượng dữ liệu tour. Input: requirement v2 đã validate, conditions/trees/party/input_kind và semantic clarifications/issues. Output: `completeness` gồm policy/profile, năm field states (`missing`, `needs_clarification`, `resolved`, `unsupported`), condition/question IDs, reasons và `is_complete`; readiness thêm `can_confirm`, `can_search`.

- Personalized: input text/structured, kể cả có reference URLs. URL-only (`input_kind=urls`, mode=compare_urls) miễn năm field; có URL và vẫn tuân thủ các hard constraints nếu được thêm.
- Năm field: positive destinations, positive departure_origin, departure_date rõ (ngày hoặc bounds), party.adults, hard upper budget (lt/lte/between) với currency/basis/coverage. Số tiền trần phải dương. Budget soft/near/prefer_low hoặc chỉ lower bound không thay trần; không ép strength hoặc tự tạo số tiền.
- Required presence độc lập hard/soft; giữ explicit soft địa danh/ngày. Một predicate phải hiện diện trên mọi nhánh của cây liên quan mới được tính là giới hạn bắt buộc; budget nằm trong OR với một điều kiện khác không đảm bảo trần giá.
- Dữ liệu entity catalog thiếu là trách nhiệm backend, không hỏi người dùng nhắc lại địa danh. Các semantic questions đã có được dùng lại, không tạo câu hỏi ngày/năm trùng. AND/OR, phủ định và các ý định khác giữ nguyên.
- Field states tham chiếu conditions hiện có để FE tự điền, không sao chép hoặc sửa các values. `can_collect_data` là capability/phạm vi acquisition; không là permission tạo comparison. `can_evaluate_hard_constraints` vẫn phản ánh nghĩa của predicates; completeness là business gate riêng.
- `can_confirm` đòi đủ core và không còn blocking semantic issues/questions. `can_search` thêm phạm vi acquisition hợp lệ. Đây là prerequisites; endpoint còn kiểm confirmed revision, pending proposal, CAS/expiry/cancel/source.

## Workflow/API

1. Text được nhận dù thiếu thông tin → NIM → semantic validation → completeness → proposal. Không sửa raw text để tự điền defaults.
2. Structured form đã đầy đủ vẫn tạo confirmed revision 201. Form thiếu/chưa rõ lưu draft + proposal 201, dùng cùng validation; malformed DTO vẫn 422. Không tự confirm một form có nghĩa chưa rõ.
3. Apply sau extraction, typed edit/answers, discard và trước confirm/comparison/worker. Confirm tính lại từ nội dung hiện tại, không tin readiness/clarifications đã lưu. Revision cũ chưa đủ được giữ để xem, nhưng cần proposal bổ sung trước tìm mới.
4. Missing core questions có target `trip.<field>` (adult target `party.adults`) và stable IDs theo requirement/revision/path/reason. `answer_clarification`: adults dùng `{ "adults": 2 }`; các field khác dùng `{ "condition": <FormConditionV2> }`, ID mới, đúng field. Backend thêm vào AND, giữ conditions/tree khác. Sửa predicate hiện có dùng typed edits. Không trộn answer và edit cùng target trong một lượt.
5. Câu trả lời text cho thiếu core dùng extraction operations/party_update đã có; prompt không yêu cầu raw-answer cho các reason chưa được hỗ trợ. Form/answer có cấu trúc không gọi NIM.
   Guard omission áp dụng grammar numeric budget/adults tường minh cả INITIAL và UPDATE trả lời core; vẫn bounded repair, không dùng regex tạo giá trị. Khi UPDATE chỉ đổi giá trị của hard cap, NIM phải giữ strength nếu không có explicit soft cue.
   Generation schema tách semantic answers khỏi operations: chỉ cấp IDs thuộc reason mà RawAnswer hỗ trợ; minItems cho các câu trả lời tường minh kể cả message có budget/party. Operation target chỉ là condition ID, không phải question ID. Loại tour cần raw value có căn cứ; không tạo condition loại tour trống từ từ “tour” chung hoặc gán địa danh catalog đã biết thành loại tour. Guard gom lỗi phân loại/party duplicate vào cùng repair; không âm thầm bỏ/chuyển predicate. Few-shot minh họa cả nhu cầu đủ core và nhu cầu Tết thiếu core, không dùng ví dụ làm defaults.
   Payload NIM thêm reply-target metadata (ID/reason/path/output_location), không tạo giá trị câu trả lời. Mixed-reply few-shot mô tả đủ party/operation/answers; validator vẫn kiểm grounding/CAS và chỉ một repair. Structured answers là đường xác định khi model trả lỗi kỹ thuật, không lấy invalid draft làm confirmed state.
   Guard gom quote/raw-value grounding cùng duplicate/classification/omission trước repair, để sửa nhiều lỗi đồng thời trong giới hạn một lượt; không để lỗi duplicate che lỗi quote của predicate được giữ lại. Exempt zero ngầm shopping/flight giữ policy cũ.
   Guard còn kiểm polarity định tính trước repair và control mức ưu tiên phải có dimension + mức 0–5 tường minh trong quote; “chỉ ưu tiên giá hợp lý” không sinh cost=0. Đây là checks trên extraction, không sinh dữ liệu thay NIM.
6. Error REQUIREMENT_NOT_READY 409 có completeness/readiness/clarifications/issues để frontend hiển thị đúng trách nhiệm. GET catalog công bố yêu cầu sau parse và budget cap semantics. V1 không đổi.

## Retrieval và chất lượng nguồn

Tái sử dụng pipeline hard-before-pool/per-offer và evidence-bound semantic assessment hiện hữu, không viết pipeline thứ hai. Hard fail chỉ loại khi có proof; unknown không trở thành recommendation. Không ghép giá/ngày giữa offers; URL tham khảo vẫn hiển thị. Backend cung cấp audit catalog read-only, có bounds/coverage và các field thiếu proof/qualifiers/freshness để crawler bổ sung; không sinh bằng chứng, đặt TTL, đổi RLS, sửa rows hoặc suy ngày về/số chỗ.

Audit đi qua bounded retrieval không có hard predicates, sample tối đa 100 tours và giới hạn offers hiện hành. Các số đếm chỉ cho sample normalized được công bố; retrieval counters mô tả scan lớn hơn. Source freshness là bootstrap, không đọc registry application đã persisted. Report phân biệt valid supplier proof với fact usable, nêu các field adapter chưa nhận (return_date/tour_type/availability capacity/qualified prices). Không hứa chỉ thêm quote giá là đủ: contract pricing hiện chưa nhận kind/coverage/applicability từ record evidence.

## Nghiệm thu

- Nhật: bốn hard conditions + party.adults=1; form/text normalized tương đương, confirm/search được khi core rõ.
- Tết nguyên bản: đủ ý đã nói, không tự tạo adults/budget/year; hỏi missing party/cap và giữ questions về semantics/year/route. Trả lời đủ → confirm được, không làm mất OR/soft priorities.
- Từng field missing/unresolved/negative-only, soft budget, zero/lower-only/OR-bypassed cap; unsupported catalog không hỏi lại user; remove/downgrade/discard; stale/mixed answers và validation atomic.
- URL-only miễn; hybrid không bypass; legacy revisions/readiness bị stale phải revalidate trước confirm/search/worker. Không network trong offline tests; live NIM/Supabase dùng application DB tạm, tách khỏi tests deterministic.
- Full regression, Ruff, schemas v2/export và v1 giữ nguyên; cập nhật kết quả thực tế và hướng dẫn FE/test sau kiểm chứng.

Kết quả thực tế: [nghiệm thu và giới hạn](backend-personalized-verification.md), [test từng bước](../examples/backend-personalized-v2.md).
# Catalog trust policy hiện hành

[catalog-validation-v1](catalog-validation-policy.md) thay yêu cầu proof website mọi field bằng trust có cấu hình + kiểm tra catalog. Các phần cũ nói unverified/unknown áp dụng cho nguồn chưa opt-in hoặc field không đạt kiểm tra; price qualifiers/freshness vẫn bắt buộc, completeness/readiness của user không đổi.
