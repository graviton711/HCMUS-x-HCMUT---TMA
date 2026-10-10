# Frontend — UI React trong cùng project

## Trách nhiệm

Giao diện tìm tour, tài khoản, lịch sử, proposal, what-if và kết quả. Backend hiện tại là nguồn chuẩn cho điều kiện, giá, eligibility, kết quả và trạng thái tác vụ. Frontend không truy cập SQLite/Supabase hoặc tự quyết định tour đạt điều kiện.

## Input/output

Nhận dữ liệu form/text, session identity và resources qua HTTP. Trả về thao tác review/confirm, yêu cầu tìm kiếm, history và what-if UI; chỉ gửi thay đổi explicit lên backend.

## Workflow

`app/` quản lý route/preferences/session shell; guest workspace dùng API hiện tại cho session, catalog, requirement interpretation, synchronous comparison và persisted snapshots. Local storage chỉ giữ draft/guest metadata; bearer token chỉ nằm trong session storage, không vào local storage hoặc URL. Account/Auth, proposals, jobs, full account history, evidence/messages và what-if từ `main` vẫn chưa được port.

## Interface với module khác

Runtime contract nằm ở [`docs/backend-contract.md`](../../docs/backend-contract.md). `api/current.ts` là HTTP boundary cho guest workspace. Client/DTO `/v2` còn lại chỉ là migration source cho features chưa port; không mở rộng hoặc dùng chúng với current backend. Không mang backend v2 hoặc logic domain vào frontend. Supabase Auth chỉ được gọi qua backend.

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

UI dev server có thể chạy ở <http://127.0.0.1:5173>. Guest search dùng current runtime; account and advanced workspace actions remain unavailable until their backend contracts are ported. Kiểm tra package bằng `corepack pnpm@11.25.0 --dir src/frontend typecheck`, `test` và `build`.
