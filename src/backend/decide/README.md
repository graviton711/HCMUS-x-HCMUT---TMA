# backend/decide — lọc, chấm, rank, phân tích

## Trách nhiệm

Toàn bộ luồng compare: lọc cứng pool → LLM chấm trường mềm trên survivors → rank → phân tích (chi phí ẩn, điều kiện, rủi ro, quyền lợi). Không lưu trữ, không HTTP.

## Input/output

Vào: `Requirement` + list `TourSnapshot` + hook LLM. Ra: `Comparison` gồm rank candidate ids, snapshot đầy đủ của candidates, chấm `pass`/`fail`/`unknown` từng offer kèm evidence, và `Analysis` chi phí/điều kiện/rủi ro/quyền lợi. Snapshots được lưu cùng comparison để detail/history render lại đúng dữ kiện đã chấm. Unknown không pass, không rank trên pass cứng.

## Workflow

`hard_filter`: mọi điều kiện cứng đánh giá trên từng offer. Destination match bỏ origin endpoints; destination thiếu/partial là unknown. Giá chỉ so khi fresh, trusted, exact, cùng currency/basis; giá `from` chỉ fail nếu lower bound đã vượt trần, nếu không unknown. `any` khớp ít nhất một lựa chọn → chỉ các tour còn offer không fail vào `assess_soft`: một call LLM cho pool survivors (prompt ở `configs/prompts/assess.yaml`, excerpt/quote theo `backend.decide` trong `configs/settings.yaml`), chấm itinerary/inclusions/exclusions/child/cancellation kèm quote → `rank`: hard status trước, rồi điểm mềm, rồi giá → `analyze`: khui surcharges, điều kiện, rủi ro availability/verification và quyền lợi matched từ text snapshot.

## Interface với module khác

`api` gọi. Đọc rows qua `data`, đổi qua `normalize`, parse user qua `input`. LLM qua `assess_fn` inject; không có thì mềm ở `unknown` và rank bằng cứng + giá.

## Quyết định kỹ thuật

- Cứng trước mềm sau, luôn: pool LLM nhỏ, chi phí chặn trên (`candidate_limit`, excerpt caps).
- Chấm theo offer, không theo tour: tour pass chỉ qua offer pass của nó.
- Không chạy soft assessment cho tour đã bị loại bởi hard filter; khi một tour có nhiều offer, chỉ gửi một snapshot mỗi tour.
- Một call LLM mỗi comparison, không phải mỗi candidate: ít hỏng, merge deterministic.
- What-if chưa có runtime; khi port phải chạy trên snapshot/revision đã lưu, apply chỉ tạo proposal và search tiếp cần user confirm tường minh.
