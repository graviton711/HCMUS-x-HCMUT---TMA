# Ý tưởng sản phẩm: Hỗ trợ quyết định chọn tour

## Bài toán

Giúp người dùng ở Việt Nam đánh giá và tự chọn giữa các tour du lịch dựa trên nhu cầu cá nhân và thông tin có thể kiểm chứng. Đây là bài toán hỗ trợ ra quyết định, không phải công cụ tự lập kế hoạch chuyến đi hay chatbot chỉ gợi ý tour.

## Người dùng nhập

Một trong hai dạng:

1. Mong muốn/ràng buộc chuyến đi: điểm đến, ngày hoặc khoảng thời gian, nơi khởi hành, ngân sách, số người/độ tuổi và sở thích hay giới hạn quan trọng.
2. Các tour đang cân nhắc: tên tour hoặc URL của một hay nhiều tour.

Người dùng có thể nhập tự nhiên; hệ thống cần làm rõ các ràng buộc còn thiếu trước khi so sánh.

## Hệ thống trả về

- Các tour hoặc lựa chọn mà dữ liệu nguồn xác nhận phù hợp với đầu vào.
- Bảng so sánh giá và dịch vụ, điểm phù hợp, hạn chế, điều kiện và rủi ro.
- Bằng chứng theo từng nhận định: nguồn/URL, thời điểm ghi nhận và nội dung liên quan.
- Nêu rõ trường nào thiếu, cũ hoặc chưa xác minh; không tự bịa để lấp dữ liệu.

Người dùng giữ quyền lựa chọn cuối cùng. Hệ thống không đặt tour thay người dùng.

## Phân biệt dữ liệu

- **Tour**: thông tin tương đối ổn định như tuyến, lịch trình khung, phương tiện, dịch vụ bao gồm/không bao gồm, chính sách và nhà cung cấp.
- **Lượt khởi hành/offer**: ngày đi, giá theo cấu hình, tình trạng chỗ và phụ thu; đây là dữ liệu biến động, phải lưu thời điểm quan sát và không khẳng định là thời gian thực nếu nguồn không đảm bảo.
- **Hồ sơ nhà cung cấp**: tên pháp nhân, giấy phép/phạm vi hoạt động và bằng chứng uy tín từ nguồn riêng; giấy phép không đồng nghĩa với chất lượng dịch vụ.

Mọi dữ liệu so sánh phải giữ nguồn gốc và độ mới. Chỉ thu thập/tái sử dụng theo quyền truy cập và điều khoản phù hợp của từng nguồn.

## Ngoài phạm vi

- Tự tạo lịch trình du lịch cá nhân từ đầu.
- Xếp hạng/gợi ý không giải thích bằng dữ liệu và tiêu chí rõ ràng.
- Đặt tour, thanh toán hoặc cam kết giá/tồn chỗ thay nhà cung cấp.

## Trạng thái

Đây là khóa phạm vi ý tưởng ban đầu để team review. Danh sách nguồn được phép dùng, schema chi tiết, cách chấm điểm và kiến trúc triển khai chưa được chốt trong tài liệu này.
