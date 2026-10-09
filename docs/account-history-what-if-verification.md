# Kiểm chứng tài khoản, lịch sử và what-if — 09/10/2026

Triển khai trên `backend` theo phạm vi FE/BE user cho phép. [Policy](account-history-what-if-integration.md), [hướng dẫn chạy/test](../examples/frontend-account-what-if.md).

## Kết quả

| Kiểm tra | Kết quả | Phạm vi |
|---|---|---|
| `uv run pytest -q` | 450 passed | Regression backend và 7 ca auth/history mới; provider Auth được stub, app/SQLite thật |
| Frontend `pnpm test` | 64 passed, 8 files | Contract API thật qua FastAPI test harness, form, auth refresh/PKCE, owner storage, workspace, what-if/evidence |
| Browser không auth | 7 passed | Form/proposal/confirm, contact, URL notes, responsive, comparison và what-if review |
| Browser auth | 1 passed | Confirmation chưa login, login, hai browser contexts cùng account, hydrate/rename/profile/archive |
| Lint/typecheck/build | Passed | Ruff các module Python thay đổi; ESLint, TypeScript và Vite production build |
| `git diff --check` | Passed | Không lỗi whitespace |

Backend có một cảnh báo deprecation sẵn có của Starlette/httpx; không có test thất bại. Browser dùng memory DB riêng, không ghi vào `data/backend.db` hoặc tạo account Supabase thật.

## Điều đã được xác nhận

- Hosted Auth verify bearer trước khi gắn owner theo UUID; token sai issuer/audience/expiry/session bị từ chối. Không echo mật khẩu hoặc chi tiết lỗi provider. Logout bổ sung revocation ở application DB.
- History tách owner; account dùng token mới vẫn đọc cùng lịch sử. Paging, metadata CAS/idempotency, archive, transcript, retention và nhập guest có chặn job đang chạy/retry receipt được kiểm tra.
- Refresh single-flight, retry 401 giữ mutation key, account switch loại response muộn, callback PKCE/state một lần. Signup chờ xác nhận email chưa trở thành login.
- Budget form mới mặc định hard cap; strength explicit của dữ liệu cũ được giữ. Response `needs_clarification` được đưa vào review, không báo lỗi contract.
- What-if gắn comparison/requirement/revision; counts/ratio lấy từ backend. Unknown không thành 0%; fail→pass và unknown→pass hiển thị riêng. Apply chỉ tạo proposal, không tự confirm/search.
- Kiểm tra màn hình 1440/1280/390/320px; panel what-if 1440/390px. Screenshot trong `artifacts/frontend/` là dữ liệu kiểm thử; bản copy đổi origin chỉ trong transport test để kiểm UI, production vẫn chặn synthetic.

## Giới hạn kiểm chứng và vận hành

Probe read-only Auth settings của project hiện có: email bật, Google tắt. Chưa thử signup/email delivery hoặc Google login với account thật; cần cấu hình provider và redirect trên Supabase rồi test bằng tài khoản nhóm.

Auth tests dùng HTTP stub; NIM/crawler/catalog trong harness dùng dữ liệu kiểm thử. Các kết quả trên không khẳng định chất lượng tour thật, email đã gửi hoặc Google đã hoạt động.

Account và catalog ở Supabase; lịch sử application vẫn SQLite, retention mặc định 7 ngày. Draft chưa gửi chỉ local. Email change, reset password, MFA, link/unlink provider chưa có UI. Không có migration/update schema kho tour, commit hoặc push trong đợt này.
