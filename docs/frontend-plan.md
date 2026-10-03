# Planning frontend / UI/UX

**Trạng thái:** Planning v1.2 trên `feature/minh-phu`, đối chiếu backend `0b7e59f`, crawler docs `4b720a9` và crawler agent `6f84417` ngày 03/10/2026. Đang PLANNING; các phase xây dựng/tích hợp bên dưới là công việc tương lai.
**Baseline:** Idea, kiến trúc và wireframe đã chốt theo xác nhận của bạn. Backend có pipeline `/v1` với session/revision/jobs; tour data API vẫn synthetic. Tourcrawl và scripts đã merge nhưng chưa có adapter/transport vào backend. Stack frontend, visual final và public contract còn cần chốt.

Giữ nguyên 7 phase và 38 task ID của v1. Đã thay giả định API cũ bằng thông tin đọc từ code; **không bỏ tính năng hoặc tick nghiệm thu chỉ vì backend/crawler đã implement một phần**. Checklist giữ G1–G8; đối chiếu crawler bổ sung D1–D5. Mọi chỉnh sửa/merge chỉ trên nhánh Minh Phú theo `AGENTS.md`.

## Tài liệu và cách làm việc

- [Idea](idea.md), [kiến trúc](system-architecture.md), [wireframe](wireframes.md): giữ phạm vi và bố cục đã chốt.
- [Luồng và trạng thái UI](frontend-flows.md): bản chi tiết hành vi để review.
- [Checklist frontend–backend](frontend-backend-checklist.md): những quyết định kỹ thuật phải thống nhất.
- [Hướng tích hợp API v1](frontend-api-integration.md): endpoint, payload, session/revision/job/offer/evidence và giới hạn thực tế.
- [Đối chiếu crawler](frontend-crawler-integration.md): output CSV/raw JSON khác contract runtime; D1–D5 để BE + crawler chốt adapter, registry, giá/evidence và profiles.
- [Contract HTTP](api-contract.md), [domain](backend-contracts.md), [schemas](../contracts/README.md), [input mẫu](../examples/README.md): nguồn chuẩn backend; chưa đủ schema cho mọi public response.
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
| P5 | Tích hợp backend và nguồn thật | Chạy API fixture trước, sau đó đủ luồng với nguồn thật; lỗi/dữ liệu thiếu đúng nghĩa | P4 + API BE; crawler thật cho P5.2–P5.3 |
| P6 | Kiểm tra và bàn giao demo | Checklist nghiệm thu đạt, demo chạy được, giới hạn được ghi nhận | P5 |

Không chốt lịch ngày khi chưa biết deadline và năng lực backend. Ưu tiên theo phụ thuộc, không làm visual final cho tính năng chưa có contract. P2/P3 có thể nghiên cứu độc lập trong khi FE + BE hoàn thiện P1.

**Điểm chặn ưu tiên P1:** G1 giá public khi không có Budget, G2 tên tour/nhà cung cấp/canonical URL, G8 schema response + snapshots. Các mục nội dung/trade-off (G3), catalog (G4), freshness (G5), revision/restore (G6), sửa AND/OR (G7) giữ nguyên để bàn với BE; không hạ yêu cầu wireframe theo giới hạn fixture.

**Phụ thuộc dữ liệu thật:** D1 adapter CrawlResult/transport; D2 registry/capability/TTL; D3 giá–ngày–availability có nghĩa; D4 provenance/access/verification; D5 thống nhất profile formats và gold fixtures. CLI crawl có code không thay nghiệm thu P5.2; FE tiếp tục dùng public API v1.

### P0. Nền tảng

- [x] P0.1 — Ghi nhận idea, kiến trúc, wireframe là baseline đã chốt. **Owner:** Bạn + Codex.
- [x] P0.2 — Cài 3 skill, ghim phiên bản, ghi phạm vi sử dụng. **Owner:** Codex.
- [x] P0.3 — Tạo roadmap, flow draft và checklist BE để review. **Owner:** Codex.

### P1. Flow và hợp đồng FE–BE

- [ ] P1.1 — Review hai luồng: tìm theo nhu cầu và so sánh URL; chốt thao tác sửa tiêu chí, thử lại, quay lại. **Owner:** Bạn + Codex. **Đầu ra:** `frontend-flows.md` đã thống nhất.
- [ ] P1.2 — Ánh xạ control form vào conditions/party/value đã có; chốt field bắt buộc/tùy chọn, hard/soft, catalog canonical IDs, budget basis/coverage, tuổi và ngày linh hoạt. **Owner:** FE + BE. **Còn mở:** C1/G4/G7; URL-only không bắt nhập party/ngày/budget.
- [ ] P1.3 — Review endpoint/lifecycle đã ghi tại `frontend-api-integration.md`: form/edits đồng bộ, text/comparison qua job; chốt FE polling/cancel/retry và base URL. **Owner:** FE + BE. **Đã có:** code `/v1`; không cần thiết kế lại endpoint từ đầu.
- [ ] P1.4 — Chốt schema request/**public response**, lỗi, offer/evidence reference, freshness, giá và kết quả lọc; BE bổ sung G1–G3/G5/G8 và cùng crawler chốt D1–D4. **Owner:** FE + BE; crawler cung cấp dữ kiện nguồn. **Đầu ra:** C1–C10 đủ hỗ trợ wireframe, không dùng CrawlResult/CSV nội bộ thay public DTO.
- [ ] P1.5 — BE cung cấp response snapshots đủ các tình huống, nối hai input mẫu đã có; hai phía xác nhận schema và expected UI. **Owner:** BE + FE. **Đầu ra:** bộ mẫu C11, bao gồm URL-only không hard/budget và groups rỗng nhưng có candidates.
- [ ] P1.6 — Review session ẩn danh v1 (chưa có account login); chốt placeholder đăng nhập, token storage, lưu IDs/khôi phục đúng revision sau refresh và hết hạn. URL đã giới hạn 2–5; chốt số cột/candidate discovery. **Owner:** Bạn + FE + BE. **Còn mở:** G6.

**Hoàn thành P1 khi:** Có contract chuẩn duy nhất được hai phía review; mọi giá trị quan trọng trên màn hình có field/nguồn hoặc cách hiển thị thiếu đã thống nhất. Không tự thêm API/enum vào frontend để lấp chỗ trống.

### P2. Nền tảng kỹ thuật frontend

- [ ] P2.1 — Chọn stack và ghi lý do theo bảng bên dưới; chốt phiên bản/runtime sau khi kiểm tra tương thích. **Owner:** Bạn + Codex.
- [ ] P2.2 — Chốt package root, route, ranh giới feature và tài liệu cạnh từng module. **Owner:** Codex + FE. **Đầu ra:** cập nhật `src/frontend/README.md`.
- [ ] P2.3 — Tách draft, committed Requirement revision, parse/comparison job, result snapshot và state hiển thị; chống response cũ ghi đè, giữ draft khi conflict, bảo toàn cây AND/OR và khôi phục đúng phiên. **Owner:** FE. **Phụ thuộc:** G6/G7.
- [ ] P2.4 — Chốt sinh type và runtime validation từ request + public response schemas; API boundary ánh xạ id/envelope, readiness, lỗi HTTP/job; policy idempotency/retry/cache/cancel. **Owner:** FE + BE. **Phụ thuộc:** G8; schema request hiện chưa đủ full client.
- [ ] P2.5 — Chốt mock và API thật dùng cùng schema/client; base URL/proxy/CORS, token/session, config local/demo, hosting refresh route và lệnh kiểm tra. **Owner:** FE + BE. **Đã có:** CORS localhost:3000/5173 và Bearer token; cấu hình hosting vẫn cần chốt.

**Hoàn thành P2 khi:** Có thể chỉ rõ UI nhận dữ liệu ở đâu, chuyển đổi thế nào, state nào do ai sở hữu và lỗi contract được phát hiện ra sao.

### P3. Thiết kế UI/UX

- [ ] P3.1 — Codex tìm 3–5 reference phù hợp form, comparison và evidence; ghi link, điểm học được, mobile và điều kiện dùng asset/template. Template bạn gửi sau được đánh giá bằng cùng tiêu chí.
- [ ] P3.2 — Codex tạo 2 hướng visual trên **cùng một màn so sánh**; bạn chọn theo khả năng đọc/đối chiếu và cảm giác sản phẩm. `minimalist-ui` là một ứng viên, chưa phải phong cách mặc định.
- [ ] P3.3 — Chốt token (màu thương hiệu/trạng thái, typography có dấu Việt, spacing, radius, icon, focus, theme) và danh sách component dùng lại cùng trạng thái của chúng. **Owner:** Codex đề xuất; bạn review.
- [ ] P3.4 — Thiết kế chi tiết input text/form hai tab, nhóm hard/soft/làm rõ, jobs, offer picker, bảng và evidence desktop/mobile; bám wireframe. Hàng giá/tên/nhà cung cấp/chính sách còn G1–G3, giữ yêu cầu và đánh dấu field chờ BE.
- [ ] P3.5 — Thiết kế loading, empty, chỉ còn 1 tour, partial, lỗi, dữ liệu cũ/thiếu/chưa xác minh; thêm không hard filter, nhiều offer chưa chọn, revision conflict, phiên hết hạn và job hủy. Viết microcopy theo enum thực tế.
- [ ] P3.6 — Chốt mobile: vẫn đối chiếu cùng hàng tiêu chí, giữ tên tour và mở evidence dễ dàng; kiểm tra bàn phím, focus và nội dung dài trên prototype.
- [ ] P3.7 — Walkthrough với bạn và một vài người đúng nhóm mục tiêu: nhập nhu cầu, giải thích trade-off, tìm nguồn giá; ghi vấn đề và chỉnh thiết kế.

**Owner P3:** Codex chuẩn bị thiết kế; bạn quyết định hướng. Backend kiểm tra dữ liệu nào thực sự hỗ trợ màn hình.
**Hoàn thành P3 khi:** Mọi component/trạng thái đã có thiết kế và mẫu dữ liệu; không dùng dữ liệu giả làm bằng chứng thật. Taste chỉ áp dụng phần giới thiệu; redesign dùng checklist kiểm tra, không tự đổi wireframe hoặc stack.

### P4. Xây frontend với mock

- [ ] P4.1 — Dựng nền tảng đã chốt, token/component dùng chung và API boundary có validation.
- [ ] P4.2 — Slice URL: bootstrap session → validate 2–5 URLs → tạo Requirement → tạo/poll comparison → bảng/evidence → sửa targets/chạy lại; giữ cột URL lỗi, không gắn eligible khi filter_applied=false.
- [ ] P4.3 — Slice nhu cầu: form hoặc text/parse job → làm rõ bằng answers/edits → review committed revision → comparison; tách hard/soft, giữ grouping, dùng can_collect_data và blockers đúng nghĩa.
- [ ] P4.4 — Chọn offer/ngày bằng snapshot + reuse cho URL; discovery hiển thị candidate theo offer; đổi tiêu chí/sắp xếp minh bạch và format tiền/ngày. Giữ yêu cầu giá/nhóm/chính sách G1–G3; không tự tính hoặc tạo budget giả để lấy giá.
- [ ] P4.5 — Hoàn thiện mọi trạng thái P3.5, mobile, keyboard, liên kết nguồn và chống submit lặp/response cũ.
- [ ] P4.6 — Kiểm tra các slice bằng JSON mẫu đã thống nhất; sửa lỗi logic/layout và đối chiếu với tài liệu.

**Owner P4:** FE + Codex. **Hoàn thành khi:** Mock thay đổi được theo scenario; mọi thao tác chính hoạt động; mock ghi rõ là dữ liệu minh họa.

### P5. Tích hợp backend thật

- [ ] P5.1 — Kết nối API v1 đang có bằng fixture; xác nhận session/Bearer, base URL/CORS, HTTP/envelope/schema và parse/comparison lifecycle. Ghi rõ synthetic, chưa nghiệm thu tour thật.
- [ ] P5.2 — Sau khi D1–D5 được chốt/nghiệm thu, chạy cả hai luồng API bằng dữ liệu nguồn thật; kiểm tra partial, zero matches, field unknown, access từ chối và toàn bộ source attempts thất bại. **Phụ thuộc BE/crawler còn giữ; merge CLI chưa hoàn thành task.**
- [ ] P5.3 — Kiểm tra giá đúng offer, phụ thu chưa biết, freshness, xác minh nguồn và trade-off mở đúng evidence bằng API public; nghiệm thu G1–G3/G5 và D3/D4. `verified` trong crawl report không phải independently_verified; lịch khởi hành không chứng minh còn chỗ.
- [ ] P5.4 — Kiểm tra text patch lỗi giữ revision, response/job cũ, 409/stale answers/selections, cancel/chạy lại, mất mạng/idempotency và khôi phục đúng phiên/revision theo G6.
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

1. FE + BE review G1/G2/G8 trước; BE + crawler đồng thời chốt D1 để dữ liệu có đường vào runtime: giá cho URL-only, nhận diện tour/nguồn, schema response và adapter/transport; ghi quyết định vào contract chuẩn.
2. Review P1.1–P1.2/P1.6 theo API đã có: field/catalog, clarification, AND/OR, offer, session và refresh. Giữ G3–G7 và từng scenario C11 để trao đổi tiếp với backend.
3. Codex chuẩn bị reference và phương án visual P3.1–P3.2; bạn có thể bổ sung template sau.

**Kiểm chứng lần cập nhật:** Hai input mẫu đã qua models/fixture/decision engine; sau merge đã tạo môi trường kiểm tra riêng `.uv/merge-env`, giữ nguyên `.venv`. Toàn bộ tests backend + tourcrawl đạt **107 passed**, lint `src tests scripts` đạt; tests API dùng SQLite tạm/fixture/NIM stub. Chưa nghiệm thu NIM/crawler nguồn thật hoặc frontend E2E, không tick P5/P6 từ kết quả này.

Các điều kiện hoàn thành thể hiện phụ thuộc trong roadmap; không tự cấp quyền triển khai. Quy trình PLANNING vẫn theo `AGENTS.md`.
