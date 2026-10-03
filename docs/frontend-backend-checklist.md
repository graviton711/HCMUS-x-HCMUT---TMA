# Checklist thống nhất frontend–backend

**Trạng thái:** Đã đối chiếu code backend `0b7e59f` ngày 03/10/2026. Giữ đủ C1–C11 của planning cũ; phần chưa đáp ứng vẫn cần FE + BE trao đổi. “Đã có” chỉ xác nhận code hiện tại, không đồng nghĩa đã nghiệm thu UI hoặc dữ liệu tour thật.
**Owner:** FE + BE cùng review; BE xác nhận dữ liệu/khả năng xử lý, FE xác nhận đủ để thực hiện [flow](frontend-flows.md).

Nguồn chuẩn: [HTTP contract v1](api-contract.md), [domain contract](backend-contracts.md), [schemas](../contracts/README.md). Hướng tích hợp theo code: [frontend-api-integration.md](frontend-api-integration.md). [Data contract cũ](data-contract.md) giữ field/yêu cầu tham khảo, API `/api/compare` không phải runtime. [Đối chiếu crawler](frontend-crawler-integration.md) ghi code đã merge và D1–D5 chưa nối; mọi gap dưới đây vẫn giữ.

## Contract hiện có

- Session ẩn danh + Bearer token; requirement có revision, form/text hai mode, typed clarification/edits.
- Comparison bất đồng bộ; GET job/result, cancel, idempotency; stable target/offer/evidence references.
- Điều kiện hard/soft, cây AND/OR, pass/fail/unknown, eligible/ineligible/needs_verification; không dùng điểm AI mặc định.
- Fact có data_state/verification/completeness/observed_at/evidence_ids; evidence endpoint có raw quote và snapshot binding.
- Mẫu input, JSON Schema request/domain và tests đã có. Tourcrawl CLI/profile và scripts đã merge; chưa có adapter/HTTP exchange tương thích vào backend. Public response chưa schema hóa đầy đủ; API tour data mặc định vẫn synthetic.

## Các quyết định cần chốt

| ID | Đã có trong backend | Còn cần chốt / bổ sung và ảnh hưởng UI |
|---|---|---|
| C1 — Criteria | Typed conditions/party/value, hard/soft, all/any trees; VND integer, ngoại tệ decimal string; basis/coverage; ngày/range, provenance/default rõ | **Một phần:** catalog canonical ID + nhãn/operator cho form (G4); map ± ngày; không ép ngày/budget/party bắt buộc. Whitelist edits chưa sửa grouping trực tiếp (G7). FE + BE chốt field và validation từng control. |
| C2 — Hai đầu vào | `/v1/requirements` chung cho discover/compare_urls; text → parse job, form → revision; GET/PATCH/answers; URL 2–5 và nhu cầu tùy chọn | **Đã có API, chờ review flow:** wireframe chọn cả text/form; chốt cách sửa/xác nhận và câu hỏi scope dùng edits. Dựa can_collect_data thay vì chặn mọi clarification. Không còn task “thiết kế API nhu cầu từ đầu”. |
| C3 — Lọc/cá nhân hóa | Criteria của lần chạy, evaluations pass/fail/unknown, groups, blockers, empty_reason; trade-off có candidate/field/evidence refs | **Một phần:** trade-off hiện chỉ soft NumberValue; chưa có giá/chính sách như ví dụ wireframe (G3). Chốt sorting minh bạch, số candidate discovery và trường hợp filter_applied=false; không thêm score/trọng số không có contract. |
| C4 — Lifecycle | Job parse/comparison, bốn terminal statuses, deadline/cancel, revision/idempotency; ownership/session | **Có cơ chế:** chốt FE polling/backoff, xử lý 401/404, local/demo hosting TTL và restore (G6). Source progress chỉ có cuối job; không % giả. Chốt token storage và retry theo action, không refetch tự crawl. |
| C5 — IDs/reference | Stable requirement/condition/child/target IDs; candidate + tour/offer snapshot IDs, evidence IDs; URL giữ thứ tự; selection/reuse kiểm tra binding | **Một phần:** canonical URL/tên tour/supplier không đủ trong public result (G2); exact duplicate mới bị chặn, canonical dedup cần thống nhất. Chốt order offers/cột discovery; offer picker URL đã có, discovery dùng candidate từng offer. Revision cũ chưa đọc đầy đủ qua API (G6). |
| C6 — Giá/nhóm | Nội bộ có PriceQuote exact/from/range, đơn vị/currency, tuổi, ExtraCharge/pricing_complete; CostEstimate bounds/components/reasons cho Budget; unknown khi thiếu dữ liệu | **Chặn hàng giá:** URL-only không Budget chưa trả public price/cost. Candidate/offer options thiếu price_quotes/extra_charges/pricing_complete (G1). BE cần trả dữ liệu giá độc lập điều kiện ngân sách; chốt contact/missing, coverage/currency, rooming/phụ thu và tổng nhóm. FE không tự tính thay BE. |
| C7 — Evidence | `/v1/evidence/{id}` raw_quote/url/publisher ID/method/locator/observed_at/snapshot; Fact raw_value/evidence_ids, conflicting + verification enums | **Một phần:** publisher display_name/binding tour thiếu public (G2), chính sách/raw nội dung thiếu (G3). Chốt UI nhiều evidence/mâu thuẫn/quote rỗng và giới hạn hiển thị; enum independently_verified chưa chứng minh có nguồn xác minh thật. |
| C8 — Freshness | SourceCapability TTL theo field; engine dùng timestamp/policy; evaluation data_quality có freshness cho Fact; selection cũ bị từ chối | **Một phần:** không có freshness trên mọi cell; Budget data_quality rỗng (G5). Chốt BE trả quality đầy đủ hay policy FE dùng có version; kiểm tra TTL nguồn thật/cache/refresh. Timestamp không thay thế xác minh. |
| C9 — Lỗi/kết quả thiếu | Error code/message/retryable/trace_id/details; 422 fields path/type; source statuses/issues; partial vs unknown vs failed; NO_SUPPORTED_TARGETS khác NO_CANDIDATES | **Có nền:** BE hoàn thiện danh mục code HTTP/job/source + retry; FE map microcopy/field_path từ details.fields. Bao phủ expired session/resource, stale answer/revision/offer, 413/429, model timeout, ALL_INELIGIBLE/ONLY_UNVERIFIED. |
| C10 — Schema | Generated request/domain JSON Schema version 1.0; business rules Python; GET comparison envelope và các keys đọc được từ code | **Chưa đủ:** response session/accepted-job/requirement revision 0/status/job/comparison/evaluation/trade-off/error/evidence chưa có bộ public typed schema đầy đủ (G8). OpenAPI routes chưa khai báo response_model; không sinh full client an toàn chỉ từ schema request. Chốt null/optional/unknown enums/version tương thích. |
| C11 — JSON mẫu | Hai JSON input tại examples; fixture và tests API/decision có scenario thành công/lỗi/clarification/reuse/cancel | **Một phần:** cần bộ response JSON snapshots theo từng scenario + expected UI và schema validate; tests Python không thay fixture FE. Thêm URL-only thiếu hard/budget, nhiều offer, revision cũ, còn dữ liệu sau lỗi và crawler thật. |

## Khoảng thiếu giữ lại để trao đổi với backend

Không bỏ hàng/tính năng trong wireframe chỉ vì backend hiện chưa trả field. Các mục sau là **yêu cầu đề nghị bổ sung**, chưa phải tên field/endpoint mới đã chốt.

| Gap | BE cần cung cấp / quyết định | Task phụ thuộc | Owner |
|---|---|---|---|
| G1 — Giá public | Giá có nguồn của từng offer, scope/đơn vị/coverage, phụ thu/completeness và cost estimate khi đủ input, kể cả không có Budget. Null/missing/contact rõ; không trả một “giá cuối” thiếu căn cứ | C6, P1.4, P3.4, P4.4, P5.3 | BE pricing + FE |
| G2 — Nhận diện tour/nguồn | Tên tour, supplier ID + display_name, canonical URL trong public result; display label cho publisher. Discovery hiện targets rỗng, candidates không có canonical_url; đường mở nhà cung cấp chưa đầy đủ | C5/C7/C10, P3.4, P4.2–P4.3 | BE DTO + FE |
| G3 — Nội dung/trade-off | Dịch vụ bao gồm/không bao gồm, điều khoản, hủy/phụ thu, lịch trình mô tả có evidence; đối chiếu giá/chính sách. included_services set chưa thay nội dung điều khoản; không tạo điểm uy tín/rủi ro nếu thiếu nguồn | C3/C7, P3.4–P3.5, P5.3 | BE domain/crawler + FE |
| G4 — Catalog form | Bảng canonical IDs–nhãn–aliases–operator–unit/default/range có version cho điểm đến/đi/nhà cung cấp/transport/services; có thể là contract file chung hoặc API, chốt cùng BE | C1, P1.2, P2.4, P4.3 | FE + BE requirements |
| G5 — Quality/freshness | Metadata đủ cho từng ô, đặc biệt giá và field không nằm trong điều kiện; TTL/refresh policy nguồn thật. Không đổi observed_at thành một badge freshness chung | C8, P3.5, P5.3 | BE decision/crawler + FE |
| G6 — Revision/restore | Cách lấy input/party/trees đúng revision của comparison cũ; token/resource/job persistence, hết hạn và back/refresh. BE có revision nội bộ nhưng GET requirement chỉ current; chưa có history/list | C4/C5, P1.6, P2.3, P5.4 | FE + BE runtime |
| G7 — Sửa nhóm điều kiện | Quyết định UI sửa AND/OR thế nào khi PATCH chưa hỗ trợ grouping. Giữ cây đã hiểu, không làm phẳng; tạo requirement mới hoặc mở rộng typed edits phải chốt cùng BE | C1/C2, P1.1, P4.3 | FE + BE requirements |
| G8 — Public schema | Model/JSON Schema/OpenAPI cho mọi response branch và error + snapshots; sinh types/validation chung, giữ invariant reference ngoài JSON Schema | C10/C11, P1.4–P1.5, P2.4, P4.6 | BE API + FE |

Ưu tiên trao đổi G1/G2/G8 trước vì ảnh hưởng trực tiếp bảng so sánh và API boundary. G3–G7 tiếp tục giữ trong plan; crawler/nguồn tour thật vẫn là phụ thuộc P5.2, không coi fixture là nghiệm thu dữ liệu thật.

**Sau khi đọc hai nhánh crawler:** có đường lấy title/price/itinerary/notes, nhưng output chưa typed, chưa binding offer/evidence và chưa vào public result. Do đó G1–G3/G5/G8 chưa đóng. Backend (Minh Khôi) + crawler/data (Thái Sơn) cần giải quyết D1–D5; frontend (Minh Phú) review giá trị/nhãn/trạng thái trên response snapshots. D3 phải thống nhất availability vì CSV dùng string và suy từ lịch trong khi domain BE hiện nhận số; D4 không đổi crawler `verified` thành “xác minh độc lập”.

## Checklist review contract

- [ ] C1–C3 được thống nhất: mỗi field UI có nơi gửi/nhận và cách xử lý khi chưa biết.
- [ ] C4 job đã có; FE + BE thống nhất polling/retry/restore và cấu hình hosting dựa trên deadline thực tế.
- [ ] C5–C8 đủ để xác định đúng offer, giá, evidence và độ mới ở từng ô.
- [ ] C9–C10 có bảng HTTP/business status và schema không mâu thuẫn.
- [ ] C11 có JSON thật hoặc mô phỏng ghi rõ, expected state và kết quả validate.
- [ ] Có bộ schema **public response + request** cùng ví dụ; FE sinh type từ nguồn đó và chọn validation runtime tương thích, không lấy CrawlResult nội bộ làm DTO frontend.
- [ ] Chốt API base URL/local/demo, CORS, auth nếu thuộc phạm vi, giới hạn input và timeout.
- [ ] Chốt retry/cache cho request có chi phí crawler; refetch không được tự chạy lại crawl chỉ vì đổi focus cửa sổ.
- [ ] FE + BE review từng trường hợp dưới đây và cập nhật HTTP/domain contract chuẩn. Điểm chưa chốt G1–G8 giữ owner và phần UI phụ thuộc.

## Cơ chế xử lý C4 đã có

| Phương án | Gain | Chi phí / rủi ro | Khi phù hợp |
|---|---|---|---|
| Đồng bộ cho form/typed edits | Không chờ LLM; nhận revision đã validate ngay | Vẫn phải xử lý conflict/validation | Backend đã implement 201/200 |
| Job + polling cho text/comparison | Theo dõi lâu, truy vấn lại sau mất mạng, kiểm soát revision/cancel/idempotency | Cần lưu IDs, dừng terminal, policy phiên và polling FE | Backend đã implement 202 + GET job/result |

Không còn lựa chọn lại sync/job từ đầu. Polling interval/timeout FE chưa chốt; default worker poll 0,2 giây là cấu hình nội bộ BE, không phải tần suất frontend. Streaming chưa có; chỉ bổ sung nếu lợi ích UI đủ rõ.

## Bộ mẫu JSON cần nhận

| Scenario | Nội dung để kiểm tra |
|---|---|
| URL success | Ít nhất 2 tour, nhiều offer cho một tour, giá/ngày khác nhau và trade-off mở đúng evidence |
| Nhu cầu success | Request criteria và response ghi lại criteria chuẩn hóa, kết quả lọc/cá nhân hóa có căn cứ |
| Clarification | Revision/câu hỏi/options, typed answers năm/currency/basis/strength; scope/mâu thuẫn dùng edits; answer cũ bị từ chối |
| Partial | Một nguồn lỗi, tour khác dùng được; lỗi chỉ rõ URL và khả năng thử lại |
| Empty / một tour | Zero matches có lý do, và một tour còn lại; không tạo trade-off giả |
| Field thiếu / partial | Fact value=null/data_state/completeness, offer_options rỗng, offer_reason, phụ thu chưa biết; không crash hoặc tính giá thiếu |
| Freshness / verification | Timestamp khác nhau theo field, nguồn tự công bố/độc lập, policy cũ và evidence mâu thuẫn nếu được hỗ trợ |
| Validation / lỗi toàn bộ | Input sai theo field/URL, nguồn không hỗ trợ, toàn bộ nguồn thất bại, lỗi hệ thống theo C9 |
| Timeout / request cũ | Parse/comparison đang chạy/terminal/cancel; hai request trả đảo thứ tự, patch parse lỗi giữ revision, 401/404/409, mất response POST/idempotency |
| URL-only / không hard | Có candidates nhưng eligibility=null/groups rỗng; không gắn “đạt nhu cầu”; hàng giá còn thiếu theo G1 |
| Chọn offer / reuse | Nhiều offers chưa chọn; selected snapshot đúng evidence; stale offer/targets đổi/discovery đổi revision không reuse |

Schema hiện ở `contracts/`, input mẫu ở `examples/`; không sửa JSON được sinh bằng tay. Đề nghị BE export thêm public response schemas và snapshots scenario từ fixture/runtime ở vị trí chung đã thống nhất. Mỗi fixture ghi scenario, schema version và expected UI; không tự coi mẫu suy từ tài liệu là response đã chốt.

## Ranh giới trách nhiệm

- **BE:** Chuẩn hóa/tìm tour, kiểm tra nguồn, lọc điều kiện, tính giá có căn cứ, đánh giá/trade-off và reference. Chỉ trả tiến độ có thể đo được.
- **FE:** Input/validation trải nghiệm, render dữ liệu và các mức trạng thái, mở evidence, điều khiển thao tác và định dạng tiền/ngày.
- **Cùng chịu trách nhiệm:** Schema/type/validation, ý nghĩa status, policy retry/freshness và regression fixture khi contract thay đổi.
