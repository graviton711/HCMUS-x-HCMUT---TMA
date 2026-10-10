# Supabase identity adapter

Input: email/password, refresh token, provider access bearer hoặc PKCE code/verifier. Output: public profile, session hoặc confirmation_required; owner stable theo verified Supabase user UUID. Giao thức/giới hạn ở [integration policy](../../../docs/account-history-what-if-integration.md).

Workflow: validate DTO → bounded Auth HTTP với publishable key → validate provider user/token binding → owner scope. Không lưu password/refresh; không network trong Store transaction. Local revocations và history metadata là bảng additive của application DB.

Interfaces: app dependency `owner_v2`; legacy v1 giữ session authentication. FE gọi `/auth` cùng-origin qua Vite proxy, dùng account bearer cho API v2. Anonymous linking có proof hai phía, từ chối khi guest có job đang chạy.
