# features/saved-tours

Danh mục snapshot tour do người dùng lưu trong trình duyệt; độc lập với session chat và vòng đời dữ liệu backend.

- Input: profile ID tùy chọn; snapshot offer/tour, điều kiện và đánh giá từ một `CurrentComparison`.
- Output: danh sách tour đã lưu, trạng thái lưu/xóa và `SavedToursDialog`.
- Workflow: app sở hữu hook và dialog; kết quả chat gửi `comparison + tour/offer ID` qua callback. Feature tạo snapshot gọn, lưu dưới key riêng theo profile hoặc guest, rồi render nguồn/thời điểm và đánh giá đã lưu.
- Dữ liệu không gồm bearer token, transcript, session ID hay toàn bộ comparison. Source URL được kiểm tra bằng `safeUrl` lúc mở. Dữ liệu local hỏng được bỏ qua; lỗi ghi được báo tại app shell.
- Giao diện dùng shared `Dialog`, nội dung phẳng, có trạng thái rỗng và hỗ trợ cả light/dark mode. Xóa một mục là thao tác cục bộ có thể đảo ngược bằng cách lưu lại từ kết quả.
