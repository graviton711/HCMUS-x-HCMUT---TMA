# Contract semantic requirements v2

Trạng thái: đã implement theo [kế hoạch](archive/requirements-improvement-plan.md), kiểm chứng 08/10/2026. API envelope vẫn `2.0-draft`; `policy_version=requirements-v2.2` phân biệt cách hiểu mới. Payload v1 giữ models riêng; v2 đọc được conditions/value cũ. [Test từng bước](../examples/backend-semantic-v2.md), [kết quả và giới hạn](archive/requirements-evaluation.md).

## Domain, workflow và interface

`RawConditionV2 → normalize_v2 → ConditionV2 → finalize_v2 → RequirementV2/proposal → legacy query adapter → evaluation v2`.

- `domain/semantic.py` cung cấp value/entity/temporal/trace/issue models và invariant, không gọi provider.
- `requirements/catalog.py`: catalog theo type, version `tour-entities-v2.1`, địa danh/vùng/phương tiện/tour type; dùng alias/hierarchy chung cho normalization và decision. Các vùng là phạm vi du lịch, không tuyên bố đơn vị hành chính hiện tại.
- `requirements/temporal.py`: đọc raw date slot có grounding, giữ calendar/group/semantics/year; converter Việt Nam UTC+7 có round-trip validation, chỉ dùng khi đủ thông tin. Wrapper pin `vi-lunaire==2026.4.11` ([package](https://pypi.org/project/vi-lunaire/), [API](https://github.com/erikdao/vilunaire)); giới hạn backend 2000–2099 và kiểm thử fixtures độc lập. Múi giờ ứng dụng giữ riêng khỏi múi giờ của lịch âm Việt Nam.
- `requirements/semantic.py`: normalization, clarification/issue/readiness, targeted answers; output có raw slots và versions, không gọi DB/network.
- `requirements/v2.py`: schema extraction mở rộng, coverage guard và bounded repair hiện có. Guard là kiểm tra tín hiệu rõ, không phải regex thay model hiểu mọi câu.
- `api/v2`: form/edit dùng ConditionV2/ValueV2, giữ proposal CAS và worker cancellation. Field mới persist trong JSON revision/proposal, không cần DDL migration.
- `data_access/v2`: chuyển query sang contract crawler v1 đang dùng; intent mới/scoped/partial chưa pushdown được giữ marker `V2_EVALUATION_ONLY`, không làm hẹp OR. Snapshot v2 mở thêm semantic facts với evidence binding; adapter hiện vẫn nhận payload cũ.
- `decision/semantic.py`: đánh giá value mới rồi delegate legacy evaluator cho giá/number/date cũ. Có three-valued OR/AND, scoped transport, tour type/route/nature; các qualitative metric chưa chốt trả unsupported.

## Value và policy

| Value | Nội dung và rule |
|---|---|
| `entities` | Từng member: raw, entity_type, entity_id nullable, status resolved/catalog_missing; catalog version. Không mất cả nhóm khi một member chưa resolve |
| `temporal` | raw, calendar, day/month/year, holiday/year, leap, group_id, role, semantics, resolved_date nullable, reason; một group nối hai mốc và một câu hỏi năm |
| `qualitative` | concept reputation/service_quality/price_value/nature; giữ intent, không gán score/budget/slider. Nature đánh giá từ taxonomy điểm tham quan có evidence; ba metric còn lại công khai unsupported |
| Legacy values | set/date/number/budget/unresolved vẫn hợp lệ, không tự suy ý mới từ record cũ |

Field mới: `tour_type` in/not_in; `route` contains_any/contains_all/excludes; `supplier_reputation`, `service_quality`, `price_value`, `nature` prefer/requires/excludes. Prefer bắt buộc soft; requires bắt buộc hard; explicit strength mơ hồ cần hỏi. Scope: `main_journey` cho ô tô từ nơi xuất phát, `itinerary` cho route/nature; quote không đủ scope thì giữ chưa rõ.

Chưa có dữ liệu nguồn khác với chưa hỗ trợ metric. Tour type, route, transport có evaluator: confirm nghĩa đã hiểu được, nhưng thiếu fact thì evaluation unknown. Reputation/service/price_value chưa có metric: soft issue không blocking, hard issue blocking và confirm bị chặn; không sinh câu hỏi user đoán dữ kiện.

## Thời gian và answers

- Raw temporal metadata: calendar, semantics, group_id; raw_values giữ các mốc nguyên văn. Không cho model sinh ngày dương từ lịch âm.
- Tet availability: 27/12 âm thuộc năm âm trước holiday_year, mùng 4 thuộc tháng 1 của holiday_year; dùng gte/lte. Exact dates dùng eq; ambiguous interval hỏi semantics.
- Giới hạn ngày mặc định hard; chỉ soft khi user nói rõ ưu tiên cho mốc ngày trong clause tương ứng. “Không bắt buộc khởi hành đúng ngày” làm linh hoạt ngày khởi hành bên trong khoảng, không hạ giới hạn của khoảng thành soft. Normalizer giữ source/rule cho quyết định strength này.
- Không tự lấy năm tương lai từ “năm nay” trong input trích dẫn. Năm explicit/context đã được user trả lời được giữ cùng provenance.
- Mốc ghi rõ “dương/dương lịch” giữ Gregorian ngay cả khi quote nhắc dịp Tết; không dùng từ Tết trong câu để ghi đè calendar đã nói rõ của raw slot.
- Typed edit `answer_clarification`: clarification_id + answer. Năm Tết gửi `{holiday_year:2027}`, năm ngày đơn gửi `{year:2027}`, semantics gửi `{semantics:availability}`; year/semantics áp cả group atomically. Answer có expected revision/proposal version ở request như các edits khác.
- Text answer qua NIM giữ question ID, raw value và quote; chỉ nhận năm/choice đã được grounded; không re-extract mốc cũ từ quote mới. Stale/duplicate/overlapping answers rejected.
- Route-strength answer phải nhắc đúng route đang được hỏi; câu ưu tiên Tây Nguyên không trả lời câu hỏi bắt buộc/ưu tiên cho route miền Trung. Reply chỉ được answers_only khi từng clause có target clarification tương ứng.
- DATE_YEAR_REQUIRED của v1 phải reject lunar quote trước khi ghép dd/mm dương. Đây là correctness guard, không nâng v1 thành lunar parser.

## Clarification, trace và coverage

- `issues`: reason, trách nhiệm user/backend/data, condition IDs, blocking. Catalog miss/metric unsupported là issue, không câu hỏi lặp nội dung đã rõ.
- `clarifications`: year/semantics/strength và các ambiguity thật; dedup theo group. Có scope đã nói nhưng catalog thiếu thì không hỏi lại SEARCH_SCOPE_REQUIRED.
- Readiness: acquisition/evaluation riêng; thêm coverage scope đầy đủ/partial/unavailable. Confirm chặn blocking issue hoặc clarification; chưa thêm action thu thập trước confirm.
- Coverage guard kiểm tra omission của tín hiệu positive rõ: ghép đoàn, route, bốn qualitative intents; provenance/whitelist/negation vẫn được validate. Một quote có thể hỗ trợ nhiều intents. Sau bounded repair còn vi phạm thì job failed với LLM_INVALID_OUTPUT, không tạo draft ready mất ý.
- Resolution trace và semantic versions nằm trong condition/revision; logs chỉ metrics/reason, không dump raw messages/keys. Existing proposal/version/expiry/retention invariants giữ nguyên.

## Snapshots và ranking

- `TourSnapshotV2.semantic_fields` chỉ cho tour_type (string ID), route/nature (list ID/tag); Fact phải có evidence cùng snapshot. Transport dùng field cũ + scope `main_journey`; taxonomy cha cho motor_vehicle gồm car/coach/minibus, không gồm train.
- Không dùng title/slogan làm fact. Nature taxonomy v1: beach/forest/mountain/waterfall/national_park/river/lake/countryside. Predicate nature chỉ nói có điểm thiên nhiên trong lịch trình, không chứng minh chất lượng dịch vụ.
- Fact chỉ nói category cha (ô tô/vùng/quốc gia) không chứng minh hoặc phủ định subtype/con cụ thể. Nếu target chỉ có thể nằm trong category đó thì unknown, không fail giả vì thiếu granularity.
- Fact có ID ngoài catalog/hierarchy được giữ nhưng không dùng để chứng minh non-match; trả unknown/ENTITY_FACT_CATALOG_MISSING khi quan hệ chưa biết có thể ảnh hưởng kết luận. Match trực tiếp đã có vẫn có thể chứng minh pass. Value tour_type sai type phải thành validation error.
- Unknown soft utility giữ null. Score tính trên phần có dữ liệu và công khai coverage; nếu không có metric nào thì score null. Không biến metric thiếu thành 0 điểm.
- Crawled payload cũ vẫn dùng được; semantic facts thật cần crawler bổ sung theo schema v2. Fixtures mới ghi rõ synthetic.

## Kiểm chứng và release

Offline gold kiểm tra normalization/resolver/temporal boundary/round-trip/year answer/coverage/OR partial/scope/unsupported soft-hard/proposal edits/stale answers/query adapter/evidence binding/ranking unknown và v1 regressions; API tests dùng DB tạm. Live evaluation v2 dùng model hiện có, ca Tết + paraphrases/repeats, ghi từng semantic assertion và repair/latency; runner không dùng DB.

Live runner `evaluate-nim-v2` không cần DB: parse trực tiếp bằng cùng v2 hooks, dùng text fixture và optional patch. Quote qualitative phải chứa tín hiệu đúng concept; phủ định/“không cần” không được biến thành positive preference bằng cách cắt quote. Answers và operations đụng cùng condition/group trong một lượt phải reject. Export thêm `contracts/v2/CrawlResultV2.schema.json`; crawler v1 vẫn giữ payload cũ.

Extraction schema v2 phân nhánh condition theo field với enum operator riêng; schema thể hiện ràng buộc cho provider và validators kiểm tra lại. Chưa khẳng định hosted provider enforce mọi schema keyword. Đây là kết quả kiểm chứng live: enum operator chung cho mọi field cho phép nhiều output sai dù JSON hợp lệ. Prompt v2 độc lập để tránh whitelist/unsupported policy v1 xung đột.

Bounded repair có feedback cụ thể cho quote không khớp/không unique và IDs tree lệch; không nới grounding hoặc tự sửa quote/logic của model. Những chẩn đoán chứa quote chỉ dùng trong request repair nội bộ; API lỗi giữ thông báo chung.

Route strength chưa rõ được chuẩn hóa unresolved; hard/soft chỉ khi quote/context clause có cue rõ. Scope route tự gắn itinerary theo nghĩa field. Coverage với UPDATE kiểm tra năm/semantics/route-strength đã được trả lời rõ; thiếu answer đúng question ID sẽ repair thay vì thành công với câu hỏi còn nguyên.

Với một khoảng Tết literal dd/mm âm → mùng N Tết đã grounded, resolver xác định grouping và semantics từ cue người dùng: availability khi rõ khoảng có thể đi, exact khi rõ ngày cố định, còn lại ambiguous. Metadata model không được tự ép exact. Lưu thêm source/rule của derivation; không dùng quy tắc này để trích dates bị thiếu. System prompt v2 mô tả shape gọn, response_format vẫn gửi schema đầy đủ để tránh lặp hàng chục định nghĩa condition trong prompt.

INITIAL và UPDATE dùng phần chỉ dẫn lượt riêng: INITIAL không chứa mẫu UPDATE conditions=[]; UPDATE có IDs/clarifications từ previous và không chứa mẫu phát lại điều kiện ban đầu. Repair giữ cùng chế độ ban đầu, không biến thành lượt sửa nhu cầu.

Coverage manifest gửi các tín hiệu rõ cùng quote nguyên văn và polarity cho NIM (không tạo conditions thay model); INITIAL có tín hiệu positive không được output conditions rỗng. Qualitative strength/operator do policy normalization xác định từ cue của concept trong clause/context, giữ source/rule. “Giá phải chăng” không phải từ “phải” bắt buộc. Không suy số điểm/tiền từ manifest.

Entity scope origin/destination/transport/tour_type áp default hard; soft cần cue ưu tiên/thích/nếu được trong clause của entity. Resolver lưu provenance cho default/context, không để model tự hạ nhu cầu tìm tour thành ưu tiên. Unsupported departure_window dạng lunar metadata được báo backend issue; Gregorian window có thể dùng DateValue/between. Enum temporal reserved không phải cam kết hỗ trợ mọi interval grammar.

Provider schema v2 thêm enum grounded quote theo từng qualitative/tour-type/route field và date clauses có mốc ngày (câu/clause/tín hiệu unique đúng concept), schema name riêng initial/update, và minItems theo số field positive đã kiểm chứng ở INITIAL. Entity/budget giữ quote nguyên văn tự chọn để chứa đủ raw slots; enum dùng chung mọi field đã làm model chọn quote thiếu raw slot, nên không dùng hướng đó. Đây là generation guard, không thay canonical DTO hoặc backend quote validator; schema export vẫn là contract tổng quát, không enum theo một người dùng. Không tạo quote bằng fuzzy match hoặc sửa casing sau response.

Một repair v2 gửi kèm draft bị lỗi (bounded 24 KB) và feedback, đánh dấu draft là dữ liệu, giữ mode INITIAL/UPDATE. Model sửa draft có đủ context thay vì tạo lại từ lỗi đơn lẻ rồi mất conditions khác. Không gửi reasoning hoặc log raw upstream. Normalization batch gom lỗi của các conditions trước repair, không giảm validator để lấy pass.

Reply chỉ gồm các grammar năm Tết/khoảng có thể đi/route-strength cho clarification hiện có được gắn `answers_only`: generation schema cấm operations, answers chỉ nhận IDs có thật. Không trích lại dates từ câu cũ. Reply có yêu cầu thêm/sửa khác vẫn dùng UPDATE đầy đủ; grammar này là guard, không fallback tạo answer thay model.

Generation schema và payload công bố các clarification IDs cần trả lời khi grammar rõ; minItems bằng số targets đó cho answers_only. Backend kiểm tra lại từng target/quote/value. Live report phân biệt lỗi lượt initial với patch để không gộp lỗi multi-turn thành lỗi extraction ban đầu.

Live Supabase smoke phát hiện INITIAL có ngân sách/số người rõ nhưng model lặp date condition thay các slot này. Coverage guard bổ sung grammar hẹp cho numeric budget và số người lớn tường minh, đồng thời từ chối predicates trùng field/operator/strength/scope/raw values dù IDs khác. Guard chỉ yêu cầu model repair toàn bộ output một lần, không tạo budget/party bằng regex và không âm thầm dedup. Budget định tính/negated vẫn không bị ép thành số. Prompt có ví dụ budget + party + ngày dương để tránh chỉ học mẫu Tết.
