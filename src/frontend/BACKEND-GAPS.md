# Tình trạng tích hợp frontend/backend

Frontend được chuyển từ `main`; runtime backend chuẩn là `src/backend`, không phải `src/api/v2`. Bảng này phân biệt implementation hiện có và phần cần port.

| Năng lực | Backend hiện tại | Hướng tích hợp |
|---|---|---|
| Requirements/comparisons | Đồng bộ, SQLite session records, API `/requirements` và `/comparisons` | Giữ routes/models hiện tại làm lõi |
| Catalog/options | `GET /catalog` trả destinations cơ bản | Port richer catalog DTO qua `backend.api`, không cho FE truy cập DB |
| Guest/account identity | Guest session token hash/expiry và owner scope đã có | Auth adapter Supabase optional; không tin owner ID từ client |
| Proposals/revisions/history | Guest history list/detail và cursor có; chưa có CAS/transcript/archive/linking | Port vào `backend.data.sessions` và `backend.input`; guest records phải được giữ |
| Jobs/events/cancel | Comparison chạy đồng bộ | Tách job orchestration trong backend khi cần; không đổi kết quả đã lưu |
| What-if/evidence/messages | Chưa có routes/resource persistence | Port vào `backend.decide`/`backend.data`, bind vào snapshot/revision |
| Pricing/freshness validation | Normalizer cơ bản; offer DB metadata chưa được đọc đầy đủ | Kiểm tra trong `backend.normalize`, giữ stale/invalid là unknown |

Cho tới khi toàn bộ DTO/flow được port và có contract test dùng FastAPI thật, React UI vẫn chưa end-to-end với backend: client hiện gọi `/v2`, trong khi runtime giữ routes hiện tại và DTO khác. Account, proposals, jobs, what-if/evidence/messages chưa có runtime. Không thay thế bằng fixture hoặc fallback im lặng.
