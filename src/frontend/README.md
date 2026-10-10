# frontend — UI React trong cùng project

## Trách nhiệm

Giao diện tìm tour, tài khoản, lịch sử, proposal, what-if và kết quả. Frontend dùng API backend làm nguồn chuẩn cho dữ liệu, eligibility và trạng thái job; không truy cập SQLite/Supabase hoặc tự quyết định tour đạt điều kiện.

## Input/output

Vào: input có cấu trúc/text, session identity và resources từ API. Ra: review/commit requirement, explicit proposal confirmation, comparison, history và what-if UI. Tháng/ngân sách dùng đúng criteria backend trả và nhận.

## Workflow

`api/` sở hữu HTTP, error handling và chuyển đổi response hiện tại sang view models; `app/` quản lý route/account/session; `features/workspace/` điều phối form, proposal, jobs, history và results; `components/` giữ control dùng lại. Local storage chỉ giữ draft/guest metadata; token chỉ ở `sessionStorage`.

## Interface với module khác

Chỉ gọi API đã mô tả ở [`docs/backend-contract.md`](../../docs/backend-contract.md). Các DTO nội bộ phải được validate từ contract hiện tại; không mang `contracts/v2` hoặc backend v2 vào module này. Supabase Auth chỉ được gọi qua backend.

## Quyết định kỹ thuật

- Đây là sibling module của `backend`, `ingest`, `shared` trong cùng `src/`; không tạo project frontend ở root hoặc layout monorepo khác.
- React state không là nguồn dữ liệu authorization, history owner, giá hay hard eligibility.
- Requirement/proposal/comparison chỉ hiển thị theo revision/resource backend trả về; thao tác confirm và search luôn explicit.
- Unit/contract/browser tests ở cạnh module; package manifest và lockfile thuộc module frontend.
