# Chia sẻ prototype frontend

Hướng dẫn xuất bản prototype bằng workflow `.github/workflows/frontend-design-pages.yml`. Hosting cần được chủ repo bật; tài liệu này không xác nhận website đã deploy.

## Phạm vi và cách triển khai

- Chỉ xuất bản `prototypes/frontend-design/`: bảng review, hai hướng A/B, viewer desktop/mobile và asset có license. Đây là prototype PLANNING với dữ liệu minh họa, chưa có API hoặc frontend production.
- Workflow `.github/workflows/frontend-design-pages.yml` chạy khi push thay đổi prototype/workflow vào **`feature/minh-phu`**. Job cũng kiểm tra đúng ref; không chạy từ nhánh khác hoặc pull request.
- GitHub Actions upload chính thư mục prototype và deploy bằng GitHub Pages. Không tạo nhánh `gh-pages`, không copy backend, contracts, dữ liệu crawler, môi trường hoặc toàn bộ repo vào website.
- Dùng các GitHub Actions chính thức ghim commit SHA, checkout không lưu credential; quyền `contents: read`, `pages: write`, `id-token: write` nằm ở job publish. Không thêm secret hoặc token riêng.
- HTML/CSS/JS dùng đường dẫn asset tương đối để hoạt động dưới đường dẫn project của GitHub Pages; không cần Node build hoặc framework.

## Thiết lập một lần

1. Đăng nhập GitHub bằng tài khoản có quyền quản lý Pages của repo `graviton711/HCMUS-x-HCMUT---TMA`; kiểm tra chưa có website Pages khác trước khi thay đổi.
2. Repo **Settings → Pages → Build and deployment → Source: GitHub Actions**. Nếu environment `github-pages` có giới hạn branch, cho phép `feature/minh-phu` xuất bản prototype. Không bỏ approval/protection hiện có; ghi nhận nếu cần người quản lý duyệt.
3. Commit/push prototype và workflow trên `feature/minh-phu`. Theo dõi run **Frontend design preview** trong Actions; nếu đã push trước khi bật Pages, re-run run đó sau khi cấu hình.
4. Chỉ ghi link public sau khi deploy thành công và đã mở kiểm tra bảng review, A/B, iframe mobile, ảnh/font và tương tác evidence trên hosting.

GitHub Free hỗ trợ Pages cho repo public; private cần gói phù hợp. Nếu repo không đủ điều kiện, giữ visibility hiện tại và báo lại lựa chọn hosting; không tự chuyển repo thành public, nâng gói hoặc thay website đang có.

## Cập nhật và kiểm tra

- Push thay đổi prototype/workflow vào `feature/minh-phu` để cập nhật preview sau khi hosting đã bật. Sửa tài liệu ngoài thư mục prototype không kích hoạt workflow.
- Sau deploy, kiểm tra đường dẫn project, asset/font, viewer desktop/mobile và thao tác evidence trên hosting; chỉ ghi link sau khi xác nhận hoạt động.
- Flow và data contract tham khảo [frontend-flows.md](frontend-flows.md), [frontend-protocol-v2.md](frontend-protocol-v2.md) và [frontend-crawler-integration.md](frontend-crawler-integration.md).

Nguồn: [GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages), [publishing source](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site), [custom Actions workflow](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).
