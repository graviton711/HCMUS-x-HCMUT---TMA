# Review visual frontend — P3.1 / P3.2

**Ngày:** 03/10/2026. **Trạng thái:** hai prototype đã dựng/kiểm tra, chờ user review; PLANNING trên `feature/minh-phu`. Hướng visual và stack chưa duyệt. [Plan](frontend-plan.md) / [flow](frontend-flows.md) / [wireframe](wireframes.md) giữ vai trò chuẩn sản phẩm.

## Đầu ra và quyết định cần review

Hai hướng dùng **cùng màn kết quả, cùng dữ liệu và hành vi** tại [prototype](../prototypes/frontend-design/README.md):

| Hướng | Đặc điểm / gain | Chi phí / điểm cần kiểm tra |
|---|---|---|
| A — Giấy & mực | Nền giấy ấm, chữ serif ở tiêu đề, UI sans, đường kẻ mảnh và ảnh tiết chế; ưu tiên đọc và đối chiếu dữ kiện | Kiểm tra không quá giống tài liệu, chữ Việt và phân cấp khi bảng dày |
| B — Hành trình xanh | Nền sáng xanh nhạt, accent xanh sâu, ảnh tour lớn hơn và phân cấp sans; nhận diện du lịch rõ hơn | Kiểm tra ảnh không đẩy thông tin quyết định xuống quá xa, màu không lẫn trạng thái dữ liệu |

`minimalist-ui` dùng cho A; B là phương án thiết kế theo brief. `redesign-existing-projects` cung cấp checklist readability/alignment/states/accessibility; bỏ các quy tắc marketing mâu thuẫn bảng sản phẩm. Không áp Taste landing vào comparison.

User review: hướng nào dễ đọc giá/điều kiện, dễ hiểu lý do, thấy rõ dữ liệu thiếu và phù hợp cảm giác sản phẩm. Sau đó chốt token/component và mở rộng Input/Review/Kết quả tại P3.3–P3.7.

Mở [bảng review local](http://127.0.0.1:4173/), [A](http://127.0.0.1:4173/viewer.html?design=paper) hoặc [B](http://127.0.0.1:4173/viewer.html?design=coastal). Khung có Desktop/Mobile 390px, không cần extension. Server chỉ phục vụ thư mục prototype trên loopback; lệnh mở lại nằm trong README prototype.

User đã đồng ý chia sẻ prototype qua GitHub Pages; [workflow preview](frontend-preview-publishing.md) đã chuẩn bị, chờ chủ repo bật Pages cho repo private. Chưa có link online được xác minh. Publish không chốt visual P3.2 hoặc thay nghiệm thu P5/P6.

Ảnh chụp: [A desktop](../prototypes/frontend-design/review/a-desktop.png), [B desktop](../prototypes/frontend-design/review/b-desktop.png), [A mobile](../prototypes/frontend-design/review/a-mobile.png), [B mobile](../prototypes/frontend-design/review/b-mobile.png). B dùng ảnh/dải nhu cầu lớn hơn nên bảng nằm thấp hơn A; đây là trade-off để user review. Tên/biểu tượng **Đi cùng** chỉ tạm, chưa chốt thương hiệu.

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
- Fixture cố định hai nhóm không trùng ID để thử Tìm phương án khác; chưa đánh giá G9/G10. Không nới điều kiện hoặc lấp giả khi ít hơn ba.
- Một URL + ba gợi ý = bốn cột là giả định FLOW-3 đang review. URL tham chiếu được giữ khi đổi nhóm hoặc chỉ còn hai gợi ý.
- Ba ảnh điểm đến free Unsplash đã lưu local, có photo/photographer cụ thể tại [asset provenance](../prototypes/frontend-design/assets/SOURCES.md); không lấy Unsplash+. [License](https://unsplash.com/license).
- Font Be Vietnam Pro / Newsreader đã lưu local; giữ hai file SIL OFL 1.1 cùng asset. Đã kiểm tra font tải và chữ Việt hiển thị trên ảnh chụp, chưa chốt font sản phẩm.
- Icon đơn sắc và logo ký hiệu tự vẽ bằng SVG; không chốt thương hiệu hoặc sao chép logo nhà cung cấp. Không cần icon package.

## Kiểm chứng và trạng thái task

- P3.1: hoàn thành bốn reference và provenance ảnh/font/icon, không nhập template hoặc code từ trang tham khảo.
- P3.2: đã có hai hướng trên cùng fixture, chờ user lựa chọn hoặc yêu cầu chỉnh, chưa chốt visual.
- P3.3–P3.7 và mọi G1–G10 / D1–D5 giữ mở. Chưa có API, rank, crawl hoặc production frontend được nghiệm thu.
- Đã kiểm tra **56/56** bằng browser automation trên Edge headless: hai hướng × bốn viewport 1440/768/390/320px không tràn ngang toàn trang; ảnh/font tải đủ; không lỗi console. [Kết quả](../prototypes/frontend-design/review/check-results.json).
- Tương tác đã kiểm tra: nguồn nhà cung cấp tham chiếu/giá/chính sách thiếu; Escape trả focus; reduced-motion; đổi lịch đồng bộ giá/ngày/nguồn; nhóm khác không lặp/giữ reference/hết nhóm; hai gợi ý không lấp ba; URL-only không suy ưu tiên/không tự điền nhu cầu; retry nguồn/empty/draft giữ kết quả cũ; viewer mobile đúng viewport 390px.
- Phạm vi kiểm tra là prototype với fixture cố định. Chưa kiểm tra điện thoại thật, toàn bộ flow Input/Review, API, dữ liệu crawler hoặc thuật toán rank; P3.4–P3.7/P5/P6 không được tick thay bởi kết quả này.
