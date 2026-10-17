# app

Bootstrap trình duyệt và lắp ghép shell. Không chứa business rule về session hay tìm kiếm.

- Input: trạng thái trình duyệt (URL, storage, khả năng kết nối backend).
- Output: các page đặt trong providers, app shell một sidebar và main canvas.
- Workflow: `main.tsx` mount providers → `App.tsx` đọc profile/sessions/saved tours/route → route `/` render sidebar cùng canvas chat + Decision Workspace; các route công khai dùng `AppHeader` + page. URL `/tours` được chuẩn hóa về `/` và giữ session. Sidebar gom nhận diện sản phẩm bằng biểu tượng độc lập, tạo phiên mới và lịch sử; header public cũng chỉ hiện biểu tượng, không đặt tên cạnh logo. Session bar mở danh mục tour đã lưu theo scope profile.
- Điều hướng client-side đặt trang mới về đầu sau khi route đã render; route có hash tiếp tục cuộn tới đúng mục. Việc đặt lại sau commit tránh giữ vị trí cuộn của tài liệu trước khi workspace đổi sang trang public.
- Header dùng chiều cao breakpoint cố định từ design tokens; không đo header đang bị ẩn rồi ghi ngược giá trị đo vào chính biến điều khiển header. Public routes dùng grid một cột vì không render sidebar; workspace routes dùng grid sidebar + canvas.
- Brand mark và favicon dùng chung SVG vector nền trong suốt `public/assets/mark.svg`; sidebar mở và public header hiển thị wordmark TourLens, rail thu gọn giữ mark.
- Interface: `src/app` export `App`. Các thành phần trong (`routing/`, `runtime/`, `shell/`) chỉ expose qua `index.ts` của chính nó.
- Quyết định kỹ thuật:
  - Routing dựa trên URL/hash, không dùng thư viện router.
  - `SessionBar` sở hữu điểm điều khiển sidebar duy nhất: collapse trên desktop, mở drawer trên mobile (qua `useIsDesktop`). Trên thanh này có lối mở danh mục tour đã lưu và hành động tạo phiên mới; trên desktop hành động tạo phiên nằm đầu sidebar, còn mobile hiển thị nút tạo mới ở thanh tiêu đề. `SessionHistoryPanel` chỉ mount sidebar desktop khi breakpoint khớp; sidebar component không render nút toggle riêng.
  - Hai nút sidebar và tour đã lưu phải nhận click chuột ở viewport fullscreen F11; vùng hit-test phải khớp bounding box của nút và không bị lớp phủ workspace che.
  - Layout state của sidebar (`useSidebarLayout`, key `di-cung:sidebar:v1`) thuộc `features/session-history` nhưng được `app` sở hữu instance và truyền xuống panel.
  - Shell không quảng bá route chưa kết nối; footer slim chỉ render ở các route public.
  - Phiên workspace có canvas chat và pane quyết định trên màn đủ rộng; tay nắm kéo đổi tỷ lệ hai pane, lưu tùy chọn và hỗ trợ bàn phím. Nội dung quyết định co theo pane, không cuộn ngang và chỉ có một vùng cuộn dọc; mobile chuyển giữa tab hội thoại và quyết định, composer luôn khả dụng. Cả hai dùng chung art direction, typography và token; không ghi đè palette/font tại shell.
  - Style nằm ở `shell/AppShell.module.css` và dùng token từ `shared/styles`; giữ điểm điều khiển sidebar duy nhất cùng responsive behavior hiện có. `MotionConfig` dùng reduced-motion preference của hệ thống cho animation Framer Motion.
