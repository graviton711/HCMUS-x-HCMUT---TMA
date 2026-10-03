# Chuẩn bị thiết kế frontend / UI/UX

**Trạng thái:** PLANNING. Chuẩn bị skill và brief; chưa chốt visual design hoặc stack frontend.

Roadmap và checklist công việc nằm ở [planning frontend](frontend-plan.md). Idea, kiến trúc và bố cục wireframe đã chốt; tài liệu này hướng dẫn dùng skill khi thiết kế chi tiết.

## Brief sản phẩm

- Người Việt đang cân nhắc tour trọn gói và nhà cung cấp.
- Hai đầu vào: nhu cầu cá nhân hoặc URL tour đang cân nhắc.
- Giá trị chính: so sánh cùng tiêu chí, giải thích đánh đổi, kiểm chứng dữ kiện và thấy dữ liệu còn thiếu.
- Luồng chính: nhập → làm rõ ràng buộc → so sánh → xem bằng chứng → sửa tiêu chí hoặc mở trang nhà cung cấp.
- Không tự tạo lịch trình, đặt tour, thanh toán hoặc chọn thay người dùng.

Nguồn yêu cầu: [proposal](idea.md), [kiến trúc](system-architecture.md), [wireframe](wireframes.md), [HTTP contract v1](api-contract.md), [domain contract](backend-contracts.md). `TMA.md` là đề bài cuộc thi; `idea.md` là proposal sản phẩm. [Hướng tích hợp](frontend-api-integration.md) ghi chi tiết đã đối chiếu code `0b7e59f`; [checklist](frontend-backend-checklist.md) giữ phần BE chưa đủ cho thiết kế.

## Skill được chọn

Nguồn: [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill).
Ghim commit `ce26fc25c0e5e8cab638f883de62d9a86ee5e45b`, kiểm tra ngày 03/10/2026.
Đã cài 3 skill trong `.agents/skills/` để Codex nhận theo phạm vi repo và team dùng cùng phiên bản. Frontmatter hợp lệ; SHA-256 của cả 3 file khớp nội dung đã đọc từ commit ghim. MIT license được lưu tại `.agents/skills/LICENSE.taste-skill`.

| Tên gọi trong Codex | Thư mục upstream / cài đặt | Vai trò |
|---|---|---|
| `design-taste-frontend` | `taste-skill` | Thiết kế phần giới thiệu/landing; đọc brief trước, điều chỉnh bố cục, typography và motion theo ngữ cảnh. V2 đang experimental. |
| `minimalist-ui` | `minimalist-skill` | Phương án visual gọn, phân cấp chữ rõ, màu tiết chế cho giao diện sản phẩm. Chỉ dùng khi chọn hướng này, không mặc định chốt palette/font. |
| `redesign-existing-projects` | `redesign-skill` | Audit và chỉnh UI khi đã có giao diện: typography, spacing, alignment, responsive, accessibility và các trạng thái tương tác. |

Taste v2 tự giới hạn phạm vi: bảng dữ liệu, form nhiều bước và UI sản phẩm dày thông tin nằm ngoài phạm vi của skill. Vì vậy không áp quy tắc hero, bento, khoảng trắng marketing hoặc cấm bảng dài vào màn so sánh tour. Màn này theo wireframe và contract của dự án.

Không chọn `gpt-taste` làm mặc định vì ép AIDA/GSAP và chuyển động mạnh cho mọi trang. `high-end-visual-design` cũng ép nhiều hiệu ứng và cấu trúc trang không cần cho việc đối chiếu dữ liệu. Skill ảnh web/mobile, brandkit và image-to-code để sau khi có yêu cầu đúng loại đầu ra; hiện cần chuẩn bị web demo, chưa cần ảnh concept hay app native.

## Cách áp dụng trong dự án

1. Đọc `AGENTS.md` và tài liệu sản phẩm trước; skill bổ sung kỹ thuật thiết kế, không thay đổi phạm vi hay contract.
2. PLANNING chỉ cập nhật tài liệu, phân tích và thiết kế để review. Cài skill không cấp quyền viết production code.
3. Chọn skill theo màn và nhiệm vụ; không cộng dồn các phong cách mâu thuẫn.
4. Hướng đề xuất ban đầu: dễ đọc, đáng tin cậy, hình ảnh du lịch có chủ đích, phản hồi tương tác nhẹ. Chưa phải visual đã duyệt.
5. Với phần giới thiệu dùng Taste: đề xuất `DESIGN_VARIANCE=4`, `MOTION_INTENSITY=2`, `VISUAL_DENSITY=5`. Màn so sánh không bị ràng buộc bởi preset landing.
6. Không lấy default React/Next.js/Tailwind trong skill làm quyết định stack. Framework, component library, font, theme và thương hiệu còn cần chốt theo yêu cầu thực tế.
7. Màu trạng thái mang ý nghĩa dữ liệu được giữ riêng với màu thương hiệu; luôn có nhãn chữ, không chỉ dùng màu.
8. Không làm dữ liệu giả trông như thật để đáp ứng chỉ dẫn visual. Mọi dữ liệu minh họa phải ghi rõ; tên/giá/đánh giá/độ uy tín thật phải có căn cứ.

## Những yêu cầu UI phải giữ

- Tách ràng buộc bắt buộc khỏi ưu tiên; người dùng nhìn thấy tiêu chí và cách sắp xếp.
- So sánh đúng offer snapshot theo ngày; nhiều offer chưa chọn vẫn xem được dữ kiện tour. Giá public cho URL-only còn thiếu (G1); không coi giá người lớn là tổng cuối cho nhóm hoặc dựng giá để hoàn thiện mock visual.
- Phân biệt data_state (`present`, `missing`, `conflicting`, `invalid`, `unsupported`), completeness (`complete`, `partial`, `unknown`), verification (`supplier_published`, `independently_verified`, `unverified`) và freshness. Có timestamp không có nghĩa đã xác minh/còn mới; freshness hiện chưa đủ mọi ô (G5).
- Không có hard filter thì eligibility=null; có tour dù groups rỗng. Dùng can_collect_data và blockers để thiết kế làm rõ; không gắn “đạt nhu cầu” cho URL-only.
- Evidence mở theo từng field, gồm giá trị nguồn, URL, thời điểm và giới hạn; không chỉ gom link chung cho cả tour.
- Bao phủ loading, không có kết quả, dữ liệu một phần, nguồn không hỗ trợ và lỗi có thể thử lại.
- Mobile vẫn đối chiếu cùng tiêu chí và mở được evidence; không chỉ thu nhỏ bảng desktop.
- Nội dung tiếng Việt, định dạng VND/ngày rõ ràng, font hiển thị dấu đầy đủ, focus bàn phím và tương phản dễ đọc; motion tôn trọng reduced-motion.

## Các điểm cần làm rõ ở bước thiết kế

Chi tiết và owner được theo dõi trong [checklist frontend–backend](frontend-backend-checklist.md), phase P1 của planning.

- Hai luồng `/v1` và clarification/jobs đã có; cần review UX text/form, hard/soft/AND/OR, offer, sửa revision và session hết hạn.
- Giữ hàng giá, tên tour/nhà cung cấp, nội dung điều kiện và trade-off giá/chính sách dù public response chưa đáp ứng (G1–G3); ghi rõ field chờ BE trên thiết kế.
- Catalog dropdown (G4), freshness mọi ô (G5), khôi phục revision (G6), grouping edits (G7), schema response/snapshots (G8) chưa đủ; không tự tạo contract để lấp.
- API tour hiện dùng fixture: mọi ví dụ/prototype phải gắn nhãn minh họa. Tourcrawl/scripts đã có nhưng chưa nối; [D1–D5](frontend-crawler-integration.md) là phụ thuộc P5. Dữ liệu CSV/raw text dùng khảo sát, không tự coi là giá/chỗ/evidence đạt contract.

Không tự bổ sung API, điểm AI, tỷ lệ tin cậy hoặc ngưỡng freshness để lấp các điểm còn mở.

## Bảo trì skill

- Giữ nguyên nội dung upstream; lưu MIT license kèm bộ skill.
- Kiểm tra frontmatter `name`/`description` và đối chiếu nội dung với commit đã ghim sau cài đặt.
- Khi cập nhật, review diff và cập nhật commit trong tài liệu này; không tự lấy `main` mới nhất.
- Có thể gọi rõ `$design-taste-frontend`, `$minimalist-ui` hoặc `$redesign-existing-projects`. Skill mới dùng được từ lượt tiếp theo; nếu không xuất hiện, khởi động lại Codex.
