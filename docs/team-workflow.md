# Phân công và quy ước làm việc

## Người phụ trách chính

| Phần | Owner chính | Trách nhiệm |
|---|---|---|
| Crawl và data | **Thái Sơn** | Khảo sát nguồn, trích xuất/làm sạch data, giữ provenance; báo backend các field còn thiếu hoặc nguồn không lấy được. |
| Backend | **Minh Khôi** | API, chuẩn hóa đầu vào, logic so sánh và trade-off; làm trước bằng fixture theo [data contract](data-contract.md). |
| Frontend | **Minh Phú** | Luồng nhập URL, giao diện kết quả, dữ liệu thiếu, trade-off và evidence; bắt đầu bằng response fixture theo contract. |

Owner chính chịu trách nhiệm tích hợp phần của mình; cả ba vẫn review và hỗ trợ chéo. Không cần chờ crawler hoàn tất mới bắt đầu backend/frontend.

## Git và tích hợp

- Dùng `main` làm nhánh tích hợp; tránh nhánh sống lâu, merge sớm và thường xuyên.
- Tạo branch ngắn theo đầu việc, ví dụ `feat/supplier_crawler_agent`, `feature/minh-phu`, `feat/compare_api`.
- Mở PR nhỏ vào `main`, review và chạy test/lint trước khi merge. Trong lúc làm, cập nhật branch từ `main` thường xuyên để tránh phát triển trên bản cũ.
- Frontend và backend dùng chung contract; nếu cần đổi request/response hoặc field, cập nhật contract và báo bên còn lại trước khi merge.
