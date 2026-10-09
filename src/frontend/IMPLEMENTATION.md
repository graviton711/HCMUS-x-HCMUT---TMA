# Kiến trúc frontend

Đợt account/history/what-if theo [contract 09/10](../../docs/account-history-what-if-integration.md): Supabase email/password/PKCE qua backend adapter, bearer dùng v2 theo verified owner; hydrate history server và what-if có review proposal. Draft chưa gửi giữ local, server history theo retention. Giữ UI tokens/components hiện hữu.

React + TypeScript + Vite, gọi API backend v2. Runtime/build dùng source và assets độc lập; prototype HTML không là dependency. Giao diện hỗ trợ responsive, VI/EN và sáng/tối.

## Modules và interfaces

| Module                | Trách nhiệm                                                      | Input / output                                                    |
| --------------------- | ---------------------------------------------------------------- | ----------------------------------------------------------------- |
| `app/`                | Shell, routes, preferences, public/auth/account và chỉ mục phiên | Navigation/identity/local history ↔ workspace                     |
| `api/`                | DTO, runtime validators, HTTP client và serialization            | JSON backend ↔ typed requirement/proposal/comparison/job/evidence |
| `features/workspace/` | Draft, committed requirement, proposal/chat, jobs và snapshots   | Form/review/confirm/search ↔ API client và results                |
| `components/`         | Controls, dialog, icons và error boundary                        | Props/callbacks dùng chung                                        |
| `public/assets/`      | Font, mark và ảnh điểm đến có license                            | Assets local; không là dữ liệu tour                               |
| `tests/`              | Contract/state/browser integration                               | Transport và fixture chỉ trong test                               |

## Workflow

Form/text/URLs → review → requirement/proposal → confirm → explicit search → comparison/job/events → bảng/phân tích/evidence. Direct edits/sliders/chat merge vào proposal backend; cancel/discard dùng version. Đổi offer/nhóm tạo comparison mới.

Catalog cấp canonical destinations/origins/operators/sliders/limits. URL-only không suy budget/party; parser backend xử lý text/notes. Edits giữ condition IDs và cây AND/OR; unknown/unsupported/conflict giữ nhãn và evidence. Backend sở hữu giá, ranking, phân tích và activity.

## Quyết định kỹ thuật

- Semantic CSS tokens; motion opacity/transform và reduced-motion. Browser history quản lý route/query phiên; deploy cần SPA fallback.
- Mutation retry dùng cùng serialized body/idempotency key. `409` giữ draft/proposal và cho tải trạng thái mới; session creation không tự retry.
- Poll sequential với event cursor, drain `has_more` kể cả terminal. AbortSignal và guard theo phiên chặn response muộn; chuyển màn không cancel job server.
- localStorage lưu chỉ mục/draft/chat/IDs, sessionStorage lưu bearer/expiry. Resume đọc resource backend đã biết ID; history account lấy từ backend, draft chưa gửi chỉ local.
- Supabase adapter dùng bearer cho API v2 sau backend verification theo owner UUID; anonymous token vẫn giữ riêng. Các giới hạn/contract tại [BACKEND-GAPS](BACKEND-GAPS.md) và [AUTH-ADAPTER](app/AUTH-ADAPTER.md).

Kiểm tra chạy bằng các scripts trong [README](README.md); contract tests dùng backend source thật, SQLite memory và FakeNim. Browser tests kiểm workflow/responsive; các test fixture không xác nhận chất lượng nguồn tour live.
