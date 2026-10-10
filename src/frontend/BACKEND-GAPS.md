# Tình trạng tích hợp frontend/backend

Frontend được chuyển từ `main`; runtime backend chuẩn là `src/backend`, không phải `src/api/v2`. Bảng này phân biệt implementation hiện có và phần cần port.

| Năng lực | Backend hiện tại | Hướng tích hợp |
|---|---|---|
| Requirements/comparisons | Guest workspace gọi API hiện tại; diễn giải, so sánh đồng bộ và render candidate snapshots đã lưu | Port richer DTO, explicit revisions/proposals và các tiêu chí còn thiếu |
| Catalog/options | `GET /catalog` trả destinations cơ bản | Port richer catalog DTO qua `backend.api`, không cho FE truy cập DB |
| Guest/account identity | Guest session token hash/expiry và owner scope đã có | Auth adapter Supabase optional; không tin owner ID từ client |
| Proposals/revisions/history | Guest history list/detail và cursor có; chưa có CAS/transcript/archive/linking | Port vào `backend.data.sessions` và `backend.input`; guest records phải được giữ |
| Jobs/events/cancel | Comparison chạy đồng bộ | Tách job orchestration trong backend khi cần; không đổi kết quả đã lưu |
| What-if/evidence/messages | Chưa có routes/resource persistence | Port vào `backend.decide`/`backend.data`, bind vào snapshot/revision |
| Pricing/freshness validation | Normalizer cơ bản; offer DB metadata chưa được đọc đầy đủ | Kiểm tra trong `backend.normalize`, giữ stale/invalid là unknown |

Guest search flow đã nối end-to-end với current backend qua DTO riêng (không gọi `/v2`): guest session, catalog destinations, requirement, comparison và owner-scoped resource reads. Các màn/account utilities còn sót từ `main` chưa được xem là runtime: Auth, rename/archive account history, proposals, jobs, what-if/evidence/messages/contact vẫn chưa được port. Không thay thế bằng fixture hoặc fallback im lặng.
