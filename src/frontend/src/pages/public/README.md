# pages/public

Các màn hình landing, hỗ trợ và trang fallback cho route chưa kết nối.

- Input: callback `onStart`/`onContinue`, helper điều hướng `link`.
- Output: các page nội dung tĩnh (`LandingPage`, `SupportPage`, `UnavailablePage`).
- Workflow: component thuần presentational; mỗi page sở hữu `*.module.css` của riêng nó.
- Interface: barrel `src/pages/public`. Không page nào import slice page khác.
- Quyết định kỹ thuật: `LandingPage` và `SupportPage` là component riêng với CSS Module riêng (không dùng chung CSS page).
