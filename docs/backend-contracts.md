# Backend contracts — bản nháp

**Trạng thái:** Domain v1 đã implement; JSON Schema được xuất ở [contracts](../contracts/README.md). Crawler thật chưa tích hợp; người crawl cần đối chiếu schema với mẫu thật. Ví dụ payload ở [crawler-contract.md](crawler-contract.md), [api-contract.md](api-contract.md); quy tắc hai luồng ở [backend-flows.md](backend-flows.md).

## 1. Yêu cầu người dùng

| Object | Nội dung tối thiểu |
|---|---|
| `RequirementRevision` | `schema_version`, id, revision, mode `discover/compare_urls`, URL targets nếu có, messages/form input, reference timestamps, timezone, party, conditions, hard tree, preferences, unresolved, readiness, policy version |
| `Party` | Số người lớn; trẻ em/infant theo tuổi hoặc age chưa biết. Phân loại tính giá cuối cùng theo chính sách offer; không tự coi trẻ em bằng người lớn |
| `Budget` | Amount/range, currency, basis `per_adult/per_person/group_total`, coverage `tour_price/trip_total`. Coverage không được nói dùng tour_price theo policy đã chốt, ghi system_default; basis/currency chưa rõ vẫn hỏi trước khi lọc |
| `Condition` | id, field, operator, typed value, strength `hard/soft/unresolved`, source references. Chỉ field/operator trong catalog được phép chạy |
| `SourceReference` | Text: message id + quote + span; form: field path + submitted value. Giá trị derived giữ reference gốc và tên normalization rule |
| `Clarification` | id, field path/condition id, reason code, question, suggested options nếu có, blocking flag |
| `Readiness` | Status `ready/needs_clarification/unsupported`, `can_collect_data`, `can_evaluate_hard_constraints`, reasons. URL có thể đối chiếu dữ liệu tĩnh trong khi giá theo nhóm chưa đủ; lỗi model nằm ở error riêng |

Span text theo Unicode code point, end-exclusive, trên nguyên văn đã lưu; frontend cần chuyển đổi nếu dùng index UTF-16. Không ép LLM đếm span: backend đối chiếu quote, yêu cầu rõ occurrence nếu quote lặp.

Hard tree gồm `all`, `any` và predicate references. Ví dụ `all(any(Japan, Korea), depart_HCM, no_transit)` giữ OR của điểm đến. Chuẩn hóa phủ định vào predicate; không nhận biểu thức/code tùy ý. Preference cũng có thể giữ nhóm OR, không tách thành các mong muốn đồng thời.

Wire shape: group `{kind: "all"|"any", children: [...]}`; leaf `{kind: "predicate", condition_id: "c_..."}`. Conditions nằm trong một list với ID duy nhất; mọi reference phải tồn tại, không tạo cycle. OR giữa các field khác nhau vẫn giữ group, không chỉ dùng danh sách điểm đến phẳng.

| Field ban đầu | Value / phép xét | Ghi chú |
|---|---|---|
| `destinations` | Place ids; `contains/contains_any/contains_all/excludes` | Quốc gia, thành phố có cấp/quan hệ; alias không tự đổi nơi chưa chắc chắn |
| `departure_origin` | Place/airport ids; `in/not_in` | Không nhầm nơi xuất phát với điểm đến; địa danh mơ hồ giữ candidates |
| `departure_date` | Date/range; `eq/lt/lte/gt/gte/between` | Lưu flexibility và rule ngày tương đối; không biến thành duration |
| `return_date` | Date/range; `eq/lt/lte/gt/gte/between` | Đánh giá cả ngày về nếu user ràng buộc |
| `duration_days`, `duration_nights` | Positive integer/range; `eq/lte/gte/between` | “5 ngày” không chứng minh “4 đêm” |
| `estimated_cost` | Budget predicate `lt/lte/gt/gte/between` | Đánh giá cùng currency, basis và coverage; giữ inclusive/exclusive |
| `transport` | Allowed modes; `in/not_in` | Dữ liệu thiếu thành unknown |
| `flight_stops` | Count/range; `eq/lte` | “Không transit” khác “không đổi máy bay”; phạm vi chặng đi/về cần rõ |
| `hotel_stars_min` | Integer 1..5; `gte` | Phải có nghĩa/cách công bố theo nguồn; có thể khác theo đêm |
| `shopping_stops` | Count/range; `eq/lte` | Tách điểm bắt buộc/tùy chọn; “ít” chưa có ngưỡng số |
| `included_services` | Service ids; `contains_all/excludes` | Chỉ xét nếu source có scope tour cụ thể |
| `supplier` | Supplier ids; `in/not_in` | Không suy ra uy tín từ tên/domain |

Các ưu tiên như ít đi bộ/nhịp độ nhẹ vẫn lưu nguyên văn với trạng thái `not_evaluable` nếu chưa có field/metric phù hợp. Không biến tuổi của khách thành hạn chế vận động hoặc sở thích chưa được nói. Condition bắt buộc ngoài catalog phải báo `unsupported`, không âm thầm bỏ.

Soft-only operators `prefer_low/prefer_high/near` chỉ dùng trên field số phù hợp, không thành hard filter hoặc trọng số bí mật. “Tầm 30tr” có thể lưu target cho `near`, không tự sinh khoảng ±10%. Một yêu cầu có thể có nhiều budget predicates với basis/coverage khác nhau; không ép vào một budget duy nhất hoặc coi chúng mâu thuẫn khi chưa chứng minh.

`QuerySpec` chứa conditions có kiểu đã resolve, party, hard tree, preferences và capability cần dùng; không đưa câu user nguyên văn cho crawler làm filter. Search planner ghi predicate được đẩy xuống nguồn và predicate phải kiểm tra sau. Unresolved/unsupported requirements giữ ở revision và decision blockers; không dùng chúng để tuyên bố pass. URL acquisition có thể chạy khi hard evaluation còn blocker; discovery không âm thầm bỏ hard condition để tìm rộng.

Thiếu date/budget không luôn là blocker: nếu user không ràng buộc và nguồn cho phép tìm rộng thì giữ unspecified. Thiếu tuổi/rooming có thể cho tìm tour nhưng làm chi phí nhóm chưa tính đủ; readiness cho truy vấn không đồng nghĩa đủ để kết luận tour đạt ngân sách.

## 2. Output crawler và kho dữ liệu

| Object | Nội dung tối thiểu |
|---|---|
| `SourceCapability` | Supplier/domain đã duyệt, search/url modes, supported fields/filter semantics, access status, checked_at |
| `CrawlResult` | Request id, schema version, source statuses, supplier/tour/offer snapshots, evidence, issues; trả partial result khi một nguồn lỗi |
| `Supplier` | Stable id, tên/pháp nhân nếu có; license/review facts có evidence độc lập hoặc ghi rõ tự công bố |
| `TourSnapshot` | Supplier/tour id, canonical URL, snapshot id, itinerary/destinations, origin, duration, transport, lodging, included/excluded services, policies |
| `OfferSnapshot` | Tour/snapshot refs, departure/return dates, price components theo khách/tuổi/room, mandatory surcharges, availability, applicability |
| `SourcedField<T>` | Typed value/raw value, unit/scope, data state, completeness `complete/partial/unknown`, verification, observed_at, evidence ids |
| `Evidence` | id, source URL, publisher, snapshot id/hash, extraction method, JSON pointer/selector hoặc snippet, observed_at; verified_at/method nếu có kiểm tra độc lập |

`data_state`: `present/missing/conflicting/invalid/unsupported`; freshness `fresh/stale/unknown` được backend tính riêng theo policy. `verification`: `supplier_published/independently_verified/unverified`. Ba trục này độc lập: mới lấy không đồng nghĩa đã xác minh.

Null không thay cho 0/false; missing field giữ lý do, không tạo evidence chứng minh. observed_at là thời điểm quan sát, không phải cam kết hiệu lực giá. Nếu không có freshness policy cho field biến động, không gọi dữ liệu đó là fresh.

Completeness là mức bao phủ của field trong scope cụ thể, cần căn cứ từ nguồn/extraction; mặc định unknown. Danh sách chưa đầy đủ có thể chứng minh đã thấy một item, nhưng không chứng minh item không tồn tại. Ví dụ không thấy Tokyo trong itinerary một phần không đủ cho `excludes Tokyo` pass hoặc `contains Tokyo` fail.

Không gộp giá/ngày/chỗ từ các offer khác nhau thành một offer giả. Dedup trong cùng nguồn theo tour id/canonical URL; so sánh giữa nguồn giữ provenance riêng. Giá “từ” giữ price type và điều kiện áp dụng, không chuyển thành exact total.

Đơn vị đánh giá là `Candidate = TourSnapshot + OfferSnapshot cụ thể + Party/CostEstimate của query`. Một tour có nhiều lượt khởi hành được xét từng offer rồi mới nhóm để hiển thị; không kết luận cả tour đạt vì có một offer khác ngày đạt. Tour chưa có offer phù hợp chỉ là ứng viên thiếu dữ liệu, không phải lựa chọn đã đủ bằng chứng.

Tiền VND dùng integer đồng; tiền khác dùng decimal string + currency/scale. Không dùng float hoặc tự đổi tỷ giá. Components tách bắt buộc/tùy chọn/unknown, thuế, visa và phụ thu khi nguồn có công bố.

“Triệu/tr/k” chỉ xác định hệ số, không tự chứng minh currency. Nếu dùng VND mặc định theo ngữ cảnh sản phẩm, phải chốt policy, ghi `system_default` và hiển thị để sửa; chưa có policy thì giữ unresolved. Không lấy giá trung bình cả nhóm để chứng minh trần giá từng người nếu user không định nghĩa như vậy.

Giá cho nhóm có trẻ em cần age brackets và chính sách room/bed phù hợp. `CostEstimate` trả lower/upper bound nếu tính được, basis, coverage, components, evidence, missing reasons; upper bound không xác định thì để null. Không nhân giá người lớn với tổng số người hoặc coi subtotal là tổng giá đầy đủ.

Crawler sở hữu registry/access checks và extraction theo nguồn; backend chỉ nhận dữ liệu qua gateway đã duyệt. URL do user gửi phải kiểm tra scheme, domain, redirect và đích mạng tại lớp fetch; không fetch tùy ý trong parser/API.

Fixtures mô phỏng có `origin=synthetic` hiển thị rõ; evidence của fixtures không được trình bày là nguồn thật. Có thể lưu fixtures nhỏ dạng `.json` vì `.jsonl` đang bị `.gitignore` loại.

## 3. Bộ lọc và kết quả frontend

`ConditionEvaluation`: condition id, `pass/fail/unknown`, actual value hoặc cost bounds, reason code, evidence ids, freshness/verification và policy version.

- ALL: fail nếu có fail; pass khi tất cả pass; còn lại unknown.
- ANY: pass nếu có pass; fail khi tất cả fail; còn lại unknown.
- `eligible`: hard tree pass; `ineligible`: fail; `needs_verification`: unknown. Preference không làm tour bị loại.
- Với budget trần: lower bound vượt trần → fail; upper bound đủ chứng cứ và không vượt trần → pass; khoảng giao nhau hoặc chưa tính đủ → unknown. Data stale/conflicting có thể làm bound không dùng được theo policy.
- Không có hard predicate thì báo rõ không áp dụng điều kiện cứng, không diễn đạt là đã chứng minh mọi nhu cầu.

Khi hard tree rỗng, `filter_applied=false`, candidate `eligibility=null`; bảng dữ liệu/trade-off vẫn có thể hiển thị. Khi requirement còn decision blocker, không có candidate được kết luận eligible; điều kiện liên quan trả unknown với reason từ blocker, không phải false.

`ComparisonResult`: requirement revision, evaluated_at, snapshot/policy versions, coverage theo nguồn, candidates ba nhóm, criterion cells, cost estimates, trade-offs, evidence refs, warnings và empty reason.

Phân biệt không có tour từ nguồn, có tour nhưng fail điều kiện, và chỉ có tour chưa đủ chứng cứ. Có thể đề xuất nới một điều kiện với tác động cụ thể; chỉ đánh giá lại khi user sửa yêu cầu, không tự áp dụng.

Mỗi cell giữ evaluation và data quality riêng. Trade-off chỉ so sánh dữ liệu cùng basis/coverage; không nói A rẻ hơn nếu chỉ có giá “từ” hoặc khác nhóm khách. Không tự kết luận nhà cung cấp đáng tin/không đáng tin từ số link.

Đề xuất ban đầu: biểu diễn ưu/nhược theo từng preference, không gom điểm tổng mặc định. Nếu bổ sung trọng số/Pareto, công khai tiêu chí; unknown/incomparable không tạo kết luận thống trị hoặc xếp hạng giả.

Giải thích đầu tiên từ các evaluation/claim có evidence ids bằng template. LLM diễn đạt là phần tùy chọn sau: không thêm dữ kiện/khuyến nghị không có claim; nếu kiểm tra không đạt thì dùng template. API trả dữ liệu có cấu trúc dù lời diễn đạt lỗi.
