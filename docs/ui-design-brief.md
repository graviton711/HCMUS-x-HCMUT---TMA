# Định hướng thiết kế giao diện TourLens

## Mục tiêu cảm nhận

TourLens là một không gian đối chiếu chuyến đi sáng, điềm tĩnh và có độ hoàn thiện cao. Giao diện cần có bề mặt phân lớp, ánh sáng dịu, bóng đổ có chủ đích và điều khiển cho cảm giác chạm được. Chất liệu tập trung vào composer, nút chính, thẻ kết quả và panel nổi; không phủ hiệu ứng lên mọi thành phần.

Giữ sắc tím chàm nhận diện và nền trung tính ấm làm trục chung cho workspace lẫn trang hỗ trợ. Manrope dùng cho giao diện tiếng Việt; Space Grotesk dùng có chọn lọc cho số liệu và nhãn thương hiệu. Workspace không dựng một bộ màu và font riêng.

## Thuật ngữ và căn cứ

- **Art direction / visual language:** đặc tính hình ảnh thống nhất của toàn sản phẩm.
- **Materiality / surface treatment:** cách màu, viền, độ trong, highlight và texture khiến bề mặt có cảm giác cụ thể.
- **Elevation / depth:** thứ tự lớp của canvas, navigation, card và thành phần nổi; bóng và độ tương phản hỗ trợ thứ tự đó.
- **Lighting / shading:** hướng highlight và bóng tiếp xúc/ambient; dùng nhất quán, có tiết chế.
- **Tactile feedback / motion design:** trạng thái hover, press, focus, loading và chuyển tiếp thể hiện phản hồi rõ ràng.

Không có thang đo phổ quát cho “đẹp”. Dùng [Material Design 3 elevation](https://m3.material.io/styles/elevation/overview) và [Apple HIG materials](https://developer.apple.com/design/human-interface-guidelines/materials) làm căn cứ cho phân lớp, không sao chép kiểu giao diện của nền tảng. Menu, popover và dialog theo [WAI-ARIA Menu Button](https://www.w3.org/WAI/ARIA/apg/patterns/menu-button/), [WAI-ARIA Menu and Menubar](https://www.w3.org/WAI/ARIA/apg/patterns/menubar/), [WAI-ARIA Modal Dialog](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/) và [Apple HIG Popovers](https://developer.apple.com/design/human-interface-guidelines/popovers/). Tương phản chữ và hỗ trợ giảm chuyển động tuân theo [WCAG 2.2](https://www.w3.org/TR/WCAG22/).

## Audit giao diện hiện tại

Quan sát ảnh render ở 1440×1000 và 390×844 cho trang chat, trang hỗ trợ, route legacy `/tours`, trang đăng nhập placeholder, 404 và trạng thái chờ/lỗi của chat. Lỗi 502 trong ảnh audit được tạo bằng mock cục bộ để xem trạng thái giao diện.

- `tokens.css` định nghĩa nền ấm, tím chàm và Manrope; workspace trong `AppShell.module.css` ghi đè sang xám lạnh, gần đen và Inter. Đây là hai visual language song song.
- Trang chat mới trên desktop dành phần lớn canvas cho khoảng trắng. Composer ban đầu rộng tới 880px và cao khoảng 136px; prompt mẫu có trọng lượng thị giác ngang nhau, chủ yếu được tách bằng viền.
- Composer trong hội thoại nổi sát đáy nhưng viền, nền và bóng còn gần với một khung nhập liệu phẳng. Nút gửi disabled chìm vào nền.
- Trạng thái agent dùng một dòng chấm và thông báo tổng quát. Lỗi hiện thành dải đỏ; nút thử lại đứng riêng bên dưới. Cả hai chưa tạo thành một cụm trạng thái có phân cấp.
- Tour card và thông tin nguồn phần lớn dựa vào viền; shadow/hover giữa card không tạo các tầng rõ ràng.
- Sidebar xám, active row xám và canvas gần trắng tách nhau bằng đường viền. Mark tím là điểm màu gần như duy nhất trong workspace.
- Mỗi dòng lịch sử có nút bút chì mở hộp thoại vừa đổi tên vừa chứa lệnh xóa; hai hành động khác mức rủi ro đang bị ghép chung, còn menu hành động không được biểu đạt trực quan.
- Dialog đổi tên/xóa và picker ngôn ngữ dùng surface trắng, bóng/ánh sáng và phân cấp nội dung còn cơ bản; confirm xóa chưa có nút Hủy ngang hàng với nút xóa.
- Trang hỗ trợ có bố cục nội dung dễ đọc, nhưng cùng header và card trắng phẳng. `/auth`, `/account`, `/contact` và 404 dùng empty-state rộng, ít định hướng thị giác; CTA 404 hiện ghi “Về Giới thiệu” dù route `/` là tìm tour.
- `/tours` vẫn render màn workspace legacy với phong cách khác trang chat. Cần thống nhất bề mặt và typography dù giữ nguyên hành vi route.

## Quy tắc visual system

### Bề mặt và ánh sáng

1. **Canvas:** nền ivory rất nhạt; ánh sáng ambient chỉ xuất hiện nhẹ quanh vùng nội dung chính để tạo điểm tụ.
2. **Navigation:** khác canvas một nấc tonal; ranh giới dùng hairline và shadow tiếp xúc rất nhẹ.
3. **Card:** surface sáng, hairline ấm, shadow thấp; hover tăng elevation vừa đủ để nhận ra tương tác.
4. **Floating layer:** composer ghim đáy; menu và dialog dùng surface đặc, viền mảnh và một bóng khuếch tán vừa đủ để tách khỏi nền. Không dùng gradient, highlight nổi hoặc nhiều lớp bóng cho popup.
5. Bóng có thành phần tiếp xúc ngắn và khuếch tán mềm; thống nhất nguồn sáng từ phía trên. Không dùng blur/glass hoặc gradient trang trí đại trà.
6. Menu hành động mở cạnh nút kích hoạt, bám theo kích thước nhãn, dùng mục cao vừa phải và hover trung tính. Chỉ mục xóa dùng màu nguy hiểm; không làm từng mục thành một nút nổi. Menu tự đặt trong viewport, đóng bằng Escape/chọn mục/click ngoài; hỗ trợ bàn phím và trả focus về nút mở khi đóng bằng Escape.
7. Dialog tập trung vào một tác vụ và chỉ rộng theo nội dung form. Header gọn, bỏ icon trang trí nếu không tăng nhận biết; nền đặc, một bóng nhẹ. Nút chính có một cấp nhấn rõ; nút phụ phẳng và ít nổi. Xóa có bước xác nhận riêng, nút Hủy rõ ràng và focus ban đầu vào lựa chọn an toàn. Không đặt lệnh xóa trong form đổi tên.
8. Dark mode có cùng thứ bậc bề mặt nhưng ánh sáng viền, màu overlay và bóng được chỉnh theo nền tối; không bê nguyên highlight trắng của light mode. Rà ảnh ở cả hai theme.

### Điều khiển

- Primary button dùng accent chàm, mép sáng mảnh và bóng tiếp xúc nhuốm accent. Hover nâng nhẹ; press hạ về mặt nền và giảm bóng.
- Secondary button dùng surface phẳng, viền mảnh và không có bóng mặc định; hover đổi tonal surface, press có phản hồi nhẹ.
- Icon button/chip có trạng thái hit-area, hover, press và focus đồng bộ; trạng thái disabled vẫn đọc được.
- Mọi component có default, hover, active, focus-visible, disabled và loading khi áp dụng. Focus không dựa riêng vào màu nền.

### Chat, kết quả và trạng thái

- Composer gọn khi trống, tự tăng chiều cao khi nội dung cần nhiều dòng, vẫn nổi rõ khỏi canvas.
- Tin người dùng, nội dung agent, hoạt động tool và kết quả có hình thức khác nhau nhưng cùng ngôn ngữ bề mặt.
- Loading mặc định là một dòng log phẳng: nội dung đổi theo hành động hiện tại, gradient chỉ chạy trên dòng của lượt đang hoạt động và dừng khi lượt hoàn tất; các dòng lịch sử giữ trạng thái tĩnh. Mở rộng cùng dòng để xem timeline tool. Lưu lại các mô tả hành động/trạng thái tool an toàn để xem lại sau reload; không lưu hay hiển thị private reasoning. Không lặp nhiều thẻ trạng thái, không mô phỏng phần trăm tiến độ, và tôn trọng `prefers-reduced-motion`.
- Lỗi gom thông điệp, nguyên nhân đã biết và hành động kế tiếp thành một cụm; giữ nguyên bản nháp.
- Tour card ưu tiên giá, ngày, điểm đến và trạng thái điều kiện; evidence mở ra khi cần, không biến card thành bảng viền dày.
- Khi chỉ có một tour, card dùng bề rộng đọc cân đối và được căn giữa; không để lưới hai cột tạo khoảng trống nửa màn hình.
- Lỗi không hiện nguyên văn thông báo kỹ thuật/tiếng Anh từ backend trong UI tiếng Việt. Thông báo ngắn, bản nháp được giữ và hành động khôi phục nằm trong cùng card.

### Typography, nhịp và motion

- Một font giao diện xuyên suốt. Phân cấp dùng kích thước, độ đậm và measure; tránh để các heading cùng quá lớn.
- Khoảng cách theo scale chung; giữ nội dung đọc theo một cột, chỉ mở rộng vùng kết quả khi so sánh cần thêm chỗ.
- Tương tác ngắn khoảng 120–220ms; xuất hiện nội dung khoảng 220–420ms. Ưu tiên opacity/transform nhẹ, giảm hoặc bỏ khi `prefers-reduced-motion` được bật.

## Cách đánh giá sau mỗi vòng

Chụp cùng trạng thái ở desktop 1440×1000 và mobile 390×844: trang chat rỗng, đang làm, có tool activity, có kết quả, lỗi thường, phiên hết hạn, trang hỗ trợ và fallback. Đánh giá theo sáu mục:

1. Một visual language nhất quán giữa shell, workspace và trang hỗ trợ trong cả light mode lẫn dark mode.
2. Bốn tầng canvas/navigation/card/floating có thể nhận ra mà không phải tăng viền khắp nơi.
3. Chỉ control cần ưu tiên mới có mặt phẳng nổi; menu item và nút phụ giữ phẳng, nhẹ, phản hồi hover/press vừa đủ.
4. Nội dung chính có thứ bậc và khoảng trắng có mục đích.
5. Loading/error/result nói rõ trạng thái và hành động kế tiếp bằng hình thức tương xứng.
6. Chữ dễ đọc, focus thấy rõ, không tràn ở mobile và motion tôn trọng thiết lập hệ thống; popup được xem ở cả hai theme.

Thay đổi chỉ đạt khi các ảnh trước/sau thể hiện được cải thiện ở cả sáu mục mà không làm sai lệch nội dung, trạng thái hay luồng quyết định của agent.

## Decision workspace

- Chat thu thập nhu cầu; sau đó hiển thị Decision Brief inline để review điều kiện cứng và sở thích mềm trước khi truy vấn catalog. Có thể sửa hoặc bỏ điều kiện trước khi chạy.
- Trọng số soft dùng tổng 100 điểm. Mặc định chia đều, có thao tác “Chia đều”, và trạng thái xác nhận bị khóa khi tổng khác 100. Mỗi tiêu chí cho thấy trọng số và mô tả ngắn; không dùng gauge hay điểm tin cậy.
- Kết quả chuyển khỏi hình thức một đoạn chat đơn thành decision workspace với các góc nhìn theo metric có dữ liệu: giá thấp nhất, hợp ưu tiên, nhiều trải nghiệm, ít chặng, linh hoạt hủy, phù hợp gia đình, độ bao gồm/ít khoản chưa định giá và cân bằng Pareto. Mỗi góc nhìn nêu metric, đơn vị, currency/phạm vi so sánh và số tour đã quét.
- Giá chỉ kết luận thấp nhất từ tổng exact cùng currency. Hiển thị riêng giá `from`/`contact`, phần tổng đã tính được và các khoản loại trừ chưa định giá. Exclusions là nguồn chính để tìm chi phí ẩn; phân loại bắt buộc/tùy chọn/có điều kiện và chỉ cộng khoản có số tiền, đơn vị cùng điều kiện áp dụng rõ.
- Hiển thị tối thiểu ba tour khác nhau nếu hard-pass catalog đủ; khi thiếu, nêu số thực có và kịch bản nới điều kiện. Mỗi phương án cho thấy vector đánh đổi, ma trận soft criteria, bằng chứng và unknown; không tạo điểm tổng hợp hay chọn hộ quán quân.
- Tour card cho phép mở evidence, so sánh/lưu tour; các số như trải nghiệm, chặng và cancellation chỉ hiện khi được tính từ nguồn, kèm độ phủ dữ kiện và thời điểm quan sát.
- Có thể giữ saved tours và chat suggestions hiện có như công cụ phụ trợ quanh workspace, không để chúng cạnh tranh với review/so sánh làm luồng chính.
- Thành phần và trạng thái cần hoạt động với bàn phím, mobile, light/dark mode. Unknown, không có kết quả, đang chạy, dừng và lỗi dùng cùng ngôn ngữ thị giác hiện có; không biến chúng thành card phụ trang trí.
