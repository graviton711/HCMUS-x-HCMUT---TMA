# backend/input — text/form thành điều kiện

## Trách nhiệm

Biến một lượt nhập của user (text tự do và/hoặc form) thành `Requirement`: điều kiện cứng (so bằng code) + sở thích mềm (so bằng LLM) + slot `missing`. Không đọc catalog, không so sánh.

## Input/output

Vào: `{text?, form?, drop_fields?}` với form (điểm đến, nơi khởi hành, ngày đi/về, ngân sách max, số khách, phương tiện, lưu trú). Ra: `Requirement` kèm quote; cái nào không parse được vào `missing`, không đoán. `drop_fields` loại field cứng khỏi form, text và `missing` (dùng cho nới điều kiện).

## Workflow

Form map thẳng thành điều kiện cứng → text gửi NIM `extract` (prompt ở `configs/prompts/extract.yaml`, model/timeout ở `configs/settings.yaml` → `backend.nim`) → merge (form thắng khi conflict) → normalize (currency về VND, ngày về ISO) → check readiness (slot nào trong `required_slots` còn thiếu thì vào `missing`, không đoán). Ngày âm lịch được đổi sang dương lịch bằng `vi_lunaire` sau khi kiểm tra round-trip; NIM chỉ nhận ngày tham chiếu và mốc Tết đã tính sẵn, không tự tính lịch. Điều kiện nhiều lựa chọn dùng operator `any`; singleton được chuẩn hóa về `contains`. Ngân sách do NIM trả về chỉ được nhận khi câu nhập có chữ số tường minh. Không có key thì keyword offline, tên địa danh lấy từ catalog đang search (không list cứng).

## Interface với module khác

`api` gọi trước `decide`. Gọi NIM qua HTTPS (`nim.py`); không có `NVIDIA_NIM_API` thì text chỉ keyword và phần còn lại ở `missing`. Chỉ phụ thuộc `models.py`.

## Quyết định kỹ thuật

- Một prompt duy nhất, không prompt từng field: rẻ, ít chỗ hỏng.
- Form thắng text khi conflict: dữ liệu explicit hơn suy diễn.
- Không machine trạng thái hội thoại/proposal: một lượt vào, một requirement ra.
- Lịch âm luôn tính bằng thư viện xác định; output của mô hình chỉ cung cấp thành phần năm/tháng/ngày để validate và resolve.
- Nhiều lựa chọn trong cùng một field được giữ thành một condition OR, không bị hiểu nhầm thành nhiều điều kiện AND.
