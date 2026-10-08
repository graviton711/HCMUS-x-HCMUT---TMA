# Chia sẻ prototype frontend

**Trạng thái:** user đã đồng ý GitHub Pages ngày 03/10/2026. Đã commit/push prototype và workflow lên `feature/minh-phu` tại `577033a`, xác nhận SHA local/remote khớp. [Run #1](https://github.com/graviton711/HCMUS-x-HCMUT---TMA/actions/runs/37135033019) chạy từ đúng nhánh nhưng dừng ở **Configure GitHub Pages: HTTP 404, Get Pages site failed**; GitHub yêu cầu bật Pages với source GitHub Actions. Chưa có link online được xác minh.

Đã đăng nhập và kiểm tra GitHub UI: repo **private**, tài khoản `minhphune` không có quyền repository options/Pages. Cần chủ repo `graviton711` hoặc người được phân quyền Pages xác nhận gói hỗ trợ và bật source GitHub Actions; sau đó re-run run trên. Không thay đổi visibility hoặc gói GitHub.

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

## Cập nhật / kiểm chứng

- Sau thiết lập, push thay đổi trong thư mục prototype/workflow vào `feature/minh-phu` sẽ cập nhật cùng link preview. Tài liệu nằm trong thư mục prototype cũng kích hoạt workflow; chỉ sửa tài liệu ngoài phạm vi này không chạy deploy.
- Commit nguồn và publish là hai trạng thái riêng; workflow thành công chưa thay nghiệm thu visual P3.2 hoặc nghiệm thu sản phẩm P5/P6.
- Local prototype đã đạt 56/56 browser checks. Bước publish cần kiểm tra thêm đường dẫn project trên hosting và xác nhận run/commit triển khai; không chạy lại backend/crawler chỉ vì thêm hosting tĩnh.
- Workflow đã parse YAML và kiểm tra giới hạn branch/artifact/quyền/SHA action; GitHub nhận workflow và chạy job. Deployment còn bị chặn ở cấu hình Pages của repo, không được ghi thành publish thành công.
- Đã kiểm tra local dưới prefix `/HCMUS-x-HCMUT---TMA/`: bảng review và A/B trả 200, ảnh/font tải đủ, không request sai prefix hoặc lỗi console; viewer B mobile có viewport 390px và mở được evidence. Đây là kiểm tra base path trước publish, chưa xác nhận website online.
- Hướng visual, count policy, framework, contract G1–G10 và crawler D1–D5 vẫn theo [design review](frontend-design-review.md) / [planning](frontend-plan.md).

Nguồn: [GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages), [publishing source](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site), [custom Actions workflow](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).
