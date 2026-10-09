# Frontend Đi cùng

React + TypeScript + Vite, gọi API backend v2. Source và assets độc lập; không import JS/CSS/fixture prototype vào runtime hoặc build. Giao diện có form/chat/proposal, comparison/evidence/activity, Việt/Anh và sáng/tối; không có trang admin.

## Chạy

Cần Node >=20.19 (hoặc >=22.12), Corepack hoặc pnpm, và backend Python đã cài dependency bằng `uv sync` từ repo root. Nếu máy có Corepack nhưng chưa nhận lệnh pnpm, chạy trực tiếp từ repo root:

```powershell
corepack pnpm --dir src/frontend install --frozen-lockfile
corepack pnpm --dir src/frontend dev
```

Nếu pnpm đã có trong PATH, có thể chạy trong thư mục frontend:

```powershell
cd src/frontend
pnpm install --frozen-lockfile
pnpm dev
```

Mở http://127.0.0.1:5173. Chạy `uv run tour-backend serve` từ repo root trong terminal khác. Vite proxy `/v2`, `/health` và `/auth/…` tới backend port 8000; có thể đặt `BACKEND_URL` trong environment của terminal trước `pnpm dev`.

`pnpm` không được nhận nghĩa là terminal chưa có lệnh trong PATH. `corepack pnpm dev` ở repo root báo `Command "dev" not found` vì package.json và script dev nằm tại `src/frontend`; dùng `--dir` như trên hoặc chuyển vào đúng thư mục. Python `.venv` không cấp các lệnh Node/pnpm.

## Cấu hình kết nối

`.env.example` là file mẫu; copy thành `.env.local` khi cần đổi cấu hình, rồi khởi động lại Vite. Chạy dev với backend mặc định không cần tạo file này hoặc cung cấp API token.

| Biến                       | Ý nghĩa                                                            | Mặc định                                   |
| -------------------------- | ------------------------------------------------------------------ | ------------------------------------------ |
| `VITE_API_BASE_URL`        | Địa chỉ backend, không thêm `/v2`; client tự nối endpoint          | Rỗng: cùng origin, dùng Vite proxy khi dev |
| `VITE_AUTH_BASE_URL`       | Địa chỉ identity adapter theo [contract auth](app/AUTH-ADAPTER.md) | Rỗng: cùng backend API                   |

Backend tự cấp token phiên qua `POST /v2/sessions`; frontend nhận và dùng token khi chạy. Các biến `VITE_*` là cấu hình công khai trong bundle; không đặt NIM/Supabase/admin/OAuth secret ở đây.

Deploy cần reverse proxy cùng origin hoặc BE cấu hình CORS cho origin frontend. Hosting source tại root và SPA fallback cho `/tours`, `/auth`, `/account`, `/contact`, `/support`.

## Trách nhiệm và interfaces

Giới thiệu → form/URL/chat → review và xác nhận → tìm kiếm → bảng/evidence/phân tích/activity. Sửa field/slider/chat chung proposal; confirm chỉ commit, search riêng. Không tự tính giá, rank, sinh analysis hoặc nhật ký.

- `api/`: DTO/validation/client `/v2`, canonical catalog, serializer và typed edits giữ IDs/tree/version/idempotency.
- `app/`: navigation, preferences, public/auth/account pages, history server theo tài khoản, draft local và identity adapter.
- `features/workspace/`: draft/committed/proposal, jobs/events, snapshots/chat/evidence; chuyển phiên và response muộn được guard.
- `components/`: controls dùng chung; `public/assets/`: font/ảnh độc lập kèm license/provenance.
- `tests/` và `api/*.test.ts`: test-only transport, không import vào runtime/build.

Input là form/text/URLs và JSON backend; output là proposal/comparison/ticket request và UI theo dữ kiện BE. URL-only không ép party/budget/ngày. Backend trả thiếu/unknown/unsupported thì giữ trạng thái; bảng cũ giữ khi chờ/lỗi hoặc chưa khớp criteria mới.

Bearer ẩn danh lưu sessionStorage theo expiry; chỉ mục phiên, draft và chat lưu localStorage. Anonymous resume bằng IDs + bearer còn hạn. Account lấy danh sách/detail/transcript từ backend, hỗ trợ đổi thiết bị trong retention. Ảnh giới thiệu là điểm đến, không giả tour/giá/weather.

## Kiểm tra

```powershell
pnpm typecheck
pnpm lint
pnpm test
pnpm build
pnpm test:e2e
```

Test contract dùng backend thật trong SQLite memory + FakeNim test-only, cần `uv sync`. Browser tests cần frontend/backend local đang chạy, Chromium (`pnpm exec playwright install chromium`) hoặc `PLAYWRIGHT_CHROME_PATH`; có thể đổi `E2E_BASE_URL`. Chi tiết ở [tests/README.md](tests/README.md).

## Phần chưa đồng bộ

Backend v2 đã có flow proposal/chat/comparison/events/evidence, nhưng default provider còn synthetic. Frontend kiểm `/health` và chặn kết quả synthetic. Cần cấu hình nguồn thật ở BE để sử dụng tìm tour.

Auth email/password, Google PKCE adapter, history account và what-if đã nối. Google chỉ bật theo GET /auth/config khi provider sẵn sàng. Chi tiết cấu hình/test ở [hướng dẫn account](../../examples/frontend-account-what-if.md). Giới hạn tại [BACKEND-GAPS.md](BACKEND-GAPS.md), [AUTH-ADAPTER.md](app/AUTH-ADAPTER.md).

Kiến trúc/workflow: [IMPLEMENTATION.md](IMPLEMENTATION.md).
