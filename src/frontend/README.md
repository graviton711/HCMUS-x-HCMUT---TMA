# Frontend Đi cùng

React + TypeScript + Vite, gọi API backend v2. Source và assets độc lập; không import JS/CSS/fixture prototype vào runtime hoặc build. Giao diện có form/chat/proposal, comparison/evidence/activity, Việt/Anh và sáng/tối; không có trang admin.

## Chạy local từng bước

Cần **Node.js 24 LTS** (hoặc 22.x >=22.13), **pnpm 11.25.0**, **Python >=3.12** và **uv**. Các lệnh dưới đây bắt đầu từ thư mục repo, nơi có `pyproject.toml` và `README.md`.

**Cài công cụ frontend một lần trên Windows:**

1. Nếu `node` hoặc `npm` báo “not recognized”, cài **Node.js 24 LTS** bằng **Windows Installer (.msi)** tại [nodejs.org](https://nodejs.org/en/download). Giữ các thành phần npm và Add to PATH của installer.
2. Đóng rồi mở lại PowerShell. Nếu dùng terminal trong VS Code, đóng/mở lại VS Code để nhận PATH mới.
3. Kiểm tra Node/npm rồi cài phiên bản pnpm dùng cho frontend:
Cần Node >=20.19 (hoặc >=22.12), Corepack hoặc pnpm, và backend Python đã cài dependency bằng `uv sync` từ repo root. Nếu máy có Corepack nhưng chưa nhận lệnh pnpm, chạy trực tiếp từ repo root:

```powershell
corepack pnpm --dir src/frontend install --frozen-lockfile
corepack pnpm --dir src/frontend dev
```

Nếu pnpm đã có trong PATH, có thể chạy trong thư mục frontend:

```powershell
node --version
npm.cmd --version
npm.cmd install --global pnpm@11.25.0
pnpm.cmd --version
```

Các tên `.cmd` trên Windows tránh lỗi PowerShell chặn `npm.ps1`/`pnpm.ps1`; không cần đổi ExecutionPolicy. Sau khi các lệnh phiên bản chạy được, tiếp tục hai terminal bên dưới. [Hướng dẫn pnpm](https://pnpm.io/installation).

Frontend là website ở port **5173**. Backend là API ở port **8000**. Cần hai terminal chạy đồng thời để điền form, xác nhận, tìm tour và chat.

**Terminal 1 — backend:**

```powershell
uv sync
uv run tour-backend serve
```

Giữ terminal mở. Vào `http://127.0.0.1:8000/health` để kiểm tra API trả JSON.

**Terminal 2 — frontend:**

```powershell
pnpm.cmd --dir src/frontend install --frozen-lockfile
pnpm.cmd --dir src/frontend dev
```

Mở **http://127.0.0.1:5173** → Tìm tour → Tiếp tục với phiên ẩn danh. Không cần đăng ký, Google login, token nhập tay hoặc cài Playwright để chạy website. Ctrl+C dừng từng server.

Vite tự chuyển `/v2` và `/health` sang backend port 8000. Không cần `.env.local` khi dùng hai port mặc định. Sau lần đầu, có thể bỏ lệnh install/sync nếu dependency không đổi.

**Dữ liệu thật:** mặc định backend là `fixture`, frontend sẽ chặn kết quả mô phỏng. Để tìm tour thật, người vận hành backend cấu hình Supabase theo [hướng dẫn backend](../../examples/backend-supabase-v2.md); chat/phân tích cần cấu hình NIM ở backend. Xem `/health`: cần `data_origin=source` và `worker_enabled=true`. Mở được giao diện chưa có nghĩa nguồn tour/AI đã sẵn sàng.

Nếu chỉ chạy frontend, vẫn xem được Giới thiệu, Đăng nhập và Hỗ trợ; form/tìm kiếm cần API để lấy danh mục và xử lý phiên.

| Triệu chứng                                | Kiểm tra                                                                                                           |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------ |
| Không tải được danh mục / lỗi kết nối      | Terminal backend còn chạy và `/health` trả JSON; frontend không trỏ nhầm port                                      |
| Báo nguồn dữ liệu chưa kết nối             | `/health` còn `data_origin=synthetic`; cấu hình provider thật ở backend                                            |
| Không đăng nhập Google được                | Auth adapter chưa cấu hình; dùng phiên ẩn danh                                                                     |
| `node` / `npm` không tồn tại               | Cài Node.js LTS theo bước đầu rồi mở lại terminal/editor                                                           |
| `pnpm` không tồn tại                       | Khi npm đã chạy được, chạy `npm.cmd install --global pnpm@11.25.0`, mở lại terminal; kiểm tra `pnpm.cmd --version` |
| Báo không chạy được `npm.ps1` / `pnpm.ps1` | Dùng `npm.cmd` / `pnpm.cmd` trong PowerShell                                                                       |
| `uv` không tồn tại                         | Cài uv cho backend và mở lại terminal để nhận PATH                                                                 |
| Mở port 8000 chỉ thấy trang backend        | Mở website ở port 5173                                                                                             |
Mở http://127.0.0.1:5173. Chạy `uv run tour-backend serve` từ repo root trong terminal khác. Vite proxy `/v2`, `/health` và `/auth/…` tới backend port 8000; có thể đặt `BACKEND_URL` trong environment của terminal trước `pnpm dev`.

`pnpm` không được nhận nghĩa là terminal chưa có lệnh trong PATH. `corepack pnpm dev` ở repo root báo `Command "dev" not found` vì package.json và script dev nằm tại `src/frontend`; dùng `--dir` như trên hoặc chuyển vào đúng thư mục. Python `.venv` không cấp các lệnh Node/pnpm.

## Cấu hình kết nối

`.env.example` là file mẫu; copy thành `.env.local` khi cần đổi cấu hình, rồi khởi động lại Vite. Chạy dev với backend mặc định không cần tạo file này hoặc cung cấp API token.

| Biến                       | Ý nghĩa                                                                                                  | Mặc định                                   |
| -------------------------- | -------------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| `VITE_API_BASE_URL`        | Địa chỉ backend, không thêm `/v2`; client tự nối endpoint                                                | Rỗng: cùng origin, dùng Vite proxy khi dev |
| `VITE_AUTH_BASE_URL`       | Địa chỉ identity adapter theo [contract auth](app/AUTH-ADAPTER.md)                                       | Rỗng: auth chưa được bật                   |
| `VITE_AUTH_GOOGLE_ENABLED` | Bật Google login sau khi adapter/OAuth đã sẵn sàng                                                       | `false`                                    |
| `BACKEND_URL`              | Origin backend khác port/host, chỉ cho proxy dev; đặt trong environment của terminal trước khi chạy Vite | `http://127.0.0.1:8000`                    |
| Biến                       | Ý nghĩa                                                            | Mặc định                                   |
| -------------------------- | ------------------------------------------------------------------ | ------------------------------------------ |
| `VITE_API_BASE_URL`        | Địa chỉ backend, không thêm `/v2`; client tự nối endpoint          | Rỗng: cùng origin, dùng Vite proxy khi dev |
| `VITE_AUTH_BASE_URL`       | Địa chỉ identity adapter theo [contract auth](app/AUTH-ADAPTER.md) | Rỗng: cùng backend API                   |

Backend tự cấp token phiên qua `POST /v2/sessions`; frontend nhận và dùng token khi chạy. Các biến `VITE_*` là cấu hình công khai trong bundle; không đặt NIM/Supabase/admin/OAuth secret ở đây.

Build production không có proxy dev. Khi nối backend riêng, đặt `VITE_API_BASE_URL` là URL **HTTPS** backend (không có `/v2`) trước build và cấu hình `CORS_ORIGINS` ở backend cho đúng origin frontend.

## Preview chung trên Vercel

Hướng tích hợp: **frontend Vercel → backend HTTPS riêng → SQLite persistent + worker + nguồn tour/NIM**. Người xem chỉ mở link; không cần cài phần mềm hoặc tự host. Source cần build là `src/frontend`, output `dist`, không phải prototype HTML.

Vercel cần Root Directory `src/frontend`, preset Vite, build `pnpm build`, install `pnpm install --frozen-lockfile`, SPA fallback và biến `VITE_API_BASE_URL`. Backend giữ secrets, storage và worker. Đây là cấu hình cần chuẩn bị, chưa có `vercel.json` hoặc link triển khai được xác nhận trong repo. Chi tiết tại [hướng dẫn Vercel](../../docs/frontend-vercel-preview.md).

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
cd src/frontend
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
