# Phân công và quy ước làm việc

## Người phụ trách chính

| Phần | Owner chính | Trách nhiệm |
|---|---|---|
| Crawl và data | **Thái Sơn** | Khảo sát nguồn, trích xuất/làm sạch data, giữ provenance; báo backend các field còn thiếu hoặc nguồn không lấy được. |
| Backend | **Minh Khôi** | API, chuẩn hóa đầu vào, logic so sánh và trade-off; fixture/HTTP runtime theo [API v1](api-contract.md), [domain](backend-contracts.md) và [crawler contract](crawler-contract.md). |
| Frontend | **Minh Phú** | Hai luồng nhu cầu/URL, kết quả, dữ liệu thiếu, trade-off và evidence; review flow/public response fixtures theo [planning](frontend-plan.md). |

Owner chính chịu trách nhiệm tích hợp phần của mình; cả ba vẫn review và hỗ trợ chéo. Không cần chờ crawler hoàn tất mới bắt đầu backend/frontend.

## Git và tích hợp

**Quy tắc riêng cho checkout/task của Minh Phú:** Theo yêu cầu ngày 03/10/2026, chỉ sửa/commit/push trên `feature/minh-phu`; nhánh backend/crawler/main chỉ fetch và tham khảo, merge về nhánh Minh Phú khi cần. Quy tắc này ưu tiên hơn quy ước branch chung bên dưới; không tự mở nhánh khác hoặc chỉnh nhánh của thành viên khác. Xem [AGENTS.md](../AGENTS.md).

- Dùng `main` làm nhánh tích hợp; không giữ nhánh `backend`/`frontend` sống lâu.
- Tạo branch ngắn theo đầu việc, dùng `_` để phân tách từ, ví dụ `feat/compare_api`, `feat/comparison_ui`, `feat/tour_data`.
- Mở PR nhỏ vào `main`, review và chạy test/lint trước khi merge. Trong lúc làm, cập nhật branch từ `main` thường xuyên để tránh phát triển trên bản cũ.
- Frontend và backend dùng chung contract; nếu cần đổi request/response hoặc field, cập nhật contract và báo bên còn lại trước khi merge.
