# features/session-history

Session lưu trên trình duyệt: tạo, đọc, sửa, xóa; UI lịch sử là sidebar duy nhất do app shell điều khiển và chuyển thành drawer trên màn hình nhỏ.

- Input: owner ID (scope tài khoản) hoặc scope ẩn danh.
- Output: `SessionHistoryPanel`, `useLocalSessions`, `useSidebarLayout`, helper/type session/access/profile. `model/access` còn sở hữu `accessFor` (bearer + dedupe inflight) và `SessionExpiredError`/`isSessionExpired` dùng chung cho mọi page.
- Workflow: `model/history` (localStorage) + `model/access` (bearer token trong sessionStorage) + `model/profile` (identity chỉ đọc) → hook `model/useLocalSessions` → `ui/SessionHistoryPanel` (`SessionHistory`/`SessionSidebar` là nội bộ của panel). Panel chỉ mount `SessionSidebar` ở desktop; mobile dùng dialog drawer. Callback tạo phiên mới được chuyển vào sidebar.
- Trình bày: sidebar theo bố cục điều hướng gọn kiểu workspace: logo dạng biểu tượng độc lập và hành động tạo mới ở trên, tìm kiếm cùng lịch sử ở giữa, thông tin tài khoản/cài đặt ghim sát đáy trên cùng một hàng với lề dưới 8px; phiên hiện tại dùng nền chọn nhẹ. Drawer mobile giữ footer cố định ngoài vùng cuộn danh sách. Sidebar/drawer có chuyển động vào nhẹ và tôn trọng reduced motion.
- Interface: chỉ qua barrel của slice. Storage keys (`di-cung:history:v1`, `di-cung:access:v1`, `di-cung-identity-v2`) và behavior phân scope identity được giữ nguyên. `LocalSession` giữ metadata/draft, ID backend và transcript chat đã hoàn tất để phục hồi sau reload; access token vẫn chỉ ở `sessionStorage`. Bản lưu cũ có key thừa (proposal/job/chat/runs/...) được strip khi load, không reject session.
- Quyết định kỹ thuật: bearer token không bao giờ chạm localStorage hay dữ liệu export; tìm kiếm không dấu nằm ở `lib/normalize`. Locale/theme control không thuộc slice này: panel nhận `controls` qua props từ `app` để giữ layer boundary.
