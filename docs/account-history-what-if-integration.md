# Tích hợp account, history và what-if vào backend hiện tại

Đây là contract đích để port tính năng từ `origin/main`; không phải xác nhận rằng chúng đã chạy trên backend hiện tại. Runtime và model chuẩn vẫn nằm trong `src/backend`. Không thêm `src/api`, API `/v2` song song hay database catalog mới.

## Identity và phiên

- `POST /sessions` cấp guest token ngẫu nhiên, có expiry; chỉ lưu hash token.
- `/auth/*` gọi Supabase Auth qua publishable key. Backend xác minh access token với đúng Auth project trước khi xác định `owner_id`; không tin owner do client gửi.
- Không lưu password, refresh/access token hoặc provider response trong SQLite/log. Nếu cấu hình Auth chưa có, guest flow vẫn chạy và account UI báo chưa khả dụng.
- Session/revocation và application data ở SQLite. Catalog Supabase giữ read-only.

## History

- `GET /history` phân trang trong owner/session scope; `GET /history/{requirement_id}` trả requirement/comparison tham chiếu và transcript giới hạn, không trả raw DB payload.
- Rename/pin dùng `expected_version`; archive chỉ ẩn entry, không xóa evidence hay hủy job.
- Guest-to-account linking phải explicit, kiểm guest token và owner, không link khi còn job chạy; guest token bị revoke sau khi link.
- Guest records hiện có phải được giữ khi migrate SQLite. Unsent drafts ở browser; resource đã commit được backend quản lý.

## What-if

- What-if được bind vào comparison, requirement revision và policy version; thiếu/stale snapshot trả giới hạn rõ ràng.
- Phân biệt `fail → pass` với `unknown → pass`; chỉ hiển thị tỷ lệ khi có population/mẫu số hợp lệ, không diễn giải như xác suất hay nhân quả.
- Apply scenario chỉ tạo proposal. User phải review/confirm, rồi chủ động search; không sửa requirement/comparison lịch sử.

## Giữ frontend trên cùng contract

React ở `src/frontend` chỉ gọi routes trong `docs/backend-contract.md`. Mọi persistence, ownership, eligibility và trạng thái công việc do `src/backend` sở hữu. Tính năng phải được kiểm bằng TestClient/SQLite memory và frontend contract tests; không dùng fixtures để giả lập runtime.
