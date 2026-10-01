# HTTP contract v1 để frontend tích hợp

**Trạng thái:** Đề xuất, chưa có endpoint chạy. Payload examples không phải dữ liệu tour thật.

## Tạo và sửa nhu cầu

`POST /v1/requirements`: mode bắt buộc; discover cần `text` hoặc `form`, compare URLs cho phép không có cả hai. Không nhận text/form ghi đè cùng field mà không có thứ tự rõ. Compare URLs cần `urls` 2–5 phần tử không trùng hoàn toàn; discover không tự fetch URL xuất hiện trong text.

```json
{
  "mode": "compare_urls",
  "text": "Ưu tiên ít shopping và khách sạn 4 sao. Giá tour tối đa 30tr VND cho cả nhóm 2 người lớn và bé 8 tuổi.",
  "urls": ["https://tour-demo.invalid/tour-a", "https://tour-demo.invalid/tour-b"],
  "timezone": "Asia/Ho_Chi_Minh"
}
```

Text → HTTP 202, `{requirement_id, revision: 0, job_id, status: "queued"}`. Khi parse thành công, revision 1 có thể ready hoặc needs_clarification. Revision chỉ là bản hiểu đã validate, không phải bằng chứng mọi thông tin đã đủ. Form hợp lệ không cần LLM có thể trả 201 + revision 1.

`GET /v1/requirements/{id}` trả current revision/status, input summary, targets, party, conditions/hard tree/preferences, unresolved, clarifications và readiness. SourceReference/span theo [backend-contracts.md](backend-contracts.md). Timestamp reference do server ghi tại lúc nhận lượt nói; timezone là input hợp lệ, không cho client tùy ý đổi clock server.

`PATCH /v1/requirements/{id}` cần `expected_revision`, và đúng một nhóm `text`, `answers`, hoặc `edits`. Structured edits chỉ dùng whitelist field/condition paths; không cho JSON patch tùy ý.

```json
{
  "expected_revision": 1,
  "edits": [
    {"op": "replace", "target": "conditions.c_budget.value.amount", "value": 35000000},
    {"op": "remove", "target": "conditions.c_hotel"}
  ]
}
```

Structured update hợp lệ trả 200 + revision mới; text update trả 202 + parse job, revision hiện tại giữ nguyên đến commit. Pending update lưu expected revision; khi commit cũng kiểm tra lại, conflict không ghi đè. Model lỗi giữ revision cũ, user có thể sửa form/retry.

IDs trong ví dụ giả định đã được backend trả qua GET requirement; frontend dùng IDs thật từ response, không suy đoán `c_budget/c_hotel` từ tên field.

Answers dùng `{clarification_id, value}` có kiểu; clarification cũ sau revision change bị từ chối. Thay mode là tạo requirement mới để không giữ nhầm URL/state từ flow trước.

Compare URLs cho typed target edits: `add` URL hợp lệ với vị trí, `remove` theo target_id, hoặc reorder bằng danh sách target IDs đầy đủ. Giữ stable IDs cho target còn lại; không dùng URL từ edit để fetch trước access check. Revision cũ và comparisons cũ giữ references riêng.

## Chạy và đọc comparison

`POST /v1/comparisons` đọc mode/targets từ requirement revision; caller không gửi một mode khác. Chấp nhận khi `can_collect_data=true`; hard evaluation còn blocker thì kết quả phải ghi unknown, không bỏ điều kiện đó.

```json
{
  "requirement_id": "req_demo",
  "revision": 2,
  "offer_selections": []
}
```

Response 202: `{comparison_id, job_id, requirement_id, revision, status: "queued"}`. Chọn offer sau lần fetch dùng thêm `reuse_comparison_id` và `offer_selections: [{target_id, offer_snapshot_id}]`; backend kiểm tra ownership, target/source binding và freshness. Nếu cần refresh, báo selection không còn áp dụng thay vì lặng lẽ đổi sang offer khác.

`GET /v1/jobs/{id}` trả kind, status, timestamps, phase, source progress, error và resource ref. Trạng thái: `queued → running → succeeded/partial/failed/cancelled`. Frontend dừng polling ở trạng thái terminal. Phase/number sources đã xử lý không được trình bày là % hoàn thành đáng tin cậy nếu chưa có cơ sở.

`POST /v1/jobs/{id}/cancel` đặt cancel_requested cho job chưa terminal; worker kiểm tra trước commit và kết thúc cancelled. Job đã terminal trả trạng thái hiện có. Đóng tab chỉ dừng polling, không mặc định hủy job trên server.

`GET /v1/comparisons/{id}` trả trạng thái khi chưa xong; khi xong có:

| Field | Frontend dùng để |
|---|---|
| `requirement_id`, `revision`, `evaluated_at`, policy/snapshot versions | Hiển thị nhu cầu và thời điểm đúng với lần chạy |
| `origin` | Nhãn dữ liệu mô phỏng nếu synthetic |
| `targets` | URL columns đúng thứ tự user chọn, acquisition status, static facts và offer options |
| `candidates` | Tour/offer refs, assessment_level, eligibility, evaluations, cost bounds và missing reasons |
| `groups` | Eligible/ineligible/needs_verification refs trong discovery; không xóa target fail khỏi URL matrix |
| `filter_applied`, `decision_blockers` | Không gắn nhãn “phù hợp” khi chưa có hard filter hoặc chưa đủ nghĩa yêu cầu |
| `criteria`, `trade_offs`, `evidence_refs` | Từng cell/claim có source và evaluation; không dựa vào một đoạn văn duy nhất |
| `source_coverage`, `warnings`, `empty_reason` | Giới hạn search, nguồn lỗi/cũ và nguyên nhân không có kết quả |

Multiple offers chưa chọn: ô phụ thuộc offer trả reason `MULTIPLE_OFFERS_UNSELECTED`; dữ liệu tour tĩnh vẫn hiện. Chỉ sort khi user chọn criterion và có dữ liệu comparable; tie-break theo stable id, không theo điểm AI.

`GET /v1/evidence/{id}` trả field/value/raw quote, URL, snapshot ref, observed_at, verification và provenance method. Không trả HTML/script gốc hoặc secret. Evidence id phải thuộc resource/session user được phép xem.

## Error và trạng thái một phần

Error shape: `{error: {code, message, field_path, retryable, trace_id, details}}`; details chỉ là thông tin an toàn. Async error nằm trong job, không biến thành requirement cần user tự đoán field.

| Nhóm | HTTP / code chính |
|---|---|
| DTO/type/URL syntax/version sai | 422: `INVALID_INPUT`, `INVALID_URL`, `UNSUPPORTED_SCHEMA_VERSION` |
| Revision/state/offer selection cũ | 409: `REVISION_CONFLICT`, `REQUIREMENT_NOT_PARSED`, `OFFER_SELECTION_INVALID` |
| Resource không tìm thấy/không thuộc session | 404; không tiết lộ ownership của user khác |
| Rate limit ở API | 429, Retry-After khi có |
| Job model lỗi | `LLM_AUTH_FAILED`, `LLM_RATE_LIMITED`, `LLM_TIMEOUT`, `LLM_INVALID_OUTPUT`, `LLM_UPSTREAM_ERROR` |
| Source/target không dùng được | `SOURCE_NOT_APPROVED`, `SOURCE_BLOCKED`, `SOURCE_UNSUPPORTED`, `SOURCE_TIMEOUT`, `FIELD_MISSING` |

Không có tour hoặc không có tour đạt là business result, không phải HTTP 500. Nguồn lỗi nhưng còn kết quả dùng được → job partial; field thiếu bình thường → job succeeded với unknown cells. Tất cả source attempts lỗi và không có usable snapshot → job failed `SOURCES_UNAVAILABLE`. Targets bị loại ngay bởi access/capability validation → succeeded với target statuses/empty_reason `NO_SUPPORTED_TARGETS`; không gọi cả hai trường hợp là “không có tour trên thị trường”.

Mutation nhận `Idempotency-Key`; cùng session/key/body trả resource cũ, key dùng lại với body khác trả 409. Job có deadline, giới hạn retry, lease/recovery và cancellation flag. Giới hạn input, concurrency, CORS/auth/retention chốt theo hosting; không xuất key NIM cho frontend.
