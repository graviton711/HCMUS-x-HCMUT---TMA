# Gọi backend v2 và nối frontend

Runtime: [phạm vi/giới hạn](../docs/backend-v2-runtime.md). Contract request/response: [schemas v2](../contracts/v2/). `/v1` tiếp tục dùng được; frontend mới dùng `/v2` cho proposal và một bảng nhu cầu + URL.

## Khởi động

Từ repo root: `uv sync`, `uv run tour-backend serve`. Sau sửa code, Ctrl+C và chạy lại. Mở `http://127.0.0.1:8000/docs`, tìm nhóm **v2**. Backend đọc NIM từ `.env` hiện có; không đưa key NIM vào frontend.

Mặc định `DATA_PROVIDER=fixture`: chỉ ba tour mô phỏng, origin `synthetic`. Các URL dưới là fixture IDs, không được fetch trên Internet. Crawler thật cần `DATA_PROVIDER=http`, `CRAWLER_URL`, `CRAWLER_REGISTRY_PATH` và endpoint chấp nhận [contract v1](../docs/crawler-contract.md); chưa nối thẳng JSON/CSV `tourcrawl`.

1. `POST /v2/sessions`, không body/auth → `data.token` và `data.id`.
2. Swagger **Authorize → SessionBearer**, dán riêng token. Khi gọi từ FE, gửi `Authorization: Bearer <token>`.
3. Giữ cùng phiên cho mọi requirement/proposal/comparison/job/evidence. Token hết hạn sau 24 giờ mặc định; các ID minh họa không phải resource thật.
4. Mọi mutation nên có `Idempotency-Key` mới cho thao tác mới; retry thao tác bị mất response dùng cùng key và body. Không tạo key mới mỗi lần retry. Key được scope theo principal/route, giữ 24 giờ.

Response v2: `{schema_version:"2.0-draft", request_id, data}`. Lỗi có `error.code/message/details`. FE lấy fields, canonical places, operators, sliders và limits từ `GET /v2/catalog`.

## Thử URL trước, không cần NIM

`POST /v2/requirements`:

```json
{
  "input": {"kind": "urls"},
  "reference_urls": [
    "https://tour-demo.invalid/tour-a",
    "https://tour-demo.invalid/tour-c"
  ]
}
```

201 trả `requirement_id`, `revision:0`, `proposal_id`. `GET /v2/proposals/{proposal_id}` lấy full `preview` và `version`; không tự suy số người/budget/sliders từ URL.

`POST /v2/proposals/{proposal_id}/confirm`:

```json
{"expected_revision": 0, "expected_proposal_version": 1}
```

Dùng version thật đã đọc. Response `data.id`, `data.revision:1` là requirement đã commit. Confirm không tự tìm tour.

`POST /v2/comparisons`, thay ID bằng requirement thật:

```json
{"requirement_id": "REPLACE_WITH_REAL_ID", "revision": 1}
```

202 trả `comparison_id` và `job_id`. Poll `GET /v2/jobs/{job_id}` đến `succeeded|partial|failed|cancelled`; đọc lỗi job khi failed. Log từ `GET /v2/jobs/{job_id}/events?after_seq=0&limit=25`; cập nhật cursor bằng `data.next_seq`, dùng `has_more` để đọc tiếp. Job và seq được lưu SQLite.

`GET /v2/comparisons/{comparison_id}` → `data.status` và `data.result`. Chỉ render result khi đã publish. Giá nằm trong row `price_quotes` kể cả không có Budget. Mở evidence bằng `GET /v2/evidence/{evidence_id}` lấy quote gốc/link best_effort; synthetic không phải chứng cứ nguồn thật.

## Nhập nhu cầu tiếng Việt

`POST /v2/requirements`:

```json
{
  "input": {
    "kind": "text",
    "text": "Đi Nhật từ TP.HCM, khởi hành 10/11/2026, 2 người lớn. Ngân sách tối đa 30 triệu đồng mỗi người lớn cho giá tour. Ưu tiên tiết kiệm mức 4."
  },
  "reference_urls": ["https://tour-demo.invalid/tour-a"],
  "timezone": "Asia/Ho_Chi_Minh"
}
```

202 trả draft/proposal/parse job. Chờ job rồi đọc proposal: `preview.conditions`, party, AND/OR, `preference_levels`, `readiness.blockers`, clarifications và từng change có before/after. Parse không commit. Proposal có TTL 30 phút và CAS version; blocking clarification hoặc parse chưa thành công chặn confirm. Sửa điều kiện bằng typed edits rồi confirm version mới.

Nhu cầu có URL → `hybrid`: cùng một comparison dùng cả reference và discovery, canonical merge tránh trùng tour. Không có URL → discover; cần positive destination/supplier scope để collect. Giá thiếu basis/currency hoặc ngày mơ hồ được giữ unresolved, không tự giả thông tin.

## Structured form cho demo deterministic

`POST /v2/requirements` với form đã được người dùng xác nhận tạo thẳng revision 1:

```json
{
  "input": {
    "kind": "structured",
    "form": {
      "conditions": [
        {"id":"destination","field":"destinations","operator":"contains","strength":"hard","value":{"kind":"set","items":["country:jp"]}},
        {"id":"origin","field":"departure_origin","operator":"in","strength":"hard","value":{"kind":"set","items":["city:vn:hcmc"]}},
        {"id":"date","field":"departure_date","operator":"eq","strength":"hard","value":{"kind":"date","value":"2026-11-10"}},
        {"id":"budget","field":"estimated_cost","operator":"lte","strength":"soft","value":{"kind":"budget","amount":30000000,"currency":"VND","basis":"per_adult","coverage":"tour_price"}}
      ],
      "party": {"adults":2,"children":[]}
    }
  },
  "reference_urls": ["https://tour-demo.invalid/tour-a"]
}
```

Tối thiểu form cần destination/origin/date/budget và adults. Slider default được công bố `origin=system_default`; muốn custom gửi `preference_levels` theo schema. Cây mặc định conjunction; OR phải gửi explicit `hard_tree`/`preference_tree` có đủ refs. Budget coverage chưa nêu mặc định giá tour, basis/currency vẫn phải rõ. Dùng ngày fixture trên để demo có kết quả; ngày khác được đánh giá đúng điều kiện, không tự nới phạm vi.

## Sửa nhiều field, chat và nhóm tiếp theo

`POST /v2/requirements/{id}/proposals`:

```json
{
  "expected_revision": 1,
  "input": {
    "kind": "structured",
    "edits": [
      {"op":"replace_condition_value","condition_id":"budget","value":{"kind":"budget","amount":32000000,"currency":"VND","basis":"per_adult","coverage":"tour_price"}},
      {"op":"set_preference_level","dimension":"comfort","level":4},
      {"op":"set_notes","notes":"Muốn có thời gian tự do."}
    ]
  }
}
```

Có proposal đang pending thì request merge phải thêm `proposal_id` và `expected_proposal_version`. Edits validate atomically: một field sai thì không ghi thay đổi nào. Với text edit: `input={kind:"message",text:"Đổi thời lượng thành 6 ngày."}` → parse job; chờ rồi đọc version mới.

- Bỏ diff: `POST /v2/proposals/{id}/discard-changes`, body gồm expected_revision/expected_proposal_version/change_ids lấy từ response. Nếu bỏ condition liên quan explicit AND/OR, `DISCARD_DEPENDENCY` trả related_change_ids để UI cho bỏ cùng.
- Hủy proposal: `POST /v2/proposals/{id}/cancel`, body expected_proposal_version. Revision đã commit giữ nguyên.
- Confirm bằng base revision + proposal version hiện tại. 409 conflict → đọc lại current/proposal, không blind retry version cũ. Sau confirm tạo comparison mới bằng revision mới; bảng cũ giữ snapshot cũ.
- Chat: `POST /v2/conversations/{requirement_id}/messages`, body text/client_message_id/context.requirement_revision; khi có proposal hoặc bảng đang xem, gửi thêm paired proposal_id/version và comparison_id/result_revision. Chờ job, lấy outcome từ `GET /v2/conversations/{requirement_id}/messages/{client_message_id}`. Edit tạo proposal; search/next_group trả requested_action để FE gọi comparison sau xác nhận. Answer chỉ dùng metric/evaluation refs đã có.
- Nhóm tiếp: POST comparison với `round_intent:"next_group"`, previous_comparison_id và cùng requirement revision; backend cộng exclusions từ nhóm đã đề xuất.
- Đổi offer: `round_intent:"offer_change"`, previous_comparison_id, offer_selections `{tour_id,offer_snapshot_id}` từ offer_options đã xem. Tạo comparison mới bằng snapshot cũ sau access/freshness checks; không đoán offer khi nhiều lựa chọn phù hợp.
- Hủy job: `POST /v2/jobs/{job_id}/cancel`, body `{}`. Late upstream response không publish lại.
- Sau reload: GET requirement trả active_proposal/latest_job_id/latest_comparison_id/latest_comparison_job_id; FE resume polling. Session token cần được giữ theo policy FE đã chốt.

## Admin/contact và dữ liệu lưu

Contact public `POST /v2/contacts`: category `feedback|data_issue|support`, message (≤4.000), reply_to optional, client_submission_id để retry, context.session_id/comparison_id phải owned. Lưu ticket `new`; không gửi email.

Admin dùng token riêng theo [runtime config](../docs/backend-v2-runtime.md), Swagger AdminBearer. API có overview `[from,to)` UTC, sources/create/check/approve/pause/refresh/runs, contacts xử lý CAS, audit, sessions/activity metadata với paging. Job nguồn đọc tại `GET /v2/admin/jobs/{id}`. Viewer bị lược email/message/internal notes; operator chỉ pause/refresh nguồn đã duyệt và xử lý ticket; admin thêm policy/approval. Không dùng token session làm admin.

Source mới gửi capabilities đầy đủ theo schema; nguồn unchecked/paused, check phải qua trusted checker đã cấu hình rồi approve, sau đó PATCH active. CLI chưa có checker robots/terms thật; job sẽ trả `ACCESS_CHECKER_NOT_CONFIGURED` nếu chưa nối. Không bật nguồn bằng cách sửa status trên UI.

SQLite `data/backend.db` có session/resources/revisions/jobs, proposals/events, snapshot_records, registry/contacts/audit/messages/activity. Request 401/404/422 không tạo resource/job; refresh database viewer để thấy row mới. Snapshot chỉ xuất hiện khi publication thành công, chưa có catalog dữ liệu tour thật từ crawler.
