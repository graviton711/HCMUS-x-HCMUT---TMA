# Supabase identity adapter

Input: email/password, refresh token, provider access bearer hoặc PKCE code/verifier. Output: public profile, session hoặc confirmation_required; owner stable theo verified Supabase user UUID. Giao thức/giới hạn ở [integration policy](../../../docs/account-history-what-if-integration.md).

Workflow: validate DTO → bounded Auth HTTP với publishable key → validate provider user/token binding → owner scope. Không lưu password/refresh; không network trong Store transaction. Local revocations và history metadata là bảng additive của application DB.

Interfaces: app dependency `owner_v2`; legacy v1 giữ session authentication. FE gọi `/auth` cùng-origin qua Vite proxy, dùng account bearer cho API v2. Anonymous linking có proof hai phía, từ chối khi guest có job đang chạy.

`PATCH /auth/me` edits name and optional phone/home_city/bio, preserving omitted fields and provider metadata. These user-editable fields never authorize access. `POST /auth/me/avatar` accepts a bounded base64 image; Pillow verifies JPEG/PNG/WebP dimensions, center-crops to 256px and removes metadata. `DELETE /auth/me/avatar` removes the owned file and selects initials. Private Storage uses the verified user's bearer and publishable key, never a service role. Owner path is derived server-side. `public_profile` signs owned uploads for 1 hour and tolerates missing storage on reads. `002_profile_avatars.sql` prepares bucket/RLS; upload failures return an actionable setup error. Existing login/me clients remain compatible with additive public fields.
