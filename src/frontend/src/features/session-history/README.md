# features/session-history

Session lưu trên trình duyệt: tạo, đọc, sửa, xóa; UI lịch sử là sidebar duy nhất do app shell điều khiển và chuyển thành drawer trên màn hình nhỏ.

- Input: owner ID (scope tài khoản) hoặc scope ẩn danh.
- Output: `SessionHistoryPanel`, `useLocalSessions`, `useSidebarLayout`, helper/type session/access/profile. `model/access` còn sở hữu `accessFor` (bearer + dedupe inflight) và `SessionExpiredError`/`isSessionExpired` dùng chung cho mọi page.
- Workflow: `model/history` (localStorage) + `model/access` (bearer token trong sessionStorage) + `model/profile` (identity chỉ đọc) → hook `model/useLocalSessions` → `ui/SessionHistoryPanel` (`SessionHistory`/`SessionSidebar` là nội bộ của panel).
- Interface: chỉ qua barrel của slice. Storage keys (`di-cung:history:v1`, `di-cung:access:v1`, `di-cung-identity-v2`) và behavior phân scope identity được giữ nguyên. `LocalSession` chỉ giữ `id/title/pinned/createdAt/updatedAt/draft/requirementId/comparisonId`; bản lưu cũ có key thừa (proposal/job/chat/runs/...) được strip khi load, không reject session.
- Quyết định kỹ thuật: bearer token không bao giờ chạm localStorage hay dữ liệu export; tìm kiếm không dấu nằm ở `lib/normalize`. Locale/theme control không thuộc slice này: panel nhận `controls` qua props từ `app` để giữ layer boundary.
