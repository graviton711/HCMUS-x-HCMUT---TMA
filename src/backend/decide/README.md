# backend/decide — lọc, chấm, rank, phân tích

## Trách nhiệm

Toàn bộ luồng compare: lọc cứng pool → LLM chấm trường mềm trên survivors → rank → phân tích (chi phí ẩn, điều kiện, rủi ro, quyền lợi). Không lưu trữ, không HTTP.

## Input/output

Vào: `Requirement` + list `TourSnapshot` + hook LLM. Ra: `Comparison` gồm rank candidate ids, chấm `pass`/`fail`/`unknown` từng offer kèm evidence, và `Analysis` chi phí/điều kiện/rủi ro/quyền lợi. Unknown không pass, không rank trên pass cứng.

## Workflow

`hard_filter`: mọi điều kiện cứng phải pass trên từng offer (ngân sách chỉ so giá exact cùng currency; giá "from" → `unknown`; destination thiếu → `unknown`; `any` khớp ít nhất một lựa chọn) → chỉ các tour còn offer qua hard filter mới vào `assess_soft`: một call LLM cho pool survivors (prompt ở `configs/prompts/assess.yaml`, excerpt/quote theo `backend.decide` trong `configs/settings.yaml`), chấm itinerary/inclusions/exclusions/child/cancellation kèm quote → `rank`: pass cứng trước, rồi điểm mềm, rồi giá → `analyze`: khui surcharges, điều kiện, rủi ro availability/verification và quyền lợi matched từ text snapshot (top_n, độ dài, risk_words cũng từ `backend.decide`).

## Interface với module khác

`api` gọi. Đọc rows qua `data`, đổi qua `normalize`, parse user qua `input`. LLM qua `assess_fn` inject; không có thì mềm ở `unknown` và rank bằng cứng + giá.

## Quyết định kỹ thuật

- Cứng trước mềm sau, luôn: pool LLM nhỏ, chi phí chặn trên (`candidate_limit`, excerpt caps).
- Chấm theo offer, không theo tour: tour pass chỉ qua offer pass của nó.
- Không chạy soft assessment cho tour đã bị loại bởi hard filter; khi một tour có nhiều offer, chỉ gửi một snapshot mỗi tour.
- Một call LLM mỗi comparison, không phải mỗi candidate: ít hỏng, merge deterministic.
- What-if chạy trên comparison/revision đã lưu, trả trạng thái/result có binding; apply chỉ tạo proposal. Search tiếp theo cần user confirm tường minh.
