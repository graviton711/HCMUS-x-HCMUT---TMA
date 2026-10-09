# Phân công và quy ước làm việc

## Người phụ trách chính

| Phần | Owner chính | Trách nhiệm |
|---|---|---|
| Crawl và data | **Thái Sơn** | Khảo sát nguồn, trích xuất/làm sạch data, giữ provenance; báo backend các field còn thiếu hoặc nguồn không lấy được. |
| Backend | **Minh Khôi** | 4 module `src/backend` (data/input/normalize/decide) + `api` mỏng, theo [backend contract](backend-contract.md). |
| Frontend | **Minh Phú** | Luồng nhập, giao diện kết quả, dữ liệu thiếu, trade-off và evidence; bám contract backend. |

Owner chính chịu trách nhiệm tích hợp phần của mình; cả ba vẫn review và hỗ trợ chéo.

## Quy ước docs

- Tài liệu chung của pipeline nằm ở `docs/` (kiến trúc, data/crawler/backend contract, idea, scope, provider-registry, workflow).
- Mỗi module chỉ có đúng một `README.md` bên trong: trách nhiệm, input/output, workflow, interface, quyết định kỹ thuật.
- Không thư mục `contracts/`, `examples/`: schema live ở `/openapi.json` và `src/backend/models.py`; payload mẫu nằm inline trong tests; walkthrough ở `README.md` và contract từng module.

## Git và tích hợp

- Dùng `main` làm nhánh tích hợp; tránh nhánh sống lâu, merge sớm và thường xuyên.
- Tạo branch ngắn theo đầu việc, ví dụ `feat/compare_api`.
- Mở PR nhỏ vào `main`, review và chạy test/lint trước khi merge.
- Đổi request/response hoặc field thì cập nhật contract và báo bên còn lại trước khi merge.
- Không commit secrets, database, reports hay artifacts local (xem `.gitignore`).
