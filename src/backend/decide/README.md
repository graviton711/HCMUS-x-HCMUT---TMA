# backend/decide — hard filter, soft verdicts, ranking

## Trách nhiệm

Áp hard rules xác định trên từng offer; giữ nguyên reason codes, freshness/trust gates, near-miss và phân tích dữ kiện tour. Sau hard pass, áp verdict mềm do agent gửi và xếp theo số `fit`, rồi giá exact VND.

## Input/output

Vào: `Requirement`, snapshots đã normalize và verdict map `(offer_id, condition_id) → (pass|unknown|fail, quote, reason)`. Ra: `Comparison` gồm hard/soft evaluations, ranked hard-pass offers, near-miss, snapshots và analysis. `unknown` không bao giờ được tính là hard pass.

## Workflow

`hard_filter` đánh giá mọi hard condition. `passing_offers` chỉ nhận offer nếu tất cả điều kiện hard đều `pass`; unknown và fail đều bị loại khỏi ranked. `score_soft` chỉ chấm offer trong tập này; quote sai hoặc thiếu được thay bằng unknown trước khi gọi `compare`. `rank` đếm soft `pass`, tie-break bằng giá exact; `near_miss` giữ riêng offer fail ít điều kiện hoặc còn unknown; `analyze` tóm tắt phụ phí, điều khoản, rủi ro và quyền lợi.

## Interface với module khác

`workflows.py` cung cấp snapshots từ `data` qua `normalize`. MCP `query_tours`, `score_soft` và `relax_criterion` gọi engine; engine không truy cập HTTP, catalog, storage hay LLM.

## Quyết định kỹ thuật

- Không còn 0–1 score hoặc LLM callback trong engine.
- Không chấm mềm cho offer có bất kỳ hard condition nào chưa được chứng minh là pass.
- Near-miss không trộn vào ranked; mọi kết quả giữ condition state, reason code và source quote.
