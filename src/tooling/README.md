# Project tooling

## Trách nhiệm

Expose các lệnh phát triển repo root với tên thống nhất, đồng thời giữ mỗi app dùng package manager gốc của nó. Lệnh frontend không đưa React/Vite vào backend runtime.

## Input và output

- Input: subcommand `dev`.
- Output: chạy script frontend tương ứng, giữ nguyên stdout/stderr và trả lại exit code của tiến trình con.

## Workflow

1. Xác định thư mục repo từ vị trí module, không phụ thuộc thư mục shell hiện tại.
2. Chạy `corepack pnpm --dir src/frontend dev` tại repo root.
3. Giữ tiến trình ở foreground để log và `Ctrl+C` hoạt động như lệnh gốc.

## Interface

Đăng ký `tour-frontend` trong `pyproject.toml`; gọi từ repo root bằng `uv run tour-frontend dev`. Cấu hình Vite và API proxy tiếp tục thuộc `src/frontend`.

## Quyết định kỹ thuật

CLI chỉ là adapter tên lệnh; package manager và script thực tế vẫn do `src/frontend/package.json` quyết định. Không nhân bản cấu hình Vite hoặc dependency frontend vào Python.
