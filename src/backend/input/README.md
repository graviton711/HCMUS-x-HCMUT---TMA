# backend/input — text/form thành điều kiện

## Trách nhiệm

Biến một lượt nhập của user (text tự do và/hoặc form) thành `Requirement`: điều kiện cứng (so bằng code) + sở thích mềm (so bằng LLM) + slot `missing`. Không đọc catalog, không so sánh.

## Input/output

Vào: `{text?, form?}` với form (điểm đến, nơi khởi hành, ngày đi/về, ngân sách max, số khách, phương tiện, lưu trú). Ra: `Requirement` kèm quote; cái nào không parse được vào `missing`, không đoán.

## Workflow

Form map thẳng thành điều kiện cứng → text gửi NIM `extract` (prompt ở `configs/prompts/extract.yaml`, model/timeout ở `configs/settings.yaml` → `backend.nim`) → merge (form thắng khi conflict) → normalize (currency về VND, ngày về ISO) → check readiness (slot nào trong `required_slots` còn thiếu thì vào `missing`, không đoán). Không có key thì keyword offline, tên địa danh lấy từ catalog đang search (không list cứng).

## Interface với module khác

`api` gọi trước `decide`. Gọi NIM qua HTTPS (`nim.py`); không có `NVIDIA_NIM_API` thì text chỉ keyword và phần còn lại ở `missing`. Chỉ phụ thuộc `models.py`.

## Quyết định kỹ thuật

- Một prompt duy nhất, không prompt từng field: rẻ, ít chỗ hỏng.
- Form thắng text khi conflict: dữ liệu explicit hơn suy diễn.
- Không machine trạng thái hội thoại/proposal: một lượt vào, một requirement ra.
