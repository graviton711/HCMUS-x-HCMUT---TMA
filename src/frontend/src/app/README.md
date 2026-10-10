# app

Bootstrap trình duyệt và lắp ghép shell. Không chứa business rule về session hay tìm kiếm.

- Input: trạng thái trình duyệt (URL, storage, khả năng kết nối backend).
- Output: các page đặt trong providers, navigation, header/footer.
- Workflow: `main.tsx` mount providers → `App.tsx` đọc profile/sessions/route → render shell + page đang active.
- Interface: `src/app` export `App`. Các thành phần trong (`routing/`, `runtime/`, `shell/`) chỉ expose qua `index.ts` của chính nó.
- Quyết định kỹ thuật: routing dựa trên URL/hash, không dùng thư viện router; style của shell nằm ở `shell/AppShell.module.css`.
