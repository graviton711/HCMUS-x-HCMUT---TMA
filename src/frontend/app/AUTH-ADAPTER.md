# Supabase Auth adapter

Đã triển khai email/password và Google PKCE qua backend `/auth`; session dùng bearer cho API v2 theo verified Supabase UUID. Không lưu password/refresh ở application DB. [Policy đầy đủ](../../../docs/account-history-what-if-integration.md).

| Endpoint | Input / output |
|---|---|
| GET /auth/config | enabled, email_enabled, google_enabled từ cấu hình Supabase |
| POST /auth/register | email, name, password, password_confirmation, return_url → session hoặc confirmation_required |
| POST /auth/login | email, password → access_token, refresh_token, expires_at, user |
| POST /auth/refresh | refresh_token → rotated session |
| GET /auth/me | bearer → user |
| PATCH /auth/me | bearer + name → user; email không sửa tại màn này |
| POST /auth/logout | revoke provider session local và application session_id |
| POST /auth/google/start | return_url + code_challenge → redirect_url |
| POST /auth/google/exchange | code + code_verifier → session |

FE dùng backend cùng origin mặc định; Vite proxy `/auth/…` nhưng navigation `/auth` vẫn là SPA. `VITE_AUTH_BASE_URL` chỉ cần khi adapter ở host khác; fallback VITE_API_BASE_URL. Credentials nằm trong sessionStorage của tab, ràng buộc service URL. Refresh single-flight; đổi account chặn response muộn. Supabase email confirmation không được coi là login: UI yêu cầu xác nhận email rồi đăng nhập. Google lưu verifier/state per-tab, kiểm callback và chỉ exchange một lần; xóa code/hash khỏi URL, không nhận token từ URL.

History account qua `/v2/history`; import guest cần thao tác explicit và token guest còn hạn. Title/pin local được gửi sau khi link. Archive ẩn index, không xóa nguồn/evidence hoặc ngầm cancel job. Retention backend mặc định 7 ngày; unsent draft vẫn local. Logout/expiry chuyển về guest history riêng. Không yêu cầu quyền Gmail; link/unlink provider, reset password, đổi email/MFA chưa triển khai.
