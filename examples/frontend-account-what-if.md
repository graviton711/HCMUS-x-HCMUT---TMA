# Đăng nhập, lịch sử và what-if

## Khởi động

Terminal ở repo root:

```powershell
uv sync
uv run tour-backend serve
```

Terminal khác:

```powershell
cd src/frontend
pnpm install --frozen-lockfile
pnpm dev
```

Mở `http://127.0.0.1:5173`. Restart backend sau sửa Python; restart Vite sau sửa `.env.local`. Dev dùng proxy nên không cần đưa Supabase/NIM key vào frontend.

## Supabase Auth

Backend dùng `SUPABASE_TOUR_URL` + `SUPABASE_TOUR_PUBLISHABLE_KEY` đã có. Nếu auth là project khác, đặt `SUPABASE_AUTH_URL` và `SUPABASE_AUTH_PUBLISHABLE_KEY` riêng trong `.env` backend. `/auth/config` cho biết email/Google đã bật; không hiển thị key.

Trong Supabase Auth cấu hình email/password và các URL redirect dùng thực tế, ví dụ `http://127.0.0.1:5173/auth`, `http://localhost:5173/auth`. Khi deploy, thêm URL HTTPS của frontend vào Supabase và origin tương ứng vào `CORS_ORIGINS` backend. Google cần bật/cấu hình provider Google trên Supabase; adapter/frontend PKCE đã có nhưng chưa thể login Google khi provider còn tắt. [Hướng dẫn Supabase PKCE](https://supabase.com/docs/guides/auth/sessions/pkce-flow).

1. Vào **Đăng nhập → Tạo tài khoản**, nhập họ tên, email, mật khẩu/xác nhận.
2. Nếu hiện **Kiểm tra email**, mở email xác nhận rồi quay lại đăng nhập. Trạng thái này chưa đăng nhập thành công; delivery phụ thuộc cấu hình email của Supabase.
3. Đăng nhập bằng email/mật khẩu. Token/refresh chỉ trong tab; UI có tên tài khoản. Mật khẩu không lưu ở app DB.
4. Vào **Tài khoản** để sửa tên hiển thị hoặc đăng xuất. Email hiện chỉ đọc; reset password, đổi email, MFA, link/unlink Google chưa có UI.

## Lịch sử

1. Khi đăng nhập, tạo **Phiên mới**, điền form hoặc nhập nhu cầu tự nhiên. Ngân sách/người lớn của form mới là trần giá hard.
2. Form đầy đủ/rõ lưu nhu cầu; text/URL hoặc thiếu thông tin tạo proposal. Xem thay đổi/câu hỏi, xác nhận rồi bấm **Tìm kiếm**.
3. Mở trình duyệt khác, đăng nhập cùng tài khoản: danh sách và nhu cầu đã gửi được lấy lại từ backend; chọn phiên để hydrate cuộc trò chuyện và refs comparison/job. Đổi tên/ghim được lưu server với version, không ghi đè thay đổi concurrent.
4. Bản nháp chưa gửi chỉ trên trình duyệt. Phiên ẩn danh còn hạn/token trong tab có thể được nhập bằng nút **Nhập lịch sử ẩn danh vào tài khoản**; tác vụ guest đang chạy cần hoàn tất trước. Không tự nhập lịch sử khi đăng nhập.
5. **Xuất dữ liệu** tải history details, không token. `limited` báo transcript/runs bị giới hạn. **Xóa khỏi lịch sử** với account là archive/ẩn danh sách; không xóa evidence/job. Bản nháp chưa gửi bị xóa local khi bỏ phiên.

History vẫn ở application DB SQLite `data/backend.db`, mặc định giữ 7 ngày (`RETENTION_DAYS`). Supabase Auth giữ tài khoản; kho tour Supabase giữ tours/offers/providers. Các bảng application bổ sung tự tạo khi khởi động; không cần sửa schema kho tour. Đổi backend/máy lưu SQLite hoặc hết retention có thể làm history không còn; nhiều máy chủ cần shared persistence trước khi deploy scale-out.

## What-if

1. Có comparison từ nguồn thật, đúng revision đã xác nhận và không pending proposal.
2. Bấm **Phân tích tác động điều kiện**. UI theo job/events; rời màn/reload có thể resume từ analysis/job IDs.
3. Xem baseline, phạm vi/giới hạn, từng kịch bản, nhóm đứng đầu và witness/nguồn. Tách lựa chọn gốc fail → pass khỏi unknown → pass.
4. Chỉ hiện % nếu backend trả `computed`; đây là tỷ lệ hạn chế trong tập đã đọc, không phải % đóng góp/quan trọng hay tác động nhân quả.
5. Bấm **Xem đề xuất sửa nhu cầu**: chỉ tạo proposal. Đọc diff và đánh đổi, trả lời phần thiếu, xác nhận nếu đồng ý. Sau đó **Tìm kiếm** riêng. What-if không tự đổi ngày/ngân sách/số người hoặc confirm/search.

Bỏ một field core vẫn được phân tích như giả thuyết; proposal có thể bị chặn confirm nếu thiếu thông tin bắt buộc. Kịch bản nới giá/ngày giữ đủ core vẫn theo policy hiện có; không tự bỏ quy tắc mandatory của personalized search.

Nguồn synthetic bị chặn. NIM dùng cho extract/chat/semantic/explanation theo policy hiện có; số đếm/tỷ lệ do decision engine tính.

## Kiểm tra tự động

Repo root: `uv run pytest -q`. Frontend: `pnpm test`, `pnpm typecheck`, `pnpm lint`, `pnpm build`. [Browser harness riêng](../src/frontend/tests/README.md) không ghi dữ liệu/account vào Supabase thật. [Kết quả kiểm chứng](../docs/account-history-what-if-verification.md).
