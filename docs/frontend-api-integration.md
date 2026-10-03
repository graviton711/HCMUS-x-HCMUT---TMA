# Frontend tích hợp backend v1

**Trạng thái:** Ghi nhận từ backend `0b7e59f`, đã merge/tham chiếu trên `feature/minh-phu` ngày 03/10/2026; dùng để review P1/P2, chưa thay việc FE + BE chốt contract. Tourcrawl/scripts cũng đã merge nhưng chưa nối với gateway; API mặc định vẫn fixture, `origin=synthetic`. Chi tiết ở [đối chiếu crawler](frontend-crawler-integration.md).
**Nguồn chuẩn:** [HTTP contract](api-contract.md), [domain contract](backend-contracts.md), [schema sinh từ models](../contracts/README.md). Tài liệu này ánh xạ API vào frontend; các khoảng thiếu được giữ tại [C1–C11 và G1–G8](frontend-backend-checklist.md).
**Đối chiếu:** [routes](../src/api/app.py), [DTO](../src/api/dto.py), [models nhu cầu](../src/domain/requirements.py), [Fact/evidence](../src/domain/crawl.py), [decision engine](../src/decision/engine.py), [store](../src/api/store.py), [settings](../src/api/settings.py).

## Endpoint và response thực tế

| Endpoint | Thành công | Frontend cần lưu / đọc |
|---|---|---|
| `POST /v1/sessions` | 201: `{session_id, token, token_type, expires_at}` | Tạo phiên ẩn danh; các endpoint v1 còn lại gửi `Authorization: Bearer <token>` |
| `GET /v1/sources` | 200: `{origin, sources}` | Capability, access status, domain, field và TTL từng nguồn; không phải catalog dropdown |
| `POST /v1/requirements` với form / chỉ URL | 201: `Requirement` | `id`, `revision=1`, conditions, targets, party, trees, clarifications, readiness |
| `POST /v1/requirements` với text | 202: `{requirement_id, revision:0, job_id, status:"queued"}` | Poll parse job, sau thành công GET requirement; không gửi revision 0 vào comparison |
| `GET /v1/requirements/{id}` | 200 | Revision 0 chỉ `{id, revision:0, status}`; đã parse trả `Requirement` + `status` của resource |
| `PATCH /v1/requirements/{id}` | Edits/answers: 200 `Requirement`; text: 202 parse job | Bắt buộc `expected_revision`; đúng một trong text/edits/answers |
| `POST /v1/comparisons` | 202: `{comparison_id, job_id, requirement_id, revision, status:"queued"}` | Snapshot lần chạy; GET job rồi GET comparison |
| `GET /v1/jobs/{id}` | 200: job | Dùng `id`, `resource_id`, `kind`, `status`, `phase`, `created_at`, `deadline_at`, `completed_at`, `error`, `metrics`; không có `started_at`/phần trăm tiến độ |
| `POST /v1/jobs/{id}/cancel` | 200: `{job_id, status}` | Có thể trả trạng thái terminal đã tồn tại; kiểm tra response trước khi ghi UI “đã hủy” |
| `GET /v1/comparisons/{id}` | 200: `{id, status, result}` | `result=null` khi chưa có kết quả; lỗi lấy ở `job.error` |
| `GET /v1/evidence/{id}` | 200: `Evidence` | `id, snapshot_id, url, publisher, method, locator, raw_quote, observed_at`; resource thuộc phiên mới xem được |

`/`, `/health`, `/docs`, `/openapi.json` công khai ở local backend. V1 chưa có tài khoản, đăng nhập mật khẩu hoặc booking. Tên key `id` ở resource không đồng nhất với `requirement_id`/`comparison_id` ở response tạo job; API boundary phải ánh xạ đúng.

## Input nhu cầu và validation

`mode=discover|compare_urls`. Discover nhận **text hoặc form**, không nhận URLs; compare URLs nhận 2–5 URLs và text/form tùy chọn. Không gửi cả text và form. Đổi mode tạo requirement mới; giữ draft hai tab riêng.

- Text: 1–8.000 ký tự; form: tối đa 50 conditions. URL tối đa 2.048 ký tự, HTTP(S), không credentials, port chỉ 80/443, không khoảng trắng/control/backslash; trùng hoàn toàn bị từ chối. Canonical dedup/giới hạn số cột discovery còn cần review C5.
- Condition: `{id, field, operator, value, strength}`; mặc định form là `hard`. FE gán ID khi tạo condition/child; sau response dùng ID thực tế. Backend tạo provenance, FE không gửi source quote tự dựng.
- Value là union theo `kind`: `set` + `items` canonical IDs; `number` + `amount`; `date` + `value`; `budget` + tiền/currency/basis/coverage; `unresolved` + raw/reason. Không gửi một object criteria phẳng.
- Set IDs như `country:jp`, `city:vn:hcmc`; catalog label/value/operator cho form chưa có API/schema đầy đủ (G4). Không gửi nhãn “Nhật Bản” thay canonical ID ở form.
- Ngày `YYYY-MM-DD`, range dùng `operator=between` + `upper`; không có field `flexibility_days`. Cần chốt cách chuyển UI “± N ngày” thành khoảng và validation ngày ở C1.
- Party: adults `1..100` hoặc null, tối đa 20 trẻ có ID riêng, age `0..17` hoặc null; `rooming` tùy chọn. Không ép party/ngày/ngân sách bắt buộc cho URL-only.
- VND dùng **integer đồng**; ngoại tệ dùng **decimal string**. Budget basis `per_adult|per_person|group_total`, coverage `tour_price|trip_total`. Currency/basis chưa biết giữ null để hỏi lại; không tự hiểu “tr” thành VND.
- Không nêu coverage: backend mặc định `tour_price`, có `coverage_origin=system_default` và provenance rule. UI phải nói rõ phạm vi giá tour; nếu user chọn coverage thì gửi lựa chọn đó.
- `hard_tree`/`preference_tree` giữ nhóm `all|any|predicate`; không làm phẳng OR thành AND. Schema JSON chưa thể hiện hết whitelist field/operator và business rules Python.

| Nhóm field hiện được hỗ trợ | Value / ví dụ operator |
|---|---|
| destinations, departure_origin, supplier, transport, included_services | Set; contains/contains_any/contains_all/excludes hoặc in/not_in tùy field |
| departure_date, return_date | Date; eq, lt/lte, gt/gte, between |
| duration_days/nights, hotel_stars_min, shopping_stops, flight_stops | Number; whitelist riêng tại `FIELDS`; near/prefer_low/prefer_high chỉ là soft khi field hỗ trợ |
| estimated_cost | Budget; lt/lte, gt/gte, between, near, prefer_low |
| unsupported | Unresolved; giữ lý do, không bỏ điều kiện khó khỏi yêu cầu |

Payload tạo hoàn chỉnh: [discover-form.json](../examples/discover-form.json), [compare-urls.json](../examples/compare-urls.json). `.invalid` chỉ định danh fixture, không được fetch. Text thay form sẽ thêm một parse job trước bước comparison.

## Sửa, làm rõ và chọn offer

Ví dụ dưới đây giả định response đã trả condition ID `budget`; phải thay bằng ID thật của requirement đang sửa:

```json
{
  "expected_revision": 1,
  "edits": [
    {"op": "replace", "target": "conditions.budget.value.amount", "value": 35000000}
  ]
}
```

- Whitelist edits: add/remove condition; replace value/strength/operator hoặc subfield value được hỗ trợ; replace party/tuổi theo child ID. URL targets có add `{url, position}`, remove theo target ID, reorder bằng đủ ID hiện tại. Không phải JSON Patch tùy ý; chưa có edit grouping tree trực tiếp (G7).
- Answers gửi `answers:[{clarification_id,value}]`. Thiếu năm nhận integer `1900..2100`; currency/basis/strength nhận string phù hợp; unresolved value khác nhận typed Value. Câu hỏi scope/mâu thuẫn có `field_path="conditions"` cần sửa conditions bằng edits.
- Text patch giữ revision đã commit đến khi parse thành công. Parse lỗi/hủy không được xóa bản hiểu trước. `REVISION_CONFLICT`/`STALE_CLARIFICATION`: GET bản mới, giữ draft, cho review thay đổi; không tự retry ghi đè.
- `readiness.can_collect_data` quyết định có thể chạy comparison; `can_evaluate_hard_constraints` là quyền kết luận đạt. Discover cần scope điểm đến/nhà cung cấp có thể truy vấn; URL có thể thu thập dữ liệu tĩnh dù còn blocker giá. Không chặn toàn bộ chỉ vì `status=needs_clarification`.

Chọn offer trong **compare URLs** lấy snapshot ID từ `targets[].offer_options`; gửi comparison mới dùng dữ liệu lần trước:

```json
{
  "requirement_id": "req_from_response",
  "revision": 1,
  "reuse_comparison_id": "comparison_from_response",
  "offer_selections": [
    {"target_id": "target_from_response", "offer_snapshot_id": "offer_from_response"}
  ]
}
```

Comparison cũ phải succeeded/partial, cùng requirement và tập target ID–URL; selections không rỗng bắt buộc có reuse ID. Nhiều offer chưa chọn trả `MULTIPLE_OFFERS_UNSELECTED`, vẫn có dữ kiện tour; không chọn rẻ nhất ngầm. Discovery trả candidate cho từng offer, chưa hỗ trợ offer_selections theo target; đổi revision discovery phải thu thập lại. URL giữ targets có thể đánh giá lại với revision mới qua reuse; selection cũ bị từ chối thì tải lại nguồn, không âm thầm đổi offer.

## Job, phiên và retry

- Job: `queued → running → succeeded|partial|failed|cancelled`; cả bốn là terminal. Parse thành công → GET requirement; comparison succeeded/partial → GET comparison. Failed đọc `job.error`; result null không phải business empty.
- Phase hiện có queued/extracting/collecting/completed/failed/cancelled. Progress từng nguồn chỉ có khi kết thúc; không diễn giải metrics thành % hoặc streaming đã có.
- FE policy **đề xuất cần chốt ở P2**: poll GET mỗi 1 giây khi visible, tăng dần tối đa 5 giây khi chờ lâu; dừng terminal, giảm/dừng khi hidden và GET lại khi quay lại. Refetch GET không tự POST/crawl mới.
- Mutation requirement/comparison/cancel nhận `Idempotency-Key`: retry cùng hành động giữ key và body; hành động mới tạo key mới. Key cùng phiên dùng khác nội dung/route trả 409; lưu server 24 giờ. Chưa có dedup retry tạo session bằng header này.
- Mất response POST: retry với key cũ để lấy resource đã tạo. Khi biết job ID, truy vấn trạng thái trước khi chạy lại. Request timeout ở FE không đồng nghĩa job failed; đóng tab không hủy BE. Cancel terminal ngăn commit kết quả muộn; upstream đang chạy có thể tiếp tục đến deadline.
- Mặc định local: session 24 giờ, retention 7 ngày, job deadline 180 giây, NIM 90 giây, crawler 60 giây, tối đa 10 pending jobs/owner. Dùng `expires_at`/`deadline_at`; không hardcode các default thành contract hosting.
- CORS default `http://localhost:3000`, `http://localhost:5173`; GET/POST/PATCH, headers Authorization/Content-Type/Idempotency-Key, credentials=false. Chốt base URL, origin thực tế, token storage và refresh route ở P2; token không đưa vào URL/log. Không cấp key NIM/crawler cho FE.
- 401: phiên không hợp lệ/hết hạn; 404: resource mất hoặc không thuộc phiên. Tạo phiên mới không lấy lại resource phiên cũ. Chưa có list/history hay GET requirement theo revision cho FE (G6).

## Đọc kết quả đúng nghĩa

| Field / nhóm | Cách dùng ở UI |
|---|---|
| `requirement_id, revision, evaluated_at, schema_version, policy_version` | Gắn kết quả với lần chạy; không gán criteria current vào comparison revision cũ |
| `origin` | Synthetic luôn có nhãn dữ liệu minh họa, không phải tour đã xác minh |
| `targets[]` | URL theo thứ tự người dùng; status/reason_code/candidate_ids/offer_options; giữ cột nguồn lỗi |
| `candidates[]` | id, tour/offer snapshot refs, assessment_level, fields, offer_fields, evaluations, eligibility, offer_reason |
| `evaluations[]` | condition_id/field/strength, `pass|fail|unknown`, actual, reason_code, evidence_ids, data_quality |
| `groups` + `filter_applied` | Khi không có hard filter: eligibility=null, groups rỗng **dù có candidates**; không coi là zero result |
| `criteria` + `decision_blockers` | Conditions của lần chạy và lý do chưa thể kết luận; chưa bao gồm toàn bộ party/trees của revision |
| `trade_offs` | candidate_a/b + condition_id + field/value_a/value_b + evidence_ids; hiện chỉ so sánh soft NumberValue, chưa có trade-off giá/chính sách |
| `source_coverage, warnings, empty_reason` | Giới hạn thu thập, nguồn lỗi/truncated và nguyên nhân thiếu lựa chọn; không chỉ nhìn số eligible |

Fact wrapper hiện tại: `value, raw_value, data_state, verification, completeness, observed_at, evidence_ids` (+ unit/scope/reason/normalization_rule tùy chọn). `data_state=present|missing|conflicting|invalid|unsupported`; `verification=supplier_published|independently_verified|unverified`; `completeness=complete|partial|unknown`. Không dùng enum `observed/provider_claimed` hay inline evidence của contract cũ.

Freshness `fresh|stale|unknown` nằm trong `evaluation.data_quality` khi có Fact tương ứng, không nằm trên mọi Fact; budget evaluation hiện không điền data_quality. Không suy timestamp thành “đã xác minh” hoặc tự gắn “vừa kiểm tra” cho toàn tour (G5).

CostEstimate chỉ xuất ở `evaluations[].actual` cho điều kiện Budget: lower/upper, basis, coverage, components, evidence_ids, reasons. Null bound không phải 0; price từ/range hoặc thiếu phụ thu không thành tổng chính xác. Ngân sách per_person với trẻ em có thể unknown (`PER_PERSON_PRICE_AMBIGUOUS`); không chia tổng nhóm để chứng minh đạt.

**Khoảng thiếu ảnh hưởng màn chính:** URL-only không có budget thì public result chưa có giá. Candidate/offer_options không trả price_quotes/extra_charges/pricing_complete; chưa có tên tour, supplier display_name/canonical URL đầy đủ trong comparison, nội dung chính sách và schema response đầy đủ. Giữ yêu cầu wireframe và đề nghị BE bổ sung G1–G3/G8; không giả tạo condition ngân sách để lấy giá hoặc gọi contract crawler nội bộ từ FE.

## Lỗi và kiểm chứng

Error: `{error:{code,message,retryable,field_path,trace_id,details}}`; validation 422 có `details.fields:[{path,type}]`, thường `field_path=null`. API boundary ánh xạ path `body.form...` về input; giữ trace_id cho debug. Async đọc cùng thông tin ở job.error.

HTTP chính: 401 UNAUTHORIZED; 404 NOT_FOUND; 409 REVISION_CONFLICT/STALE_CLARIFICATION/REQUIREMENT_NOT_READY/OFFER_SELECTION_INVALID/IDEMPOTENCY_CONFLICT; 422 INVALID_INPUT; 413 INPUT_TOO_LARGE (body >64 KiB); 429 RATE_LIMITED với Retry-After. Danh mục đầy đủ và nhãn tiếng Việt chốt C9, không suy retry chỉ từ HTTP.

Một nguồn lỗi nhưng còn snapshot dùng được → partial; thiếu field bình thường → succeeded + unknown cells; mọi source attempt lỗi và không có snapshot → failed SOURCES_UNAVAILABLE. Tất cả target bị access/capability từ chối có thể succeeded + NO_SUPPORTED_TARGETS. ALL_INELIGIBLE/ONLY_UNVERIFIED có thể vẫn có candidates để xem lý do.

Đã chạy experiment offline bằng models + fixture + decision engine cho hai JSON đầu vào: discover cho ba nhóm 1/1/1; URL-only có candidates, groups rỗng và chưa có giá public. Sau merge, tests backend/tourcrawl (bao gồm API integration bằng TestClient) đạt **107 passed** trong `.uv/merge-env`, lint đạt; `.venv` cũ giữ nguyên. Chưa xác nhận frontend E2E, NIM/crawler nguồn thật. Schema response còn thiếu typed models/response_model; JSON schemas hiện chưa đủ sinh toàn bộ API client (C10).
