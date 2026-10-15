# TourLens — không gian hỗ trợ quyết định chọn tour

TourLens giúp người Việt chọn tour đóng gói bằng cách làm rõ yêu cầu, lọc lựa chọn thật trong catalog, lượng hóa các đánh đổi và để người dùng quyết định cuối cùng. Chat thu thập nhu cầu; Decision Workspace trình bày các lựa chọn và bằng chứng.

## Luồng quyết định

1. Trích điều kiện bắt buộc và sở thích; preflight catalog theo hard conditions trước khi gợi ý địa điểm.
2. Người dùng review brief và trọng số các sở thích mềm.
3. Engine áp hard filter, phân tích metric chuẩn cho từng offer còn lại, rồi tạo ít nhất ba lựa chọn tour khác nhau nếu dữ liệu hỗ trợ.
4. Workspace cho so sánh giá, trải nghiệm, tuyến đi, độ bao gồm, chi phí bị loại trừ, rủi ro và điều kiện gia đình. Mỗi kết luận có evidence, trạng thái dữ liệu và thời điểm quan sát.
5. Người dùng đổi điều kiện/trọng số để chạy what-if. Nếu không đủ ba tour đạt điều kiện, hệ thống đưa kịch bản nới điều kiện riêng và chờ người dùng chọn.

## Không gian metric chuẩn

Mọi tour được mô tả theo cùng các trục, không gộp thành một điểm chất lượng duy nhất:

- **Chi phí:** giá exact/from/contact; tổng tính được cho nhóm; khoản cộng thêm đã định giá; và khoản chưa định giá. Đọc `exclusions` và `surcharges` để phát hiện khoản bắt buộc, tùy chọn hoặc có điều kiện. Không phải mọi exclusion đều là chi phí cần cộng.
- **Khớp ưu tiên:** điểm từng soft condition theo trọng số đã duyệt; thiếu bằng chứng tạo khoảng điểm và giảm độ phủ, không tự thành đạt/trượt.
- **Trải nghiệm:** số hoạt động/điểm tham quan được nêu rõ, tổng và trên mỗi ngày.
- **Độ phức tạp tuyến:** số chặng và lần đổi phương tiện chỉ khi route/lịch trình nêu rõ.
- **Độ bao gồm:** phương tiện, lưu trú, bữa ăn, vé/hoạt động, hướng dẫn viên và bảo hiểm; mỗi mục là gồm đủ/một phần/không gồm/chưa rõ.
- **Linh hoạt hủy:** hạn miễn phí và mức phạt theo mốc ngày nếu điều khoản cho phép tính.
- **Phù hợp gia đình:** giới hạn tuổi, giá theo tuổi, giường/phòng và điều kiện trẻ em.
- **Độ phủ dữ kiện:** số metric có evidence và độ mới nguồn; đây là thông tin chất lượng dữ liệu, không phải điểm tour hay xác suất tin cậy.

Góc nhìn có thể tối ưu các metric này: rẻ nhất, hợp ưu tiên, nhiều trải nghiệm, ít chặng, linh hoạt hủy, phù hợp gia đình, độ bao gồm cao/ít chi phí chưa rõ và Pareto cân bằng. Chỉ tạo góc nhìn khi metric có dữ liệu so sánh được; không suy diễn từ văn bản thiếu căn cứ.

## Nguyên tắc

- Hard conditions quyết định eligibility; metric mềm không được nới hard condition.
- Thứ hạng và mọi phép tính phải tái lập được từ dữ kiện, công thức và evidence đã lưu.
- Chỉ cộng khoản chi phí khi có số tiền/đơn vị và điều kiện áp dụng rõ; khoản loại trừ chưa định giá vẫn hiện riêng.
- Giá khác currency không so trực tiếp; `from` là lower bound, không phải tổng tour.
- Dữ kiện nhà cung cấp là provider-claimed; stale/unknown/mâu thuẫn phải hiện rõ.
- Tối thiểu ba lựa chọn phải là ba tour thật khác nhau. Thiếu thì trình bày số thực có và what-if minh bạch.
- Không tự quyết thay người dùng; đề xuất một lựa chọn chỉ khi metric và evidence phân biệt đủ rõ.

## Phạm vi

Chọn tour đóng gói có sẵn. Không booking, tự tạo tour, ước lượng xác suất rủi ro, quy tiền quyền lợi không có giá nguồn, hay suy thời gian/quãng đường từ tên địa điểm.

Định hướng theo `docs/TMA.md`: quyết định có thể dùng trong thực tế, khác chatbot/tìm kiếm, dùng dữ liệu/AI có giải thích và nêu giới hạn.
