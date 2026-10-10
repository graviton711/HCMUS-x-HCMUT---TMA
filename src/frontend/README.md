# Frontend — UI React trong cùng project

## Trách nhiệm

Giao diện tìm tour, tài khoản, lịch sử, proposal, what-if và kết quả. Backend hiện tại là nguồn chuẩn cho điều kiện, giá, eligibility, kết quả và trạng thái tác vụ. Frontend không truy cập SQLite/Supabase hoặc tự quyết định tour đạt điều kiện.

## Input/output

Nhận dữ liệu form/text, session identity và resources qua HTTP. Trả về thao tác review/confirm, yêu cầu tìm kiếm, history và what-if UI; chỉ gửi thay đổi explicit lên backend.

## Workflow

`app/` quản lý route/preferences/session shell; `features/workspace/` điều phối form, proposal, jobs, history và results; `components/` giữ control dùng lại. Phần UI được port từ `main`, nhưng API client hiện còn DTO/path `/v2`; chưa dùng được với API runtime hiện tại. Local storage chỉ giữ draft/guest metadata; credential không được ghi vào local storage hoặc URL.

## Interface với module khác

Contract đích nằm ở [`docs/backend-contract.md`](../../docs/backend-contract.md). Client/DTO `/v2` còn sót là code migration chưa hoàn tất; không mở rộng chúng. Không mang backend v2 hoặc logic domain vào frontend. Supabase Auth chỉ được gọi qua backend.

## Quyết định kỹ thuật

- Frontend là sibling module của `backend`, `ingest` và `shared` bên trong `src/`; không tạo project frontend ở root hoặc layout monorepo khác.
- React state không là nguồn dữ liệu cho quyền sở hữu history, giá hay hard eligibility.
- Requirement/proposal/comparison chỉ hiển thị theo resource backend trả về; confirm và search luôn là thao tác riêng, explicit.
- Tests, package manifest và lockfile thuộc module này.

## Chạy và kiểm tra

Từ repo root, backend hiện có thể chạy bằng terminal thứ nhất:

```powershell
uv sync
uv run tour-backend serve
```

Trong terminal thứ hai:

```powershell
pnpm.cmd --dir src/frontend install --frozen-lockfile
pnpm.cmd --dir src/frontend dev
```

UI dev server có thể chạy ở <http://127.0.0.1:5173>, nhưng một số workspace actions chưa nối với runtime API. Kiểm tra package bằng `corepack pnpm@11.25.0 --dir src/frontend typecheck`, `test` và `build`.
