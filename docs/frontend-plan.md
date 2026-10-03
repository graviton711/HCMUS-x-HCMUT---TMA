# Planning frontend / UI/UX

**Trạng thái:** Bản planning v1 để cùng review. Đang PLANNING; các phase xây dựng/tích hợp bên dưới là công việc tương lai.
**Baseline:** Idea, kiến trúc và wireframe đã chốt theo xác nhận ngày 03/10/2026. Chưa chốt stack frontend, visual final và phần API còn thiếu.

## Tài liệu và cách làm việc

- [Idea](idea.md), [kiến trúc](system-architecture.md), [wireframe](wireframes.md): giữ phạm vi và bố cục đã chốt.
- [Luồng và trạng thái UI](frontend-flows.md): bản chi tiết hành vi để review.
- [Checklist frontend–backend](frontend-backend-checklist.md): những quyết định kỹ thuật phải thống nhất.
- [Chuẩn bị skill](frontend-design-preparation.md), [module frontend](../src/frontend/README.md).

Mỗi task có ID, người phụ trách, đầu ra và điều kiện hoàn thành. `[ ]` chưa xong; `[x]` chỉ dùng khi có đầu ra đã kiểm tra. Khi đang làm hoặc bị chặn, thêm `Đang làm` / `Bị chặn: <lý do>` vào task; không tick thay cho tiến độ.

Mỗi phiên: chọn task → đọc/cập nhật tài liệu liên quan → tạo đầu ra → kiểm tra → review điểm cần quyết định → cập nhật checklist. Thay đổi phạm vi hoặc contract phải ghi quyết định và tác động trước khi làm phần phụ thuộc.

**Phân công:** Bạn phụ trách frontend và quyết định trải nghiệm sản phẩm; Codex soạn phương án, nghiên cứu reference, thiết kế, hỗ trợ kỹ thuật và kiểm tra; backend phụ trách endpoint, dữ liệu, lọc/so sánh và bằng chứng. FE + BE cùng chốt contract. Bạn review màn hình và hành vi cụ thể, không cần tự chọn font/token/thư viện từ đầu.

## Các phase

| Phase | Công việc | Đầu ra / điều kiện hoàn thành | Phụ thuộc |
|---|---|---|---|
| P0 | Ghi nhận nền tảng | Tài liệu nền và skill có thể truy cập | Đã có |
| P1 | Chốt flow và contract với BE | Không còn điểm chưa chốt ảnh hưởng luồng chính; có schema và JSON mẫu dùng được | P0 |
| P2 | Chốt nền tảng kỹ thuật FE | Stack, cấu trúc, state, chiến lược API/mock/kiểm tra được ghi rõ | P1; so sánh stack có thể làm sớm |
| P3 | Thiết kế UI/UX chi tiết | Màn chính, mobile, token và trạng thái đã review trên cùng dữ liệu mẫu | P1; tìm reference có thể làm sớm |
| P4 | Xây frontend với mock đúng contract | Hai luồng đầu vào đi hết đến kết quả và evidence; đủ trạng thái | P1–P3 |
| P5 | Tích hợp backend thật | Chạy được luồng đầy đủ; lỗi và dữ liệu thiếu được xử lý đúng | P4 + API BE sẵn sàng |
| P6 | Kiểm tra và bàn giao demo | Checklist nghiệm thu đạt, demo chạy được, giới hạn được ghi nhận | P5 |

Không chốt lịch ngày khi chưa biết deadline và năng lực backend. Ưu tiên theo phụ thuộc, không làm visual final cho tính năng chưa có contract. P2/P3 có thể nghiên cứu độc lập trong khi FE + BE hoàn thiện P1.

### P0. Nền tảng

- [x] P0.1 — Ghi nhận idea, kiến trúc, wireframe là baseline đã chốt. **Owner:** Bạn + Codex.
- [x] P0.2 — Cài 3 skill, ghim phiên bản, ghi phạm vi sử dụng. **Owner:** Codex.
- [x] P0.3 — Tạo roadmap, flow draft và checklist BE để review. **Owner:** Codex.

### P1. Flow và hợp đồng FE–BE

- [ ] P1.1 — Review hai luồng: tìm theo nhu cầu và so sánh URL; chốt thao tác sửa tiêu chí, thử lại, quay lại. **Owner:** Bạn + Codex. **Đầu ra:** `frontend-flows.md` đã thống nhất.
- [ ] P1.2 — Chốt danh sách field nhập, bắt buộc/tùy chọn, validation và đơn vị ngân sách; xử lý nhóm khách, tuổi trẻ em, ngày linh hoạt. **Owner:** FE + BE.
- [ ] P1.3 — Chốt endpoint cho nhu cầu, làm rõ yêu cầu và so sánh; quyết định request đồng bộ hay job theo thời gian xử lý thực tế. **Owner:** FE + BE.
- [ ] P1.4 — Chốt schema request/response, lỗi, offer/evidence reference, freshness, giá và kết quả lọc. **Owner:** FE + BE. **Đầu ra:** các mục C1–C10 trong checklist BE.
- [ ] P1.5 — BE cung cấp JSON mẫu đủ các tình huống; hai phía xác nhận mẫu hợp lệ với schema. **Owner:** BE + FE. **Đầu ra:** bộ mẫu C11.
- [ ] P1.6 — Chốt đăng nhập có thuộc demo hay chỉ là placeholder wireframe; chốt lưu/khôi phục kết quả khi refresh và phạm vi số URL/tour. **Owner:** Bạn + FE + BE.

**Hoàn thành P1 khi:** Có contract chuẩn duy nhất được hai phía review; mọi giá trị quan trọng trên màn hình có field/nguồn hoặc cách hiển thị thiếu đã thống nhất. Không tự thêm API/enum vào frontend để lấp chỗ trống.

### P2. Nền tảng kỹ thuật frontend

- [ ] P2.1 — Chọn stack và ghi lý do theo bảng bên dưới; chốt phiên bản/runtime sau khi kiểm tra tương thích. **Owner:** Bạn + Codex.
- [ ] P2.2 — Chốt package root, route, ranh giới feature và tài liệu cạnh từng module. **Owner:** Codex + FE. **Đầu ra:** cập nhật `src/frontend/README.md`.
- [ ] P2.3 — Tách form draft, criteria đã submit, kết quả BE và state hiển thị; quy định bảo toàn state và chống response cũ ghi đè request mới. **Owner:** FE.
- [ ] P2.4 — Chốt sinh type từ schema chung, validation lúc nhận response, API client, error mapping, timeout/retry/cache và hủy request. **Owner:** FE + BE.
- [ ] P2.5 — Chốt mock dùng cùng API client/schema với dữ liệu thật; cấu hình API base URL, proxy/CORS, môi trường local/demo và lệnh kiểm tra. **Owner:** FE + BE.

**Hoàn thành P2 khi:** Có thể chỉ rõ UI nhận dữ liệu ở đâu, chuyển đổi thế nào, state nào do ai sở hữu và lỗi contract được phát hiện ra sao.

### P3. Thiết kế UI/UX

- [ ] P3.1 — Codex tìm 3–5 reference phù hợp form, comparison và evidence; ghi link, điểm học được, mobile và điều kiện dùng asset/template. Template bạn gửi sau được đánh giá bằng cùng tiêu chí.
- [ ] P3.2 — Codex tạo 2 hướng visual trên **cùng một màn so sánh**; bạn chọn theo khả năng đọc/đối chiếu và cảm giác sản phẩm. `minimalist-ui` là một ứng viên, chưa phải phong cách mặc định.
- [ ] P3.3 — Chốt token (màu thương hiệu/trạng thái, typography có dấu Việt, spacing, radius, icon, focus, theme) và danh sách component dùng lại cùng trạng thái của chúng. **Owner:** Codex đề xuất; bạn review.
- [ ] P3.4 — Thiết kế chi tiết input hai tab, xử lý/làm rõ, bảng so sánh và panel evidence trên desktop/mobile, bám wireframe đã chốt.
- [ ] P3.5 — Thiết kế loading, empty, chỉ còn 1 tour, partial, lỗi, dữ liệu cũ/thiếu/chưa xác minh; viết microcopy cho thao tác tiếp theo.
- [ ] P3.6 — Chốt mobile: vẫn đối chiếu cùng hàng tiêu chí, giữ tên tour và mở evidence dễ dàng; kiểm tra bàn phím, focus và nội dung dài trên prototype.
- [ ] P3.7 — Walkthrough với bạn và một vài người đúng nhóm mục tiêu: nhập nhu cầu, giải thích trade-off, tìm nguồn giá; ghi vấn đề và chỉnh thiết kế.

**Owner P3:** Codex chuẩn bị thiết kế; bạn quyết định hướng. Backend kiểm tra dữ liệu nào thực sự hỗ trợ màn hình.
**Hoàn thành P3 khi:** Mọi component/trạng thái đã có thiết kế và mẫu dữ liệu; không dùng dữ liệu giả làm bằng chứng thật. Taste chỉ áp dụng phần giới thiệu; redesign dùng checklist kiểm tra, không tự đổi wireframe hoặc stack.

### P4. Xây frontend với mock

- [ ] P4.1 — Dựng nền tảng đã chốt, token/component dùng chung và API boundary có validation.
- [ ] P4.2 — Slice URL: nhập/validate → gửi request mock → xử lý → so sánh → mở evidence → thử lại/sửa URL.
- [ ] P4.3 — Slice nhu cầu: form → làm rõ nếu cần → xác nhận criteria → kết quả; giữ ưu tiên tách ràng buộc cứng.
- [ ] P4.4 — Thêm chọn offer/ngày, đổi tiêu chí/sắp xếp minh bạch và định dạng tiền/ngày theo contract; không tính hộ backend khi thiếu dữ liệu.
- [ ] P4.5 — Hoàn thiện mọi trạng thái P3.5, mobile, keyboard, liên kết nguồn và chống submit lặp/response cũ.
- [ ] P4.6 — Kiểm tra các slice bằng JSON mẫu đã thống nhất; sửa lỗi logic/layout và đối chiếu với tài liệu.

**Owner P4:** FE + Codex. **Hoàn thành khi:** Mock thay đổi được theo scenario; mọi thao tác chính hoạt động; mock ghi rõ là dữ liệu minh họa.

### P5. Tích hợp backend thật

- [ ] P5.1 — Kết nối môi trường BE; xác nhận base URL, CORS, HTTP status, schema và timeout/job lifecycle.
- [ ] P5.2 — Chạy cả hai luồng bằng dữ liệu thật; kiểm tra một phần nguồn lỗi, không có tour phù hợp và toàn bộ nguồn thất bại.
- [ ] P5.3 — Kiểm tra giá đúng offer, phụ thu chưa biết, freshness, xác minh nguồn và reference trade-off mở đúng evidence.
- [ ] P5.4 — Kiểm tra sửa criteria trong lúc xử lý, hủy/chạy lại, mất mạng và khôi phục màn hình theo chính sách đã chốt.
- [ ] P5.5 — Ghi bug FE/BE với request ID và payload tái hiện phù hợp; đồng bộ tài liệu sau sửa contract. Mock và API thật phải cùng schema.

**Owner P5:** FE + BE. **Hoàn thành khi:** Không có phần UI quan trọng phải suy đoán dữ liệu; không che lỗi nguồn bằng success state.

### P6. Nghiệm thu và bàn giao

- [ ] P6.1 — Typecheck, lint, build và kiểm tra schema/fixture đạt; kiểm tra logic giá/ngày/status/reference có rủi ro sai nghĩa.
- [ ] P6.2 — E2E cho hai luồng thành công và các nhánh partial/error/empty; test response cũ và giữ input khi thử lại.
- [ ] P6.3 — Kiểm tra trên desktop/mobile mục tiêu, nội dung dài, bàn phím, contrast, reduced-motion và theme đã chọn.
- [ ] P6.4 — Kiểm tra hiệu năng trang thực tế và thời gian BE riêng; xử lý ảnh/font/layout shift, không che chờ BE bằng tiến độ giả.
- [ ] P6.5 — Walkthrough: người dùng hiểu vì sao tour khác nhau, nhận ra giá cũ/thiếu và mở được nguồn đúng field.
- [ ] P6.6 — Chuẩn bị môi trường demo, hướng dẫn chạy, kịch bản trình diễn, giới hạn nguồn/dữ liệu và checklist bàn giao; smoke test sau triển khai.

**Owner P6:** FE + Codex; BE hỗ trợ các lỗi pipeline. **Hoàn thành khi:** Luồng đầy đủ chạy được, kết quả kiểm chứng được và không còn lỗi chặn thao tác chính.

## Stack đề xuất để review ở P2

| Phương án | Gain thực tế | Chi phí / rủi ro | Fit pipeline và dài hạn |
|---|---|---|---|
| React + TypeScript + Vite | UI tương tác, type rõ; tách được form, comparison, evidence; build frontend độc lập | Phải chốt routing, data fetching và cách host SPA/refresh route | Phù hợp API JSON riêng; giữ được contract validation, component system và kiểm tra đầy đủ |
| Next.js + TypeScript | Thêm server rendering, ranh giới server/client; phù hợp khi có trang tour công khai cần SEO | Thêm runtime và luồng server/client; cần tránh lặp trách nhiệm với BE | Tốt khi SSR/SEO là yêu cầu thực tế; chưa thấy yêu cầu này trong baseline |

**Đề xuất ban đầu:** React + TypeScript + Vite cho ứng dụng so sánh. Lý do là phần giá trị nằm ở tương tác và kiểm chứng dữ liệu; hai hướng đều có thể mạnh về chất lượng UI, còn lợi ích SSR chưa được yêu cầu. Đây là đề xuất, chưa chốt stack.

Data fetching/cache có thể dùng [TanStack Query](https://tanstack.com/query/latest/docs/framework/react/overview); vẫn phải tự đặt policy cho POST so sánh, retry và freshness. Routing, form/schema library, bảng và styling sẽ chọn theo flow, khả năng accessibility và nhu cầu mobile; không gom nhiều thư viện chỉ vì skill gợi ý.

Tham chiếu chính thức: [Vite](https://vite.dev/guide/), [Next.js server/client components](https://nextjs.org/docs/app/getting-started/server-and-client-components). Chọn phiên bản khi chốt P2, không dùng version từ trí nhớ.

## Việc làm tiếp theo

1. Review P1.1–P1.2: flow và dữ liệu người dùng thực sự cần nhập.
2. Đưa checklist C1–C11 cho team backend để chốt API/JSON, owner và tiến độ từng mục.
3. Codex chuẩn bị reference và phương án visual P3.1–P3.2; bạn có thể bổ sung template sau.

Các điều kiện hoàn thành thể hiện phụ thuộc trong roadmap; không tự cấp quyền triển khai. Quy trình PLANNING vẫn theo `AGENTS.md`.
