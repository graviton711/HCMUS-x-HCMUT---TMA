# pages/workspace (legacy)

Màn hình form/so sánh cũ, route `/tours` ẩn khỏi nav, giữ cho tới agent phase. Mọi flow mới ở `pages/chat`; không thêm tính năng tại đây.

- Input: `LocalSession` đang active, các callback session từ `app`.
- Output: empty state hoặc `CurrentWorkspace` (heading, form, requirement, comparison, expired-recovery).
- Workflow: `WorkspacePage` (shell) → `CurrentWorkspace` (lắp ghép) → `RequirementForm` / `RequirementView` / `ComparisonView`; state lấy từ `model/useCurrentWorkspace`. Mapping draft→form dùng chung ở `entities/search-draft`.
- Interface: `src/pages/workspace` export `WorkspacePage`, `CurrentWorkspace`. `model/` nội bộ; không giữ bản copy `access`/`title`/`format` per-page — dùng chung từ `features/session-history`, `shared/lib`, `features/chat`.
- Quyết định kỹ thuật: session bar và sidebar toggle do `app` sở hữu; page không render toolbar riêng. Title dùng `sessionTitle` cùng fallback chuẩn, không slice thô theo UTF-16 code unit.
- Trình bày: route legacy vẫn dùng token chữ, viền và khoảng cách chung; form và kết quả là các bề mặt riêng, có thể co về một cột ở màn hình nhỏ.
