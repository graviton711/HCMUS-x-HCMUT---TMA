# Proposal: Hỗ trợ quyết định chọn tour

**Trạng thái:** Bản đề xuất để team review  
**Định vị:** Decision support cho người Việt chọn tour và nhà cung cấp; không phải công cụ lập kế hoạch chuyến đi.

## Tóm tắt

Hệ thống giúp người dùng thu thập, xác minh và so sánh các tour phù hợp với nhu cầu cá nhân. Kết quả nêu rõ dữ liệu, nguồn, thời điểm ghi nhận, lợi ích, hạn chế và rủi ro của từng lựa chọn để người dùng tự quyết định.

## Phân tích bài toán

- **Người dùng mục tiêu:** Người ở Việt Nam đang cân nhắc tour trọn gói, cần chọn giữa nhiều tour hoặc công ty lữ hành.
- **Quyết định cần hỗ trợ:** Tour/nhà cung cấp nào phù hợp với ngân sách, thời gian, điểm đi, sở thích và mức rủi ro người dùng chấp nhận?
- **Vấn đề hiện tại (giả thuyết cần kiểm chứng):** Thông tin nằm rải rác trên website nhà cung cấp và nguồn đánh giá; tên gọi, cách trình bày và mức độ cập nhật không đồng nhất. Người dùng khó so sánh cùng tiêu chí và phân biệt thông tin quảng bá với thông tin đã xác minh.
- **Giá trị cần tạo:** Giảm công sức tìm và đối chiếu; làm lộ rõ đánh đổi và dữ liệu còn thiếu, thay vì đưa ra một gợi ý không giải thích được.

## Luồng người dùng và kết quả

Người dùng có thể:

1. Nhập nhu cầu/ràng buộc: điểm đến, ngày hoặc độ linh hoạt, nơi khởi hành, ngân sách, số người/độ tuổi, sở thích và điều kiện quan trọng.
2. Đưa vào các tour hoặc URL đang cân nhắc để hệ thống đối chiếu trực tiếp.

Hệ thống lọc theo ràng buộc cứng, sau đó so sánh các lựa chọn còn lại theo độ phù hợp, tổng giá/dịch vụ, điều kiện tour và tín hiệu rủi ro nhà cung cấp. Kết quả cần có bảng so sánh, giải thích trade-off, dữ liệu chưa biết/chưa xác minh và bằng chứng cho từng nhận định. Không tự chọn thay người dùng.

## Phân biệt với recommendation và lập kế hoạch

- **Decision support:** Truy xuất dữ liệu nguồn, kiểm tra mức độ tin cậy, so sánh theo tiêu chí minh bạch và giải thích vì sao các lựa chọn khác nhau.
- **Recommendation thuần túy:** Đưa ra một gợi ý mà không chứng minh bằng dữ liệu và trade-off cụ thể — không phải mục tiêu sản phẩm.
- **Lập kế hoạch du lịch:** Tạo lịch trình cá nhân từ đầu — ngoài phạm vi.

AI có thể giúp hiểu yêu cầu ngôn ngữ tự nhiên và trình bày so sánh; không được dùng để bịa hoặc lấp dữ liệu tour còn thiếu.

## Dữ liệu và độ tin cậy

- **Hồ sơ tour:** Tuyến, thời lượng, lịch trình, phương tiện, dịch vụ bao gồm/không bao gồm và chính sách.
- **Lượt khởi hành/offer:** Ngày, giá, phụ thu và tình trạng chỗ; các trường này biến động, phải lưu `observed_at` và không gọi là thời gian thực nếu nguồn không bảo đảm.
- **Hồ sơ nhà cung cấp:** Tên pháp nhân, giấy phép/phạm vi hoạt động, đánh giá và tín hiệu rủi ro. Tách rõ nội dung nhà cung cấp tự khai báo với thông tin xác minh từ nguồn độc lập.
- Mỗi dữ kiện hiển thị phải có nguồn, thời điểm lấy và trạng thái xác minh. Không tìm thấy dữ liệu thì ghi rõ chưa có; không suy diễn từ nội dung chung của trang.

## Nguyên tắc thu thập

Ưu tiên dữ liệu có cấu trúc (JSON-LD/JSON/API được phép truy cập). Kiểm tra robots.txt và điều khoản nguồn trước khi gọi endpoint. Không dùng matching trên toàn bộ text trang cho field quyết định như giá, ngày khởi hành hay điểm xuất phát. Nếu nguồn không cung cấp dữ liệu đủ sạch hoặc không cho phép truy cập, đánh dấu thiếu/không hỗ trợ thay vì coi kết quả phỏng đoán là dữ kiện.

## Ngoài phạm vi

- Tự tạo lịch trình và đặt tour/thanh toán thay người dùng.
- Xếp hạng bằng điểm số bí mật hoặc gợi ý không kèm lý do, nguồn và trade-off.
- Khẳng định nhà cung cấp uy tín, có giấy phép hoặc còn chỗ nếu chưa có bằng chứng phù hợp.
- Cam kết giá và tình trạng chỗ luôn mới theo thời gian thực.

## Tiêu chí thành công sơ bộ

1. Có thể so sánh ít nhất một nhóm tour theo cùng tiêu chí, đồng thời giữ nguyên nguồn gốc và thời điểm của từng dữ kiện.
2. Giá/ngày/tình trạng chỗ cũ hoặc chưa xác minh được hiển thị cảnh báo; dữ liệu thiếu không bị tự điền.
3. Người dùng hiểu được vì sao các lựa chọn khác nhau và có thể tự chọn dựa trên trade-off.
4. Đánh giá crawler trên bộ trang được gán nhãn thủ công; đo độ chính xác theo field và tỷ lệ nguồn đủ điều kiện, không chỉ đo số trang crawl được.

## Rủi ro và giả định cần kiểm chứng

- Mỗi nhà cung cấp có cấu trúc và mức độ công khai dữ liệu khác nhau; không mặc định một parser/API dùng được cho tất cả.
- Một số endpoint bị robots chặn hoặc không cung cấp dữ liệu đủ chi tiết; cần quyết định nguồn nào thực sự đủ điều kiện cho sản phẩm.
- Đánh giá uy tín/giấy phép cần nguồn độc lập đáng tin cậy; không thể suy ra chỉ từ website bán tour.
- Cần kiểm chứng với người dùng xem bảng so sánh và trade-off có giúp họ quyết định tốt hơn quy trình tìm tour hiện tại hay không.

## Phạm vi tài liệu liên quan

Tài liệu này chốt bài toán và nguyên tắc sản phẩm. Kiến trúc mục tiêu ở `docs/system-architecture.md`, wireframe ở `docs/wireframes.md`; cả hai là bản review, chưa đồng nghĩa với implementation.
