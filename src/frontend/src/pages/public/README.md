# pages/public

Các màn hình hỗ trợ và trang fallback cho route chưa kết nối (`SupportPage`, `UnavailablePage`).

- Input: callback `onStart`/`onContinue`, helper điều hướng `link`.
- Output: các page nội dung tĩnh.
- Workflow: component thuần presentational; mỗi page sở hữu `*.module.css` của riêng nó.
- Interface: barrel `src/pages/public`. Không page nào import slice page khác.
- Quyết định kỹ thuật: mỗi page là component riêng với CSS Module riêng (không dùng chung CSS page).
- Trình bày: trang hỗ trợ dùng cùng thang chữ và bề mặt sáng của app; nội dung FAQ giữ độ rộng đọc thoải mái, khối liên hệ xếp cạnh trên desktop và thành một cột trên màn hình nhỏ.
