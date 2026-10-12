# app

Bootstrap trình duyệt và lắp ghép shell. Không chứa business rule về session hay tìm kiếm.

- Input: trạng thái trình duyệt (URL, storage, khả năng kết nối backend).
- Output: các page đặt trong providers, app shell một sidebar và main canvas.
- Workflow: `main.tsx` mount providers → `App.tsx` đọc profile/sessions/route → với workspace, render sidebar điều hướng cùng canvas chat; các route công khai dùng `AppHeader` + page. Sidebar gom nhận diện sản phẩm bằng biểu tượng độc lập, tạo phiên mới và lịch sử; header public cũng chỉ hiện biểu tượng, không đặt tên cạnh logo. Canvas giữ tiêu đề phiên, hội thoại và composer.
- Điều hướng client-side đặt trang mới về đầu sau khi route đã render; route có hash tiếp tục cuộn tới đúng mục. Việc đặt lại sau commit tránh giữ vị trí cuộn của tài liệu trước khi workspace đổi sang trang public.
- Header dùng chiều cao breakpoint cố định từ design tokens; không đo header đang bị ẩn rồi ghi ngược giá trị đo vào chính biến điều khiển header. Public routes dùng grid một cột vì không render sidebar; workspace routes dùng grid sidebar + canvas.
- Brand mark và favicon dùng chung SVG vector nền trong suốt `public/assets/mark.svg`, vẽ lại biểu tượng định vị/ống kính theo `public/assets/brand.png`; không có ô nền vuông, wordmark hoặc slogan cạnh logo.
- Interface: `src/app` export `App`. Các thành phần trong (`routing/`, `runtime/`, `shell/`) chỉ expose qua `index.ts` của chính nó.
- Quyết định kỹ thuật:
  - Routing dựa trên URL/hash, không dùng thư viện router.
  - `SessionBar` sở hữu điểm điều khiển sidebar duy nhất: collapse trên desktop, mở drawer trên mobile (qua `useIsDesktop`). Hành động tạo phiên mới nằm đầu sidebar desktop; trên mobile nó hiện trong thanh tiêu đề vì sidebar desktop bị ẩn. `SessionHistoryPanel` chỉ mount sidebar desktop khi breakpoint khớp; sidebar component không render nút toggle riêng.
  - Layout state của sidebar (`useSidebarLayout`, key `di-cung:sidebar:v1`) thuộc `features/session-history` nhưng được `app` sở hữu instance và truyền xuống panel.
  - Shell không quảng bá route chưa kết nối; footer slim chỉ render ở các route public.
  - Workspace dùng bố cục dashboard: sidebar cố định, canvas sáng thoáng, nội dung chat căn theo trục và composer ghim đáy. Typography, viền, surface và trạng thái tương tác dùng chung tokens để tạo hệ thống nhất quán.
  - Style nằm ở `shell/AppShell.module.css` và dùng token từ `shared/styles`; giữ điểm điều khiển sidebar duy nhất cùng responsive behavior hiện có. Chuyển động ngắn tôn trọng reduced motion.
