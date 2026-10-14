# TourLens — hỗ trợ quyết định chọn tour

**Định vị:** Không gian quyết định cho người Việt chọn tour. Chat giúp diễn đạt và làm rõ nhu cầu; việc review điều kiện, xem đánh đổi và chọn phương án diễn ra trong decision workspace.

## Luồng chính

1. Người dùng mô tả điểm đến, ngày đi, ngân sách, nhóm đi và sở thích trong chat.
2. Agent tạo requirement draft gồm điều kiện cứng, sở thích mềm và phần còn thiếu. Draft chưa truy vấn tour.
3. Người dùng review/sửa điều kiện và phân bổ đúng 100 điểm giữa các sở thích mềm; có thể chia đều.
4. Khi xác nhận, hệ thống quét catalog trong giới hạn cấu hình, áp hard filter rồi agent đánh giá từng sở thích trên mọi ứng viên hard-pass theo batch, kèm evidence.
5. Decision workspace trình bày ba góc nhìn có thể đối chiếu: giá thấp nhất, hợp ưu tiên nhất và tập phương án Pareto cân bằng. Người dùng xem bằng chứng/đánh đổi rồi tự quyết định.

## Quy tắc quyết định

- Hard conditions là cổng đủ điều kiện; thay đổi trọng số mềm không làm đổi eligibility.
- Giá thấp nhất chỉ so sánh giá exact cùng currency. Giá `from`, `contact` hoặc thiếu giá không được xem là giá thấp nhất.
- Mức khớp ưu tiên là tổng `weight_percent` của các sở thích có verdict `pass`; `fail` và `unknown` không được cộng điểm. `unknown` vẫn được trình bày riêng.
- Cân bằng là Pareto frontier giữa giá exact thấp và mức khớp ưu tiên cao; không ép thành một điểm tổng hợp hay quán quân duy nhất.
- Kết quả nêu số tour đã quét trong phạm vi cấu hình, không suy ra tổng kích thước catalog. Mọi kết luận giữ evidence từ snapshot catalog.
- Điểm khớp là phép xếp hạng minh bạch theo verdict và trọng số người dùng, không phải xác suất hay điểm tin cậy đã hiệu chuẩn.
- Không quy đổi currency để tuyên bố tour rẻ nhất toàn cục. Tour thiếu giá exact vẫn có thể xuất hiện ở góc nhìn mức khớp, nhưng giá được ghi là chưa so sánh được.

## Phạm vi

Trong demo, agent diễn giải yêu cầu và evidence; backend kiểm tra điều kiện, áp hard filter và tính các góc nhìn. Database là nguồn dữ liệu có thẩm quyền. Không làm booking, ingest mới, tích hợp production, điểm tin cậy, dashboard độ phủ hay chỉ số di chuyển khi catalog chưa có dữ liệu cần thiết.

Tài liệu kiến trúc: [system-architecture](system-architecture.md). API: [backend-contract](backend-contract.md). Giao diện: [ui-design-brief](ui-design-brief.md).
