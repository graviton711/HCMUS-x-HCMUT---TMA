# Checklist thống nhất frontend–backend

**Trạng thái:** Đã đối chiếu backend `0b7e59f` ngày 03/10/2026; flow chung URL + tìm thêm và ranking/đề xuất 3 tour trước so sánh sâu là yêu cầu sản phẩm. Giữ C1–C11/G1–G9, thêm G10 cho ranking; contract/thuật toán chưa chốt không chặn thiết kế. “Đã có” chỉ xác nhận code hiện tại, không đồng nghĩa nghiệm thu UI/dữ liệu thật.
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
| C2 — Đầu vào chung | V1 có discover/compare_urls loại trừ nhau; text → parse job, form → revision; GET/PATCH/answers; URL 2–5 và nhu cầu tùy chọn | **Flow đã duyệt, API chưa đủ:** nhận nhu cầu + URL tùy chọn; kể cả một URL thì phân tích và tìm thêm. Chốt gợi ý/review phạm vi từ URL và orchestration chung G9; không suy đặc điểm tour thành ràng buộc người dùng. |
| C3 — Lọc/cá nhân hóa | Evaluations pass/fail/unknown, groups/blockers, empty_reason, trade-off có refs; chưa có ranking/Top 3 | **Một phần:** BE tự rank/chọn tối đa ba gợi ý và tạo comparison ngay (G10/G9), bỏ danh sách/chọn thủ công. Chốt pool/budget 20 thử nghiệm, hard gating/unknown, policy/trọng số/tie-break/offer context; vòng phương án khác/exclusion/hết phương án. Giữ G3, không score bí mật. |
| C4 — Lifecycle | Job parse/comparison, bốn terminal statuses, deadline/cancel, revision/idempotency; ownership/session | **Có cơ chế:** chốt FE polling/backoff, xử lý 401/404, local/demo hosting TTL và restore (G6). Source progress chỉ có cuối job; không % giả. Chốt token storage và retry theo action, không refetch tự crawl. |
| C5 — IDs/reference | Stable requirement/condition/child/target IDs; candidate + tour/offer snapshot IDs, evidence IDs; URL giữ thứ tự; selection/reuse kiểm tra binding | **Một phần:** G2 nhận diện; G9 dedup hai nguồn/offer/evidence và nhóm so sánh tự động, round/exclusion theo canonical tour identity. Giữ tour URL tham chiếu, không lặp làm gợi ý mới hoặc ghép theo tên/rẻ nhất. G6 context cũ còn thiếu. |
| C6 — Giá/nhóm | Nội bộ có PriceQuote exact/from/range, đơn vị/currency, tuổi, ExtraCharge/pricing_complete; CostEstimate bounds/components/reasons cho Budget; unknown khi thiếu dữ liệu | **Chặn hàng giá:** URL-only không Budget chưa trả public price/cost. Candidate/offer options thiếu price_quotes/extra_charges/pricing_complete (G1). BE cần trả dữ liệu giá độc lập điều kiện ngân sách; chốt contact/missing, coverage/currency, rooming/phụ thu và tổng nhóm. FE không tự tính thay BE. |
| C7 — Evidence | `/v1/evidence/{id}` raw_quote/url/publisher ID/method/locator/observed_at/snapshot; Fact raw_value/evidence_ids, conflicting + verification enums | **Một phần:** publisher display_name/binding tour thiếu public (G2), chính sách/raw nội dung thiếu (G3). Chốt UI nhiều evidence/mâu thuẫn/quote rỗng và giới hạn hiển thị; enum independently_verified chưa chứng minh có nguồn xác minh thật. |
| C8 — Freshness | SourceCapability TTL theo field; engine dùng timestamp/policy; evaluation data_quality có freshness cho Fact; selection cũ bị từ chối | **Một phần:** không có freshness trên mọi cell; Budget data_quality rỗng (G5). Chốt BE trả quality đầy đủ hay policy FE dùng có version; kiểm tra TTL nguồn thật/cache/refresh. Timestamp không thay thế xác minh. |
| C9 — Lỗi/kết quả thiếu | Error code/message/retryable/trace_id/details; 422 fields path/type; source statuses/issues; partial vs unknown vs failed; NO_SUPPORTED_TARGETS khác NO_CANDIDATES | **Có nền:** BE hoàn thiện danh mục code HTTP/job/source + retry; FE map microcopy/field_path từ details.fields. Bao phủ expired session/resource, stale answer/revision/offer, 413/429, model timeout, ALL_INELIGIBLE/ONLY_UNVERIFIED. |
| C10 — Schema | Generated request/domain JSON Schema version 1.0; business rules Python; GET comparison envelope và các keys đọc được từ code | **Chưa đủ:** response session/accepted-job/requirement revision 0/status/job/comparison/evaluation/trade-off/error/evidence chưa có bộ public typed schema đầy đủ (G8). OpenAPI routes chưa khai báo response_model; không sinh full client an toàn chỉ từ schema request. Chốt null/optional/unknown enums/version tương thích. |
| C11 — JSON mẫu | Hai JSON input tại examples; fixture và tests API/decision có scenario thành công/lỗi/clarification/reuse/cancel | **Một phần:** snapshots/expected UI/schema cho nhóm đề xuất/so sánh tự động, URL tham chiếu, budget/coverage, vòng phương án khác/hết phương án. Giữ lỗi hai phần, không hard/budget, multiple offers/revision cũ/crawler thật. |

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
| G9 — URL + retrieval chung | Nhu cầu + URL tùy chọn, một URL/gợi ý phạm vi/review; phân tích tham chiếu và retrieval chung, canonical dedup/offer/evidence/criteria/revision. BE tự tạo comparison; hỗ trợ vòng phương án khác/exclusion/cancel/reuse snapshot còn hợp lệ. Review pool/budget 20 và count URL ngoài ba gợi ý; chưa chốt DTO/job/endpoint, không ghép v1 ở FE | C2/C3/C5/C10/C11, P1.3–P1.6, P2.3–P2.4, P4.2–P4.4, P5.1–P5.2 | BE orchestration + FE; crawler hỗ trợ |
| G10 — Ranking / Top 3 | BE rank các tour tìm thêm đã đánh giá, tự chọn tối đa ba tour khác nhau và trả comparison/trade-off ngay; lý do/criteria/evidence/offer context/coverage/budget/policy version. Review khởi điểm tối đa 20 ứng viên/lượt bằng đo quality/latency; số 20 là giả định. Chốt hard gating/unknown/tie/URL-only/thiếu ba, loại tour đã xem khi tìm phương án khác; không bù fail hoặc coi unknown pass. FE render nhóm BE chọn, không checkbox chọn tour/tự rank | C3/C5/C10/C11, P1.4–P1.5, P2.4, P3.4–P3.5, P4.3, P5.1–P5.3, P6.2 | BE decision + FE |

Ưu tiên G9/G10/G1/G2/G8 song song với thiết kế; G3–G7 tiếp tục giữ. Ranking cần dựa evaluations/provenance và policy có thể kiểm tra, không chỉ sinh lời giải thích bằng AI sau khi chọn tùy ý. Chưa cần chốt công thức/trọng số để thiết kế kết quả/so sánh trực tiếp và hành động tìm phương án khác; contract cần đủ trước tích hợp. Crawler vẫn phụ thuộc P5.2, fixture không thay dữ liệu thật.

**Hướng xử lý G9 đề xuất:** BE điều phối chung để giữ nhất quán criteria, dedup, offer/evidence và retry từng phần; chi phí là mở rộng orchestration/public DTO, phù hợp gateway/engine hiện có và dễ debug lâu dài. Ghép hai job v1 tại FE không tạo được so sánh chung có căn cứ vì criteria, snapshot, identity và trade-off có thể khác; frontend quản lý yêu cầu/lượt kết quả và hiển thị, không bắt user sàng lọc pool. Đây là yêu cầu sản phẩm/ranh giới đề xuất, chưa chốt tên field hay endpoint.

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
- [ ] FE + BE review từng trường hợp dưới đây và cập nhật HTTP/domain contract chuẩn. Giữ G1–G10 và D1–D5; flow/ranking mới không đóng các gap cũ.

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
| Nhu cầu + URL | Phân tích tham chiếu + nhóm tối đa ba gợi ý mới, tự so chung một revision; review count ví dụ một URL + ba gợi ý = bốn tour |
| Ranking / Top 3 | BE tự chọn/so sánh tối đa ba tour khác nhau, rank/lý do đúng policy/evaluations, offer/evidence binding; hard fail/unknown không lấp giả; budget 20/coverage/latency được kiểm chứng |
| Phương án khác / URL-only | Không bước chọn tour; vòng mới loại đề xuất đã xem, giữ URL và criteria; hết nhóm thì báo rõ. URL-only chưa ưu tiên: đề xuất tương tự có cơ sở, không giả tối ưu cá nhân |
| Một URL-only | Đọc tour → gợi ý phạm vi có nguồn → review → tìm thêm; không tự đặt ngân sách/sở thích từ tour |
| Trùng hai nguồn | Một tour với cả hai nguồn gốc; canonical identity và các offer riêng không bị mất |
| Lỗi từng phần | URL lỗi vẫn có tour tìm thêm; retrieval lỗi vẫn có tour URL; retry giữ dữ liệu và binding hợp lệ |
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

- **BE:** Chuẩn hóa/tìm tour, kiểm tra nguồn, lọc/tính giá, đánh giá, ranking/Top 3 có giải thích, trade-off và reference. Chỉ trả tiến độ đo được; policy ranking là G10 chưa implement.
- **FE:** Input/validation trải nghiệm, render dữ liệu và các mức trạng thái, mở evidence, điều khiển thao tác và định dạng tiền/ngày.
- **Cùng chịu trách nhiệm:** Schema/type/validation, ý nghĩa status, policy retry/freshness và regression fixture khi contract thay đổi.
