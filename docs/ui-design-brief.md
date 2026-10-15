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

Audit source hiện tại tập trung vào luồng quyết định. `tokens.css` đã cung cấp nền ấm, indigo, typography và trạng thái dùng chung; `AppShell` lấy từ các token này.

- `/` đang render Brief/kết quả trực tiếp trong transcript, nên người dùng phải tìm artifact giữa hội thoại.
- `/tours` đang dùng form legacy gọi `/requirements` và `/comparisons` trực tiếp, bỏ qua luồng agent/MCP metric-enrichment; trang còn thông báo sai về tuổi dữ liệu ngày khởi hành.
- Local session và agent response đã có artifact `decision_draft`/`comparison` có cấu trúc, đủ để dựng pane quyết định mà không đọc văn xuôi.
- Thay đổi này giữ nguyên visual language hiện tại và đưa artifact vào bố cục ổn định; không cần thêm theme hoặc API backend.

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

- Chat tiếp tục thu thập nhu cầu và giải thích; Brief có cấu trúc và kết quả được mở trong workspace quyết định cố định, không lặp toàn bộ artifact trong transcript. Transcript giữ lời thoại, tiến độ và liên kết để mở đúng Brief/kết quả.
- Desktop chia canvas giữa chat/tiến độ và Decision Workspace. Tay nắm kéo đổi tỷ lệ hai pane, lưu tùy chọn và hỗ trợ bàn phím. Nội dung ma trận/option co theo bề rộng, không cuộn ngang; workspace chỉ có một vùng cuộn dọc cho nội dung dài. Mobile dùng tab “Trao đổi”/“Quyết định”, tự mở “Quyết định” khi nhận Brief/kết quả có cấu trúc. Composer luôn khả dụng; gửi từ tab quyết định chuyển về trao đổi.
- Chỉ artifact có cấu trúc đã lưu trong phiên mới được dựng thành Brief/kết quả. Giữ Brief khi lỗi hoặc dừng; chỉ coi kết quả hiện hành nếu điều kiện của nó khớp Brief đã duyệt. Khi tiêu chí đổi, kết quả cũ được đánh dấu và còn mở được từ lịch sử.
- Brief giữ điều kiện cứng và sở thích mềm đã duyệt; trọng số soft tổng 100 điểm, mặc định chia đều, có thao tác “Chia đều”, và không cho chạy khi tổng sai. Không dùng gauge hay điểm tin cậy.
- Khi sửa một trọng số thành `x`, các soft criteria còn lại tự chia `100 - x` theo tỷ lệ hiện tại; dùng phần dư lớn nhất để làm tròn ổn định. Nếu tổng cũ của nhóm còn lại bằng 0 thì chia đều. Chỉ nhận giá trị hợp lệ và luôn giữ tổng bằng 100.
- Kết quả dùng các góc nhìn theo metric có dữ liệu: giá thấp nhất, hợp ưu tiên, nhiều trải nghiệm, ít chặng, linh hoạt hủy, phù hợp gia đình, độ bao gồm/ít khoản chưa định giá và cân bằng Pareto. Mỗi góc nhìn nêu metric, đơn vị, currency/phạm vi so sánh và số tour đã quét.
- Giá chỉ kết luận thấp nhất từ tổng exact cùng currency. Hiển thị riêng giá `from`/`contact`, phần tổng đã tính được và các khoản loại trừ chưa định giá. Exclusions là nguồn chính để tìm chi phí ẩn; chỉ cộng khoản có số tiền, đơn vị cùng điều kiện áp dụng rõ.
- Hiển thị tối thiểu ba tour khác nhau nếu hard-pass catalog đủ; khi thiếu, nêu số thực có và kịch bản nới điều kiện. Mỗi phương án cho thấy vector đánh đổi, ma trận soft criteria, bằng chứng và unknown; không tạo metric từ dữ liệu chưa có hay chọn hộ quán quân.
- Workspace có mục “Cách lọc” với funnel offer/tour, số blocker đầu tiên và bộ đếm từng điều kiện (có thể chồng lấp); mở danh sách offer bị loại theo trang để xem pass/fail/unknown và evidence. Có mục “Thử kịch bản”: thay điều kiện để so trên cùng snapshot, hoặc thay giả định chi phí có đơn giá/evidence. Điều kiện chỉ được chép vào Brief để review; giả định chi phí không sửa Brief hay comparison gốc.
- Brief, kết quả cũ và kết quả mới dùng chung token, typography, surface/elevation và màu trạng thái của giao diện hiện tại; trạng thái unknown, chạy, dừng, lỗi và rỗng không tạo theme riêng.
