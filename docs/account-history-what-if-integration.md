# Tích hợp tài khoản, lịch sử và what-if — 09/10/2026

User duyệt Supabase Auth và cho phép sửa cả FE/BE trên `backend` trong đợt này. Không tự cấu hình Google/SMTP/redirect allowlist trên Supabase, không sửa catalog, không commit/push.

## Tài khoản

- Backend adapter `/auth`: config, register, login, refresh, me GET/PATCH, logout, Google start/exchange. Email + password đi tới Supabase Auth bằng publishable key; không lưu password hoặc refresh token tại backend. Register chưa có session trả `confirmation_required`, không giả đăng nhập.
- FE lưu access/refresh token và expires_at trong sessionStorage; refresh có single-flight. Password không persist. Không nhận bearer từ URL. Google dùng PKCE S256, verifier/state theo tab và return URL đúng origin/path được phép; callback xóa code/state khỏi URL và exchange một lần.
- Owner v2 là `user_<Supabase UUID>` sau GET `/auth/v1/user` thành công tại đúng project; không tin profile/user ID phía FE hoặc decode JWT chưa được provider kiểm tra. Session ẩn danh cũ giữ nguyên. V1 vẫn chỉ dùng session cũ.
- Logout revoke provider session local và chặn session_id tại application DB ít nhất 30 ngày, hoặc tới hết hạn JWT nếu dài hơn; refresh/access thuộc session đã logout không được cấp quyền v2. Không network trong SQLite transaction. Errors không xuất credential/provider response.
- `SUPABASE_AUTH_URL/ SUPABASE_AUTH_PUBLISHABLE_KEY` có thể riêng; mặc định dùng biến tour URL/key hiện có. Config provider được lấy từ `/settings`. Không cần service-role key hoặc truy vấn bảng `auth` trực tiếp. Profile sửa tên; email đổi cần flow xác nhận riêng nên UI chỉ đọc email.

## Lịch sử

- `GET /v2/history`: pagination theo created_at + ID, owner scope; không trả raw snapshot/payload/token. Items gồm requirement ID/revision, title/pinned/version, proposal/comparison/job refs và timestamps. `GET /v2/history/{rid}` lấy requirement, refs và transcript có giới hạn; không hydrate lịch sử người khác.
- Metadata title/pinned được PATCH với expected_version/CAS. Hide một cuộc hội thoại bằng POST archive; không xóa job/evidence hoặc cancel ngầm. Export theo pages/history detail; FE báo giới hạn nếu export bị cắt. Draft chưa gửi vẫn ở browser; committed requirement/proposal/transcript là dữ liệu server.
- Link phiên ẩn danh vào tài khoản là thao tác explicit có cả account bearer và anonymous token. Transaction kiểm token/expiry, chặn job queued/running, chuyển toàn bộ owner refs và revoke token cũ. Receipt token hash/owner cho phép retry cùng account sau mất response; bị purge khi guest expiry. Không tự nhập dữ liệu local của tài khoản khác.
- History retention vẫn theo backend hiện tại; đăng nhập thiết bị khác thấy lịch sử trong retention, không hứa lưu vĩnh viễn. Không di chuyển SQLite application data sang Supabase trong đợt này.

## What-if UI

Form personalized dùng ngân sách/người lớn mặc định hard theo policy nhóm đã chốt. Giữ strength explicit của nhu cầu cũ khi sửa; không tự nâng soft lịch sử. Contract createRequirement nhận cả needs_clarification/proposal_version từ BE để tiếp tục review thay vì báo response lỗi.

- Dùng API đã có: create analysis → poll/drain events → GET result. Resume bằng analysis/job IDs. Result binding phải khớp comparison/requirement/revision; response muộn không ghi đè phiên hoặc bảng mới.
- Hiển thị baseline, phạm vi/truncation, kịch bản, fail→pass và unknown→pass riêng; tỷ lệ chỉ hiển thị khi state=computed, không gọi contribution/causal importance. Witness links/evidence/rank bounds theo response.
- Apply chỉ tạo proposal đúng expected_revision; UI render diff/clarifications và chờ confirm, search vẫn explicit. Không tự confirm hoặc dùng scenario như recommendation cho yêu cầu gốc.

## Nghiệm thu

BE: stub Auth HTTP (signup confirmation, invalid/expired/other-project tokens, refresh/logout, provider errors), account ownership qua nhiều tokens, guest isolation/link CAS/active-job guard, history paging/metadata/archive/transcript/retention. Không tạo user thật trong test.

FE: auth confirmation/refresh/PKCE/storage/identity switch, real backend contract test, history hydrate/paging/archive, what-if schema/binding/null ratios/apply proposal/cancel/late response; lint/typecheck/unit/build và browser smoke ở desktop/mobile. Live chỉ probe public Auth settings, catalog read-only; Google live cần provider/redirect setup.

Nguồn giao thức: [Supabase Auth OpenAPI](https://github.com/supabase/auth/blob/master/openapi.yaml), [PKCE](https://supabase.com/docs/guides/auth/sessions/pkce-flow), [sign-out](https://supabase.com/docs/reference/javascript/auth-signout). Provider JWT có thể còn hạn sau logout; application revocation bổ sung cho API của mình.
