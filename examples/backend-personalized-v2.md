# Test đủ nhu cầu cá nhân hóa — form, text và proposal

Chạy từ repo root: `uv sync`, `uv run tour-backend serve`; restart server sau sửa. Dùng `/docs`, tạo session và Authorize bằng token như [walkthrough v2](backend-v2.md). Không nhập IDs minh họa như IDs thật.

[Kết quả đã chạy và giới hạn](../docs/archive/backend-personalized-verification.md): 358 offline tests; hai input thật + follow-up minh họa đã đi qua NIM/Supabase. Comparison thành công vẫn có thể không có recommendation vì catalog thiếu proof/freshness.

## 1. Đọc contract mới

GET `/v2/catalog`: `required_by_input_kind` cho raw DTO; `required_before_confirm` cho nhu cầu đã hiểu. Form/text/hybrid cần destination/origin/date/adults/hard upper budget; URL-only không cần. Budget form là trần giá tour/VND/người lớn, không là tổng chi phí chuyến đi.

`preview.completeness.fields` tham chiếu condition_ids/clarification_ids và có status/responsibility; FE dùng conditions/party để autofill. `missing/needs_clarification` hỏi user; `unsupported` là giới hạn backend. Đọc thêm semantic issues. `can_collect_data` chỉ có scope, không cho phép tìm khi chưa đủ core. `can_confirm/can_search` vẫn cần confirmed revision/CAS/pending checks ở endpoint.

## 2. Nhật: đủ năm mục, bốn conditions + party

POST `/v2/requirements`:

```json
{"input":{"kind":"text","text":"Tôi muốn tìm tour Nhật Bản khởi hành từ Hồ Chí Minh ngày 03/11/2026, đi 1 người lớn, ngân sách tối đa 30 triệu VND mỗi người lớn cho giá tour."},"timezone":"Asia/Ho_Chi_Minh"}
```

202 → poll parse job → GET proposal. Kỳ vọng core complete, adults=1, bốn hard conditions, không condition số người thừa. Confirm bằng version thật → POST comparison bằng id/revision đã confirmed. Có core đủ không có nghĩa catalog đủ proof để recommendation: xem hard unknown/evidence/coverage.

## 3. Tết: nhận thiếu và bổ sung, không bịa defaults

Nhập câu Tết nguyên bản của nhóm. Sau parse, kỳ vọng OR Đà Nẵng/Tây Nguyên, origin Hải Phòng, main_journey motor_vehicle, join_group, route và bốn soft qualitative priorities; không tự tạo adults/budget/year. Core thiếu adults/trần ngân sách, date chưa rõ; semantic questions về năm/ý nghĩa khoảng/route được giữ.

GET proposal lấy `id`, `base_revision`, `version`, clarification IDs. POST `/v2/requirements/{rid}/proposals` với các IDs/version thật:

```json
{
  "expected_revision": 0,
  "proposal_id": "REPLACE_PROPOSAL_ID",
  "expected_proposal_version": 2,
  "input": {
    "kind": "structured",
    "edits": [
      {"op":"answer_clarification","clarification_id":"REPLACE_ADULT_QUESTION_ID","answer":{"adults":2}},
      {"op":"answer_clarification","clarification_id":"REPLACE_BUDGET_QUESTION_ID","answer":{"condition":{"id":"budget_cap","field":"estimated_cost","operator":"lte","strength":"hard","value":{"kind":"budget","amount":10000000,"currency":"VND","basis":"per_adult","coverage":"tour_price","coverage_origin":"explicit"}}}}
    ]
  }
}
```

2 người/10 triệu là **câu trả lời minh họa**, thay theo người dùng thật. Answer thêm condition dùng ID mới; sửa predicate hiện có dùng typed edits. Các answers này không gọi NIM, không bỏ soft “giá hợp lý” hoặc OR. Version tăng; dùng version mới cho lượt trả lời năm/calendar/semantics/strength tiếp theo theo [ca Tết](backend-semantic-v2.md).

Có thể trả lời bằng message: “Nhóm có 2 người lớn. Giá tour tối đa 10 triệu VND mỗi người lớn. Đi dịp Tết 2027. Đây là khoảng thời gian tôi có thể đi. Đi dọc miền Trung chỉ là ưu tiên.” Đây là input mới phải gửi vào API, không phải lời xác nhận riêng trong chat với Codex. Đọc lại proposal và kiểm preservation trước confirm.

## 4. Kiểm tra không bypass

- Xóa budget hoặc đổi hard cap thành soft → proposal chưa đủ, confirm409 với completeness/clarifications trong error.details. Discard thay đổi để khôi phục hoặc thêm cap mới.
- Chỉ “Đi Nhật” → proposal có destination, hỏi bốn mục còn thiếu, chưa confirm/search.
- Form thiếu → 201 có requirement_id/revision0/proposal_id thay cho Requirement revision1. FE phân nhánh theo revision/proposal_id, không chỉ status code201.
- URL-only → confirm/search được, không hỏi ngân sách/số người. Text + URL vẫn phải đủ core.
- Revision cũ trước policy vẫn xem được; tìm mới revalidate và có thể cần proposal bổ sung. Không sửa hoặc xóa history.

## 5. Kiểm tra catalog và regression

```powershell
uv run pytest -q
uv run ruff check src tests
uv run tour-backend audit-supabase --output data/catalog-audit.local.json
```

Audit chỉ đọc Supabase, không gọi NIM/crawler hoặc tạo SQLite. Report nêu sample/retrieval truncation, field proof/state, price qualifiers và adapter limitations. Freshness trong report là bootstrap, không mô tả registry persisted của server. Không lấy phần trăm sample làm chất lượng toàn kho nếu coverage bị cắt.

Live smoke hai câu + follow-up minh họa: `uv run python examples/check-personalized-v2.py`. Đọc `.env`, gọi NIM/Supabase thật, dùng application SQLite trong memory; không đụng `data/backend.db`. Artifacts/summary ở `data/live-tests/personalized-<timestamp>/`, không lưu token. Không gọi script này trong pytest; smoke nhỏ không đại diện accuracy tổng quát.
