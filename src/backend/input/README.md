# backend/input — validate điều kiện có cấu trúc

## Trách nhiệm

Chuẩn hóa và kiểm tra `Requirement` có cấu trúc do agent tools gửi. Không trích điều kiện từ câu tự do, không đọc catalog và không so sánh.

## Input/output

Vào: điều kiện JSON có field/operator/value/strength/quote đã được agent xác định. Ra: `Requirement` hợp lệ. Tiền chỉ là integer VND; ngày chỉ là ISO dương lịch; dữ liệu lỗi định dạng bị từ chối hoặc trở thành `unknown`, không tự quy đổi/đoán. Lunar date được chuyển đổi riêng qua tool `clarify_date`.

## Workflow

Agent gửi điều kiện đã cấu trúc tới tool; validator kiểm tra field/operator/value và giữ quote làm chứng cứ cho nguồn user. Điều kiện nhiều lựa chọn dùng operator `any`. `clarify_date` dùng `vi_lunaire` và kiểm tra round-trip trước khi trả ISO. `relax_criterion` xóa đúng một hard condition rồi chạy lại hard filter.

## Interface với module khác

Agent MCP tools gọi validator trước `decide`; không có keyword parser hoặc NIM extraction fallback. Chỉ phụ thuộc `models.py` và lunar calendar helper.

## Quyết định kỹ thuật

- Không trích xuất điều kiện bằng regex, từ khóa hoặc LLM phụ; agent là hội thoại và công cụ là ranh giới dữ liệu có cấu trúc.
- Chỉ chấp nhận tiền VND dạng integer và ngày ISO; không có heuristic đổi đơn vị/định dạng.
- Lịch âm được tính bằng thư viện xác định và kiểm tra round-trip.
- Nhiều lựa chọn trong cùng một field là một condition OR (`any`).
