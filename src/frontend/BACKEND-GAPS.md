# Trạng thái tích hợp backend

Contract runtime: `src/api/v2/models.py`, `routes.py`, `service.py`, domain và `/v2/catalog`. FE kiểm cấu trúc/binding trước khi dùng JSON.

| Phần | Đã nối | Giới hạn còn lại |
|---|---|---|
| Identity | Supabase email/password, profile/name, refresh/logout, Google PKCE adapter | Google cần bật provider và allow-list redirect; reset password/đổi email/MFA và link/unlink chưa có UI |
| History | Owner-scoped list/detail/transcript, pagination, title/pin CAS, archive/export, explicit guest linking | Application DB còn SQLite, retention mặc định 7 ngày; unsent drafts không đồng bộ |
| What-if | Create/poll/resume/result, baseline/scenarios/ratios/witnesses, apply → review proposal | Snapshot/candidate/scenario bounds được công khai; không khẳng định % contribution hay nguyên nhân |
| Dữ liệu tour | Supabase/HTTP qua BE; `catalog_validated` được FE nhận đúng | Nguồn thật và price coverage/TTL phải đủ; synthetic vẫn chặn |
| Worker | Jobs/events/cancel; không ngầm hủy khi rời màn | Worker phải bật cho parse/chat/comparison/what-if |
| Locale | UI Việt/Anh + theme | Input, quotes, insights giữ nguyên ngôn ngữ BE |
| Deploy | Dev proxy /v2, /health, /auth/… | Production cần SPA fallback và reverse proxy/CORS đúng origin |

- V2 dùng envelope `2.0-draft`; `/health` và `/auth` có JSON riêng. Bearer anonymous/account không xuất vào history file.
- Form personalized mặc định trần ngân sách hard; khi sửa giữ strength của nhu cầu cũ. CreateRequirement nhận needs_clarification; không coi draft là nhu cầu đã confirm.
- Direct edits/what-if/chat cùng review/confirm CAS. Search riêng; proposal đang chờ, stale revision/source/cancel được backend chặn.
- Mutation retry cùng body/key; 409/422 giữ draft. Session creation không retry. Poll drain events sau terminal; không suy % tiến độ.
- Export tải history details; file báo limited nếu transcript/runs bị giới hạn. Archive chỉ ẩn hội thoại, không xóa dữ liệu đang theo retention.
- [Kiểm chứng](../../docs/account-history-what-if-verification.md), [contract auth](app/AUTH-ADAPTER.md), [test scripts](tests/README.md). Test identity stub/fixture không chứng minh Google, email delivery hoặc chất lượng tour live.
