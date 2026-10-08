# Cải thiện extraction nhu cầu tour

Trạng thái: đã implement phạm vi semantic v2 trên `feature/minh-phu`, kiểm chứng ngày 08/10/2026. Baseline và input ở [ca Tết](requirements-case-tet.md), gold rộng/kết quả ở [requirements-evaluation](requirements-evaluation.md). Contract ở [semantic runtime](requirements-semantics.md), [hướng dẫn test](../examples/backend-semantic-v2.md).

## Những điểm user đã chốt

- 27/12 âm → mùng 4 Tết là khoảng có thể đi, không ép ngày khởi hành/kết thúc chính xác.
- Uy tín, dịch vụ tốt, giá hợp lý, gần thiên nhiên mặc định là ưu tiên mềm. Nếu user nói rõ bắt buộc thì xử lý hard; nếu câu có mâu thuẫn về strength thì hỏi đúng ý đó.
- Coverage tiền mặc định là giá tour, không tự tạo số tiền từ “giá hợp lý”.
- Chưa chốt năm Tết, nghĩa bắt buộc của hành trình dọc miền Trung hoặc nguồn/metric đánh giá các ưu tiên định tính.

## Nguyên nhân baseline trước thay đổi

| Phần hiện tại | Giới hạn |
|---|---|
| `requirements/extraction.py` | Schema có field `unsupported` nhưng chưa có tour type, route, qualitative intent riêng; prompt nhấn giữ unsupported hard, chưa kiểm tra đủ ý định tính |
| `requirements/normalize.py` | Alias địa danh/phương tiện dùng chung dictionary nhỏ; một entity lạ làm mất SetValue của cả nhóm; unresolved giữ quote, không giữ trạng thái từng raw slot |
| `date_value()` | Hiểu ISO, dd/mm/yyyy và tháng nay/sau; chưa giữ calendar, mốc lễ hoặc ý nghĩa available window |
| `requirements/service.py` | UNKNOWN_ENTITY sinh câu hỏi chung; scope chỉ xét SetValue đã resolve, dẫn đến hỏi lại điểm đến; câu hỏi năm theo regex trên quote nên lặp cả hai ngày |
| `requirements/edits.py:answer_edits()` (v1) | Trả lời DATE_YEAR_REQUIRED ghép trực tiếp dd/mm thành ngày dương; không được tái dùng cho lunar input chưa phân biệt calendar |
| `domain/requirements.py`, `domain/crawl.py` | Whitelist/value types/validator snapshot hiện chưa hỗ trợ các field mới; thêm prompt hoặc thêm FIELDS riêng lẻ chưa đủ |
| API v2 | Typed edits dùng Value/FormCondition chung; confirm chặn blocking clarifications; mọi thay đổi readiness phải xét cùng các gate này |

## Phương án đề xuất

| Hướng | Gain | Cost/rủi ro | Phù hợp pipeline và dài hạn |
|---|---|---|---|
| Bổ sung prompt + vài alias | Sửa được một số ca quen thuộc | Thấp; vẫn thiếu calendar/intents, chưa bắt silent drop | Bước nhỏ hữu ích, chưa đủ tiêu chí hoàn thành |
| Để NIM trả luôn ID chuẩn/ngày dương/điểm uy tín | Output có vẻ hoàn chỉnh | Khó kiểm chứng ID, calendar và scores; dễ có false-ready | Không chọn làm nguồn chuẩn cho giá trị quyết định |
| NIM trích ý có cấu trúc + resolver/validator xác định + kiểm tra coverage | Giữ đủ nhu cầu, debug theo bước, replay được, kiểm tra semantics | Vừa; cần mở contract và fixtures qua các module | Đề xuất chọn; tận dụng proposal/worker/evidence đang có |

Không cần đổi model, fine-tune, vector database hoặc gọi model thứ hai mặc định để giải quyết các lỗi đã thấy. Chỉ đo thêm những lựa chọn đó khi baseline mới còn lỗi cụ thể.

## Pipeline và trách nhiệm

`Text + context → grounded semantic draft → entity/temporal resolution → coverage + validation → proposal/clarifications → confirm → QuerySpec → snapshots → hard evaluation + soft ranking`

1. **Extraction:** NIM giữ raw slots, quote/span, quan hệ, strength, scope và intent category; không tạo ID ngoài catalog, quy đổi lịch hay metric. Intent draft tách khỏi điều kiện đã dùng được cho search.
2. **Resolution:** lookup catalog theo loại entity; temporal resolver phân biệt lịch/holiday/year/window. Giữ riêng giá trị gốc, giá trị chuẩn, rule/version và lý do chưa resolve.
3. **Coverage/validation:** kiểm tra hình dạng, grounding, field/operator, omission, mâu thuẫn và capability; không coi JSON đúng schema là hiểu đủ.
4. **Proposal:** hiện cả nhu cầu đã hiểu, điều cần hỏi user và giới hạn backend/nguồn dữ liệu. Answer có target + revision/version; không làm mất nhu cầu khác.
5. **Query/snapshots:** chỉ compile prefilter có nghĩa đã xác định; capability nguồn công khai. Catalog và taxonomy đồng bộ với crawler qua adapter; snapshot mới có evidence/state/observed_at.
6. **Decision:** đánh giá đúng hard tree và offer cụ thể; soft contribution chỉ từ metric có evidence/policy. Unknown không thành pass hoặc số 0.

## Thiết kế tối thiểu cần đủ sức xử lý

### Entity và quan hệ

- Catalog có version, type, aliases và quan hệ vùng/địa danh; lookup origin/destination khác transport/service/supplier. Không cho alias khác loại khớp nhầm.
- Giữ trạng thái từng thành viên của contains_any/contains_all; không bỏ Tây Nguyên hoặc làm mất Đà Nẵng vì một nhánh chưa resolve.
- OR: nhánh đã chứng minh pass đủ để predicate OR pass; tất cả nhánh chứng minh fail mới fail; còn khả năng ở nhánh chưa rõ thì unknown. AND: một fail đủ fail, mọi nhánh pass mới pass.
- Resolver không suy thành phố cụ thể cho một vùng. Fuzzy/LLM candidates chỉ là gợi ý cho entity mơ hồ, không tự coi là ID đã xác nhận.
- “Xe ô tô” giữ loại rộng và phạm vi di chuyển; không tự chọn coach/số chỗ. Tour có chuyến bay chính và xe đưa đón không được mặc nhiên đáp ứng ý đi ô tô từ Hải Phòng.
- Route/corridor và ghép đoàn là intents riêng, không giấu trong quote transport/destination. Route có scope và strength cần review khi câu chưa rõ bắt buộc.

### Thời gian

- Temporal intent giữ calendar (Gregorian/Vietnamese lunar), anchor holiday/year, hai mốc riêng và semantics: availability / exact departure-return / departure window / unresolved.
- Ca đã làm rõ: mốc đầu 27 tháng 12 âm trước Tết; mốc cuối mùng 4 tháng 1 âm của Tết đã chọn. Năm Tết và năm âm của mốc đầu là hai thông tin liên quan, không gán cùng năm cho cả hai.
- Chỉ chuyển sang ISO bằng converter có kiểm thử khi đủ year/calendar; lưu timezone, nguồn/context và converter version để replay. Test biên năm, tháng nhuận, ngày không tồn tại và đối chiếu fixture độc lập.
- Với câu gốc mơ hồ, hỏi một câu về ý nghĩa khoảng; với câu đã làm rõ dùng gte/lte. “Trước” và “không muộn hơn” giữ biên khác nhau. Không suy duration từ độ dài availability.
- Hỏi năm Tết một lần, answer gắn interval ID và cập nhật cả hai mốc; reject stale answer. Calendar chưa resolve không được đi qua handler dd/mm dương, kể cả khi user bổ sung năm.

### Nhu cầu định tính và coverage

- Mỗi ý cần được giữ dưới dạng intent có ID, quote và trạng thái hỗ trợ: reputation, service_quality, price_value, nature, group_tour, route (tên field còn là đề xuất).
- Phân biệt ba trục: user muốn gì/strength; đã chuẩn hóa nghĩa chưa; có capability/evidence để đánh giá chưa. “Đã hiểu uy tín” không đồng nghĩa đã xác minh nhà cung cấp.
- Ưu tiên chưa có metric được giữ và hiển thị chưa đánh giá; không chặn confirm/search chỉ vì soft metric thiếu. Hard unsupported vẫn chặn tuyên bố đáp ứng.
- Giá hợp lý không tạo budget cap, mức cost 0–5 hoặc đồng nhất với rẻ nhất. Chưa có policy value-for-money thì giữ qualitative intent, không tự dùng giá làm điểm đáp ứng ý này.
- Nature có thể đánh giá theo điểm/hành trình gắn evidence + taxonomy được review; reputation/service cần policy và nguồn bằng chứng phù hợp. Không lấy slogan/tên tour làm chứng minh.
- Coverage check phân loại các mệnh đề có nhu cầu thành represented / ambiguity / unsupported / non-requirement. Cho phép một quote hỗ trợ nhiều intents; không ép lời chào thành điều kiện.
- Kết hợp schema completeness + rules cho tín hiệu quan trọng với tập gold/manual audit. Một lượt LLM tự audit không bảo đảm hết omission; không hứa kiểm tra đầy đủ mọi câu tự nhiên.
- Khi phát hiện omission có căn cứ, repair có feedback cụ thể tối đa theo budget hiện có; vẫn thiếu thì trả partial/issue rõ, không silently ready.

### Clarification và readiness

- User ambiguity (năm/ý nghĩa khoảng/địa danh đa nghĩa): hỏi đúng phần thiếu, có target và lựa chọn phù hợp.
- Catalog miss/backend unsupported: giữ intent, hiển thị giới hạn; không bắt user nói lại địa danh đã rõ. Data missing: báo thiếu evidence của nhà cung cấp, không hỏi user đoán.
- Dedup câu hỏi chung year/calendar/interval, ưu tiên blocker ảnh hưởng hành động. Không sinh SEARCH_SCOPE_REQUIRED khi scope đã được nói nhưng resolver chưa hỗ trợ.
- Giữ readiness acquisition khác hard evaluation, soft coverage khác hai trạng thái trên. Search một phần nếu được mở phải công khai phạm vi chưa bao phủ; không tự hẹp OR mà gọi là kết quả đầy đủ.
- Giữ flow proposal → confirm → comparison. Luồng collect một phần khi hard chưa rõ là mở rộng cần chốt API/gate riêng; đổi hai flags không đủ để vượt confirm hiện có.

## Interface, storage và tương thích

- `domain`/API v2: semantic draft, typed entity alternatives, temporal intent, qualitative intents/issue records; cập nhật schema, typed form/edit, proposal diff và clarification answer cùng nhau.
- `requirements`: gateway prompt version mới, resolvers, coverage/finalize và targeted updates. Input/output từng bước có thể replay bằng fixture.
- `data_access`: QuerySpec mapping, source capabilities và crawler adapter/taxonomy. `decision`: field evaluators + hierarchy/scope + unknown/coverage-aware rank.
- Persist draft/resolution trace theo proposal/revision với policy/catalog/prompt/converter version, lý do lỗi, latency/repair; không thêm kho vector. Raw messages tuân retention hiện có, không dump ra logs/API debug công khai.
- DTO v2 mới cần version/compatibility rule rõ; nhiều types hiện dùng chung v1. Giữ v1 payload ổn định bằng adapter/versioned models và regression tests; đọc được stored proposal/revision cũ trước khi rollout.
- Crawler chưa có mẫu không chặn work contract/fixture. Những metric chưa có evidence thật vẫn được công khai unsupported; không tạo dữ liệu đánh giá giả.

## Thứ tự thực hiện đề xuất

1. Chốt semantic contract + gold ca Tết/biến thể và policy đã thống nhất; ghi baseline, ưu tiên test ngăn lunar → solar sai.
2. Catalog/resolver theo type, partial alternatives và trace; xuyên tới QuerySpec/snapshot/evaluator bằng fixtures, không dừng ở output parser.
3. Intent representation/coverage cho ghép đoàn, route và qualitative soft; unsupported path có nghĩa rõ, chưa ép phải có metric cho mọi ý.
4. Temporal representation/converter/targeted year-window answers; kiểm tra original ambiguity và clarified gte/lte, Gregorian/lunar tách biệt.
5. Clarification/readiness đồng bộ proposal/confirm/actions; adapter/schema/storage compatibility và regression v1/v2.
6. Live NIM evaluation v2 riêng, held-out paraphrases + nhiều lượt, đo semantic assertions/repair/latency; sau đó demo end-to-end bằng snapshot fixtures và dữ liệu crawler thật khi có.

## Tiêu chí đạt

- Origin/OR/transport/group tour/route và bốn soft intents không bị mất; những ý chưa rõ hiện đúng trạng thái và trách nhiệm.
- Không invent budget/party/vehicle subtype/year/ngày dương; year answer không biến lịch âm thành dương giả.
- Original date interval được hỏi đúng semantics; clarified input có gte/lte; xác nhận năm cập nhật đúng hai mốc và không đổi nhu cầu khác.
- No false-ready cho hard uncertainty; unsupported soft không loại tour; thiếu evidence không thành điểm 0 hoặc chứng minh pass.
- Gold tests tách extraction → normalization → clarification/patch → query/evaluation; test OR/AND/negation, thiếu một nhánh, mô tả không phải yêu cầu, contradiction và stale revision.
- Kết quả hai response giữ làm baseline ca cụ thể, không phải accuracy tổng quát. Smoke v2 riêng đã chạy; bộ 50+15 và nguồn crawler thật còn cần nghiệm thu tiếp.

## Kết quả implementation

Đã nối contract/entity catalog/temporal resolver/coverage/targeted answers qua API, persistence, crawler adapter và evaluation/ranking. NIM vẫn dùng model và `.env` hiện có; v1 giữ contract riêng. Các metrics reputation/service/value-for-money chưa có nguồn được giữ unsupported thay vì tạo điểm; nature có evaluator theo tags itinerary có evidence. Chưa nối crawler thật, chưa mở collect trước confirm, chưa nâng database hoặc frontend.
