# pages/workspace

Màn hình tìm kiếm/so sánh tour của guest và vòng đời request riêng của page.

- Input: `LocalSession` đang active, profile, các callback session từ `app`.
- Output: toolbar workspace + empty state hoặc `CurrentWorkspace`.
- Workflow: `WorkspacePage` (shell) → `CurrentWorkspace` (lắp ghép) → `RequirementForm` / `RequirementView` / `ComparisonView`; state lấy từ `model/useCurrentWorkspace`. Style toolbar/content/empty-state nằm ở `ui/WorkspacePage.module.css`.
- Interface: `src/pages/workspace` export `WorkspacePage`, `CurrentWorkspace`. `model/` và `lib/` là nội bộ (`lib/form` map draft sang field backend và chặn tiêu chí chưa hỗ trợ; `lib/access` resolve bearer access).
- Quyết định kỹ thuật: mapping field backend nằm ở `lib/`, không bao giờ nằm trong UI component.
