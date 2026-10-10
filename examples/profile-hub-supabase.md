# Bật Profile Hub

1. Chọn **Supabase project dùng để đăng nhập**. Nếu Auth và catalog cùng project thì dùng project đó. Mở [file migration](../migrations/profile-hub/001_profile_hub.sql), copy toàn bộ **nội dung SQL** từ `begin;` đến `commit;`, dán vào SQL Editor → New → Run. Migration thêm `profile_hub_items`, `profile_hub_receipts`, hàm kiểm định dữ liệu, RLS và RPC; không sửa tours/offers/providers. Không chỉ dán tên file hay tự nhập các bản ghi mẫu.
2. Backend `.env` nằm ở repo root. **Auth dùng chung project tour:** nếu đã có `SUPABASE_TOUR_URL` và `SUPABASE_TOUR_PUBLISHABLE_KEY`, không cần thêm biến mới; backend tự dùng hai biến này cho đăng nhập và Hub. **Auth dùng project riêng:** thêm cả `SUPABASE_AUTH_URL` và `SUPABASE_AUTH_PUBLISHABLE_KEY` của project Auth, rồi chạy migration ở project đó. URL là HTTPS origin, không có `/auth/v1` hoặc `/rest/v1`; key là publishable key, không phải mật khẩu database/Google Client Secret. Không cần service role hoặc `SUPABASE_AUTH_DB_URL`. FE gọi backend hiện tại; local port mặc định không cần thêm `.env.local` hay biến Supabase vào VITE.
3. Khởi động lại BE: từ repo root `uv run tour-backend serve`; terminal khác `corepack pnpm --dir src/frontend dev`. Đăng nhập, mở Tài khoản. Nếu chưa chạy migration, Hub báo kho cá nhân chưa sẵn sàng, các tính năng tìm tour hiện có vẫn dùng được.
4. Lưu sở thích: chọn khách sạn mong muốn và mức quan trọng riêng, bấm Lưu. Tải lại trang: dữ liệu còn. Bấm Dùng cho chuyến mới: chỉ tạo bản nháp; chọn lại điểm đến/lịch/số người/ngân sách, review rồi xác nhận. Nhịp đi/văn hóa hiện được lưu nhưng chưa có metric xếp hạng.
5. Trong nhu cầu đã xác nhận, bấm Lưu mẫu. Mở Hub → Dùng mẫu: lịch/ngân sách/tuổi trẻ em phải được điền lại. Mẫu không lưu ngày sinh, giấy tờ, hội thoại hoặc ngân sách cũ.
6. Kết quả đối chiếu có dữ liệu nguồn: bấm Lưu tour. Hub giữ tên/link/lịch/giá tại lúc lưu, có ghi chú/bộ sưu tập. Bấm Kiểm tra lại hoặc chọn tối đa 5 tour rồi Đối chiếu: tạo phiên URL mới, cần review và gọi acquisition mới. Không coi giá cũ là giá còn hiệu lực. Snapshot chưa có offer không tự chọn giá rẻ nhất.
7. Xuất dữ liệu cá nhân ra JSON. Xóa từng mục hoặc toàn bộ Hub cần xác nhận; lịch sử tìm kiếm và tài khoản Auth có thao tác riêng. Xóa item xóa payload và retry receipts chứa payload; giữ ID/version tombstone để chống thiết bị cũ ghi đè. Receipt tự hết hiệu lực sau 24h, được dọn khi người đó ghi tiếp.

## Kiểm migration đã tạo đủ đối tượng

Chạy query riêng sau migration trong SQL Editor:

```sql
select
  to_regclass('public.profile_hub_items') is not null as items_ready,
  to_regclass('public.profile_hub_receipts') is not null as receipts_ready,
  to_regprocedure('public.profile_hub_mutate(text,text,bigint,jsonb,text,text)') is not null as rpc_ready;
```

Cả ba cần là `true`. Trong Table Editor, chọn schema `public` và refresh để thấy hai bảng mới. Bảng có thể còn trống cho đến khi user đăng nhập và bấm Lưu. `owner_id` do backend/RPC xác định từ tài khoản, không điền tay.

Nếu web báo kho chưa sẵn sàng: kiểm đúng project Auth, chạy đủ SQL và tải lại. Nếu endpoint `/v2/profile-hub` trả 404: kiểm backend đã restart với code mới. Nếu trả 401: đăng nhập lại. Nếu trả 403: kiểm URL/key đúng project và migration đã tạo quyền/RLS/RPC; không gỡ RLS để khắc phục. Chi tiết lỗi API ở DevTools → Network → request `/v2/profile-hub` → Response.

## Kiểm quyền trên cloud sau migration

Đăng nhập hai tài khoản A/B. A lưu sở thích/tour/mẫu; B phải thấy Hub riêng. Guest gọi GET `/v2/profile-hub` nhận 401. Token người B không được đọc dữ liệu A cả khi gọi REST trực tiếp (RLS). Thử hai tab cùng sửa một mục: tab ghi sau nhận 409 và yêu cầu tải lại, không tự ghi đè. Sau đăng xuất không còn nội dung Hub trong màn hình hoặc storage của trình duyệt.

Các test repo dùng Auth/REST harness riêng và database PostgreSQL tạm nếu môi trường hỗ trợ; không thay thế kiểm quyền trên project thật. Migration không được tự chạy vào Supabase production. Đặc quyền SQL Editor/postgres vẫn đọc được dữ liệu theo quyền quản trị.

Thiết kế RLS/RPC dựa [Supabase RLS](https://supabase.com/docs/guides/database/postgres/row-level-security) và [database functions](https://supabase.com/docs/guides/database/functions). Chỉ user đã đăng nhập gọi RPC, owner lấy từ `auth.uid()`, không lấy từ body hay user_metadata.

## Hồ sơ cá nhân và ảnh đại diện

Tên hiển thị, số điện thoại, thành phố và giới thiệu ngắn được lưu bằng Supabase Auth user metadata. Không cần thêm biến `.env` hay sửa các bảng tours/offers. Các thông tin này không tự tạo điều kiện tìm tour. Email đăng nhập chỉ hiển thị.

Để tải ảnh riêng lên, mở `migrations/profile-hub/002_profile_avatars.sql`, copy **toàn bộ nội dung**, dán vào SQL Editor của project **Auth** đang dùng rồi bấm Run. Migration tạo bucket riêng `profile-avatars` (private), giới hạn JPEG 64 KB và policy chỉ cho tài khoản truy cập đường dẫn `<auth.uid()>/avatar.jpg`. Không đổi bucket thành public, không cần service-role key. Có thể chạy lại migration. Query kiểm:

```sql
select id, public, file_size_limit, allowed_mime_types
from storage.buckets where id = 'profile-avatars';
select policyname, cmd from pg_policies
where schemaname = 'storage' and tablename = 'objects'
and policyname like 'profile_avatar_%';
```

Kết quả cần có bucket `public = false` và 4 policy select/insert/update/delete. Ảnh Google và chữ viết tắt vẫn hiển thị khi chưa tạo bucket; thiếu migration chỉ chặn tải ảnh riêng.

Sau cập nhật code: dừng backend cũ bằng Ctrl+C trong terminal của nó, chạy `uv sync`, rồi khởi động lại backend như trước. Nếu backend đang giữ `tour-backend.exe`, Windows có thể chặn cập nhật package; dừng đúng terminal backend trước khi chạy `uv sync`. Dependency Pillow dùng để kiểm tra/nén ảnh. Frontend đang chạy Vite nhận code mới; reload trang `/account`.

Trong Hồ sơ: sửa tên/thông tin → Lưu hồ sơ. Chọn ảnh JPG/PNG/WebP ≤5 MB → xem trước → Lưu ảnh. Browser cắt giữa ảnh thành 256px và giảm kích thước; backend kiểm tra lại, bỏ EXIF và lưu JPEG. Navbar/sidebar đổi ngay; reload vẫn thấy ảnh. Gỡ ảnh chuyển sang chữ viết tắt. Nếu upload lỗi, ảnh đang chọn và thông tin chưa lưu được giữ để thử lại. Signed URL có hiệu lực một giờ; tải lại hồ sơ/làm mới phiên nhận URL mới, ảnh lỗi dùng chữ viết tắt.

Kiểm thêm bằng hai tài khoản: ảnh A không hiện ở B và B không đọc/xóa/ghi ảnh A. Tên, điện thoại và giới thiệu là user metadata có thể chỉnh sửa, không dùng làm quyền truy cập. Trong Cài đặt, Xuất hồ sơ chỉ xuất trường thông tin; không xuất URL ảnh có chữ ký. Quyền Storage theo [hướng dẫn Supabase](https://supabase.com/docs/guides/storage/security/access-control).
