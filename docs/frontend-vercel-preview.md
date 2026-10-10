# Frontend Vercel và backend riêng

Hướng tích hợp để dùng đầy đủ website qua một link: frontend tĩnh Vercel gọi backend HTTPS riêng. Tài liệu mô tả cấu hình cần chuẩn bị; không xác nhận đã tạo project hoặc deploy. GitHub Pages trong [hướng dẫn prototype](frontend-preview-publishing.md) chỉ phục vụ prototype, không thay frontend React/API.

## Cấu hình frontend

| Thiết lập           | Giá trị                                                                  |
| ------------------- | ------------------------------------------------------------------------ |
| Root Directory      | `src/frontend`                                                           |
| Framework Preset    | Vite                                                                     |
| Install Command     | `pnpm install --frozen-lockfile`                                         |
| Build Command       | `pnpm build`                                                             |
| Output Directory    | `dist`                                                                   |
| Node                | 24 LTS; nếu dùng dòng 22 thì >=22.13 để chạy cả Vite và pnpm 11          |
| `VITE_API_BASE_URL` | Origin HTTPS của backend, không kèm `/v2`                                |
| Auth                | Giữ cấu hình adapter rỗng/Google false đến khi backend identity sẵn sàng |

Dùng pnpm 11.25.0 theo README; ghim phiên bản package manager trước triển khai. Biến `VITE_*` được đóng vào bundle khi build; sửa biến phải build/deploy lại. Không đưa NIM, database hoặc OAuth secrets vào frontend. `BACKEND_URL` và proxy trong `vite.config.ts` chỉ có tác dụng khi dev.

SPA cần fallback cho `/tours`, `/auth`, `/account`, `/contact`, `/support`, gồm query phiên và hash. Khi chuẩn bị deploy, thêm rewrites trong `src/frontend/vercel.json` theo [Vite trên Vercel](https://vercel.com/docs/frameworks/frontend/vite#using-vite-to-make-spas). Không để API `/v2` hoặc `/health` bị rewrite thành HTML; với backend riêng client gọi trực tiếp origin qua `VITE_API_BASE_URL`.

## Backend dùng chung

- Chạy `uv run tour-backend serve --host 0.0.0.0` trong dịch vụ/container/VM có ổ persistent, một process cho một application database. Reverse proxy cung cấp HTTPS. Chưa chọn nhà cung cấp backend.
- `DATABASE_URL` là SQLite trên ổ persistent; catalog tour Supabase là kho riêng, không thay database phiên/jobs. Runtime hiện chỉ chấp nhận SQLite, giữ `RuntimeLock` và chạy worker nền trong lifespan.
- Cấu hình nguồn tour thật và NIM theo [Supabase v2](../examples/backend-supabase-v2.md) và [runtime](backend-v2-runtime.md). `/health` phải `status=ok`, `data_origin=source`, `worker_enabled=true`.
- Đặt `CORS_ORIGINS` ở backend là JSON array các origin frontend được phép, không gồm path hoặc dấu `/` cuối; ví dụ `["https://frontend-preview.example.com"]`. Không dùng `*`. Link preview thay đổi cần thêm đúng origin/restart backend, hoặc dùng một domain preview ổn định.
- `/v2/sessions` cấp bearer runtime; người xem không nhập token hoặc API key. History vẫn riêng từng browser, chưa có đồng bộ tài khoản.

Vercel hỗ trợ FastAPI, nhưng backend repo đang phụ thuộc SQLite persistent và worker chạy liên tục. Vì vậy hướng backend riêng phù hợp runtime hiện tại; chuyển backend sang functions cần thiết kế lại persistence/jobs, không chỉ upload source. Đây là đánh giá từ code hiện hành, không phải giới hạn tuyệt đối của FastAPI trên Vercel. [Tài liệu FastAPI](https://vercel.com/docs/frameworks/backend/fastapi).

## Link chia sẻ và kiểm tra trước phát hành

Chọn nhánh frontend cần review, dùng URL theo nhánh để nhóm mở cùng bản mới nhất; ghi URL theo commit khi cần kiểm tra một bản cụ thể. Theo Vercel, lần deploy đầu của project mới là production; sau đó branch khác Production Branch tạo Preview. Dùng project preview độc lập hoặc cấu hình môi trường rõ trước lần deploy đầu. [Environments](https://vercel.com/docs/deployments/environments).

Kiểm tra Deployment Protection: link có thể yêu cầu quyền Vercel; cấu hình quyền cho nhóm theo nhu cầu và gói hiện có. Không mặc định rằng có URL là mọi người truy cập được. [Deployment Protection](https://vercel.com/docs/deployment-protection/methods-to-protect-deployments).

Kiểm trước khi chia sẻ: build/typecheck/lint/tests, refresh trực tiếp các route, assets, `/health`, tạo phiên/form tháng rời nhau và range giá, confirm, tìm tour source/evidence, chat/NIM, đổi phiên và mobile. Secrets chỉ ở backend; ảnh/report QA không nằm trong output deploy.

Nguồn cấu hình build: [Vercel Build Settings](https://vercel.com/docs/builds/configure-a-build#root-directory).
