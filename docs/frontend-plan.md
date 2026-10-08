# Planning frontend / UI/UX

**Trạng thái:** Planning v1.8 trên feature/minh-phu, sửa ngày 06/10/2026: user chốt **Giấy & Mực**, Newsreader + Be Vietnam Pro; [review nhóm](frontend-review-2026-10-06.md) là hướng bố cục mới. PLANNING, tài liệu và HTML/CSS/JS thử nghiệm ngoài `src/`; chưa frontend production hoặc chốt stack. [Workflow preview GitHub Pages](frontend-preview-publishing.md) vẫn chờ chủ repo bật hosting cho repo private.
**Baseline:** Giới thiệu → điền nhu cầu và xác nhận ngay trong form → kết quả/so sánh; cột criteria rộng, sửa trực tiếp và chat có diff/xác nhận, bảng kiểm chứng + tab Phân tích AI, nhật ký bước xử lý. Bỏ stepper và các nút Sửa yêu cầu/Lưu bản nháp/Tìm lại. V1 chưa G9–G13; API synthetic/crawler chưa nối. Budget 20 ứng viên và URL tham chiếu ngoài ba gợi ý vẫn cần review, không phải contract đã chốt.

**Review điều khiển mới:** [Navigation/slider/tìm kiếm](frontend-review-controls.md): sửa tự cuộn tới xác nhận; confirm chỉ cập nhật criteria, nút Tìm kiếm hoặc chat mới chạy. Không hiện revision trên UI; giữ bảo vệ nội bộ. Nav Giới thiệu/Tìm tour/Liên hệ/Hỗ trợ; chữ nội dung 14–16px, slider 0–5 còn mapping G14. P3.3–P3.7 chờ review bản mẫu.

Giữ 7 phase/38 task ID; P1.1 tick cho journey, P3.2 tick cho style đã duyệt, không thay nghiệm thu contract hoặc các màn mới. Giữ G1–G10/D1–D5; thêm G11 chat preview/commit, G12 phân tích có căn cứ, G13 nhật ký tác vụ. Mọi chỉnh sửa/merge chỉ trên nhánh Minh Phú theo `AGENTS.md`.

## Tài liệu và cách làm việc

- [Idea](idea.md), [kiến trúc](system-architecture.md), [wireframe](wireframes.md): giữ phạm vi và bố cục đã chốt.
- [Luồng và trạng thái UI](frontend-flows.md): bản chi tiết hành vi để review.
- [Checklist frontend–backend](frontend-backend-checklist.md): những quyết định kỹ thuật phải thống nhất.
- [Hướng tích hợp API v1](frontend-api-integration.md): endpoint, payload, session/revision/job/offer/evidence và giới hạn thực tế.
- [Đối chiếu crawler](frontend-crawler-integration.md): output CSV/raw JSON khác contract runtime; D1–D5 để BE + crawler chốt adapter, registry, giá/evidence và profiles.
- [Contract HTTP](../src/api/api-contract.md), [domain](../src/domain/backend-contracts.md), [schemas](../contracts/README.md), [input mẫu](../examples/README.md): nguồn chuẩn backend; chưa đủ schema cho mọi public response.
- [Chuẩn bị skill](frontend-design-preparation.md), [module frontend](../src/frontend/README.md).
- [Review nhóm 06/10/2026](frontend-review-2026-10-06.md): quyết định style, ba màn, chat, phân tích, loading/motion và field mẫu.

Mỗi task có ID, người phụ trách, đầu ra và điều kiện hoàn thành. `[ ]` chưa xong; `[x]` chỉ dùng khi có đầu ra đã kiểm tra. Khi đang làm hoặc bị chặn, thêm `Đang làm` / `Bị chặn: <lý do>` vào task; không tick thay cho tiến độ.

Mỗi phiên: chọn task → đọc/cập nhật tài liệu liên quan → tạo đầu ra → kiểm tra → review điểm cần quyết định → cập nhật checklist. Thay đổi phạm vi hoặc contract phải ghi quyết định và tác động trước khi làm phần phụ thuộc.

**Phân công:** Bạn phụ trách frontend và quyết định trải nghiệm sản phẩm; Codex soạn phương án, nghiên cứu reference, thiết kế, hỗ trợ kỹ thuật và kiểm tra; backend phụ trách endpoint, dữ liệu, lọc/so sánh và bằng chứng. FE + BE cùng chốt contract. Bạn review màn hình và hành vi cụ thể, không cần tự chọn font/token/thư viện từ đầu.

## Các phase

| Phase | Công việc | Đầu ra / điều kiện hoàn thành | Phụ thuộc |
|---|---|---|---|
| P0 | Ghi nhận nền tảng | Tài liệu nền và skill có thể truy cập | Đã có |
| P1 | Chốt flow và contract với BE | Không còn điểm chưa chốt ảnh hưởng luồng chính; có schema và JSON mẫu dùng được | P0 |
| P2 | Chốt nền tảng kỹ thuật FE | Stack, cấu trúc, state, chiến lược API/mock/kiểm tra được ghi rõ | Flow P1.1; API boundary cần contract P1 |
| P3 | Thiết kế UI/UX chi tiết | Ba bề mặt chính và panel evidence, mobile/token/trạng thái; đánh dấu contract chờ BE | Flow P1.1 đã chốt; không chờ field/survey/schema hoàn tất |
| P4 | Xây frontend với mock đúng contract | Ba màn với nhu cầu/URL/cả hai, criteria/chat/diff, bảng/phân tích/evidence và activity | P1–P3 |
| P5 | Tích hợp backend và nguồn thật | Chạy API fixture trước, sau đó đủ luồng với nguồn thật; lỗi/dữ liệu thiếu đúng nghĩa | P4 + API BE; crawler thật cho P5.2–P5.3 |
| P6 | Kiểm tra và bàn giao demo | Checklist nghiệm thu đạt, demo chạy được, giới hạn được ghi nhận | P5 |

Không chốt lịch ngày khi chưa biết deadline và năng lực backend. Có thể thiết kế flow/wireframe/visual ngay từ P1.1 đã duyệt, dùng dữ liệu minh họa và ghi rõ field chờ BE; không chặn thiết kế bởi tên biến, catalog hay survey. Contract phải hoàn thiện trước phần mock/tích hợp runtime phụ thuộc nó. P2/P3 tiến hành song song với các task contract còn mở của P1.

**Ưu tiên contract, không chặn design:** G9 pipeline hợp nhất, G10 ranking/Top 3/lý do, G11 preview chat không commit + xác nhận theo revision, G12 phân tích/phép tính/evidence, G13 activity thật; G1 giá public không Budget, G2 nhận diện, G8 schemas/snapshots. Engine hiện có groups/evaluations, chưa có ranking; thuật toán/trọng số còn chốt với BE. G3–G7 giữ nguyên; không hạ wireframe theo fixture.

**Phụ thuộc dữ liệu thật:** D1 adapter CrawlResult/transport; D2 registry/capability/TTL; D3 giá–ngày–availability có nghĩa; D4 provenance/access/verification; D5 thống nhất profile formats và gold fixtures. CLI crawl có code không thay nghiệm thu P5.2; FE tiếp tục dùng public API v1.

### P0. Nền tảng

- [x] P0.1 — Ghi nhận idea, kiến trúc, wireframe là baseline đã chốt. **Owner:** Bạn + Codex.
- [x] P0.2 — Cài 3 skill, ghim phiên bản, ghi phạm vi sử dụng. **Owner:** Codex.
- [x] P0.3 — Tạo roadmap, flow draft và checklist BE để review. **Owner:** Codex.

### P1. Flow và hợp đồng FE–BE

- [x] P1.1 — Giới thiệu → form nhu cầu + URL và xác nhận → hệ thống tự tìm/rank/so sánh tối đa ba gợi ý → evidence/phân tích, sửa criteria trực tiếp hoặc trao đổi qua chat. Bỏ chọn tour thủ công và stepper. **Owner:** Bạn + Codex. **Đầu ra:** frontend-flows.md và review 06/10; budget 20, cách đếm URL và contract G9–G13 còn review.
- [ ] P1.2 — Ánh xạ control form vào conditions/party/value đã có; chốt field bắt buộc/tùy chọn, default hiển thị, hard/soft, catalog canonical IDs, budget basis/coverage, tuổi và ngày linh hoạt. **Owner:** FE + BE. **Còn mở:** C1/G4/G7; bộ field mẫu cá nhân hóa ở review 06/10 chưa thay contract; URL-only không bắt nhập party/ngày/budget.
- [ ] P1.3 — Review lifecycle v1/polling/cancel/retry/base URL và orchestration thu thập chung → nhóm đề xuất/so sánh tự động. Chốt activity log thật, chat preview không commit → diff → xác nhận atomic, vòng phương án khác qua chat/exclusion/reuse snapshot. **Owner:** FE + BE. **Còn mở:** G9/G11/G13.
- [ ] P1.4 — Chốt request/public response/lỗi, origin/dedup, giá/offer/evidence/quality; nhóm tối đa ba gợi ý mới, comparison/phân tích có operands/basis/coverage/offer/evidence và activity/proposal. Chốt giả định 20 ứng viên và count tham chiếu theo FLOW-3. **Owner:** FE + BE; G1–G3/G5/G8–G13 và D1–D4 giữ nguyên.
- [ ] P1.5 — BE cung cấp snapshots cho nhu cầu-only/URL-only/cả hai; trùng nguồn/partial/ít hơn ba/hard unknown/tie/multiple offers/nhóm khác; thêm chat hỏi–preview–confirm–cancel–conflict, phân tích/phép tính và activity chậm/lỗi/hủy. **Owner:** BE + FE. **Đầu ra:** C11; kiểm tra lý do/phép tính đúng evaluations/policy/binding, không mock thành năng lực backend.
- [ ] P1.6 — Phiên ẩn danh, token/IDs/đúng revision và result round sau refresh/hết hạn. Tách số URL nhập, budget retrieval nội bộ và ba gợi ý hiển thị; review đề xuất URL tham chiếu ngoài số ba. V1 hiện URL 2–5, mục tiêu một URL cần G9. **Owner:** Bạn + FE + BE. **Còn mở:** G6/FLOW-3.

**Hoàn thành P1 khi:** Có contract chuẩn duy nhất được hai phía review; mọi giá trị quan trọng trên màn hình có field/nguồn hoặc cách hiển thị thiếu đã thống nhất. Không tự thêm API/enum vào frontend để lấp chỗ trống.

### P2. Nền tảng kỹ thuật frontend

- [ ] P2.1 — Chọn stack và ghi lý do theo bảng bên dưới; chốt phiên bản/runtime sau khi kiểm tra tương thích. **Owner:** Bạn + Codex.
- [ ] P2.2 — Chốt package root, route, ranh giới feature và tài liệu cạnh từng module. **Owner:** Codex + FE. **Đầu ra:** cập nhật `src/frontend/README.md`.
- [ ] P2.3 — Tách draft, pending proposal/diff, committed revision, jobs và snapshots/vòng kết quả do BE chọn; proposal hết hiệu lực khi context đổi, chống response cũ/conflict, giữ AND/OR và lịch sử nhóm đã xem. Kết quả cũ ghi revision riêng. **Owner:** FE. **Phụ thuộc:** G6/G7/G9/G11.
- [ ] P2.4 — Chốt sinh type và runtime validation từ request + public response schemas; API boundary ánh xạ id/envelope, readiness, lỗi HTTP/job; policy idempotency/retry/cache/cancel. **Owner:** FE + BE. **Phụ thuộc:** G8; schema request hiện chưa đủ full client.
- [ ] P2.5 — Chốt mock và API thật dùng cùng schema/client; base URL/proxy/CORS, token/session, config local/demo, hosting refresh route và lệnh kiểm tra. **Owner:** FE + BE. **Đã có:** CORS localhost:3000/5173 và Bearer token; cấu hình hosting vẫn cần chốt.

**Hoàn thành P2 khi:** Có thể chỉ rõ UI nhận dữ liệu ở đâu, chuyển đổi thế nào, state nào do ai sở hữu và lỗi contract được phát hiện ra sao.

### P3. Thiết kế UI/UX

- [x] P3.1 — Có bốn reference form/comparison/evidence, điểm học được, mobile và điều kiện sử dụng tại [design review](frontend-design-review.md). [Nguồn ảnh/font/icon](../prototypes/frontend-design/assets/SOURCES.md) đầy đủ; template bạn gửi sau được đánh giá bằng cùng tiêu chí.
- [x] P3.2 — User chốt **A — Giấy & Mực** ngày 06/10/2026: nền giấy ấm, Newsreader + Be Vietnam Pro; tăng accent xanh sâu/đất nung, ảnh và motion nhẹ theo [review nhóm](frontend-review-2026-10-06.md). B giữ làm lịch sử phương án. Chỉ chốt style; token/component, màn mới, stack và frontend production chưa nghiệm thu.
- [ ] P3.3 — Chốt token (màu thương hiệu/trạng thái, typography có dấu Việt, spacing, radius, icon, focus, theme) và danh sách component dùng lại cùng trạng thái của chúng. **Owner:** Codex đề xuất; bạn review.
- [ ] P3.4 — Thiết kế Giới thiệu / form + xác nhận / Kết quả: widget/demo minh họa, field bắt buộc/tùy chọn + chat ghi chú; cột criteria 340–380px/~30% có sửa trực tiếp/chat/diff, bảng kiểm chứng + tab Phân tích AI/evidence/offer. Bỏ stepper/nút Sửa yêu cầu/Lưu bản nháp/Tìm lại; yêu cầu nhóm khác qua chat, Retry nguồn lỗi riêng. Review count URL/mobile theo FLOW-3; G1–G3/G9–G13 chờ BE.
- [ ] P3.5 — Skeleton + log bước mock có nhãn; success/chậm/partial/empty/error/cancel, giữ kết quả revision cũ; ít hơn ba/hết nhóm/missing/cũ/chưa xác minh, URL-only/multiple offers/conflict/hết phiên. Widget có loading/từ chối quyền/fallback; không % giả ở runtime hoặc gắn phù hợp cho hard unknown.
- [ ] P3.6 — Chốt mobile: vẫn đối chiếu cùng hàng tiêu chí, giữ tên tour và mở evidence dễ dàng; kiểm tra bàn phím, focus và nội dung dài trên prototype.
- [ ] P3.7 — Walkthrough Giới thiệu → form/validation/xác nhận → log xử lý → bảng/Phân tích AI/evidence; chat hỏi–đề xuất diff–xác nhận–hủy, sửa trực tiếp và nhóm khác, giữ revision cũ khi lỗi/hủy/Back. Giữ ba tổ hợp đầu vào trong kế hoạch; không bước sàng lọc pool/chọn tour.

**Owner P3:** Codex chuẩn bị các màn theo style đã chốt; bạn review token, bố cục và hành vi chi tiết. Backend kiểm tra dữ liệu nào thực sự hỗ trợ màn hình.
**Hoàn thành P3 khi:** Mọi component/trạng thái đã có thiết kế và mẫu dữ liệu; không dùng dữ liệu giả làm bằng chứng thật. Taste chỉ áp dụng phần giới thiệu; redesign dùng checklist kiểm tra, không tự đổi wireframe hoặc stack.

### P4. Xây frontend với mock

- [ ] P4.1 — Dựng nền tảng đã chốt, token/component dùng chung và API boundary có validation.
- [ ] P4.2 — Slice Giới thiệu → form + xác nhận: session/draft nhu cầu + URL, validation bắt buộc/tùy chọn theo C1, chat ghi chú, review criteria/phạm vi ngay form. URL-only giữ flow riêng không ép party/budget; giữ hard/soft/AND/OR/readiness/draft khi lỗi.
- [ ] P4.3 — Job retrieval/đánh giá/rank + activity → BE chọn nhóm/so sánh/analysis → render đề xuất/bảng/Phân tích AI/evidence; nhóm khác qua chat giữ criteria/URL/exclusion. Không tạo danh sách chọn tour hoặc tự ghép/rank v1 tại FE. **Phụ thuộc:** G9–G13.
- [ ] P4.4 — Offer/ngày/evidence/phép tính đồng bộ theo snapshot. Sửa trực tiếp/chat dùng diff → confirm atomic theo expected revision rồi chạy lại phần phụ thuộc; Retry nguồn lỗi riêng. Giữ kết quả revision cũ khi chờ/lỗi/hủy; không ngầm chọn rẻ nhất/tính giá thiếu thay BE. **Phụ thuộc:** G1–G3/G9–G12.
- [ ] P4.5 — Hoàn thiện mọi trạng thái P3.5, mobile, keyboard, liên kết nguồn và chống submit lặp/response cũ.
- [ ] P4.6 — Kiểm tra các slice bằng JSON mẫu đã thống nhất; sửa lỗi logic/layout và đối chiếu với tài liệu.

**Owner P4:** FE + Codex. **Hoàn thành khi:** Mock thay đổi được theo scenario; mọi thao tác chính hoạt động; mock ghi rõ là dữ liệu minh họa.

### P5. Tích hợp backend thật

- [ ] P5.1 — Kết nối API v1 fixture kiểm tra session/Bearer/CORS/envelope/schema/jobs; tích hợp orchestration/ranking/chat/analysis/activity khi BE cung cấp G9–G13. Ghi synthetic; groups/job phase v1 không nghiệm thu các gap mới.
- [ ] P5.2 — Sau G9/G10/D1–D5, chạy nguồn thật ba tổ hợp: tự đề xuất/so sánh và tìm phương án khác; kiểm tra ít hơn ba/hết nhóm mới, trùng tour/offers/nguồn lỗi/unknown/access từ chối. Đo budget 20 theo chất lượng/latency/coverage trước chốt runtime; merge CLI chưa nghiệm thu.
- [ ] P5.3 — Kiểm tra giá/analysis/phép tính đúng offer/basis/coverage/evidence, unknown phụ thu/trẻ em, freshness/xác minh; nghiệm thu G1–G3/G5/G12 và D3/D4. `verified` crawler không phải independently_verified; lịch khởi hành không chứng minh còn chỗ.
- [ ] P5.4 — Kiểm tra text patch lỗi giữ revision, chat preview không commit/confirm atomic/409/stale proposal (G11), activity chậm/partial/error/cancel (G13), response cũ/mất mạng/idempotency/restore đúng phiên/revision (G6).
- [ ] P5.5 — Ghi bug FE/BE với request ID và payload tái hiện phù hợp; đồng bộ tài liệu sau sửa contract. Mock và API thật phải cùng schema.

**Owner P5:** FE + BE. **Hoàn thành khi:** Không có phần UI quan trọng phải suy đoán dữ liệu; không che lỗi nguồn bằng success state.

### P6. Nghiệm thu và bàn giao

- [ ] P6.1 — Typecheck, lint, build và kiểm tra schema/fixture đạt; kiểm tra logic giá/ngày/status/reference có rủi ro sai nghĩa.
- [ ] P6.2 — E2E Giới thiệu → form/xác nhận → activity → bảng/analysis/evidence cho ba tổ hợp đầu vào; chat hỏi/diff/confirm/hủy/sửa trực tiếp/nhóm khác, exclusion/vòng cũ/ít hơn ba/hard unknown/offer binding. Giữ partial/error/empty/response cũ/input khi retry.
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

1. Review prototype mới theo [quyết định nhóm 06/10](frontend-review-2026-10-06.md): ba màn Giới thiệu → form + xác nhận → Kết quả, chat/diff, Phân tích AI, log/loading, accent và reduced-motion. P3.3–P3.7 còn mở.
2. Chốt token/component và kiểm tra mobile/các trạng thái sau review; giữ Giấy & Mực làm baseline, có thể bổ sung template sau. Field chưa có contract và widget/demo dùng minh họa có nhãn; không gọi API ngoài hoặc geolocation thật trong prototype.
3. FE + BE trao đổi G9–G13/G1/G2/G8 và C1: pool/rank/coverage, chat preview không commit, phân tích có căn cứ, activity thật; BE + crawler D1–D5. Giữ G3–G7/C11, chốt trước tích hợp.

**Kiểm chứng lịch sử ngày 03/10/2026:** Hai input mẫu đã qua models/fixture/decision engine; tests backend + tourcrawl đạt **107 passed** và lint đạt trong `.uv/merge-env`, giữ `.venv`. P3 prototype A/B cũ đạt **56/56 kiểm tra trình duyệt** trên fixture local ở 1440/768/390/320px. Kết quả này chưa kiểm tra màn/flow mới ngày 06/10, G9–G13/API/nguồn thật/production E2E và không tick P5/P6.

Các điều kiện hoàn thành thể hiện phụ thuộc trong roadmap; không tự cấp quyền triển khai. Quy trình PLANNING vẫn theo `AGENTS.md`.
