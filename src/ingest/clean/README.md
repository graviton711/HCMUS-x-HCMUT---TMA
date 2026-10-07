# clean — lọc rác theo loại, không theo tên site

## Trách nhiệm

Giảm khối thô thành dữ liệu dùng được mà không mất fact: bỏ field kỹ thuật,
hoist giá trị lặp lên cấp tour, tách boilerplate khỏi prose, gom notes theo
key ngữ nghĩa. Mọi rule đều category-based (loại field), không chứa tên
site, endpoint hay selector nào.

## Input / Output

- Input: khối thô từ `blocks` + pattern từ profile (presentation keys,
  keep patterns, note patterns).
- Output: cùng cấu trúc, đã lọc + `shared` (giá trị lặp) — mất mát nào cũng
  giải thích được bằng rule.

## Workflow

Drop null/rỗng/UUID/presentation → dedup giá trị giống hệt qua các đợt
(hoist lên cấp tour) → prose: bỏ dòng code + chạy boilerplate dài (cloud tag,
nav) → notes: gom subtree theo key ngữ nghĩa (`includ|exclud|condition|...`).

## Interface

- Đọc pattern từ profile (`junk`, `keep`, `notes`), engine không hardcode.
- Output cho `validate` kiểm evidence và `pipeline` ghi CSV/JSON.

## Quyết định kỹ thuật

- Function thuần; mỗi rule có test riêng chứng minh giữ fact đúng, bỏ rác đúng.
- Ngưỡng (độ dài prose, độ dài chạy boilerplate, overlap fuzzy) nằm ở
  `settings.yaml`, không nằm trong code.
