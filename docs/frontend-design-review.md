# Review visual frontend — P3.1 / P3.2

Ảnh/báo cáo QA trong `prototypes/frontend-design/review/` chỉ giữ local từ 07/10/2026; bản cũ vẫn có trong lịch sử Git. Mở các trang prototype bên dưới để xem giao diện; số kiểm tra ghi lại chỉ áp với phiên bản tương ứng.

**Cập nhật:** 06/10/2026. **Trạng thái:** user chốt **A — Giấy & Mực**, font Newsreader + Be Vietnam Pro; P3.2 hoàn thành. Theo [review nhóm](frontend-review-2026-10-06.md), mở rộng thành Giới thiệu → form + xác nhận → Kết quả, criteria rộng/chat/diff, Phân tích AI, log mock và accent/motion. P3.3–P3.7 còn chờ review prototype mới; stack/frontend production chưa duyệt. Các số liệu QA và ảnh A/B bên dưới là lịch sử 03/10/2026.

## Prototype mới — 06/10/2026

**Lượt điều khiển mới:** [Review chi tiết](frontend-review-controls.md). Sửa tự cuộn tới xác nhận, Tìm kiếm bằng nút/chat, slider sở thích, font nội dung 14–16px, nav bốn mục và motion/reduced-motion. QA 57/57 đạt; ảnh/báo cáo chỉ local. 61 checks dưới đây ghi lại lượt trước, không đại diện điều khiển mới.

- [Mở Giấy & Mực](../prototypes/frontend-design/paper.html): Giới thiệu → form/xác nhận → Kết quả. Có chat ghi chú, sửa trực tiếp/diff/xác nhận, hai tab dữ kiện/phân tích, phép tính/evidence/offer, skeleton/log, chậm/lỗi/retry/cancel.
- Cột yêu cầu đo được 376px tại 1440px và 340px tại 1280px; mobile xếp dọc, bảng cuộn riêng. Accent xanh sâu/đất nung, ảnh rõ hơn, motion nhẹ và reduced-motion.
- [Khung desktop/mobile](../prototypes/frontend-design/viewer.html?design=paper) mở trực tiếp các màn prototype; ảnh chụp lịch sử không còn là phụ thuộc của tài liệu.
- QA: 61/61 browser checks đạt, không console error; 1440/1280/768/390/320px không tràn ngang. Đã kiểm tra revision cũ, response muộn, đề xuất chat, nhập trẻ/tuổi atomic, giữ ghi chú khi Back. QA dùng file local vì sandbox chặn localhost; chưa HTTP preview/hosting/API.
- Tour, chat, widget và activity đều mô phỏng; fixture không retrieval/rank theo input mới. Chat chỉ nhận câu mẫu; demo tương tác thay video thật chưa có. G11–G13 chưa backend; P3.3–P3.7 chờ review, không tick theo QA.

## Phương án đã review ngày 03/10/2026

Hai hướng dùng **cùng màn kết quả, cùng dữ liệu và hành vi** tại [prototype](../prototypes/frontend-design/README.md):

| Hướng | Đặc điểm / gain | Chi phí / điểm cần kiểm tra |
|---|---|---|
| A — Giấy & mực | Nền giấy ấm, chữ serif ở tiêu đề, UI sans, đường kẻ mảnh và ảnh tiết chế; ưu tiên đọc và đối chiếu dữ kiện | Kiểm tra không quá giống tài liệu, chữ Việt và phân cấp khi bảng dày |
| B — Hành trình xanh | Nền sáng xanh nhạt, accent xanh sâu, ảnh tour lớn hơn và phân cấp sans; nhận diện du lịch rõ hơn | Kiểm tra ảnh không đẩy thông tin quyết định xuống quá xa, màu không lẫn trạng thái dữ liệu |

`minimalist-ui` dùng cho A; B là phương án thiết kế theo brief. `redesign-existing-projects` cung cấp checklist readability/alignment/states/accessibility; bỏ các quy tắc marketing mâu thuẫn bảng sản phẩm. Không áp Taste landing vào comparison.

Ngày 06/10 user chọn A, giữ style/bố cục nhẹ nhàng và cho phép thêm template sau. Phần tiếp theo cần review là token/accent và ba màn mới, chat diff/xác nhận, tab phân tích, loading/animation/mobile tại P3.3–P3.7; không còn chờ lựa chọn A/B. Review form nằm ngay màn 2, bỏ stepper.

Mở [bảng review local](http://127.0.0.1:4173/), [A](http://127.0.0.1:4173/viewer.html?design=paper) hoặc [B](http://127.0.0.1:4173/viewer.html?design=coastal). Khung có Desktop/Mobile 390px, không cần extension. Server chỉ phục vụ thư mục prototype trên loopback; lệnh mở lại nằm trong README prototype.

User đã đồng ý chia sẻ prototype qua GitHub Pages; [workflow preview](frontend-preview-publishing.md) đã chuẩn bị, chờ chủ repo bật Pages cho repo private. Chưa có link online được xác minh. Publish không thay nghiệm thu P3.3–P3.7/P5/P6.

Hai hướng vẫn mở trực tiếp trong khung review; ảnh chụp cũ chỉ local/lịch sử Git. B dùng ảnh/dải nhu cầu lớn hơn nên bảng nằm thấp hơn A; đây là trade-off để user review. Tên/biểu tượng **Đi cùng** chỉ tạm, chưa chốt thương hiệu.

## Reference đã khảo sát

| Nguồn | Điểm tham khảo / áp dụng | Mobile / điều kiện tái sử dụng |
|---|---|---|
| [Klook Tour & Trải nghiệm](https://www.klook.com/vi/experiences/) | Ngôn ngữ tour/địa điểm và thứ tự ảnh → tên → thông tin; ảnh giúp nhận tuyến, không thay chứng cứ | Prototype chuyển thẻ thành luồng dọc ở màn nhỏ. Chỉ tham khảo cách tổ chức; không sao chép ảnh, logo hoặc code Klook |
| [Apple Compare](https://www.apple.com/iphone/compare/) | Tên đối tượng và từng nhóm tiêu chí đặt cùng hàng; ưu tiên so sánh trực tiếp thay mô tả rời rạc | Prototype kiểm tra giữ tên tour/cột tiêu chí trong vùng cuộn. Không sao chép assets/code hoặc flow chọn sản phẩm của Apple |
| [GOV.UK Details](https://design-system.service.gov.uk/components/details/) | Giải thích bổ sung mở khi cần; nội dung quyết định chính luôn hiện | Evidence tách thành panel có focus/đóng rõ; đây là chuyển thể cho dự án, không khẳng định GOV.UK dùng panel. Không nhập template/code |
| [GOV.UK Text input](https://design-system.service.gov.uk/components/text-input/) | Nhãn rõ, hint cạnh field, lỗi cụ thể giữ input; tham khảo cho bước Input và sửa nhu cầu sau này | Form review sẽ xếp dọc trên mobile; các hành vi input đầy đủ còn P3.4. Không nhập template/code |

Đây là bảng tham khảo, không chọn một template hoàn chỉnh. Nhận xét mobile là quyết định thử trong prototype, không phải kết luận đã kiểm tra mọi trang nguồn trên thiết bị.

## Dữ liệu và asset

- Tất cả tour/nhà cung cấp/giá/ngày/lý do/nguồn là dữ liệu minh họa có nhãn. Không có điểm AI, phần trăm tin cậy hoặc khẳng định tốt nhất thị trường.
- Fixture cố định hai nhóm không trùng ID để thử phương án khác; bản cũ dùng nút, hướng 06/10 chuyển sang chat. Chưa đánh giá G9/G10. Không nới điều kiện hoặc lấp giả khi ít hơn ba.
- Một URL + ba gợi ý = bốn cột là giả định FLOW-3 đang review. URL tham chiếu được giữ khi đổi nhóm hoặc chỉ còn hai gợi ý.
- Ba ảnh điểm đến free Unsplash đã lưu local, có photo/photographer cụ thể tại [asset provenance](../prototypes/frontend-design/assets/SOURCES.md); không lấy Unsplash+. [License](https://unsplash.com/license).
- Font Be Vietnam Pro / Newsreader lưu local và giữ hai file SIL OFL 1.1 cùng asset. Đã kiểm tra tải/chữ Việt trong QA cũ; user chốt font cùng Giấy & Mực ngày 06/10.
- Icon đơn sắc và logo ký hiệu tự vẽ bằng SVG; không chốt thương hiệu hoặc sao chép logo nhà cung cấp. Không cần icon package.

## Kiểm chứng và trạng thái task

- P3.1: hoàn thành bốn reference và provenance ảnh/font/icon, không nhập template hoặc code từ trang tham khảo.
- P3.2: hoàn thành lựa chọn Giấy & Mực ngày 06/10; token/bố cục mới/trạng thái/motion chưa tự hoàn thành.
- P3.3–P3.7 và mọi G1–G13 / D1–D5 giữ mở. Chưa có API chat, analysis, activity, rank, crawl hoặc production frontend được nghiệm thu.
- **QA lịch sử 03/10/2026:** **56/56** bằng browser automation trên Edge headless: hai hướng cũ × bốn viewport 1440/768/390/320px không tràn ngang toàn trang; ảnh/font tải đủ; không lỗi console. Báo cáo giữ local/lịch sử Git. Không áp kết quả này cho prototype ba màn mới.
- Tương tác đã kiểm tra: nguồn nhà cung cấp tham chiếu/giá/chính sách thiếu; Escape trả focus; reduced-motion; đổi lịch đồng bộ giá/ngày/nguồn; nhóm khác không lặp/giữ reference/hết nhóm; hai gợi ý không lấp ba; URL-only không suy ưu tiên/không tự điền nhu cầu; retry nguồn/empty/draft giữ kết quả cũ; viewer mobile đúng viewport 390px.
- Phạm vi QA cũ là màn so sánh A/B với fixture cố định. Chưa kiểm tra điện thoại thật, ba màn mới/chat/analysis/activity, API, dữ liệu crawler hoặc thuật toán rank; P3.4–P3.7/P5/P6 không được tick thay bởi kết quả này.
