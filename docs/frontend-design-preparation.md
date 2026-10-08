# Chuẩn bị thiết kế frontend / UI/UX

**Trạng thái:** PLANNING, cập nhật 06/10/2026. User chốt **Giấy & Mực**, Newsreader + Be Vietnam Pro theo [review nhóm](frontend-review-2026-10-06.md); token/component và các màn mới còn review. Stack/frontend production chưa chốt.

Roadmap và checklist công việc nằm ở [planning frontend](frontend-plan.md). Idea, kiến trúc và bố cục wireframe đã chốt; tài liệu này hướng dẫn dùng skill khi thiết kế chi tiết.

P3.1 có bốn reference và asset provenance; P3.2 hoàn thành lựa chọn A — Giấy & Mực. B — Hành trình xanh giữ làm lịch sử phương án tại [design review](frontend-design-review.md). Bổ sung accent xanh sâu/đất nung, nền nhạt, ảnh và motion nhẹ; không tự coi token/trạng thái đã nghiệm thu.

[Review điều khiển](frontend-review-controls.md) bổ sung chữ 14–16px, slider mức sở thích, sửa tự cuộn tới xác nhận và Tìm kiếm bằng nút/chat; bỏ số revision khỏi UI, mở rộng nav bốn mục. Tiếp tục áp checklist redesign trong style Giấy & Mực; không đổi stack hoặc xếp hạng từ slider chưa chốt G14.

## Brief sản phẩm

- Người Việt đang cân nhắc tour trọn gói và nhà cung cấp.
- Ba màn: giới thiệu dự án/tour minh họa/widget/demo → form bắt buộc/tùy chọn + chat ghi chú và xác nhận tại chỗ → kết quả. URL tham chiếu tùy chọn, URL-only vẫn giữ trong kế hoạch; field mẫu cá nhân hóa chưa thay C1/G4.
- Giá trị chính: so sánh cùng tiêu chí, giải thích đánh đổi, kiểm chứng dữ kiện và thấy dữ liệu còn thiếu.
- Kết quả có cột criteria rộng, sửa trực tiếp/chat tạo diff trước xác nhận, bảng kiểm chứng + tab Phân tích AI/evidence và nhật ký xử lý. BE tự rank/tạo nhóm tối đa ba tour; nhóm khác qua chat. Bỏ stepper/nút Sửa yêu cầu/Lưu bản nháp/Tìm lại.
- Không tự tạo lịch trình, đặt tour, thanh toán hoặc chọn thay người dùng.

Nguồn yêu cầu: [proposal](idea.md), [kiến trúc](system-architecture.md), [wireframe](wireframes.md), [HTTP contract v1](../src/api/api-contract.md), [domain contract](../src/domain/backend-contracts.md). `TMA.md` là đề bài cuộc thi; `idea.md` là proposal sản phẩm. [Hướng tích hợp](frontend-api-integration.md) ghi chi tiết đã đối chiếu code `0b7e59f`; [checklist](frontend-backend-checklist.md) giữ phần BE chưa đủ cho thiết kế.

## Skill được chọn

Nguồn: [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill).
Ghim commit `ce26fc25c0e5e8cab638f883de62d9a86ee5e45b`, kiểm tra ngày 03/10/2026.
Đã cài 3 skill trong `.agents/skills/` để Codex nhận theo phạm vi repo và team dùng cùng phiên bản. Frontmatter hợp lệ; SHA-256 của cả 3 file khớp nội dung đã đọc từ commit ghim. MIT license được lưu tại `.agents/skills/LICENSE.taste-skill`.

| Tên gọi trong Codex | Thư mục upstream / cài đặt | Vai trò |
|---|---|---|
| `design-taste-frontend` | `taste-skill` | Thiết kế phần giới thiệu/landing; đọc brief trước, điều chỉnh bố cục, typography và motion theo ngữ cảnh. V2 đang experimental. |
| `minimalist-ui` | `minimalist-skill` | Nền visual Giấy & Mực đã được chọn cho UI sản phẩm: giấy ấm, tương phản typography, mặt phẳng và màu tiết chế. Accent/ảnh/motion theo review nhóm; không tự thêm palette/font khác. |
| `redesign-existing-projects` | `redesign-skill` | Audit và chỉnh UI khi đã có giao diện: typography, spacing, alignment, responsive, accessibility và các trạng thái tương tác. |

Taste v2 tự giới hạn phạm vi: bảng dữ liệu, form nhiều bước và UI sản phẩm dày thông tin nằm ngoài phạm vi của skill. Vì vậy không áp quy tắc hero, bento, khoảng trắng marketing hoặc cấm bảng dài vào màn so sánh tour. Màn này theo wireframe và contract của dự án.

Không chọn `gpt-taste` làm mặc định vì ép AIDA/GSAP và chuyển động mạnh cho mọi trang. `high-end-visual-design` cũng ép nhiều hiệu ứng và cấu trúc trang không cần cho việc đối chiếu dữ liệu. Skill ảnh web/mobile, brandkit và image-to-code để sau khi có yêu cầu đúng loại đầu ra; hiện cần chuẩn bị web demo, chưa cần ảnh concept hay app native.

## Cách áp dụng trong dự án

1. Đọc `AGENTS.md` và tài liệu sản phẩm trước; skill bổ sung kỹ thuật thiết kế, không thay đổi phạm vi hay contract.
2. PLANNING chỉ cập nhật tài liệu, phân tích và thiết kế để review. Cài skill không cấp quyền viết production code.
3. Chọn skill theo màn và nhiệm vụ; không cộng dồn các phong cách mâu thuẫn.
4. Giữ Giấy & Mực đã duyệt; tăng nhận diện du lịch bằng ảnh, xanh sâu/đất nung/nền nhạt và phản hồi nhẹ. Không tăng mật độ chữ, không đổi thành style B; token chi tiết còn P3.3.
5. Với phần giới thiệu dùng Taste: đề xuất `DESIGN_VARIANCE=4`, `MOTION_INTENSITY=2`, `VISUAL_DENSITY=5`. Màn so sánh không bị ràng buộc bởi preset landing.
6. Không lấy default React/Next.js/Tailwind trong skill làm quyết định stack. Font Newsreader + Be Vietnam Pro đã chốt; framework/component library/token/theme chi tiết và thương hiệu còn P2/P3.3.
7. Màu trạng thái mang ý nghĩa dữ liệu được giữ riêng với màu thương hiệu; luôn có nhãn chữ, không chỉ dùng màu.
8. Không làm dữ liệu giả trông như thật để đáp ứng chỉ dẫn visual. Mọi dữ liệu minh họa phải ghi rõ; tên/giá/đánh giá/độ uy tín thật phải có căn cứ.

## Những yêu cầu UI phải giữ

- Tách ràng buộc bắt buộc khỏi ưu tiên; người dùng nhìn thấy tiêu chí và cách sắp xếp.
- Kết quả có tối đa ba gợi ý/lý do và bảng tự động từ BE; tìm phương án khác giữ criteria và loại nhóm đã xem. Hard fail/unknown không lấp giả; chưa ưu tiên thì nhãn tương tự. G10 còn chốt, không tự tạo điểm AI.
- Giữ tour cung cấp và nhãn nguồn gốc; tour tìm thêm dùng cùng criteria. Chỉ URL thì gợi ý phạm vi từ dữ kiện, không suy sở thích/điều kiện cá nhân. Tour URL giữ làm tham chiếu/so chung, không màn danh sách/chọn tour trước bảng.
- So sánh đúng offer snapshot theo ngày; nhiều offer chưa chọn vẫn xem được dữ kiện tour. Giá public cho URL-only còn thiếu (G1); không coi giá người lớn là tổng cuối cho nhóm hoặc dựng giá để hoàn thiện mock visual.
- Phân biệt data_state (`present`, `missing`, `conflicting`, `invalid`, `unsupported`), completeness (`complete`, `partial`, `unknown`), verification (`supplier_published`, `independently_verified`, `unverified`) và freshness. Có timestamp không có nghĩa đã xác minh/còn mới; freshness hiện chưa đủ mọi ô (G5).
- Không có hard filter thì eligibility=null; có tour dù groups rỗng. Dùng can_collect_data và blockers để thiết kế làm rõ; không gắn “đạt nhu cầu” cho URL-only.
- Evidence mở theo từng field, gồm giá trị nguồn, URL, thời điểm và giới hạn; không chỉ gom link chung cho cả tour.
- Bao phủ loading, không có kết quả, dữ liệu một phần, nguồn không hỗ trợ và lỗi có thể thử lại.
- Cột criteria desktop 340–380px/~30%, có đủ field/default/blocker và chat; sửa trực tiếp/chat cần diff/xác nhận, atomic revision còn G11. Kết quả cũ ghi revision riêng khi chờ/lỗi/hủy.
- Phân tích AI giải thích kết luận/đánh đổi/phép tính có basis/coverage/offer/evidence và unknown; không suy nghĩ nội bộ hoặc điểm chưa chốt (G12).
- Nhật ký bước/skeleton success/chậm/partial/empty/error/cancel mô phỏng có nhãn; runtime chỉ activity thật (G13). Widget vị trí/thời tiết/loading/từ chối quyền và walkthrough demo minh họa; không API ngoài/geolocation thật trong prototype.
- Mobile vẫn đối chiếu cùng tiêu chí và mở được evidence; không chỉ thu nhỏ bảng desktop.
- Nội dung tiếng Việt, định dạng VND/ngày rõ ràng, font hiển thị dấu đầy đủ, focus bàn phím và tương phản dễ đọc; motion tôn trọng reduced-motion.

Budget nội bộ khởi điểm 20 ứng viên và URL tham chiếu ngoài ba gợi ý là đề xuất ở FLOW-3; chưa benchmark/chốt, không expose pool hoặc checkbox để user sàng lọc.

## Các điểm cần làm rõ ở bước thiết kế

Chi tiết và owner được theo dõi trong [checklist frontend–backend](frontend-backend-checklist.md), phase P1 của planning.

- Flow ba màn đã duyệt, có thể thiết kế mà không chờ field/survey/tên biến. `/v1` vẫn hai mode loại trừ nhau; URL + retrieval/review phạm vi/dedup/nhóm tự động/vòng phương án khác còn G9. Bộ field bắt buộc/default của form cá nhân hóa là mẫu review C1/G4, không ép URL-only.
- Giữ hàng giá, tên tour/nhà cung cấp, nội dung điều kiện và trade-off giá/chính sách dù public response chưa đáp ứng (G1–G3); ghi rõ field chờ BE trên thiết kế.
- Catalog dropdown (G4), freshness mọi ô (G5), khôi phục revision (G6), grouping edits (G7), schema response/snapshots (G8) chưa đủ; không tự tạo contract để lấp.
- Chat preview không commit + context/diff/confirm atomic (G11), phân tích có operands/offer/evidence (G12), activity có thứ tự/thời điểm/phase/source/terminal (G13) chưa endpoint/DTO. PATCH text v1 sẽ commit sau parse, không đáp ứng preview.
- API tour hiện dùng fixture: mọi ví dụ/prototype phải gắn nhãn minh họa. Tourcrawl/scripts đã có nhưng chưa nối; [D1–D5](frontend-crawler-integration.md) là phụ thuộc P5. Dữ liệu CSV/raw text dùng khảo sát, không tự coi là giá/chỗ/evidence đạt contract.

Không tự bổ sung API, điểm AI, tỷ lệ tin cậy hoặc ngưỡng freshness để lấp các điểm còn mở.

## Bảo trì skill

- Giữ nguyên nội dung upstream; lưu MIT license kèm bộ skill.
- Kiểm tra frontmatter `name`/`description` và đối chiếu nội dung với commit đã ghim sau cài đặt.
- Khi cập nhật, review diff và cập nhật commit trong tài liệu này; không tự lấy `main` mới nhất.
- Có thể gọi rõ `$design-taste-frontend`, `$minimalist-ui` hoặc `$redesign-existing-projects`. Skill mới dùng được từ lượt tiếp theo; nếu không xuất hiện, khởi động lại Codex.
