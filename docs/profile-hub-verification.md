# Profile Hub — kiểm chứng ngày 10/10/2026

Triển khai trên `backend`, trong checkout chính. Không commit/push và không chạy migration trên Supabase thật.

## Kết quả

| Kiểm tra | Kết quả |
| --- | --- |
| `uv run pytest -q --tb=short` | 516 passed; một cảnh báo dependency Starlette/httpx hiện có |
| `corepack pnpm --dir src/frontend test` | 92 passed |
| `corepack pnpm --dir src/frontend build` | TypeScript/Vite đạt |
| `corepack pnpm --dir src/frontend lint` | Đạt, không warning |
| Ruff cho module/file Python được sửa | Đạt |
| `corepack pnpm --dir tests/profile-hub-sql test` | Migration chạy hai lần; RLS/quyền/CAS/receipt/giới hạn/xóa/cascade và format JSON đạt |
| Playwright `--grep 'Profile Hub saves'` với Auth/REST loopback | 1 passed: lưu/tải lại sở thích, tạo draft mới, mobile, VI/EN, dark, xóa và đăng xuất |

Test backend kiểm token/owner, phân tách hai tài khoản, retry không tạo bản ghi trùng, stale version trả 409, restore sau xóa, thiếu migration, response hỏng không lộ provider content, không nhận extra field vào template, tour phải thuộc comparison của người lưu, giữ đúng offer/date/giá và ghi chú, retry sau comparison hết hạn. Test ranking kiểm ưu tiên giá thấp là soft và không nới hard budget; dữ liệu thiếu/cũ không được chấm utility.

Test FE kiểm không tự thêm hard input khi dùng sở thích, reset lịch/ngân sách/tuổi trẻ em/URL/nội dung khi dùng mẫu, giữ form khi lưu lỗi, bỏ response đến muộn của tài khoản cũ, selection không còn hợp lệ sau sync, và recheck chỉ tạo draft URL mới. Hub documents không được cache vào browser storage. Lịch sử/draft hiện có vẫn theo cơ chế riêng.

Đã xem screenshot desktop VI và mobile VI/dark EN, kiểm không tràn ngang. Ảnh QA nằm tại `artifacts/frontend/profile-hub-*.png`, chỉ lưu local. Các test dùng dữ liệu và tài khoản cô lập; không phải tour hay user thật.

## Việc cần làm trên project thật

Theo [hướng dẫn bật Profile Hub](../examples/profile-hub-supabase.md), chạy [migration](../migrations/profile-hub/001_profile_hub.sql) trong **Supabase dùng cho Auth**, kiểm URL/key đúng project, khởi động lại backend/frontend. Sau đó kiểm hai tài khoản A/B và hai tab sửa cùng mục. PostgreSQL tạm đã kiểm policy SQL; cấu hình REST/role thực tế và concurrency qua nhiều connection của Supabase vẫn cần kiểm sau migration.

Giới hạn: nhịp đi/văn hóa chỉ lưu mức quan trọng, chưa có metric ranking. Saved tour là snapshot lịch sử, không xác nhận giá hiện tại/tổng thực trả/chỗ trống. Xóa toàn bộ Hub thực hiện từng mục có version; nếu một mục đã thay đổi hoặc mạng lỗi, giữ trạng thái đã xóa thành công, tải lại rồi chọn tiếp. Không xóa tài khoản Auth từ Hub.
# Account layout and avatar verification — 10/10/2026

Replaced stacked account sections with one six-view navigation, compact overview and dedicated profile/settings. Added optional phone/home city/introduction and Google/custom/initial avatars. Header account entry is avatar-only with an accessible name. Editors retain unsaved data during panel switches, cloud failures and profile refresh.

Validation: backend suite 521 passing; frontend unit suite 99 passing; lint/Ruff/typecheck/production build passing. Three isolated browser flows pass: personal fields/avatar upload-remove-refresh, preference save/reuse and account history/profile/archive. Screenshots `artifacts/frontend/account-new-*` cover 1440/390/320 px, VI/EN and light/dark, with no page overflow. Local SQL/WASM verifies both migrations and owner isolation. Photos in screenshots are test assets, not a live user upload.

Hosted limitation: `002_profile_avatars.sql` is prepared, not executed against Supabase. Actual Storage bucket/RLS and Google/custom photo access still require the setup check in `examples/profile-hub-supabase.md`. No service-role key, hosted user edits or automatic migration were used. Restart the running backend and sync dependencies before using the new avatar endpoint.
