# backend/decide — eligibility và decision views

## Trách nhiệm

Đánh giá hard conditions một cách xác định; kiểm tra soft verdict/evidence từ agent; tính điểm ưu tiên minh bạch; tạo cheapest, best-fit và balanced Pareto views.

## Input/output

Vào: requirement đã validate, tour snapshots, soft verdict map `(offer_id, condition_id) -> verdict/quote/reason`. Ra: hard/soft evaluations, `ranked`, `near_miss`, tối đa 5 lựa chọn mỗi `decision_view`, snapshots, evidence và số candidate đã quét.

## Workflow

1. Hard filter chạy trước; chỉ offers pass toàn bộ hard conditions vào soft evaluation.
2. Xác thực quote khớp snapshot. `unknown` giữ nguyên trạng thái và không đóng góp vào điểm; chỉ verdict `pass` cộng `weight_percent`.
3. Cheapest sắp exact-price candidates theo giá trong từng currency riêng; nếu giá bằng nhau thì ưu tiên weighted fit cao hơn rồi dùng ID ổn định. `from`, `contact`, thiếu giá bị loại khỏi kết luận cheapest.
4. Best-fit sắp tổng trọng số pass giảm dần, với tie-break ổn định theo giá/currency rồi ID.
5. Balanced trả Pareto frontier giữa giá exact thấp và điểm best-fit cao trong từng currency. Candidate thiếu exact price không bị giả định có giá; có thể trình bày như dữ liệu chưa đủ để so.
6. Trả danh sách view giới hạn tối đa 5, nhưng giữ đủ evaluations trong dữ liệu cần cho explanations và compatibility fields.

## Interface với module khác

`workflows.py` truyền snapshots đã normalize; MCP/service điều phối batch và gọi engine. Engine không truy cập HTTP, storage, catalog trực tiếp hay LLM.

## Quyết định kỹ thuật

- Trọng số chỉ đổi thứ tự/view, không thay eligibility.
- Điểm phù hợp là tổng các weight pass (0–100), không phải xác suất/confidence.
- Multi-currency không quy đổi; cheapest/Pareto được nhóm currency-wise.
- Tie-break dùng khóa xác định để kết quả ổn định.
- `ranked`/`near_miss` được giữ cho consumer cũ.
