# Test extraction semantic v2 — ca tour Tết

## Khởi động

Từ repo root, dừng server đang chạy bằng Ctrl+C trước `uv sync` (Windows có thể khóa `tour-backend.exe` khi server chưa dừng):

```powershell
uv sync
uv run tour-backend serve
```

Mở `http://127.0.0.1:8000/docs`. Tạo nhu cầu mới để test parser mới; response/proposal cũ không tự được parse lại.

## Tạo và đọc bản trích xuất

1. POST `/v2/sessions` với `{}`. Copy `data.token` vào Authorize → SessionBearer.
2. POST `/v2/requirements`:

```json
{
  "input": {
    "kind": "text",
    "text": "Tết Nguyên đán năm nay e dự định đi du lịch ghép đoàn bằng xe ô tô từ Hải Phòng đi dọc miền trung vào Đà Nẵng hoặc Tây Nguyên.\nCty nào uy tín và dv tốt, giá hợp lý, tour có các điểm đẹp gần gũi thiên nhiên e tham khảo ạ.\nTừ 27/12 âm đến mùng 4 Tết ạ."
  },
  "timezone": "Asia/Ho_Chi_Minh"
}
```

3. Copy `requirement_id`, `proposal_id`, `job_id` thực từ response. GET `/v2/jobs/{job_id}` đến `succeeded`/`failed`. Nếu failed thì đọc `error`; không confirm proposal đang parse/lỗi. Parser chỉ repair một lần, không trả bản thiếu ý giả thành công.
4. GET `/v2/proposals/{proposal_id}`. Đọc `data.preview.conditions`, `clarifications`, `issues` và `readiness`.

Kỳ vọng semantic (không so exact IDs hoặc câu hỏi):

| Phần | Kết quả |
|---|---|
| Hải Phòng | `departure_origin`, entities → `city:vn:haiphong` |
| Đà Nẵng hoặc Tây Nguyên | Một `destinations/contains_any`, hai members giữ nguyên OR |
| Ô tô từ Hải Phòng | `transport/in`, `motor_vehicle`, scope `main_journey` |
| Ghép đoàn | `tour_type/in`, `join_group` |
| Đi dọc miền Trung | `route`, scope `itinerary`, hỏi bắt buộc hay ưu tiên |
| Uy tín, dv tốt, giá hợp lý, thiên nhiên | Bốn conditions soft riêng; không sinh ngân sách hoặc slider |
| Hai mốc Tết | `temporal`, lịch âm, cùng group; thiếu năm và ý nghĩa khoảng còn ambiguous |

Tổng 11 conditions, bốn soft ở câu gốc. Chỉ hỏi một lần năm Tết và một lần semantics của khoảng; không hỏi lại nơi đã nói. Ba metric uy tín/dịch vụ/value-for-money hiện là backend issue không blocking vì soft; nature chờ fact itinerary có evidence.

## Trả lời câu hỏi — bản typed kiểm chứng được

Bạn đã chốt đây là khoảng có thể đi. **2027 dưới đây chỉ là năm giả định để test**, không phải backend tự chọn năm người dùng muốn.

5. Copy IDs thật từ `data.clarifications`: DATE_YEAR_REQUIRED, TEMPORAL_SEMANTICS_REQUIRED, CONDITION_STRENGTH_REQUIRED của route. POST `/v2/requirements/{requirement_id}/proposals`:

```json
{
  "expected_revision": 0,
  "proposal_id": "THAY_BANG_PROPOSAL_ID_THAT",
  "expected_proposal_version": 2,
  "input": {
    "kind": "structured",
    "edits": [
      {"op": "answer_clarification", "clarification_id": "Q_NAM_THAT", "answer": {"holiday_year": 2027}},
      {"op": "answer_clarification", "clarification_id": "Q_KHOANG_THAT", "answer": {"semantics": "availability"}},
      {"op": "answer_clarification", "clarification_id": "Q_ROUTE_THAT", "answer": "soft"}
    ]
  }
}
```

`expected_proposal_version` phải lấy `data.version` mới nhất, không mặc định 2. Nếu input đã thêm câu “Đây là khoảng thời gian tôi có thể đi” thì không còn Q_KHOANG, bỏ edit đó. Nếu muốn route bắt buộc, answer `hard`. Không gửi IDs mẫu hoặc question cũ; CAS/stale answer trả 409.

Có thể thử cùng nội dung bằng `input: {"kind":"message","text":"Tết 2027. Đây là khoảng thời gian tôi có thể đi. Đi dọc miền Trung chỉ là ưu tiên."}` với version mới nhất; chờ parse job rồi GET proposal. Bản typed không cần gọi NIM.

6. Kiểm tra hai mốc cập nhật cùng nhau: departure_date `gte 2027-02-03`, return_date `lte 2027-02-09`; năm âm đầu 2026, năm âm cuối 2027. Các nhu cầu khác vẫn còn. `readiness.status=ready` khi không còn câu hỏi/issue blocking.
7. POST `/v2/proposals/{proposal_id}/confirm` với `expected_revision:0` và `expected_proposal_version` mới nhất. GET requirement phải có revision 1 và values/trace đã lưu. Confirm không tự tạo comparison.

## Test và tích hợp

```powershell
uv run pytest -q
uv run ruff check src tests
uv run tour-backend evaluate-nim-v2 --repeat 2
uv run tour-backend export-schemas
```

`evaluate-nim-v2` gọi model NVIDIA thật và lưu report local trong `data/`, không ghi DB. Fixture smoke gồm câu gốc/clarified/paraphrase/partial OR/hard metric; kết quả không đại diện accuracy toàn bộ tiếng Việt. Report local có nội dung fixture và diagnostics; không đưa file chứa dữ liệu riêng lên Git.

Frontend: render theo `value.kind`: entities (từng member resolved/catalog_missing), temporal (raw + ISO/reason/semantics), qualitative (ý muốn + trạng thái đánh giá); hiển thị issues khác clarifications. Đọc operators/taxonomy từ `/v2/catalog`, giữ revision/proposal version khi gửi answer.

Crawler: request HTTP còn theo `CrawlRequest` v1. Response extension [CrawlResultV2](../contracts/v2/CrawlResultV2.schema.json) nhận `semantic_fields` tour_type/route/nature; mỗi Fact phải có evidence cùng snapshot, scope đúng. `transport.scope=main_journey` cần evidence hành trình chính, xe đưa đón không đủ. Adapter giữ marker cho phần không pushdown an toàn; crawler không được tự thu hẹp OR hoặc bỏ marker khi báo coverage.

Runtime fixture mặc định vẫn là tour Nhật/Hàn mô phỏng, **không có tour Việt Nam phù hợp ca Tết**. Không có kết quả tour lúc này không chứng minh extraction sai. Ca đánh giá Việt Nam end-to-end nằm trong offline tests; tour/giá/uy tín thật cần nguồn crawler và policy riêng.
