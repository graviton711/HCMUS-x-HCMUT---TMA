# app

Bootstrap trình duyệt và lắp ghép shell. Không chứa business rule về session hay tìm kiếm.

- Input: trạng thái trình duyệt (URL, storage, khả năng kết nối backend).
- Output: các page đặt trong providers, app shell một sidebar và main canvas.
- Workflow: `main.tsx` mount providers → `App.tsx` đọc profile/sessions/route → render `AppHeader` + sidebar + session bar + page đang active.
- Interface: `src/app` export `App`. Các thành phần trong (`routing/`, `runtime/`, `shell/`) chỉ expose qua `index.ts` của chính nó.
- Quyết định kỹ thuật:
  - Routing dựa trên URL/hash, không dùng thư viện router.
  - `SessionBar` sở hữu điểm điều khiển sidebar duy nhất: collapse trên desktop, mở drawer trên mobile (qua `useIsDesktop`). Sidebar component không render nút toggle riêng.
  - Layout state của sidebar (`useSidebarLayout`, key `di-cung:sidebar:v1`) thuộc `features/session-history` nhưng được `app` sở hữu instance và truyền xuống panel.
  - Shell không quảng bá route chưa kết nối; footer slim chỉ render ở các route public.
  - Style nằm ở `shell/AppShell.module.css` chuẩn Calm Density.
